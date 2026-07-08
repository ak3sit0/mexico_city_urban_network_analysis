"""
Phase 3, Step 1 + Step 2: building the service edges (per-layer L-space)
and their aggregation.

Graph node: (station_id, agency_id) — see design discussion: separate
per-agency layers, coupled by transfers, are needed for the cascade
study (Phase 5), not a collapsed graph.

Functional style: no classes, pure functions, explicit composition in
main(). Same pattern as ingest.py and dedup.py.
"""

from __future__ import annotations

from functools import reduce

import pandas as pd
import partridge as ptg
from partridge.gtfs import Feed


# ---------- Loading ----------

def load_feed(path: str) -> Feed:
    return ptg.load_feed(path)


def load_crosswalk(path: str) -> dict[str, str]:
    """stop_id -> station_id, finalized result from Phase 2."""
    crosswalk = pd.read_csv(path)
    return dict(zip(crosswalk.stop_id, crosswalk.station_id))


def trip_agency_map(feed: Feed) -> pd.DataFrame:
    """trip_id -> (route_id, agency_id)."""
    return feed.trips.merge(
        feed.routes[["route_id", "agency_id"]], on="route_id", how="left"
    )[["trip_id", "route_id", "agency_id"]]


# ---------- Step 1: (raw) service edges ----------

def warn_trips_without_stop_times(feed: Feed) -> tuple[str, bool, str]:
    """
    Trips referenced in trips.txt (or frequencies.txt) with no row at all
    in stop_times -> can't generate edges. Reported, not hidden.
    """
    expected = set(feed.trips.trip_id) | set(feed.frequencies.trip_id)
    present = set(feed.stop_times.trip_id)
    missing = expected - present

    if not missing:
        return ("trips con stop_times presente", True, "")

    missing_agencies = (
        feed.trips[feed.trips.trip_id.isin(missing)]
        .merge(feed.routes[["route_id", "agency_id"]], on="route_id", how="left")
        .agency_id.unique().tolist()
    )
    return (
        "trips con stop_times presente", False,
        f"{len(missing)} trip(s) sin stop_times: {sorted(missing)[:5]} "
        f"(agencias afectadas: {missing_agencies})"
    )


def raw_service_edges(feed: Feed, crosswalk: dict[str, str]) -> pd.DataFrame:
    """
    One row per consecutive pair of stops for each trip, already resolved
    to station_id. Still unaggregated (multiple rows for the same segment,
    one per trip that traverses it).
    """
    st = feed.stop_times.sort_values(["trip_id", "stop_sequence"]).copy()
    st["station_id"] = st.stop_id.map(crosswalk)

    if st.station_id.isna().any():
        n_missing = st.station_id.isna().sum()
        raise ValueError(
            f"{n_missing} stop_times rows with stop_id outside the crosswalk "
            "(crosswalk out of date relative to the feed?)"
        )

    grouped = st.groupby("trip_id")

    def edges_for_trip(trip_id: str, g: pd.DataFrame) -> pd.DataFrame:
        stations = g.station_id.tolist()
        times = g.arrival_time.tolist()
        pairs = [
            (trip_id, stations[i], stations[i + 1], times[i + 1] - times[i])
            for i in range(len(stations) - 1)
            if stations[i] != stations[i + 1]  # drop self-edges from dedup
        ]
        return pairs

    all_pairs = [
        pair
        for trip_id, g in grouped
        for pair in edges_for_trip(trip_id, g)
    ]

    edges = pd.DataFrame(all_pairs, columns=["trip_id", "source", "target", "travel_time_s"])
    return edges.merge(trip_agency_map(feed), on="trip_id", how="left")


# ---------- Step 2: aggregation ----------

def aggregate_edges(raw_edges: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates multi-edges by (source, target, route_id) — distinct
    routes covering the same segment are not collapsed, so an express
    route isn't averaged with a local one and lose the capacity difference.
    """
    agg = raw_edges.groupby(["source", "target", "route_id", "agency_id"]).agg(
        avg_travel_time_s=("travel_time_s", "mean"),
        trip_count=("trip_id", "nunique"),
    ).reset_index()
    return agg


def attach_headway(edges: pd.DataFrame, feed: Feed) -> pd.DataFrame:
    """
    Adds headway_secs per route_id: the most frequent (minimum) headway
    declared in frequencies.txt for that route, when it exists. Routes
    without frequencies.txt are left with NaN — no value is invented.
    """
    freq_by_route = (
        feed.frequencies
        .merge(feed.trips[["trip_id", "route_id"]], on="trip_id", how="left")
        .groupby("route_id").headway_secs.min()
        .rename("headway_secs")
    )
    return edges.merge(freq_by_route, on="route_id", how="left")


# ---------- Nodes ----------

def build_nodes(edges: pd.DataFrame, feed: Feed, crosswalk: dict[str, str]) -> pd.DataFrame:
    """(station_id, agency_id) present in the edges, with representative
    lat/lon/name (average of the stops collapsed into that station_id)."""
    node_ids = pd.concat([
        edges[["source", "agency_id"]].rename(columns={"source": "station_id"}),
        edges[["target", "agency_id"]].rename(columns={"target": "station_id"}),
    ]).drop_duplicates()

    stop_to_station = pd.Series(crosswalk, name="station_id").rename_axis("stop_id").reset_index()
    stops_with_station = feed.stops.merge(stop_to_station, on="stop_id", how="inner")

    representative = stops_with_station.groupby("station_id").agg(
        lat=("stop_lat", "mean"),
        lon=("stop_lon", "mean"),
        stop_name=("stop_name", "first"),
    ).reset_index()

    return node_ids.merge(representative, on="station_id", how="left")


def warn_sparse_routes(edges: pd.DataFrame, max_gap_s: float = 3600) -> tuple[str, bool, str]:
    """
    Edges with avg_travel_time_s > max_gap_s between CONSECUTIVE stops
    flag routes with very few real checkpoints (sparse sequence, not the
    full street) — the time isn't reliable as a 'shortest path' weight
    in Phase 5/6, though it's still valid to leave it in the table for
    whoever wants to filter it out.
    """
    suspect = edges[edges.avg_travel_time_s > max_gap_s]
    if suspect.empty:
        return ("aristas con salto sospechoso entre paradas consecutivas", True, "")
    routes = sorted(suspect.route_id.unique())
    return (
        "aristas con salto sospechoso entre paradas consecutivas", False,
        f"{len(suspect)} arista(s) en rutas {routes} con >1h entre paradas "
        "consecutivas — probablemente secuencia de paradas dispersa, no ruta real"
    )


# ---------- Orchestration ----------

def main(feed_path: str, crosswalk_path: str, out_nodes: str, out_edges: str) -> None:
    feed = load_feed(feed_path)
    crosswalk = load_crosswalk(crosswalk_path)

    name, ok, detail = warn_trips_without_stop_times(feed)
    print(f"[{'OK' if ok else 'ADVERTENCIA'}] {name}{' - ' + detail if detail else ''}")

    raw = raw_service_edges(feed, crosswalk)
    print(f"Aristas crudas (una por tramo por trip): {len(raw)}")

    edges = aggregate_edges(raw)
    edges = attach_headway(edges, feed)
    print(f"Aristas agregadas (source, target, route_id): {len(edges)}")
    print(f"  con headway conocido: {edges.headway_secs.notna().sum()}")
    print(f"  sin headway (route sin frequencies.txt): {edges.headway_secs.isna().sum()}")

    name, ok, detail = warn_sparse_routes(edges)
    print(f"[{'OK' if ok else 'ADVERTENCIA'}] {name}{' - ' + detail if detail else ''}")

    nodes = build_nodes(edges, feed, crosswalk)
    print(f"Nodos (station_id, agency_id): {len(nodes)}")
    print(f"  agencias representadas: {sorted(nodes.agency_id.unique())}")

    nodes.to_csv(out_nodes, index=False)
    edges.to_csv(out_edges, index=False)


if __name__ == "__main__":
    main(
        feed_path="../data/raw/gtfs.zip",
        crosswalk_path="../data/processed/crosswalk.csv",
        out_nodes="../data/processed/nodes.csv",
        out_edges="../data/processed/edges.csv",
    )