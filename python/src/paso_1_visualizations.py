"""
Phase 4, Step 1: Visualizations of descriptive statistics by agency.

Generates degree distributions, headway patterns, weight distributions
per layer. Charts saved to figures/ subdirectory.

Functional style: pure functions, explicit composition in main().
"""

from __future__ import annotations

import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


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


def ensure_figures_dir() -> str:
    """Create figures/ directory if it doesn't exist; return path."""
    fig_dir = "../figures"
    if not os.path.exists(fig_dir):
        os.makedirs(fig_dir)
    return fig_dir


def plot_degree_distribution(nodes: pd.DataFrame, edges: pd.DataFrame, fig_dir: str) -> None:
    """
    Service degree distribution per agency.
    One subplot per agency with histogram and median line.
    """
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
    """
    Headway distribution per agency (service edges only).
    Box plot showing median, quartiles, outliers.
    """
    service = edges[edges.edge_type == "servicio"].copy()
    service = service[service.headway_secs.notna()]

    if service.empty:
        print("⚠ No service edges with headway data; skipping headway plot")
        return

    agencies = sorted(service.agency_id.unique())

    fig, ax = plt.subplots(figsize=(10, 5))
    data_by_agency = [service[service.agency_id == a].headway_secs.values for a in agencies]
    bp = ax.boxplot(data_by_agency, labels=agencies, patch_artist=True)

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
    """
    Stacked bar chart: service vs. transfer edge counts per agency.
    """
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
    """
    Travel time distribution comparison: service vs. transfer edges.
    Two histograms on same figure.
    """
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


def main(nodes_path: str, edges_path: str) -> None:
    fig_dir = ensure_figures_dir()
    nodes, edges = load_graph(nodes_path, edges_path)

    print(f"Generating visualizations for {len(nodes)} nodes, {len(edges)} edges...\n")

    plot_degree_distribution(nodes, edges, fig_dir)
    plot_headway_by_agency(edges, fig_dir)
    plot_edge_count_by_type(edges, fig_dir)
    plot_travel_time_distribution(edges, fig_dir)

    print(f"\n✓ All visualizations saved to {fig_dir}/")


if __name__ == "__main__":
    main("../data/processed/nodes.parquet", "../data/processed/edges.parquet")
