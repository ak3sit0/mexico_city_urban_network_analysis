# Fase 5 — Guía de planeación (actualizada)

## Checklist previa — verificar antes de saltar a Fase 5

La Fase 4 se consolidó (4 scripts sueltos → `phase_4_analysis.py`, commit
`c1d9fff`) y los nombres de script cambiaron respecto a las fases
anteriores. Antes de construir sobre esto, vale la pena confirmar lo
siguiente — no asumirlo porque "ya se hizo antes":

- [x] **Rutas relativas al script, no al cwd.** ✅ `phase_4_analysis.py` usa
  rutas relativas `../data/processed/...`. Scripts ejecutan sin errores desde
  `python/`. Verificado: `deduplication.py` completa con 8,374 stations.
- [x] **El chequeo bloqueante de overrides duplicados sigue presente.** ✅
  `apply_overrides()` en `deduplication.py` (líneas 193-203) detecta y lanza
  `ValueError` si un `stop_id` tiene >1 `target_station_id` distinto.
  Verificado: corre sin errores.
- [x] **`KNOWN_GAPS` (SEMOVI) — reemplazo.** `validate_graph.py` nunca existió.
  Se crea `capacity_assumptions.py` como "lugar de verdad" para supuestos
  documentados en Fase 5, mismo espíritu (constante explícita, visible).
- [x] **No-regresión de números tras la consolidación** — ✅ confirmado:
  8,722 nodos / 23,790 aristas / 1,240 transbordo / 481 hubs idénticos.
- [x] **`tests/test_dedup.py` y `test_graph_integrity.py`.** Stubs vacíos con
  `TODO` — sin contenido real. No hay red de seguridad automática, solo
  verificación manual. Aceptable para avanzar a Fase 5.
- [x] **Empaquetado Python.** `pyproject.toml` tiene `[tool.setuptools.packages.find]
  include = ["cdmx_gtfs*"]` (legacy), pero layout es `python/src/` con scripts
  sueltos. `uv run` + `uv sync` funcionan sin fricción. Scripts invocan con
  rutas relativas, no como paquete. Aceptable.
- [x] **`transfer_matrix.csv` verificada.** ✅ Matriz 10×10, CC↔RTP: 302 ✓,
  RTP↔TROLE: 59 ✓. Valores reproducibles desde CSV.
- [x] **Commit `c1d9fff` sin referencias huérfanas.** ✅ README apunta a
  `phase_4_analysis.py`. Ningún notebook ni docs referencia a los 4 scripts
  eliminados. Clean.

---

## Estructura real del repositorio (actualizada)

```
cdmx-transit-resilience/
├── README.md
├── .gitignore
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
│       ├── nodes.parquet
│       ├── edges.parquet
│       ├── transfer_matrix.csv          # nuevo (Fase 4)
│       └── capacity_assumptions.csv     # nuevo (Fase 5, Paso 0 — pendiente)
├── manual_overrides/
│   └── station_merge_overrides.csv
├── python/
│   ├── pyproject.toml
│   ├── src/
│   │   ├── loading_data.py          # Fase 1
│   │   ├── deduplication.py         # Fase 2
│   │   ├── build_graph.py           # Fase 3
│   │   ├── phase_4_analysis.py      # Fase 4 (consolidado, --steps)
│   │   └── capacity_assumptions.py  # Fase 5, Paso 0 (pendiente de crear)
│   └── notebooks/
├── julia/
│   ├── Project.toml
│   ├── Manifest.toml
│   └── src/
│       ├── graph_load.jl
│       ├── cascade.jl               # Fase 5 (pendiente)
│       └── random_walk.jl           # Fase 6 (pendiente)
├── figures/
└── tests/
    ├── test_dedup.py                # stub, sin contenido real
    └── test_graph_integrity.py      # stub, sin contenido real
```

---

## Fase 5 — Cómo ejecutar cada paso

### Paso 0 — ✅ Tabla de capacidad por vehículo (COMPLETADO)

**Qué hace:** Documenta, como archivo versionado, el supuesto de
pasajeros/vehículo por agencia. Insumo directo del Paso 1 (cálculo de
capacidad por nodo `C_i`).

**Fuente de datos:** `python/src/capacity_assumptions.py`

Tabla final (10 agencias, todos investigadas):

| Agencia | Capacidad (pax/vehículo) | Confianza / Fuente |
|---|---|---|
| **CBB** | 10 | Oficial: cabinas de teleférico |
| **CC** | 80 | Estándar: autobús rápido urbano |
| **INTERURBANO** | 719 | **Alta:** Tren México-Toluca "El Insurgente" (CAF Civity, 5 vagones, 326 asientos + pie) |
| **MB** | 160 | **Alta:** Autobús articulado estándar |
| **METRO** | 1,300 | **Media:** Representativo entre líneas 6 y 9 vagones (6: 1,130; 9: 1,500) |
| **PUMABUS** | 40 | **Baja:** Estimación sin dato oficial de flota UNAM |
| **RTP** | 80 | Estándar: autobús rápido urbano (mismo que CC) |
| **SUB** | 1,130 | **Alta:** Tren Suburbano oficial (Buenavista-Cuautitlán, 4 vagones) |
| **TL** | 400 | **Media:** Flota mixta en transición (viejas 374, CRRC 292, nuevas 750 entrando 2026) |
| **TROLE** | 90 | Estándar: trolebús urbano |

**Archivo de referencia:** `python/src/capacity_assumptions.py`
- Constante `CAPACITY_PER_VEHICLE`: dict con 10 agencias
- Constante `CAPACITY_NOTES`: documentación por agencia (fuente, confianza)
- Constante `METHODOLOGY_CAVEATS`: supuestos generales que aplican a toda la tabla
- Función `export_csv()`: exporta a `data/processed/capacity_assumptions.csv`
- Función `main()`: imprime tabla + caveats, exporta CSV

**Verificación:** ✅ 10/10 agencias, match perfecto con `nodes.parquet`
```bash
cd python
uv run python src/capacity_assumptions.py
# Salida: data/processed/capacity_assumptions.csv
```

### Paso 1 — Capacidad por nodo (`C_i`)

**Qué hace:** `C_i = Σ (rutas por nodo i) (3600 / headway_secs) ×
capacidad_por_vehículo(agencia)`.

**Cómo ejecutarlo:**
1. Crear `python/src/node_capacity.py`.
2. Cargar `data/processed/edges.parquet` (aristas de servicio) y
   `data/processed/capacity_assumptions.csv` (Paso 0).
3. Agrupar aristas de servicio por nodo origen, sumar
   `(3600/headway_secs) * capacidad_pax` por cada arista saliente.
4. **Caso a decidir explícitamente, no ignorar:** nodos con
   `headway_secs` nulo (rutas sin `frequencies.txt`, ya documentado desde
   Fase 1) — ¿se excluyen del análisis o se les asigna un valor por
   defecto? Documentar la decisión en el mismo script, como comentario
   visible, no como default silencioso.
5. Correr:
   ```bash
   cd python
   python src/node_capacity.py
   ```
6. **Salida esperada:** `data/processed/node_capacity.csv` (`node_id,
   C_i`). **Verificación:** cruzar 2-3 nodos conocidos (Pantitlán,
   Indios Verdes) y confirmar que su `C_i` es alto — si no, algo está mal
   en el join agencia/headway antes de seguir.

### Paso 2 — Carga inicial (`L_i`) — dos variantes

**Qué hace:** calcula la carga de cada nodo de dos formas distintas, para
poder comparar (ver hallazgo de Fase 4: CC/RTP dominan en grado crudo por
tamaño de red, no por importancia real — hay que confirmar si eso se
sostiene o se corrige con la variante de flujo).

**Variante A (topológica) — más simple, hacerla primero:**
1. Crear `python/src/load_topological.py`.
2. Cargar el grafo en `networkx.MultiDiGraph` desde
   `nodes.parquet`/`edges.parquet`.
3. Calcular `nx.betweenness_centrality()` (o su versión aproximada si
   8,722 nodos resulta lento — `k=` muestreo).
4. Correr: `python src/load_topological.py` desde `python/`.
5. Salida: `data/processed/load_topological.csv`.

**Variante B (de flujo) — comparte trabajo con Fase 6, hacerla en Julia:**
1. Esta es la matriz de transición sesgada `P_ij ∝ w_ij^β` que también
   necesita Fase 6 — no la dupliques en Python y Julia por separado.
2. Crear `julia/src/random_walk.jl` (el archivo ya está en el roadmap
   para Fase 6, pero su primera mitad — construir `P_ij` y calcular la
   distribución estacionaria `π_i` — es exactamente lo que Fase 5
   necesita aquí).
3. Cargar `nodes.parquet`/`edges.parquet` con `graph_load.jl`.
4. Calcular `π_i` (distribución estacionaria) — random-walk betweenness.
5. Exportar `data/processed/load_flujo.csv` desde Julia (`CSV.jl` o
   `Arrow.jl`).
6. Correr desde `julia/`:
   ```bash
   cd julia
   julia --project=. src/random_walk.jl
   ```

**Verificación de ambas variantes antes de seguir:** comparar el ranking
top-10 de nodos por `L_i` entre variante A y B. Si Pantitlán/Indios
Verdes no aparecen arriba en la variante B, revisar antes de confiar en
el resultado — es la misma intuición de dominio que ya usamos para
validar Fase 2/4.

### Paso 3 — Regla de cascada (Motter-Lai)

**Cómo ejecutarlo:**
1. Crear `julia/src/cascade.jl` (Julia desde aquí en adelante — Monte
   Carlo pesado, ver sección de stack más abajo).
2. Cargar grafo + `C_i` (Paso 1) + `L_i` (Paso 2, ambas variantes).
3. Implementar función `run_cascade(graph, C, L, α, seed_failure)` que:
   - fija `C_i = (1+α) * L_i`,
   - falla el nodo `seed_failure`,
   - redistribuye su carga a vecinos (peso = peso de arista saliente),
   - itera mientras algún nodo tenga `L_j > C_j`,
   - devuelve el conjunto final de nodos fallidos.
4. Probar con un solo `α` y un solo nodo semilla primero (ej. Pantitlán)
   antes de correr el barrido completo del Paso 5 — confirmar que la
   cascada converge (termina) y no entra en loop infinito.

### Paso 4 — Métricas de salida

**Cómo ejecutarlo:**
1. Agregar a `cascade.jl` (o un archivo separado `metrics.jl`) funciones
   para, dado el grafo post-cascada:
   - `giant_component_ratio(graph_before, graph_after)`,
   - `global_efficiency(graph_after)`,
   - `flujo_varado(π, nodos_fallidos)` (usa la `π_i` del Paso 2B),
   - `cascade_size(nodos_fallidos, total_nodos)`.
2. Cada corrida de `run_cascade()` (Paso 3) debe devolver estas 4
   métricas, no solo la lista de nodos fallidos.

### Paso 5 — Barrido de tolerancia

**Cómo ejecutarlo:**
1. Crear `julia/src/sweep_alpha.jl`.
2. Loop sobre `α ∈ [0, 2]` (empezar con paso grueso 0.1, refinar cerca de
   donde se vea la transición).
3. Para cada `α`: correr `run_cascade()` con varios nodos semilla
   (aleatorio y dirigido — por grado, por `L_i`, por si es nodo de
   transbordo), promediar métricas.
4. Exportar resultados a `data/processed/alpha_sweep.csv`
   (`alpha, tipo_ataque, variante_carga, giant_component_ratio,
   global_efficiency, flujo_varado, cascade_size`).
5. Correr:
   ```bash
   cd julia
   julia --project=. src/sweep_alpha.jl
   ```
   (esto puede tardar — es el paso computacionalmente pesado que
   justifica estar en Julia y no en Python).

### Paso 6 — Validación de sanity antes de reportar nada

**Cómo ejecutarlo:**
1. Cargar `alpha_sweep.csv` y graficar `cascade_size` vs. `alpha` — debe
   ser monótona decreciente. Si no lo es, hay un bug en la redistribución
   de carga (Paso 3), no un resultado real.
2. Confirmar que Pantitlán/Indios Verdes aparecen entre los nodos más
   críticos (mayor `cascade_size` promedio al fallar primero) en la
   variante de flujo — mismo chequeo de intuición de dominio del Paso 2.
3. Figuras finales con `CairoMakie` (`julia/src/cascade.jl` o un script
   de figuras aparte) — reusar el theme del skill `makie-figures`.

---

## Python vs. Julia en esta fase (confirmado)

- **Python:** Paso 0 (tabla de capacidad), Paso 1 (`C_i`), Variante A del
  Paso 2 (`L_i` topológico) — todo territorio ya conocido, pandas/networkx
  bastan.
- **Julia:** Variante B del Paso 2 (`π_i`, compartida con Fase 6) en
  adelante — Pasos 3, 4, 5 son simulación Monte Carlo pesada,
  `Graphs.jl`/`MetaGraphsNext.jl` para el grafo, `CairoMakie` para
  figuras finales.

## Estado actual

- Fase 4 consolidada y sin regresión (commit `c1d9fff`).
- Fase 5, Paso 0: investigación de capacidades completada (TL, SUB,
  INTERURBANO, PUMABUS), falta reconciliar con la tabla borrador
  existente en `phase_5_guide.md` y escribir `capacity_assumptions.py`.
- Pasos 1-6: no iniciados.

## Próximo paso sugerido

Resolver la checklist previa (arriba) — en particular confirmar que las
rutas relativas y el chequeo de overrides duplicados sobrevivieron al
refactor de Fase 4 — antes de escribir `capacity_assumptions.py`. Un
prerrequisito roto en silencio ahora es más caro de encontrar después de
correr una simulación de horas en Julia.
