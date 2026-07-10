"""
Phase 4: Complete analysis suite — statistics, visualizations, transfer matrix, and interactive map.

Consolidates four separate scripts (visualization.py, paso_1_visualizations.py,
transfer_matrix.py, paso_4_interactive_map.py) into a single entry point with
--steps flag for selective execution.

Functional style: pure functions, explicit composition in main().
"""

from __future__ import annotations

import argparse
import os
import pandas as pd
import numpy as np
import folium
import matplotlib.pyplot as plt


def load_graph(nodes_path: str, edges_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load nodes and edges from parquet."""
    return pd.read_parquet(nodes_path), pd.read_parquet(edges_path)


def degree_by_node(edges: pd.DataFrame) -> pd.DataFrame:
    """out_degree/in_degree per node_id, separated by edge type."""
    out_deg = edges.groupby(["source", "edge_type"]).size().unstack(fill_value=0)
    in_deg = edges.groupby(["target", "edge_type"]).size().unstack(fill_value=0)
    out_deg = out_deg.add_prefix("out_")
    in_deg = in_deg.add_prefix("in_")
    return out_deg.join(in_deg, how="outer").fillna(0).astype(int)


def degree_summary_by_agency(nodes: pd.DataFrame, degree: pd.DataFrame) -> pd.DataFrame:
    """Summary (median, mean, max) of service degree and transfer degree, per agency."""
    merged = nodes.set_index("node_id").join(degree, how="left").fillna(0)
    merged["grado_servicio"] = merged.get("out_servicio", 0) + merged.get("in_servicio", 0)
    merged["grado_transbordo"] = merged.get("out_transbordo", 0) + merged.get("in_transbordo", 0)
    return merged.groupby("agency_id")[["grado_servicio", "grado_transbordo"]].agg(
        ["median", "mean", "max"]
    ).round(1)


def weight_summary(edges: pd.DataFrame) -> pd.DataFrame:
    """Distribution of avg_travel_time_s by edge type, and distance_m for transfer edges."""
    service = edges[edges.edge_type == "servicio"].avg_travel_time_s.describe()
    transfer_time = edges[edges.edge_type == "transbordo"].avg_travel_time_s.describe()
    transfer_dist = edges[edges.edge_type == "transbordo"].distance_m.describe()
    return pd.DataFrame({
        "tiempo_servicio_s": service,
        "tiempo_transbordo_s": transfer_time,
        "distancia_transbordo_m": transfer_dist,
    }).round(1)


def headway_summary_by_agency(edges: pd.DataFrame) -> pd.DataFrame:
    """Distribution of headway_secs (service) per agency."""
    service = edges[edges.edge_type == "servicio"]
    return service.groupby("agency_id").headway_secs.describe()[
        ["count", "mean", "50%", "min", "max"]
    ].round(1)


# --- Paso 1: Console statistics ---

def print_step1_stats(nodes: pd.DataFrame, edges: pd.DataFrame) -> None:
    """Print Phase 4, Step 1 statistics to console."""
    degree = degree_by_node(edges)

    print("=== Grado por agencia (servicio vs. transbordo) ===")
    print(degree_summary_by_agency(nodes, degree).to_string())

    print("\n=== Distribución de pesos ===")
    print(weight_summary(edges).to_string())

    print("\n=== Headway (servicio) por agencia ===")
    print(headway_summary_by_agency(edges).to_string())


# --- Paso 1: Visualizations (plots) ---

def ensure_figures_dir(fig_dir: str) -> str:
    """Create figures directory if it doesn't exist; return path."""
    if not os.path.exists(fig_dir):
        os.makedirs(fig_dir)
    return fig_dir


def plot_degree_distribution(nodes: pd.DataFrame, edges: pd.DataFrame, fig_dir: str) -> None:
    """Service degree distribution per agency with histograms and median lines."""
    degree = degree_by_node(edges)
    merged = nodes.set_index("node_id").join(degree, how="left").fillna(0)
    merged["grado_servicio"] = merged.get("out_servicio", 0) + merged.get("in_servicio", 0)

    agencies = sorted(merged["agency_id"].unique())
    n_agencies = len(agencies)
    cols = min(3, n_agencies)
    rows = (n_agencies + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(12, 3.5 * rows))
    if n_agencies == 1:
        axes = [axes]
    else:
        axes = axes.flatten()

    for idx, agency in enumerate(agencies):
        ax = axes[idx]
        data = merged[merged["agency_id"] == agency]["grado_servicio"]
        ax.hist(data, bins=15, color="steelblue", edgecolor="black", alpha=0.7)
        median = data.median()
        ax.axvline(median, color="red", linestyle="--", linewidth=2, label=f"Mediana: {median:.0f}")
        ax.set_xlabel("Service Degree")
        ax.set_ylabel("Count")
        ax.set_title(f"{agency} (n={len(data)} nodes)")
        ax.legend()
        ax.grid(True, alpha=0.3)

    for idx in range(n_agencies, len(axes)):
        axes[idx].set_visible(False)

    plt.tight_layout()
    path = os.path.join(fig_dir, "degree_distribution_by_agency.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"✓ Saved: {path}")
    plt.close()


def plot_headway_by_agency(edges: pd.DataFrame, fig_dir: str) -> None:
    """Headway distribution per agency (service edges only) with box plots."""
    service = edges[edges.edge_type == "servicio"].copy()
    service = service[service.headway_secs.notna()]

    if service.empty:
        print("⚠ No service edges with headway data; skipping headway plot")
        return

    agencies = sorted(service.agency_id.unique())

    fig, ax = plt.subplots(figsize=(10, 5))
    data_by_agency = [service[service.agency_id == a].headway_secs.values for a in agencies]
    bp = ax.boxplot(data_by_agency, tick_labels=agencies, patch_artist=True)

    for patch in bp["boxes"]:
        patch.set_facecolor("lightblue")
    for whisker in bp["whiskers"]:
        whisker.set_linewidth(1.5)

    ax.set_xlabel("Agency")
    ax.set_ylabel("Headway (seconds)")
    ax.set_title("Service Headway Distribution by Agency")
    ax.grid(True, alpha=0.3, axis="y")
    plt.xticks(rotation=45)

    path = os.path.join(fig_dir, "headway_by_agency.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"✓ Saved: {path}")
    plt.close()


def plot_edge_count_by_type(edges: pd.DataFrame, fig_dir: str) -> None:
    """Stacked bar chart: service vs. transfer edge counts per agency."""
    by_agency_type = edges.groupby(["agency_id", "edge_type"]).size().unstack(fill_value=0)

    fig, ax = plt.subplots(figsize=(10, 5))
    by_agency_type.plot(kind="bar", stacked=True, ax=ax, color=["steelblue", "coral"])
    ax.set_xlabel("Agency")
    ax.set_ylabel("Edge Count")
    ax.set_title("Edge Composition by Agency (Service vs. Transfer)")
    ax.legend(title="Edge Type")
    ax.grid(True, alpha=0.3, axis="y")
    plt.xticks(rotation=45)

    path = os.path.join(fig_dir, "edge_count_by_agency.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"✓ Saved: {path}")
    plt.close()


def plot_travel_time_distribution(edges: pd.DataFrame, fig_dir: str) -> None:
    """Travel time distribution comparison: service vs. transfer edges."""
    service = edges[edges.edge_type == "servicio"].avg_travel_time_s.dropna()
    transfer = edges[edges.edge_type == "transbordo"].avg_travel_time_s.dropna()

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    axes[0].hist(service, bins=30, color="steelblue", edgecolor="black", alpha=0.7)
    axes[0].set_xlabel("Travel Time (seconds)")
    axes[0].set_ylabel("Count")
    axes[0].set_title(f"Service Edges (n={len(service)})")
    axes[0].grid(True, alpha=0.3)

    axes[1].hist(transfer, bins=30, color="coral", edgecolor="black", alpha=0.7)
    axes[1].set_xlabel("Travel Time (seconds)")
    axes[1].set_ylabel("Count")
    axes[1].set_title(f"Transfer Edges (n={len(transfer)})")
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    path = os.path.join(fig_dir, "travel_time_distribution.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"✓ Saved: {path}")
    plt.close()


def run_step1_visualizations(nodes: pd.DataFrame, edges: pd.DataFrame, fig_dir: str) -> None:
    """Execute Paso 1: generate all visualizations."""
    print(f"\n=== PASO 1: Visualizations ===")
    print(f"Generating visualizations for {len(nodes)} nodes, {len(edges)} edges...\n")

    plot_degree_distribution(nodes, edges, fig_dir)
    plot_headway_by_agency(edges, fig_dir)
    plot_edge_count_by_type(edges, fig_dir)
    plot_travel_time_distribution(edges, fig_dir)

    print(f"\n✓ All visualizations saved to {fig_dir}/")


# --- Paso 3: Transfer matrix ---

def extract_agency_from_node_id(node_id: str) -> str:
    """Extract agency_id from composite node_id (station_id|agency_id)."""
    return node_id.split("|")[1]


def transfer_matrix(edges: pd.DataFrame) -> pd.DataFrame:
    """Aggregate transfer edges by (source_agency, target_agency) pair."""
    transfers = edges[edges.edge_type == "transbordo"].copy()

    transfers["source_agency"] = transfers.source.apply(extract_agency_from_node_id)
    transfers["target_agency"] = transfers.target.apply(extract_agency_from_node_id)

    matrix = transfers.groupby(["source_agency", "target_agency"]).size().unstack(fill_value=0)
    return matrix.astype(int)


def transfer_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    """Row/column sums (total outgoing/incoming transfers per agency)."""
    return pd.DataFrame({
        "outgoing": matrix.sum(axis=1),
        "incoming": matrix.sum(axis=0),
        "total_both_directions": matrix.sum(axis=1) + matrix.sum(axis=0),
    })


def run_step3_transfer_matrix(edges: pd.DataFrame, out_csv: str) -> None:
    """Execute Paso 3: compute and export transfer matrix."""
    print(f"\n=== PASO 3: Transfer Matrix ===")

    transfers = edges[edges.edge_type == "transbordo"]
    print(f"Total transfer (transbordo) edges: {len(transfers)}")

    matrix = transfer_matrix(edges)
    print(f"\nTransfer matrix ({len(matrix)} × {len(matrix.columns)} agencies):")
    print(matrix.to_string())

    summary = transfer_summary(matrix)
    print(f"\nTransfer summary (outgoing / incoming / total):")
    print(summary.to_string())

    matrix.to_csv(out_csv)
    print(f"\n✓ Exported: {out_csv}")


# --- Paso 4: Interactive map ---

def agency_color_map(nodes: pd.DataFrame) -> dict[str, str]:
    """Assign a fixed color to each agency_id."""
    agencies = sorted(nodes.agency_id.unique())
    colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    ]
    return {agency: colors[i % len(colors)] for i, agency in enumerate(agencies)}


def transfer_station_ids(nodes: pd.DataFrame) -> set[str]:
    """Station IDs with >=2 agencies (multi-agency stations = transfer hubs)."""
    multi_agency = nodes.groupby("station_id").agency_id.nunique()
    return set(multi_agency[multi_agency >= 2].index)


def build_map(nodes: pd.DataFrame, color_map: dict[str, str], transfer_ids: set[str]) -> folium.Map:
    """Build folium.Map with nodes as CircleMarkers, colored by agency."""
    center_lat = nodes.lat.mean()
    center_lon = nodes.lon.mean()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles="OpenStreetMap"
    )

    for _, node in nodes.iterrows():
        is_transfer = node.station_id in transfer_ids
        radius = 8 if is_transfer else 5
        weight = 3 if is_transfer else 1
        opacity = 0.8 if is_transfer else 0.6

        popup_text = (
            f"<b>{node.station_id}</b><br>"
            f"Agency: {node.agency_id}<br>"
            f"Stop: {node.stop_name}"
        )

        folium.CircleMarker(
            location=[node.lat, node.lon],
            radius=radius,
            popup=folium.Popup(popup_text, max_width=250),
            color=color_map[node.agency_id],
            fill=True,
            fillColor=color_map[node.agency_id],
            fillOpacity=opacity,
            weight=weight,
        ).add_to(m)

    return m


def run_step4_interactive_map(nodes: pd.DataFrame, out_html: str) -> None:
    """Execute Paso 4: generate and export interactive folium map."""
    print(f"\n=== PASO 4: Interactive Map ===")

    color_map = agency_color_map(nodes)
    transfer_ids = transfer_station_ids(nodes)

    print(f"Total nodes: {len(nodes)}")
    print(f"Agencies: {sorted(nodes.agency_id.unique())}")
    print(f"Transfer stations (>=2 agencies): {len(transfer_ids)}")

    m = build_map(nodes, color_map, transfer_ids)
    m.save(out_html)
    print(f"\n✓ Saved: {out_html}")


# --- Main orchestrator ---

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 4: Complete network analysis (statistics, visualizations, transfer matrix, map)"
    )
    parser.add_argument(
        "--steps",
        type=str,
        default="1,3,4",
        help="Comma-separated list of steps to run: 1 (stats/plots), 3 (transfer matrix), 4 (map). Default: all",
    )
    parser.add_argument(
        "--nodes",
        type=str,
        default="../data/processed/nodes.parquet",
        help="Path to nodes.parquet",
    )
    parser.add_argument(
        "--edges",
        type=str,
        default="../data/processed/edges.parquet",
        help="Path to edges.parquet",
    )
    parser.add_argument(
        "--figures-dir",
        type=str,
        default="../figures",
        help="Directory for output figures",
    )
    parser.add_argument(
        "--transfer-csv",
        type=str,
        default="../data/processed/transfer_matrix.csv",
        help="Output path for transfer matrix CSV",
    )
    parser.add_argument(
        "--output-map",
        type=str,
        default="../figures/interactive_map.html",
        help="Output path for interactive map HTML",
    )

    args = parser.parse_args()
    steps = [int(s.strip()) for s in args.steps.split(",")]

    fig_dir = ensure_figures_dir(args.figures_dir)
    nodes, edges = load_graph(args.nodes, args.edges)

    print(f"Loaded {len(nodes)} nodes, {len(edges)} edges")

    if 1 in steps:
        print_step1_stats(nodes, edges)
        run_step1_visualizations(nodes, edges, fig_dir)

    if 3 in steps:
        run_step3_transfer_matrix(edges, args.transfer_csv)

    if 4 in steps:
        run_step4_interactive_map(nodes, args.output_map)

    print(f"\n✅ Phase 4 analysis complete (steps: {sorted(steps)})")


if __name__ == "__main__":
    main()
