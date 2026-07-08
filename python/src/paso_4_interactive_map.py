"""
Phase 4, Step 4: Interactive folium map of the multiplex network.

Shows nodes colored by agency, highlights transfer stations (multi-agency
nodes), centered on Mexico City. No edge drawing — 23,790 edges would make
the map unreadable; node colors and spatial distribution communicate the
per-layer topology already.

Functional style: pure functions, explicit composition in main().
"""

from __future__ import annotations

import pandas as pd
import folium
from folium import plugins


def load_nodes(path: str) -> pd.DataFrame:
    """Load nodes from parquet."""
    return pd.read_parquet(path)


def agency_color_map(nodes: pd.DataFrame) -> dict[str, str]:
    """
    Assign a fixed color to each agency_id.
    Uses a categorical palette deterministic across runs.
    """
    agencies = sorted(nodes.agency_id.unique())
    colors = [
        "#1f77b4",  # blue
        "#ff7f0e",  # orange
        "#2ca02c",  # green
        "#d62728",  # red
        "#9467bd",  # purple
        "#8c564b",  # brown
        "#e377c2",  # pink
        "#7f7f7f",  # gray
        "#bcbd22",  # olive
    ]
    return {agency: colors[i % len(colors)] for i, agency in enumerate(agencies)}


def transfer_station_ids(nodes: pd.DataFrame) -> set[str]:
    """
    Station IDs with >=2 agencies (multi-agency stations = transfer hubs).
    Same criterion as build_graph.warn_stations_without_transfer().
    """
    multi_agency = nodes.groupby("station_id").agency_id.nunique()
    return set(multi_agency[multi_agency >= 2].index)


def build_map(nodes: pd.DataFrame, color_map: dict[str, str], transfer_ids: set[str]) -> folium.Map:
    """
    Build folium.Map with nodes as CircleMarkers, colored by agency.
    Transfer stations get larger circles with distinct borders.
    """
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


def main(nodes_path: str, out_html: str) -> None:
    nodes = load_nodes(nodes_path)
    color_map = agency_color_map(nodes)
    transfer_ids = transfer_station_ids(nodes)

    print(f"Total nodes: {len(nodes)}")
    print(f"Agencies: {sorted(nodes.agency_id.unique())}")
    print(f"Transfer stations (>=2 agencies): {len(transfer_ids)}")

    m = build_map(nodes, color_map, transfer_ids)
    m.save(out_html)
    print(f"\n✓ Saved: {out_html}")


if __name__ == "__main__":
    main("../data/processed/nodes.parquet", "../figures/interactive_map.html")
