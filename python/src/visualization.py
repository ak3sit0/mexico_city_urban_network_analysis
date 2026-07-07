"""
Phase 4: validation and visualization.

Planned plots:
- Interactive map (folium), colored by agency/layer, transfer nodes
  highlighted.
- In/out degree distribution per layer.
- Connected component sizes (per layer and combined).
- Inter-layer edge heatmap (transfers between each pair of agencies).
- Histogram of clustering distances from dedup (Phase 2), to justify
  the chosen radius.
"""

import networkx as nx
import folium


def plot_interactive_map(nodes, edges) -> folium.Map:
    """Folium map colored by agency_id, transfers highlighted."""
    raise NotImplementedError


def degree_distribution_by_layer(graph: nx.MultiDiGraph):
    """In/out degree histogram, split by layer (agency_id)."""
    raise NotImplementedError


def connected_components_report(graph: nx.MultiDiGraph) -> dict:
    """Connected component sizes per layer and for the combined graph."""
    raise NotImplementedError


def interlayer_transfer_heatmap(edges):
    """Heatmap of transfer edge counts between each pair of agencies."""
    raise NotImplementedError
