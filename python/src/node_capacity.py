"""
Phase 5, Paso 1: Per-node vehicle capacity (C_i).

Computes the total passenger capacity throughput available at each node,
aggregated over all outgoing service edges.

Formula:
  C_i = Σ_{j: source=i, edge_type=servicio} (3600 / headway_secs) × capacity_per_vehicle(agency_id)

The term (3600 / headway_secs) converts headway (seconds) to frequency (vehicles/hour).
Example: headway 120s → 30 veh/hour; headway 3600s → 1 veh/hour.

Input:
  - data/processed/edges.parquet (service edges with headway_secs, agency_id)
  - data/processed/capacity_assumptions.csv (capacity per vehicle per agency)

Output:
  - data/processed/node_capacity.csv (node_id, C_i)

Caveat: One-directional (outgoing edges only). A node's capacity is its ability
to send load to neighbors, not its ability to receive it.
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path


def load_capacity_assumptions(csv_path: str | Path) -> dict[str, int]:
    """Load capacity_per_vehicle dict from CSV."""
    df = pd.read_csv(csv_path)
    return dict(zip(df.agency_id, df.capacity_per_vehicle))


def compute_node_capacity(edges: pd.DataFrame, capacity_map: dict[str, int]) -> pd.DataFrame:
    """
    Compute C_i for each node.

    Returns DataFrame with columns: node_id, C_i
    """
    # Filter to service edges only
    service = edges[edges.edge_type == "servicio"].copy()

    # Ensure headway_secs has no nulls (should be guaranteed from Paso 0 check)
    assert service.headway_secs.notna().all(), "Found null headway_secs in service edges"

    # Map capacity per vehicle for each edge
    service["capacity_pax_per_vehicle"] = service.agency_id.map(capacity_map)

    # Compute frequency in vehicles/hour: 3600 seconds / headway_secs
    service["frequency_veh_per_hour"] = 3600.0 / service.headway_secs

    # Compute throughput per edge: freq * capacity
    service["capacity_contribution"] = service.frequency_veh_per_hour * service.capacity_pax_per_vehicle

    # Aggregate by source node (outgoing edges only)
    node_capacity = service.groupby("source")["capacity_contribution"].sum().reset_index()
    node_capacity.columns = ["node_id", "C_i"]
    node_capacity["C_i"] = node_capacity["C_i"].round(1)

    return node_capacity.sort_values("C_i", ascending=False)


def main() -> None:
    """Load inputs, compute node capacities, export CSV."""
    print("=" * 80)
    print("FASE 5, PASO 1: Capacidad por nodo (C_i)")
    print("=" * 80)
    print()

    # Paths
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent  # python/src -> python -> repo root
    python_dir = script_dir.parent  # python/src -> python

    edges_path = repo_root / "data" / "processed" / "edges.parquet"
    capacity_csv = python_dir / "data" / "processed" / "capacity_assumptions.csv"
    out_csv = python_dir / "data" / "processed" / "node_capacity.csv"

    # Load
    print(f"Loading edges from {edges_path.name}...")
    edges = pd.read_parquet(edges_path)

    print(f"Loading capacity assumptions from {capacity_csv.name}...")
    capacity_map = load_capacity_assumptions(capacity_csv)
    print(f"  ✓ {len(capacity_map)} agencies loaded")

    # Compute
    print("\nComputing C_i for each node...")
    node_cap = compute_node_capacity(edges, capacity_map)

    # Export
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    node_cap.to_csv(out_csv, index=False)
    print(f"✓ Exported: {out_csv}")
    print()

    # Summary stats
    print(f"Summary:")
    print(f"  Nodes with C_i > 0: {len(node_cap)}")
    print(f"  Min C_i: {node_cap['C_i'].min():.0f} pax/hour")
    print(f"  Max C_i: {node_cap['C_i'].max():.0f} pax/hour")
    print(f"  Mean C_i: {node_cap['C_i'].mean():.0f} pax/hour")
    print()

    # Spot check: known high-capacity stations
    print("Top 10 nodes by capacity (should be major hub stations):")
    print(node_cap.head(10)[["node_id", "C_i"]].to_string(index=False))
    print()

    # Verification: known stations (METRO hubs)
    known_ids = ["station_27_0|METRO", "station_1357_0|METRO"]
    print("Spot check — known METRO stations:")
    for nid in known_ids:
        row = node_cap[node_cap.node_id == nid]
        if not row.empty:
            c_i = row["C_i"].values[0]
            print(f"  {nid:<25} C_i = {c_i:>10,.0f} pax/hour")
        else:
            print(f"  {nid:<25} NOT FOUND (may have no outgoing service edges)")


if __name__ == "__main__":
    main()
