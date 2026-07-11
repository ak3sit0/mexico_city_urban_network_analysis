"""
Phase 5, Paso 2 Variante B: Flow-based load (L_i_flujo = random walk stationary distribution).

Computes the stationary distribution of a random walk biased by edge frequency.
This represents the long-run proportion of time a random walker spends at each node.

Interpretation:
  L_i_flujo = steady-state visitation frequency at node i
  High L_i_flujo = nodes that see more "traffic" from the random walk

This complements Variante A (topological betweenness):
  - Variante A (betweenness): structural bridges (disconnects graph if removed)
  - Variante B (random walk): high-traffic nodes (receive more demand)

Input:
  - data/processed/nodes.parquet
  - data/processed/edges.parquet (service edges with headway_secs)

Output:
  - data/processed/load_flujo.csv (node_id, L_i_flujo)
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path
from scipy.sparse import csr_matrix
from scipy.linalg import eig


def build_transition_matrix(edges: pd.DataFrame, node_list: list[str]) -> tuple[csr_matrix, dict]:
    """
    Build sparse transition matrix P where P[i,j] is the probability of
    transitioning from node i to node j, weighted by service frequency.

    Returns:
        P: sparse row-stochastic matrix (n × n)
        node_to_idx: dict mapping node_id to row index
    """
    n = len(node_list)
    node_to_idx = {node: i for i, node in enumerate(node_list)}

    # Filter to service edges only
    service = edges[edges.edge_type == "servicio"].copy()

    # Compute frequency (vehicles/hour) = 3600 / headway_secs
    service["frequency"] = 3600.0 / service.headway_secs

    # Aggregate by (source, target) to handle multi-edges
    grouped = service.groupby(["source", "target"])["frequency"].sum().reset_index()

    # Build matrix: P[i,j] = transition probability from i to j
    # Note: sparse matrix is typically column-indexed, but we want row-stochastic
    # so we'll build dense then convert
    P = np.zeros((n, n), dtype=float)

    for _, row in grouped.iterrows():
        i = node_to_idx.get(row["source"], -1)
        j = node_to_idx.get(row["target"], -1)
        if i >= 0 and j >= 0:
            P[i, j] += row["frequency"]

    # Normalize to make row-stochastic (each row sums to 1)
    row_sums = P.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1  # Avoid division by zero
    P = P / row_sums

    return csr_matrix(P), node_to_idx


def compute_stationary_distribution(P: np.ndarray, max_iter: int = 5000, tol: float = 1e-10, damping: float = 0.85) -> np.ndarray:
    """
    Compute the stationary distribution π of transition matrix P with damping (PageRank-style).

    Solves: π = π * (damping * P + (1 - damping) * uniform)

    The damping factor (default 0.85, PageRank value) adds uniform "teleportation"
    to handle disconnected components and speed convergence.
    With damping, π converges to a unique distribution even with disconnected components.

    Args:
        P: row-stochastic transition matrix
        max_iter: maximum iterations
        tol: convergence tolerance
        damping: probability of following an edge (vs teleporting). damping=1 is exact.
    """
    n = P.shape[0]
    uniform = np.ones(n) / n
    π = uniform.copy()  # Start with uniform distribution

    # Construct damped transition matrix
    P_damped = damping * P + (1 - damping) * uniform[np.newaxis, :]

    for iter_num in range(max_iter):
        π_new = π @ P_damped  # Apply damped transition
        π_new = π_new / np.sum(π_new)  # Re-normalize

        residual = np.linalg.norm(π_new - π)
        if residual < tol:
            print(f"  ✓ Converged in {iter_num + 1} iterations (residual: {residual:.2e})")
            return π_new

        if (iter_num + 1) % 200 == 0:
            print(f"    Iteration {iter_num + 1}: residual = {residual:.2e}")

        π = π_new

    print(f"  ⚠ Did not converge after {max_iter} iterations (final residual: {residual:.2e})")
    return π / np.sum(π)


def main() -> None:
    """Load graph, compute random walk stationary distribution, export CSV."""
    print("=" * 80)
    print("FASE 5, PASO 2 VARIANTE B: Carga de flujo (L_i_flujo = random walk)")
    print("=" * 80)
    print()

    # Paths
    repo_root = Path(__file__).resolve().parent.parent.parent
    nodes_path = repo_root / "data" / "processed" / "nodes.parquet"
    edges_path = repo_root / "data" / "processed" / "edges.parquet"
    out_csv = Path(__file__).resolve().parent.parent / "data" / "processed" / "load_flujo.csv"

    # Load data
    print(f"Loading nodes and edges from parquets...")
    nodes = pd.read_parquet(nodes_path)
    edges = pd.read_parquet(edges_path)
    node_list = nodes.node_id.tolist()

    print(f"  {len(nodes)} nodes, {len(edges)} edges")
    service_edges = edges[edges.edge_type == "servicio"]
    print(f"  {len(service_edges)} service edges")
    print()

    # Build transition matrix
    print("Building transition matrix P (biased by service frequency)...")
    P_sparse, node_to_idx = build_transition_matrix(edges, node_list)
    P = P_sparse.toarray()  # Convert to dense for power iteration
    print(f"  Matrix size: {P.shape}")
    print(f"  Non-zero entries: {np.count_nonzero(P)}")
    print()

    # Compute stationary distribution
    print("Computing stationary distribution π (random walk steady state)...")
    π = compute_stationary_distribution(P)
    print()

    # Sanity checks
    assert abs(np.sum(π) - 1.0) < 1e-6, f"π should sum to 1 (is {np.sum(π)})"
    assert np.all(π >= 0), "π should be non-negative"
    print("✓ π sums to 1, all entries ≥ 0")
    print()

    # Summary
    π_nonzero = np.count_nonzero(π)
    π_nz = π[π > 0]
    print("Summary:")
    print(f"  Nodes with L_i_flujo > 0: {π_nonzero} / {len(π)}")
    print(f"  Min L_i_flujo: {π_nz.min():.6f}")
    print(f"  Max L_i_flujo: {π_nz.max():.6f}")
    print(f"  Mean L_i_flujo: {π.mean():.6f}")
    print()

    # Top 10
    π_df = pd.DataFrame({"node_id": node_list, "L_i_flujo": π})
    π_df = π_df.sort_values("L_i_flujo", ascending=False)
    print("Top 10 nodes by flow-based load:")
    print(π_df.head(10).to_string(index=False))
    print()

    # Spot check: known METRO stations
    print("Spot check — known METRO stations:")
    for nid in ["station_27_0|METRO", "station_1357_0|METRO"]:
        row = π_df[π_df.node_id == nid]
        if not row.empty:
            l_i = row["L_i_flujo"].values[0]
            rank = (π_df["L_i_flujo"] > l_i).sum() + 1
            print(f"  {nid:<25} L_i_flujo = {l_i:.6f} (rank {rank}/{len(π_df)})")
        else:
            print(f"  {nid:<25} NOT FOUND")
    print()

    # Export
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    π_df.to_csv(out_csv, index=False)
    print(f"✓ Exported: {out_csv}")


if __name__ == "__main__":
    main()
