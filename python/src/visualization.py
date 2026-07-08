"""
Fase 4, Paso 1: estadísticas descriptivas del grafo multiplex por capa.

Grado in/out resumido por agencia (no un histograma global -- un nodo de
RTP y uno de METRO tienen roles topológicos muy distintos). Distribución
de pesos por tipo de arista (servicio vs. transbordo).

Estilo funcional: mismo patrón que ingest.py/dedup.py/build_graph.py.
"""

from __future__ import annotations

import pandas as pd


def load_graph(nodes_path: str, edges_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.read_parquet(nodes_path), pd.read_parquet(edges_path)


def degree_by_node(edges: pd.DataFrame) -> pd.DataFrame:
    """out_degree/in_degree por node_id, separado por tipo de arista."""
    out_deg = edges.groupby(["source", "edge_type"]).size().unstack(fill_value=0)
    in_deg = edges.groupby(["target", "edge_type"]).size().unstack(fill_value=0)
    out_deg = out_deg.add_prefix("out_")
    in_deg = in_deg.add_prefix("in_")
    return out_deg.join(in_deg, how="outer").fillna(0).astype(int)


def degree_summary_by_agency(nodes: pd.DataFrame, degree: pd.DataFrame) -> pd.DataFrame:
    """Resumen (mediana, media, máximo) de grado de servicio y de transbordo, por agencia."""
    merged = nodes.set_index("node_id").join(degree, how="left").fillna(0)
    cols = [c for c in merged.columns if c.startswith(("in_", "out_"))]
    merged["grado_servicio"] = merged.get("out_servicio", 0) + merged.get("in_servicio", 0)
    merged["grado_transbordo"] = merged.get("out_transbordo", 0) + merged.get("in_transbordo", 0)
    return merged.groupby("agency_id")[["grado_servicio", "grado_transbordo"]].agg(
        ["median", "mean", "max"]
    ).round(1)


def weight_summary(edges: pd.DataFrame) -> pd.DataFrame:
    """Distribución de avg_travel_time_s por tipo de arista, y distance_m para transbordo."""
    service = edges[edges.edge_type == "servicio"].avg_travel_time_s.describe()
    transfer_time = edges[edges.edge_type == "transbordo"].avg_travel_time_s.describe()
    transfer_dist = edges[edges.edge_type == "transbordo"].distance_m.describe()
    return pd.DataFrame({
        "tiempo_servicio_s": service,
        "tiempo_transbordo_s": transfer_time,
        "distancia_transbordo_m": transfer_dist,
    }).round(1)


def headway_summary_by_agency(edges: pd.DataFrame) -> pd.DataFrame:
    """Distribución de headway_secs (servicio) por agencia."""
    service = edges[edges.edge_type == "servicio"]
    return service.groupby("agency_id").headway_secs.describe()[
        ["count", "mean", "50%", "min", "max"]
    ].round(1)


def main(nodes_path: str, edges_path: str) -> None:
    nodes, edges = load_graph(nodes_path, edges_path)
    degree = degree_by_node(edges)

    print("=== Grado por agencia (servicio vs. transbordo) ===")
    print(degree_summary_by_agency(nodes, degree).to_string())

    print("\n=== Distribución de pesos ===")
    print(weight_summary(edges).to_string())

    print("\n=== Headway (servicio) por agencia ===")
    print(headway_summary_by_agency(edges).to_string())


if __name__ == "__main__":
    main("data/processed/nodes.parquet", "data/processed/edges.parquet")