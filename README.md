# CDMX Transit Resilience

Multiplex graph of Mexico City's mobility system (Metro, Metrobús,
Trolebús, RTP, Corredores Concesionados, Cablebús, Pumabús, Tren Ligero,
Suburbano, Tren Interurbano) built from GTFS data, to study:

1. **Dynamic resilience and cascading failure propagation** (Motter & Lai
   style load-capacity model, with Buldyrev et al. style inter-layer
   coupling).
2. **Peak-hour passenger flow** modeled as a biased random walk over the
   graph (Fronczak & Fronczak; Noh & Rieger), using service frequency as
   a proxy for capacity/flow.

This README covers the **first part**: ingestion, spatial deduplication of
stations, and construction of the multiplex graph. The simulation phases
(cascades, random walk) remain on the roadmap.

---

## Data source

Combined multi-agency GTFS (`data/raw/`, not versioned in git — see
`.gitignore`). Tables: `agency`, `routes`, `trips`, `stop_times`, `stops`,
`shapes`, `frequencies`, `calendar`.

**Does not include an origin-destination passenger matrix.** Any reference
to "flow" or "demand" in this project is a *proxy* derived from service
supply (frequency, assumed vehicle capacity), not real boarding data. This
must be made explicit in any reported result.

---

## Repository structure

```
cdmx-transit-resilience/
├── README.md
├── .gitignore
├── data/
│   ├── raw/                    # original GTFS (gitignored)
│   ├── interim/                # validated/cleaned tables
│   └── processed/              # nodes.parquet, edges.parquet (final graph)
├── python/
│   ├── pyproject.toml
│   ├── src/
│   │   ├── __init__.py
│   │   ├── loading_data.py      # Phase 1: load + schema validation
│   │   ├── deduplication.py     # Phase 2: spatial deduplication of stations
│   │   ├── build_graph.py       # Phase 3: multiplex graph construction
│   │   └── visualization.py     # Phase 4: validation maps and plots
│   └── notebooks/
│       ├── 01_exploration.ipynb
│       ├── 02_dedup_qc.ipynb
│       └── 03_graph_validation.ipynb
├── julia/
│   ├── Project.toml
│   ├── Manifest.toml
│   └── src/
│       ├── graph_load.jl        # imports nodes/edges.parquet into Graphs.jl
│       ├── cascade.jl           # Phase 5 (future): cascade simulation
│       └── random_walk.jl       # Phase 6 (future): biased random walk
├── figures/                    # exported (PNG/HTML/SVG)
└── tests/
    ├── test_dedup.py
    └── test_graph_integrity.py
```

---

## Roadmap / Phases

- [ ] **Phase 0** — Environment setup (Python + Julia)
- [ ] **Phase 1** — GTFS ingestion and schema validation
- [ ] **Phase 2** — Spatial deduplication of stations (+ manual overrides)
- [ ] **Phase 3** — Multiplex graph construction (L-space per layer/agency)
- [ ] **Phase 4** — Validation and visualization
- [ ] **Phase 5** *(future)* — Cascading failure simulation (Julia)
- [ ] **Phase 6** *(future)* — Biased random walk / peak-hour flow (Julia)

---

## Stack

**Python** — ingestion, geospatial work, prototyping, interactive maps:
`pandas`, `gtfs-kit` or `partridge`, `scikit-learn` (BallTree/haversine),
`rapidfuzz`, `networkx` (construction/export, not heavy simulation),
`geopandas`, `folium`/`plotly`.

**Julia** — heavy simulation (Monte Carlo cascades and random walks) and
final publication figures: `Graphs.jl`, `MetaGraphsNext.jl`, `CairoMakie`
(reused paper theme), optionally `DifferentialEquations.jl` if load
redistribution is modeled as a continuous mean-field system.

**Cross-language interface:** `data/processed/nodes.parquet` +
`edges.parquet` (columns: `source, target, layer, weight, route_id,
agency_id, ...`). GraphML is deliberately avoided — Parquet is more
flexible for the multiplex schema and both ecosystems read it without
friction.

---

## Known limitations

- There is no real passenger demand (OD) data; service frequency
  (`frequencies.txt`) is used as a proxy for capacity/flow.
- Only ~31% of trips distinguish a peak/off-peak window in
  `frequencies.txt`; the rest report a flat headway all day. The
  peak-vs-off-peak bias is only empirically grounded for that subset.
- Automatic spatial deduplication (distance + name) can fail for large
  transfer stations with widely separated platforms (e.g. Pantitlán,
  Chabacano) — requires manual review via explicit overrides (see
  `apply_manual_overrides` in `deduplication.py`).

---

## How to reproduce

```bash
# Python
cd python && uv sync

# Julia
cd julia && julia --project=. -e 'using Pkg; Pkg.instantiate()'

# Tests
cd python && uv run pytest ../tests

# Lint
cd python && uv run ruff check . && uv run ruff format --check .
```

---

## References

- Motter, A.E. & Lai, Y.C. (2002). *Cascade-based attacks on complex networks.*
- Buldyrev, S.V. et al. (2010). *Catastrophic cascade of failures in interdependent networks.*
- Newman, M.E.J. (2005). *A measure of betweenness centrality based on random walks.*
- Von Ferber, C. et al. *L-space / P-space / C-space formalism for transport networks.*
- Noh, J.D. & Rieger, H. (2004). *Random walks on complex networks.*
- Fronczak, A. & Fronczak, P. (2009). *Biased random walks in complex networks.*
