"""
Phase 2: spatial deduplication of stations.

Pipeline:
1. Candidate geographic clustering: BallTree (haversine metric) over
   stop_lat/lon, configurable radius (~80-100m).
2. Secondary filter: name similarity (rapidfuzz) within each candidate
   cluster, to avoid merging stops that only happen to be close (e.g.
   two different streets that cross).
3. Apply manual overrides (hand-corrected crosswalk) — needed for large
   transfer stations with widely separated platforms (Pantitlán,
   Chabacano, etc.) that automatic clustering misses or over-merges.

Output: stop_id -> station_id crosswalk in data/interim/.
"""

import pandas as pd


def cluster_candidates(
    stops: pd.DataFrame, radius_m: float = 100.0
) -> pd.DataFrame:
    """BallTree/haversine over stops; returns stops with a cluster_id column."""
    # TODO: sklearn.neighbors.BallTree(metric='haversine'),
    # convert lat/lon to radians before fit.
    raise NotImplementedError


def refine_with_name_similarity(
    stops_clustered: pd.DataFrame, threshold: float = 85.0
) -> pd.DataFrame:
    """Split clusters whose names don't meet the similarity threshold."""
    # TODO: rapidfuzz.fuzz.token_sort_ratio within each cluster_id.
    raise NotImplementedError


def apply_manual_overrides(
    crosswalk: pd.DataFrame, overrides_path: str
) -> pd.DataFrame:
    """Apply manual merges/splits on top of the automatic crosswalk."""
    # TODO: read overrides_path (CSV with stop_id, action, target_station_id),
    # apply explicit merge/split per stop_id.
    raise NotImplementedError
