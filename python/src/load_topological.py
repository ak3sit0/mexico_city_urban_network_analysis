"""
Phase 5, Paso 2 Variante A: Topological load (L_i).

Computes the topological importance of each node using betweenness centrality.
This measures how many shortest paths pass through each node — nodes that
connect different parts of the network have high betweenness.

Formula: L_i = betweenness_centrality(node_i)
  where betweenness is normalized to [0, 1] by default in NetworkX.

This is one of two variants for computing L_i (Paso 2). The other variant
(Paso 2B) uses flow-based centrality (random walk stationary distribution),
computed in Julia.

Caveat:
- This uses directed betweenness centrality (respects edge direction).
- For large graphs (8.7k nodes), we use approximate betweenness with k=100
  node samples instead of full computation (saves ~50x time, minimal accuracy loss).
- Betweenness is not a direct measure of load (which depends on frequency and
  capacity, already captured in C_i from Paso 1). Rather, it's a measure of
  *structural criticality* — if a node fails, how many shortest paths are broken?

Input:
  - data/processed/nodes.parquet (node_id, agency_id, station_id, ...)
  - data/processed/edges.parquet (source, target, edge_type == 'servicio')

Output:
  - data/processed/load_topological.csv (node_id, L_i_topo)

Note: Column named L_i_topo (not L_i) to distinguish from flow-based variant (L_i_flujo).
"""

from __future__ import annotations

import pandas as pd
import networkx as nx
from pathlib import Path
import time


def load_graph_from_parquets(nodes_path: str | Path, edges_path: str | Path) -> nx.MultiDiGraph:
    """
    Build MultiDiGraph from nodes and service edges.

    Only service edges are included (edge_type == 'servicio'), since transfer
    edges represent walking, not network flow.
    """
    nodes = pd.read_parquet(nodes_path)
    edges = pd.read_parquet(edges_path)

    # Filter to service edges only
    service_edges = edges[edges.edge_type == "servicio"]

    # Build graph
    G = nx.MultiDiGraph()
    G.add_nodes_from(nodes.node_id)
    for _, row in service_edges.iterrows():
        G.add_edge(row.source, row.target)

    return G


def compute_topological_load(G: nx.MultiDiGraph, k: int = 100) -> dict[str, float]:
    """
    Compute approximate betweenness centrality for all nodes.

    Args:
        G: Directed multigraph
        k: Number of random nodes to sample for shortest-path calculation.
           If None, uses all nodes (exact but slow, O(n^2.4) time).
           k=100 gives ~10-50x speedup with minimal loss of accuracy.

    Returns:
        dict: node_id -> L_i_topo (normalized betweenness, [0, 1])
    """
    return nx.betweenness_centrality(G, k=k)


def main() -> None:
    """Load graph, compute topological load, export CSV."""
    print("=" * 80)
    print("FASE 5, PASO 2 VARIANTE A: Carga topológica (L_i_topo = betweenness)")
    print("=" * 80)
    print()

    # Paths
    repo_root = Path(__file__).resolve().parent.parent.parent
    nodes_path = repo_root / "data" / "processed" / "nodes.parquet"
    edges_path = repo_root / "data" / "processed" / "edges.parquet"
    out_csv = Path(__file__).resolve().parent.parent / "data" / "processed" / "load_topological.csv"

    # Load graph
    print(f"Loading graph from {nodes_path.name} + {edges_path.name}...")
    t0 = time.time()
    G = load_graph_from_parquets(nodes_path, edges_path)
    print(f"  {len(G.nodes())} nodes, {len(G.edges())} edges (service only)")
    print(f"  {nx.number_weakly_connected_components(G)} weakly connected components")
    print()

    # Compute betweenness with sampling (k=100)
    print("Computing betweenness centrality (k=100 sampling)...")
    t1 = time.time()
    bc = compute_topological_load(G, k=100)
    t2 = time.time()
    print(f"  ✓ Computed in {t2 - t1:.2f}s")
    print()

    # Convert to DataFrame and export
    df = pd.DataFrame(list(bc.items()), columns=["node_id", "L_i_topo"])
    df = df.sort_values("L_i_topo", ascending=False)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(f"✓ Exported: {out_csv}")
    print()

    # Summary
    print("Summary:")
    print(f"  Nodes with L_i_topo > 0: {(df['L_i_topo'] > 0).sum()}")
    print(f"  Min L_i_topo: {df['L_i_topo'].min():.6f}")
    print(f"  Max L_i_topo: {df['L_i_topo'].max():.6f}")
    print(f"  Mean L_i_topo: {df['L_i_topo'].mean():.6f}")
    print()

    # Top 10
    print("Top 10 nodes by topological importance (betweenness):")
    print(df.head(10)[["node_id", "L_i_topo"]].to_string(index=False))
    print()

    # Spot check
    known_ids = ["station_27_0|METRO", "station_1357_0|METRO"]
    print("Spot check — known METRO stations:")
    for nid in known_ids:
        row = df[df.node_id == nid]
        if not row.empty:
            l_i = row["L_i_topo"].values[0]
            rank = (df['L_i_topo'] > l_i).sum() + 1
            print(f"  {nid:<25} L_i_topo = {l_i:.6f} (rank {rank}/{len(df)})")
        else:
            print(f"  {nid:<25} NOT FOUND")
    print()

    print(f"Total time: {t2 - t0:.2f}s")


if __name__ == "__main__":
    main()
