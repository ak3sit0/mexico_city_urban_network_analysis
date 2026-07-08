"""
Phase 1: GTFS load and schema validation.

Responsibilities:
- Load the 7 tables (agency, routes,
trips, stop_times, stops, shapes,
  frequencies, calendar) from data/raw/.
- Validate referential integrity: no orphaned stop_id, monotonic
  stop_sequence per trip_id, service_id crossing correctly with
  calendar.txt, headway_secs > 0.
- Emit a data quality report (counts, dropped rows, warnings).

Output: cleaned tables in data/interim/.

Functional style: each check is a pure (Feed) -> CheckResult function.
run_checks applies them all with map(); all_passed aggregates with reduce().
"""

from __future__ import annotations

import sys
from functools import reduce
from typing import Callable

import pandas as pd
import partridge as ptg
from partridge.gtfs import Feed

CheckResult = tuple[str, bool, str]  # (name, ok, detail)


def load_feed(path: str) -> Feed:
    """Load the GTFS feed from a zip."""
    return ptg.load_feed(path)

# ---------- Blocking Checks ----------

def check_orphan_stops(feed: Feed) -> CheckResult:
    orphans = set(feed.stop_times.stop_id) - set(feed.stops.stop_id)
    return ("stop_id in stop_times exists in stops", not orphans,
            f"{len(orphans)} orphans" if orphans else "")


def check_orphan_routes(feed: Feed) -> CheckResult:
    orphans = set(feed.trips.route_id) - set(feed.routes.route_id)
    return ("route_id in trips exists in routes", not orphans,
            f"{len(orphans)} orphans: {sorted(orphans)[:5]}" if orphans else "")


def check_orphan_services(feed: Feed) -> CheckResult:
    orphans = set(feed.trips.service_id) - set(feed.calendar.service_id)
    return ("service_id in trips exists in calendar", not orphans,
            f"{len(orphans)} orphans: {sorted(orphans)[:10]}" if orphans else "")


def check_orphan_frequency_trips(feed: Feed) -> CheckResult:
    orphans = set(feed.frequencies.trip_id) - set(feed.trips.trip_id)
    return ("trip_id in frequencies exists in trips", not orphans,
            f"{len(orphans)} orphans" if orphans else "")


def _is_strictly_increasing(seq: pd.Series) -> bool:
    return seq.is_monotonic_increasing and seq.is_unique


def check_stop_sequence_monotonic(feed: Feed) -> CheckResult:
    bad = [
        trip_id
        for trip_id, g in feed.stop_times.groupby("trip_id")
        if not _is_strictly_increasing(g.sort_values("stop_sequence").stop_sequence)
    ]
    return ("stop_sequence strictly increasing per trip_id", not bad,
            f"{len(bad)} trips: {bad[:5]}" if bad else "")


def check_positive_headways(feed: Feed) -> CheckResult:
    bad = feed.frequencies[feed.frequencies.headway_secs <= 0]
    return ("headway_secs > 0", bad.empty,
            f"{len(bad)} rows <= 0" if not bad.empty else "")


BLOCKING_CHECKS: list[Callable[[Feed], CheckResult]] = [
    check_orphan_stops,
    check_orphan_routes,
    check_orphan_services,
    check_orphan_frequency_trips,
    check_stop_sequence_monotonic,
    check_positive_headways,
]


# ---------- Warnings (get information, don't block) ----------

def warn_frequency_granularity(feed: Feed) -> CheckResult:
    windows = feed.frequencies.groupby("trip_id").size()
    multi, single = (windows > 1).sum(), (windows == 1).sum()
    pct = multi / (multi + single) * 100
    return ("peak/off-peak granularity in frequencies", True,
            f"{multi} trips with >1 window ({pct:.1f}%), {single} with a single window")


def warn_route_type_consistency(feed: Feed) -> CheckResult:
    mixed = feed.routes.groupby("agency_id").route_type.nunique().pipe(lambda s: s[s > 1])
    return ("route_type consistent per agency", mixed.empty,
            f"agencies with mixed types: {mixed.index.tolist()}" if not mixed.empty else "")


WARNING_CHECKS: list[Callable[[Feed], CheckResult]] = [
    warn_frequency_granularity,
    warn_route_type_consistency,
]


# ----------  ----------

def run_checks(feed: Feed, checks: list[Callable[[Feed], CheckResult]]) -> list[CheckResult]:
    """Apply each check to the feed, return the list of results."""
    return list(map(lambda check: check(feed), checks))


def all_passed(results: list[CheckResult]) -> bool:
    """True if all results in a list of checks are OK."""
    return reduce(lambda ok, r: ok and r[1], results, True)


def print_report(title: str, results: list[CheckResult]) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")
    for name, ok, detail in results:
        suffix = f" - {detail}" if detail else ""
        print(f"[{'OK' if ok else 'FAIL'}] {name}{suffix}")


def main(feed_path: str) -> bool:
    feed = load_feed(feed_path)

    blocking = run_checks(feed, BLOCKING_CHECKS)
    warnings = run_checks(feed, WARNING_CHECKS)

    print_report("BLOCKING", blocking)
    print_report("WARNINGS", warnings)

    passed = all_passed(blocking)
    n_ok = sum(ok for _, ok, _ in blocking)
    print(f"\nPhase 1 {'CLOSED' if passed else 'BLOCKED'} — {n_ok}/{len(blocking)} blocking checks OK")
    return passed


if __name__ == "__main__":
    feed_path = sys.argv[1] if len(sys.argv) > 1 else "cdmx_gtfs_feed.zip"
    sys.exit(0 if main(feed_path) else 1)