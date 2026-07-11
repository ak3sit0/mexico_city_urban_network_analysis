"""
    load_nodes_edges(processed_dir::AbstractString)

Load nodes.parquet and edges.parquet (exported by python/src/build_graph.py)
and return as DataFrames.

Returns:
    (nodes_df, edges_df)

Expected columns in edges.parquet: source, target, edge_type, agency_id,
headway_secs, avg_travel_time_s (all critical for Fase 5).
"""

using Arrow, DataFrames

function load_nodes_edges(processed_dir::AbstractString)
    nodes_path = joinpath(processed_dir, "nodes.parquet")
    edges_path = joinpath(processed_dir, "edges.parquet")

    nodes = Arrow.Table(nodes_path) |> DataFrame
    edges = Arrow.Table(edges_path) |> DataFrame

    return nodes, edges
end
