"""
Phase 4, Step 3: Transfer edge matrix (agency × agency heatmap).

Computes how many inter-layer (transbordo) edges connect each pair of
agencies at the same physical station. Results in a symmetric heatmap
that shows which agencies are most interconnected.

Functional style: pure functions, explicit composition in main().
"""

from __future__ import annotations

import pandas as pd
import numpy as np


def load_edges(path: str) -> pd.DataFrame:
    """Load edges from parquet."""
    return pd.read_parquet(path)


def extract_agency_from_node_id(node_id: str) -> str:
    """Extract agency_id from composite node_id (station_id|agency_id)."""
    return node_id.split("|")[1]


def transfer_matrix(edges: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate transfer edges by (source_agency, target_agency) pair.
    Result is a pivot table (rows=source, cols=target, values=edge_count).
    The matrix is typically asymmetric (more edges from METRO→RTP than vice versa).
    """
    transfers = edges[edges.edge_type == "transbordo"].copy()

    transfers["source_agency"] = transfers.source.apply(extract_agency_from_node_id)
    transfers["target_agency"] = transfers.target.apply(extract_agency_from_node_id)

    matrix = transfers.groupby(["source_agency", "target_agency"]).size().unstack(fill_value=0)
    return matrix.astype(int)


def transfer_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    """
    Row sums (total outgoing transfers per agency) and column sums
    (total incoming transfers per agency).
    """
    return pd.DataFrame({
        "outgoing": matrix.sum(axis=1),
        "incoming": matrix.sum(axis=0),
        "total_both_directions": matrix.sum(axis=1) + matrix.sum(axis=0),
    })


def main(edges_path: str) -> None:
    edges = load_edges(edges_path)

    transfers = edges[edges.edge_type == "transbordo"]
    print(f"Total transfer (transbordo) edges: {len(transfers)}")

    matrix = transfer_matrix(edges)
    print(f"\nTransfer matrix ({len(matrix)} × {len(matrix.columns)} agencies):")
    print(matrix.to_string())

    summary = transfer_summary(matrix)
    print(f"\nTransfer summary (outgoing / incoming / total):")
    print(summary.to_string())

    # Export for use in Paso 4 visualizations
    matrix.to_csv("../data/processed/transfer_matrix.csv")
    print(f"\nExported: ../data/processed/transfer_matrix.csv")


if __name__ == "__main__":
    main("../data/processed/edges.parquet")
