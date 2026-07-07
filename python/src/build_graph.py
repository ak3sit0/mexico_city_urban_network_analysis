"""
Phase 3: multiplex graph construction (L-space).

Pipeline:
1. For each trip_id, sort stop_times by stop_sequence -> consecutive
   pairs (directed edge).
2. Aggregate repeated multi-edges (same route/direction, many trips)
   into a single weighted edge: weight = mean travel time, aggregated
   frequency (frequencies.txt), trip count.
3. Add inter-layer edges at the deduplicated station_id's (Phase 2), one
   per pair of agencies that share that physical station.
4. Export to data/processed/{nodes,edges}.parquet — not GraphML.

Working graph in Python: networkx.MultiDiGraph (construction/QC), not
for heavy simulation (that lives in Julia, Phase 5/6).
"""

import pandas as pd
import networkx as nx


def build_lspace_edges(
    stop_times: pd.DataFrame, trips: pd.DataFrame, routes: pd.DataFrame
) -> pd.DataFrame:
    """Build the directed L-space edge table from stop_times."""
    # TODO: groupby trip_id, sort by stop_sequence, zip(stops[:-1], stops[1:]),
    # join with trips/routes for agency_id and route_id.
    raise NotImplementedError


def add_transfer_edges(
    edges: pd.DataFrame, station_crosswalk: pd.DataFrame
) -> pd.DataFrame:
    """Add inter-layer edges at transfer nodes (shared station_id)."""
    raise NotImplementedError


def export_graph(nodes: pd.DataFrame, edges: pd.DataFrame, out_dir: str) -> None:
    """Export nodes.parquet and edges.parquet to out_dir."""
    raise NotImplementedError


def to_networkx(nodes: pd.DataFrame, edges: pd.DataFrame) -> nx.MultiDiGraph:
    """Build a networkx MultiDiGraph for quick QC/visualization."""
    raise NotImplementedError
