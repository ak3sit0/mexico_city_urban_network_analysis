"""
    load_multiplex(processed_dir::AbstractString) -> MetaGraph

Loads nodes.parquet and edges.parquet (exported by
python/src/build_graph.py) and builds a multiplex MetaGraph using
MetaGraphsNext.jl.

Expected columns in edges.parquet: source, target, layer, weight,
route_id, agency_id.
"""

# TODO: use Arrow.jl or Parquet.jl to read nodes/edges,
# build a Graphs.jl SimpleDiGraph + metadata via MetaGraphsNext.
function load_multiplex(processed_dir::AbstractString)
    error("not implemented — Phase 3 must export nodes/edges.parquet first")
end
