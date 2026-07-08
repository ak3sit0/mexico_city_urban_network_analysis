"""
Phase 1: GTFS ingestion and schema validation.

Functional style: each check is a pure function (Feed) -> CheckResult.
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


# ---------- Blocking checks ----------

def check_orphan_stops(feed: Feed) -> CheckResult:
    orphans = set(feed.stop_times.stop_id) - set(feed.stops.stop_id)
    return ("stop_id de stop_times existe en stops", not orphans,
            f"{len(orphans)} huérfanos" if orphans else "")


def check_orphan_routes(feed: Feed) -> CheckResult:
    orphans = set(feed.trips.route_id) - set(feed.routes.route_id)
    return ("route_id de trips existe en routes", not orphans,
            f"{len(orphans)} huérfanos: {sorted(orphans)[:5]}" if orphans else "")


def check_orphan_services(feed: Feed) -> CheckResult:
    orphans = set(feed.trips.service_id) - set(feed.calendar.service_id)
    return ("service_id de trips existe en calendar", not orphans,
            f"{len(orphans)} huérfanos: {sorted(orphans)[:10]}" if orphans else "")


def check_orphan_frequency_trips(feed: Feed) -> CheckResult:
    orphans = set(feed.frequencies.trip_id) - set(feed.trips.trip_id)
    return ("trip_id de frequencies existe en trips", not orphans,
            f"{len(orphans)} huérfanos" if orphans else "")


def _is_strictly_increasing(seq: pd.Series) -> bool:
    return seq.is_monotonic_increasing and seq.is_unique


def check_stop_sequence_monotonic(feed: Feed) -> CheckResult:
    bad = [
        trip_id
        for trip_id, g in feed.stop_times.groupby("trip_id")
        if not _is_strictly_increasing(g.sort_values("stop_sequence").stop_sequence)
    ]
    return ("stop_sequence estrictamente creciente por trip_id", not bad,
            f"{len(bad)} trips: {bad[:5]}" if bad else "")


def check_positive_headways(feed: Feed) -> CheckResult:
    bad = feed.frequencies[feed.frequencies.headway_secs <= 0]
    return ("headway_secs > 0", bad.empty,
            f"{len(bad)} filas <= 0" if not bad.empty else "")


BLOCKING_CHECKS: list[Callable[[Feed], CheckResult]] = [
    check_orphan_stops,
    check_orphan_routes,
    check_orphan_services,
    check_orphan_frequency_trips,
    check_stop_sequence_monotonic,
    check_positive_headways,
]


# ---------- Warnings (informational, don't block) ----------

def warn_frequency_granularity(feed: Feed) -> CheckResult:
    windows = feed.frequencies.groupby("trip_id").size()
    multi, single = (windows > 1).sum(), (windows == 1).sum()
    pct = multi / (multi + single) * 100
    return ("granularidad pico/valle en frequencies", True,
            f"{multi} trips con >1 ventana ({pct:.1f}%), {single} con ventana única")


def warn_route_type_consistency(feed: Feed) -> CheckResult:
    mixed = feed.routes.groupby("agency_id").route_type.nunique().pipe(lambda s: s[s > 1])
    return ("route_type consistente por agencia", mixed.empty,
            f"agencias con tipos mixtos: {mixed.index.tolist()}" if not mixed.empty else "")


def warn_calendar_dates_empty(feed: Feed) -> CheckResult:
    empty = feed.calendar_dates.empty
    return ("calendar_dates declarado", not empty,
            "vacío -> se asume sin excepciones de calendario" if empty else "")


def warn_orphan_agencies(feed: Feed) -> CheckResult:
    orphans = set(feed.routes.agency_id) - set(feed.agency.agency_id)
    return ("agency_id de routes.txt declarado en agency.txt", not orphans,
            f"{sorted(orphans)} referenciada(s) en routes.txt pero ausente(s) de agency.txt "
            "-- no rompe joins (agency_id ya vive en routes.txt), pero deja sin nombre/URL "
            "esa agencia; no se resuelve aquí, se hereda a fases siguientes" if orphans else "")


WARNING_CHECKS: list[Callable[[Feed], CheckResult]] = [
    warn_frequency_granularity,
    warn_route_type_consistency,
    warn_calendar_dates_empty,
    warn_orphan_agencies,
]


# ---------- Orchestration ----------

def run_checks(feed: Feed, checks: list[Callable[[Feed], CheckResult]]) -> list[CheckResult]:
    """Apply each check to the feed, return the list of results."""
    return list(map(lambda check: check(feed), checks))


def all_passed(results: list[CheckResult]) -> bool:
    """True if every result in a list of checks is OK."""
    return reduce(lambda ok, r: ok and r[1], results, True)


def print_report(title: str, results: list[CheckResult]) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")
    for name, ok, detail in results:
        suffix = f" - {detail}" if detail else ""
        print(f"[{'OK' if ok else 'FALLA'}] {name}{suffix}")


def main(feed_path: str) -> bool:
    feed = load_feed(feed_path)

    blocking = run_checks(feed, BLOCKING_CHECKS)
    warnings = run_checks(feed, WARNING_CHECKS)

    print_report("BLOQUEANTES", blocking)
    print_report("ADVERTENCIAS", warnings)

    passed = all_passed(blocking)
    n_ok = sum(ok for _, ok, _ in blocking)
    print(f"\nFase 1 {'CERRADA' if passed else 'BLOQUEADA'} — {n_ok}/{len(blocking)} bloqueantes OK")
    return passed


if __name__ == "__main__":
    feed_path = sys.argv[1] if len(sys.argv) > 1 else "../data/raw/gtfs.zip"
    sys.exit(0 if main(feed_path) else 1)