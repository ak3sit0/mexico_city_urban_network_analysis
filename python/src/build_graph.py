"""
Phase 3, Step 1 + Step 2: build the service edges (per-layer L-space)
and aggregate them.

Graph node: (station_id, agency_id) -- see design discussion: we need
separate layers per agency, coupled by transfer edges, for the cascade
study (Phase 5). A collapsed graph would lose that.

Functional style: no classes, pure functions, explicit composition in
main(). Same pattern as ingest.py and dedup.py.
"""

from __future__ import annotations

from functools import reduce

import pandas as pd
import partridge as ptg

from deduplication import haversine_m
from partridge.gtfs import Feed


# ---------- Loading ----------

def load_feed(path: str) -> Feed:
    return ptg.load_feed(path)


def load_crosswalk(path: str) -> dict[str, str]:
    """stop_id -> station_id, the closed result from Phase 2."""
    crosswalk = pd.read_csv(path)
    return dict(zip(crosswalk.stop_id, crosswalk.station_id))


def trip_agency_map(feed: Feed) -> pd.DataFrame:
    """trip_id -> (route_id, agency_id)."""
    return feed.trips.merge(
        feed.routes[["route_id", "agency_id"]], on="route_id", how="left"
    )[["trip_id", "route_id", "agency_id"]]


# ---------- Step 1: raw service edges ----------

def warn_trips_without_stop_times(feed: Feed) -> tuple[str, bool, str]:
    """
    Trips referenced in trips.txt (or frequencies.txt) with no row at
    all in stop_times -> they can't generate any edge. Reported, not
    silently dropped.
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
    One row per consecutive stop pair of each trip, already resolved to
    station_id. Not aggregated yet (multiple rows for the same segment,
    one per trip that covers it).
    """
    st = feed.stop_times.sort_values(["trip_id", "stop_sequence"]).copy()
    st["station_id"] = st.stop_id.map(crosswalk)

    if st.station_id.isna().any():
        n_missing = st.station_id.isna().sum()
        raise ValueError(
            f"{n_missing} filas de stop_times con stop_id fuera del crosswalk "
            "(¿crosswalk desactualizado respecto al feed?)"
        )

    grouped = st.groupby("trip_id")

    def edges_for_trip(trip_id: str, g: pd.DataFrame) -> pd.DataFrame:
        stations = g.station_id.tolist()
        times = g.arrival_time.tolist()
        pairs = [
            (trip_id, stations[i], stations[i + 1], times[i + 1] - times[i])
            for i in range(len(stations) - 1)
            if stations[i] != stations[i + 1]  # drop self-loops created by dedup
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
    Aggregate multi-edges by (source, target, route_id) -- different
    routes covering the same segment are NOT collapsed together, to
    avoid averaging an express service with a local one and losing the
    capacity difference between them.
    """
    agg = raw_edges.groupby(["source", "target", "route_id", "agency_id"]).agg(
        avg_travel_time_s=("travel_time_s", "mean"),
        trip_count=("trip_id", "nunique"),
    ).reset_index()
    return agg


def attach_headway(edges: pd.DataFrame, feed: Feed) -> pd.DataFrame:
    """
    Attach headway_secs per route_id: the most frequent (minimum)
    headway declared in frequencies.txt for that route, when it exists.
    Routes without frequencies.txt stay NaN -- no value is invented.
    """
    freq_by_route = (
        feed.frequencies
        .merge(feed.trips[["trip_id", "route_id"]], on="trip_id", how="left")
        .groupby("route_id").headway_secs.min()
        .rename("headway_secs")
    )
    return edges.merge(freq_by_route, on="route_id", how="left")


# ---------- Nodes ----------

def stop_agency_pairs(feed: Feed) -> pd.DataFrame:
    """(stop_id, agency_id) -- one row per agency that actually serves
    that stop, derived from stop_times -> trips -> routes."""
    ta = trip_agency_map(feed)
    return (
        feed.stop_times[["trip_id", "stop_id"]]
        .merge(ta[["trip_id", "agency_id"]], on="trip_id", how="left")
        [["stop_id", "agency_id"]]
        .drop_duplicates()
    )


def build_nodes(edges: pd.DataFrame, feed: Feed, crosswalk: dict[str, str]) -> pd.DataFrame:
    """
    (station_id, agency_id) pairs present in the edges, with a
    representative lat/lon/name -- averaged over the stop_id's that
    serve THAT SPECIFIC agency within that station_id, NOT over the
    whole station_id at once (otherwise every layer of the same station
    would share the same coordinate, and we'd lose the real distance
    between platforms that Step 3 needs to weight transfer edges).
    """
    node_ids = pd.concat([
        edges[["source", "agency_id"]].rename(columns={"source": "station_id"}),
        edges[["target", "agency_id"]].rename(columns={"target": "station_id"}),
    ]).drop_duplicates()

    stop_to_station = pd.Series(crosswalk, name="station_id").rename_axis("stop_id").reset_index()
    stop_agency = stop_agency_pairs(feed)

    stops_with_station_agency = (
        feed.stops
        .merge(stop_to_station, on="stop_id", how="inner")
        .merge(stop_agency, on="stop_id", how="inner")
    )

    representative = stops_with_station_agency.groupby(["station_id", "agency_id"]).agg(
        lat=("stop_lat", "mean"),
        lon=("stop_lon", "mean"),
        stop_name=("stop_name", "first"),
    ).reset_index()

    nodes = node_ids.merge(representative, on=["station_id", "agency_id"], how="left")
    nodes["node_id"] = nodes.station_id + "|" + nodes.agency_id
    return nodes


def to_node_ids(edges: pd.DataFrame) -> pd.DataFrame:
    """
    Convert source/target from plain station_id to the composite
    node_id (station_id|agency_id) -- needed because transfer edges DO
    need to distinguish agency per endpoint, and the whole graph must
    use a single node-id scheme, not two different ones.
    """
    edges = edges.copy()
    edges["source_station"] = edges["source"]
    edges["target_station"] = edges["target"]
    edges["source"] = edges["source"] + "|" + edges["agency_id"]
    edges["target"] = edges["target"] + "|" + edges["agency_id"]
    return edges


# ---------- Step 3: inter-layer transfer edges ----------

WALKING_SPEED_MPS = 1.3  # explicit assumption, typical urban walking speed


def transfer_edges(nodes: pd.DataFrame, walking_speed_mps: float = WALKING_SPEED_MPS) -> pd.DataFrame:
    """
    All-to-all within each station_id with >=2 agency_id: every pair of
    layers present at the same physical station gets connected in both
    directions, weighted by real distance / walking speed. No artificial
    hub node is used (see design discussion).
    """
    rows = []
    for station_id, group in nodes.groupby("station_id"):
        agencies = group.agency_id.tolist()
        if len(agencies) < 2:
            continue
        for i in range(len(group)):
            for j in range(len(group)):
                if i == j:
                    continue
                a, b = group.iloc[i], group.iloc[j]
                dist_m = haversine_m(a.lat, a.lon, b.lat, b.lon)
                rows.append({
                    "source": f"{station_id}|{a.agency_id}",
                    "target": f"{station_id}|{b.agency_id}",
                    "route_id": None,
                    "agency_id": None,
                    "avg_travel_time_s": dist_m / walking_speed_mps,
                    "trip_count": None,
                    "headway_secs": None,
                    "source_station": station_id,
                    "target_station": station_id,
                    "edge_type": "transbordo",
                    "distance_m": dist_m,
                })
    return pd.DataFrame(rows)


def warn_stations_without_transfer(nodes: pd.DataFrame, transfers: pd.DataFrame) -> tuple[str, bool, str]:
    """Every station_id with >=2 agency_id MUST have at least one
    transfer edge -- if not, something broke in the grouping step,
    it's not a legitimate 'not applicable' case."""
    multi_agency_stations = nodes.groupby("station_id").agency_id.nunique()
    expected = set(multi_agency_stations[multi_agency_stations >= 2].index)
    got = set(s.split("|")[0] for s in transfers.source) if len(transfers) else set()
    missing = expected - got
    if not missing:
        return ("station_id multi-agencia con arista de transbordo", True, "")
    return (
        "station_id multi-agencia con arista de transbordo", False,
        f"{len(missing)} station_id con >=2 agencias pero SIN transbordo generado: {sorted(missing)[:5]}"
    )


def warn_sparse_routes(edges: pd.DataFrame, max_gap_s: float = 3600) -> tuple[str, bool, str]:
    """
    Edges with avg_travel_time_s > max_gap_s between CONSECUTIVE stops
    flag routes with very few real checkpoints (a sparse sequence, not
    the full street-level path) -- the time isn't reliable as a
    'shortest path' weight in Phase 5/6, though it's still valid to
    keep it in the table for whoever wants to filter it out.
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

    service_edges = aggregate_edges(raw)
    service_edges = attach_headway(service_edges, feed)
    print(f"Aristas de servicio agregadas: {len(service_edges)}")
    print(f"  con headway conocido: {service_edges.headway_secs.notna().sum()}")
    print(f"  sin headway (route sin frequencies.txt): {service_edges.headway_secs.isna().sum()}")

    name, ok, detail = warn_sparse_routes(service_edges)
    print(f"[{'OK' if ok else 'ADVERTENCIA'}] {name}{' - ' + detail if detail else ''}")

    # Nodes are built BEFORE converting to composite node_id, because
    # build_nodes needs plain station_id/agency_id columns to group by.
    nodes = build_nodes(service_edges, feed, crosswalk)
    print(f"Nodos (station_id, agency_id): {len(nodes)}")
    print(f"  agencias representadas: {sorted(nodes.agency_id.unique())}")

    # Now service edges switch to composite node_id (same scheme the
    # transfer edges will use).
    service_edges = to_node_ids(service_edges)
    service_edges["edge_type"] = "servicio"
    service_edges["distance_m"] = None

    transfers = transfer_edges(nodes)
    print(f"Aristas de transbordo (todas-contra-todas): {len(transfers)}")

    name, ok, detail = warn_stations_without_transfer(nodes, transfers)
    print(f"[{'OK' if ok else 'ADVERTENCIA'}] {name}{' - ' + detail if detail else ''}")

    all_edges = pd.concat([service_edges, transfers], ignore_index=True)
    print(f"Aristas totales (servicio + transbordo): {len(all_edges)}")

    nodes.to_parquet(out_nodes, index=False)
    all_edges.to_parquet(out_edges, index=False)
    print(f"Exportado: {out_nodes}, {out_edges}")


if __name__ == "__main__":
    main(
        feed_path="../data/raw/gtfs.zip",
        crosswalk_path="../data/processed/crosswalk.csv",
        out_nodes="../data/processed/nodes.parquet",
        out_edges="../data/processed/edges.parquet",
    )