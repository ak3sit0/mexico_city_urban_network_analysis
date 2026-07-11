"""
Phase 5, Paso 2 Variante B: Flow-based load (L_i_flujo = random walk stationary distribution).

Computes the stationary distribution of a random walk biased by edge frequency.
This represents the long-run proportion of time a random walker spends at each node,
weighted by service frequency.

Interpretation:
  L_i_flujo = steady-state visitation frequency at node i
  High L_i_flujo = nodes that see more "traffic" from the random walk

This complements Variante A (topological betweenness):
  - Variante A: structural bridges (disconnects graph if removed)
  - Variante B: high-traffic nodes (receive more demand)
"""

include("graph_load.jl")

using DataFrames, Arrow, CSV, SparseArrays, LinearAlgebra

function build_transition_matrix(edges_df::DataFrame, node_list::Vector{String})
    """
    Build sparse transition matrix P where P[i,j] is the probability of
    transitioning from node i to node j, weighted by service frequency.

    Returns:
        P::Matrix (n × n, row-stochastic)
        node_to_idx::Dict (node_id -> row index)
    """
    n = length(node_list)
    node_to_idx = Dict(node => i for (i, node) in enumerate(node_list))

    # Filter to service edges only
    service = filter(row -> row.edge_type == "servicio", edges_df)

    # Compute frequency (vehicles/hour) = 3600 / headway_secs
    service[!, :frequency] = 3600.0 ./ service[!, :headway_secs]

    # Aggregate by (source, target) to handle multi-edges
    grouped = combine(groupby(service, [:source, :target]), :frequency => sum => :frequency)

    # Build matrix: P[i,j] = transition probability from i to j
    P = zeros(Float64, n, n)

    for row in eachrow(grouped)
        i = get(node_to_idx, row.source, 0)
        j = get(node_to_idx, row.target, 0)
        if i > 0 && j > 0  # Skip nodes not in our list
            P[i, j] += row.frequency
        end
    end

    # Normalize to make row-stochastic (each row sums to 1)
    for i in 1:n
        row_sum = sum(P[i, :])
        if row_sum > 0
            P[i, :] ./= row_sum
        end
    end

    return P, node_to_idx
end

function compute_stationary_distribution(P::Matrix)
    """
    Compute the stationary distribution π of the transition matrix P.

    Solves: π^T = π^T * P (left eigenvector of P, or right eigenvector of P^T)

    Uses power iteration: repeatedly multiply π by P until convergence.
    """
    n = size(P, 1)
    π = ones(n) / n  # Start with uniform distribution

    max_iter = 1000
    tol = 1e-8

    for iter in 1:max_iter
        π_new = P' * π  # Apply transition matrix (transpose because P is row-stochastic)
        π_new = π_new / sum(π_new)  # Re-normalize

        if norm(π_new - π) < tol
            println("  Converged in $iter iterations")
            return π_new
        end
        π = π_new
    end

    println("  Warning: did not converge after $max_iter iterations")
    return π / sum(π)
end

function main()
    println("=" ^ 80)
    println("FASE 5, PASO 2 VARIANTE B: Carga de flujo (L_i_flujo = random walk)")
    println("=" ^ 80)
    println()

    # Paths
    proj_dir = dirname(dirname(dirname(@__FILE__)))
    processed_dir = joinpath(proj_dir, "data", "processed")
    out_csv = joinpath(processed_dir, "load_flujo.csv")

    # Load data
    println("Loading nodes and edges from parquets...")
    nodes_df, edges_df = load_nodes_edges(processed_dir)
    node_list = string.(nodes_df.node_id)  # Ensure strings

    println("  $(nrow(nodes_df)) nodes, $(nrow(edges_df)) edges")
    service_edges = filter(row -> row.edge_type == "servicio", edges_df)
    println("  $(nrow(service_edges)) service edges")
    println()

    # Build transition matrix
    println("Building transition matrix P (biased by service frequency)...")
    P, node_to_idx = build_transition_matrix(edges_df, node_list)
    println("  Matrix size: $(size(P))")
    println("  Non-zero entries: $(count(x -> x > 0, P))")
    println()

    # Compute stationary distribution
    println("Computing stationary distribution π (random walk steady state)...")
    π = compute_stationary_distribution(P)
    println()

    # Sanity checks
    @assert abs(sum(π) - 1.0) < 1e-6 "π should sum to 1 (is $(sum(π)))"
    @assert all(π .≥ 0) "π should be non-negative"
    println("✓ π sums to 1, all entries ≥ 0")
    println()

    # Summary
    π_nonzero = count(x -> x > 0, π)
    π_nz = π[π .> 0]
    println("Summary:")
    println("  Nodes with L_i_flujo > 0: $π_nonzero / $(length(π))")
    println("  Min L_i_flujo: $(minimum(π_nz))")
    println("  Max L_i_flujo: $(maximum(π_nz))")
    println("  Mean L_i_flujo: $(mean(π))")
    println()

    # Top 10
    π_df = DataFrame(node_id=node_list, L_i_flujo=π)
    sort!(π_df, :L_i_flujo, rev=true)
    println("Top 10 nodes by flow-based load:")
    println(first(π_df, 10))
    println()

    # Spot check: known METRO stations
    println("Spot check — known METRO stations:")
    for nid in ["station_27_0|METRO", "station_1357_0|METRO"]
        row = filter(r -> r.node_id == nid, π_df)
        if !isempty(row)
            l_i = row.L_i_flujo[1]
            rank = findfirst(==(nid), π_df.node_id)
            rank_str = rank === nothing ? "NOT FOUND" : "rank $rank / $(nrow(π_df))"
            println("  $nid: L_i_flujo = $(round(l_i, digits=6)) ($rank_str)")
        else
            println("  $nid: NOT FOUND")
        end
    end
    println()

    # Export
    mkpath(processed_dir)
    println("Exporting to $out_csv...")
    CSV.write(out_csv, π_df)
    println("✓ Done")
end

# Entry point
if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
