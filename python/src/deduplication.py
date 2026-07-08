"""
Phase 2: spatial deduplication of stations.

Functional style: each transformation is a pure function that takes and
returns DataFrames/arrays; no classes, explicit composition in main().

Step 1: geographic clustering (haversine BallTree + connected components).
Step 2: administrative prefix normalization + name filter
        (rapidfuzz + connected components) within each geographic cluster.
Step 3: identification of manual override candidates (clusters that,
        after Step 2, remain fragmented and multi-agency).
"""

from __future__ import annotations

import re
from collections.abc import Hashable
from functools import reduce

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from sklearn.neighbors import BallTree

EARTH_RADIUS_M = 6_371_000
RADIUS_M = 150
NAME_THRESHOLD = 85
MAX_MERGE_DISTANCE_M = 150  # pairwise cap, independent of the geo_cluster chain
NAME_PREFIXES = [
    "c. c. metro ", "c.c. metro ", "cetram metro ",
    "base metro ", "base cetram ", "mb ", "metro ", "base ", "cetram ",
]


# ---------- Loading ----------

def load_stops(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def load_stop_agencies(stops_path: str, routes_path: str, trips_path: str,
                        stop_times_path: str) -> pd.Series:
    """stop_id -> frozenset(agency_id) serving that stop."""
    routes = pd.read_csv(routes_path)
    trips = pd.read_csv(trips_path)
    stop_times = pd.read_csv(stop_times_path, usecols=["trip_id", "stop_id"])

    trip_agency = trips.merge(routes[["route_id", "agency_id"]], on="route_id", how="left")
    st_agency = stop_times.merge(trip_agency[["trip_id", "agency_id"]], on="trip_id", how="left")
    return st_agency.groupby("stop_id").agency_id.apply(lambda s: frozenset(s.dropna()))


# ---------- Step 1: geographic clustering ----------

def _connected_components_from_pairs(rows: np.ndarray, cols: np.ndarray, n: int) -> np.ndarray:
    graph = coo_matrix((np.ones(len(rows), dtype=bool), (rows, cols)), shape=(n, n))
    _, labels = connected_components(graph, directed=False)
    return labels


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


def geographic_clusters(stops: pd.DataFrame, radius_m: float = RADIUS_M) -> np.ndarray:
    """Radius-based geographic clustering (haversine BallTree + connected components)."""
    coords_rad = np.radians(stops[["stop_lat", "stop_lon"]].values)
    tree = BallTree(coords_rad, metric="haversine")
    neighbors = tree.query_radius(coords_rad, r=radius_m / EARTH_RADIUS_M)

    rows = np.concatenate([[i] * len(nb) for i, nb in enumerate(neighbors)])
    cols = np.concatenate(neighbors)
    return _connected_components_from_pairs(rows, cols, len(stops))


# ---------- Step 2: normalization + name filter ----------

def normalize_name(name: str) -> str:
    """Strip repeated administrative prefixes (Metro, Base, Cetram, ...)."""
    n = name.strip().lower()
    stripped = True
    while stripped:
        stripped = False
        for prefix in NAME_PREFIXES:
            if n.startswith(prefix):
                n = n[len(prefix):].strip()
                stripped = True
    return n


def name_subclusters(names: list[str], lats: list[float], lons: list[float],
                      threshold: float = NAME_THRESHOLD,
                      max_distance_m: float = MAX_MERGE_DISTANCE_M) -> np.ndarray:
    """
    Sub-clusters a group of names by similarity after normalizing,
    additionally requiring the pair to be <= max_distance_m apart.
    Without this cap, two stops with the same generic name (e.g. two
    distinct 'Boulevard Puerto Aéreo' 700m apart) could be merged by
    mistake within a chained geographic cluster.
    """
    normalized = list(map(normalize_name, names))
    n = len(normalized)
    pairs = [
        (i, j)
        for i in range(n)
        for j in range(i, n)
        if fuzz.token_sort_ratio(normalized[i], normalized[j]) >= threshold
        and haversine_m(lats[i], lons[i], lats[j], lons[j]) <= max_distance_m
    ]
    if not pairs:
        return np.arange(n)
    rows, cols = zip(*pairs)
    rows, cols = np.array(rows + cols), np.array(cols + rows)
    return _connected_components_from_pairs(rows, cols, n)


# ---------- Crosswalk construction ----------

def build_crosswalk(stops: pd.DataFrame) -> pd.DataFrame:
    """stop_id -> station_id combining Step 1 (geo) + Step 2 (name)."""
    geo_labels = geographic_clusters(stops)
    stops = stops.assign(geo_cluster=geo_labels)

    def assign_station_ids(geo_cluster_id: Hashable, group: pd.DataFrame) -> pd.DataFrame:
        sub_labels = name_subclusters(
            group.stop_name.tolist(), group.stop_lat.tolist(), group.stop_lon.tolist()
        )
        station_ids = [f"station_{geo_cluster_id}_{s}" for s in sub_labels]
        return group.assign(station_id=station_ids)

    parts = [
        assign_station_ids(geo_cluster_id, group)
        for geo_cluster_id, group in stops.groupby("geo_cluster")
    ]
    return pd.concat(parts, ignore_index=True)[["stop_id", "stop_name", "station_id", "geo_cluster"]]


# ---------- Step 3: manual override candidates ----------

def override_candidates(crosswalk: pd.DataFrame, stop_agencies: pd.Series) -> pd.DataFrame:
    """
    geo_cluster that, after Step 2, still has >1 station_id AND more than
    one agency involved in the whole cluster -> candidate for manual review
    (the automatic pipeline couldn't decide whether they're the same station).
    """
    def cluster_summary(geo_cluster_id: Hashable, group: pd.DataFrame) -> dict | None:
        n_stations = group.station_id.nunique()
        agencies = reduce(
            lambda acc, sid: acc | stop_agencies.get(sid, frozenset()),
            group.stop_id, frozenset(),
        )
        if n_stations > 1 and len(agencies) > 1:
            return {
                "geo_cluster": geo_cluster_id,
                "n_stops": len(group),
                "n_station_ids_tras_paso2": n_stations,
                "n_agencias": len(agencies),
                "agencias": sorted(agencies),
                "nombres": sorted(group.stop_name.unique().tolist()),
            }
        return None

    rows = [
        cluster_summary(gc, g)
        for gc, g in crosswalk.groupby("geo_cluster")
    ]
    rows = list(filter(None, rows))
    return pd.DataFrame(rows).sort_values("n_stops", ascending=False)


# ---------- Step 4: apply manual overrides ----------

def apply_overrides(crosswalk: pd.DataFrame, overrides_path: str) -> pd.DataFrame:
    """
    Applies manual_overrides/station_merge_overrides.csv on top of the
    automatic crosswalk (Step 1+2). The override always wins: if a stop_id
    appears in the file, its station_id is replaced by target_station_id,
    regardless of what the automatic clustering decided.
    """
    overrides = pd.read_csv(overrides_path)
    override_map = dict(zip(overrides.stop_id, overrides.target_station_id))

    crosswalk = crosswalk.copy()
    crosswalk["station_id"] = crosswalk.apply(
        lambda row: override_map.get(row.stop_id, row.station_id), axis=1
    )
    return crosswalk


# ---------- Orchestration ----------

def main(stops_path: str, routes_path: str, trips_path: str, stop_times_path: str,
         overrides_path: str, out_crosswalk: str, out_candidates: str) -> None:
    stops = load_stops(stops_path)
    stop_agencies = load_stop_agencies(stops_path, routes_path, trips_path, stop_times_path)

    crosswalk = build_crosswalk(stops)
    crosswalk = apply_overrides(crosswalk, overrides_path)
    crosswalk.to_csv(out_crosswalk, index=False)

    candidates = override_candidates(crosswalk, stop_agencies)
    candidates.to_csv(out_candidates, index=False)

    print(f"Stops originales: {len(stops)}")
    print(f"station_id únicos tras Paso 1+2+4 (con overrides): {crosswalk.station_id.nunique()}")
    print(f"Candidatos a override manual restantes: {len(candidates)}")


if __name__ == "__main__":
    main(
        stops_path="../data/raw/gtfs/stops.txt",
        routes_path="../data/raw/gtfs/routes.txt",
        trips_path="../data/raw/gtfs/trips.txt",
        stop_times_path="../data/raw/gtfs/stop_times.txt",
        overrides_path="../manual_overrides/station_merge_overrides.csv",
        out_crosswalk="../data/processed/crosswalk.csv",
        out_candidates="../data/processed/override_candidates.csv",
    )