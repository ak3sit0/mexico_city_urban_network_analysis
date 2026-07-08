# Fase 4 — Guía de avance

## Objetivo

Entender la topología real del grafo multiplex ya construido (Fase 3)
antes de tocar cascadas/random walk (Fase 5/6). Todo en Python —
8,722 nodos / ~23,790 aristas no justifica migrar a Julia todavía.

## Plan original (4 pasos)

1. **Estadísticas descriptivas por capa** — grado in/out y distribución
   de pesos, resumidos por agencia (no un histograma global).
2. **Componentes conexas a fondo** — identificar exactamente qué nodos
   caen fuera de la componente gigante y por qué.
3. **Matriz de transbordos agencia×agencia** — heatmap de cuántas
   aristas de transbordo conectan cada par de capas.
4. **Mapa interactivo** (`folium`) — coloreado por agencia, resaltando
   nodos de transbordo.

---

## Estado actual

### Paso 1 — ✅ Completado

Ejecutado `graph_stats.py`. Hallazgos:

- Grado de servicio: mediana 4 en casi todas las agencias, **TROLE en 2**
  (más nodos terminales relativos a su tamaño).
- Grado de transbordo: mediana 0 en todas — el transbordo es un
  fenómeno raro y concentrado (coherente con que solo ~480 `station_id`
  de 8,722 nodos son multi-agencia).
- Nodo `CC` de grado 66 investigado: `Tlalpan - Estadio Azteca`, real,
  no error (corredor con muchas rutas convergiendo).
- Headway máximo RTP de 85 min investigado: caso aislado, no
  sistémico.
- **Jerarquía de frecuencia por agencia ya cuantificada** (insumo
  directo para Fase 6): METRO (3 min) > MB/CBB/SUB (~5 min) > TROLE
  (6 min) > PUMABUS (8 min) > RTP (mediana 30 min, cola hasta 85 min).

### Paso 2 — ✅ Efectivamente resuelto (aunque se hizo fuera de orden)

Se adelantó antes de cerrar el Paso 1 porque generó hallazgos que valía
la pena corregir de inmediato:

- Componentes conexas: 5 → **3**, componente gigante 99.6% → 99.8%.
- **Hallazgo metodológico importante**: el radio fijo de 150m de Fase 2
  no detecta CETRAMs grandes y dispersos (plataformas de distintas
  agencias a más de 150m entre sí). Se encontraron y corrigieron **11
  CETRAMs** con este problema: Indios Verdes, Buenavista, Constitución
  de 1917, El Rosario, San Lázaro (extensión), Tasqueña (extensión),
  Martín Carrera (extensión), La Raza, Deportivo 18 de Marzo,
  Chapultepec, Coyuya (fusión parcial, verificado que son dos puntos
  reales distintos).
- Las 2 componentes restantes están diagnosticadas como legítimas, no
  huecos de dedup: un ramal RTP alimentador en Santa Fe, y el Tren
  Interurbano completo (746-989m de cualquier otra agencia — distancia
  real, no error).
- **Efecto colateral encontrado y corregido**: un bug real de
  integridad en `station_merge_overrides.csv` (un `stop_id` con dos
  destinos contradictorios, resuelto en silencio por orden de fila) —
  `apply_overrides()` ahora lo detecta y detiene la ejecución en vez de
  aplicarlo a ciegas.

*No hay un cierre formal documentado de este paso más allá de lo
anterior — si se quiere dar por "a fondo" en el sentido estricto del
plan original, faltaría solo confirmar que no queden más CETRAMs
oficiales sin revisar (se cubrieron los que aparecían como componentes
aisladas o en la lista oficial de 36, pero no se agotó exhaustivamente
cada uno).*

### Paso 3 — ⏳ Pendiente

Matriz de transbordos agencia×agencia. No iniciado.

### Paso 4 — ⏳ Pendiente

Mapa interactivo con `folium`. No iniciado — depende de tener la lista
de nodos de transbordo del Paso 3 para resaltarlos bien.

---

## Dónde vive esto

- `graph_stats.py` — Paso 1 (ya escrito y corrido).
- Paso 2 se resolvió con exploración directa + ediciones a
  `manual_overrides/station_merge_overrides.csv` + re-corridas de
  `dedup.py`/`build_graph.py`/`validate_graph.py` — no generó un
  script propio nuevo.
- Paso 3 y 4 — sin archivo todavía. `figures/` sigue sin crearse (se
  crea recién cuando el Paso 4 genere el primer mapa exportado).

## Próximo paso sugerido

Paso 3 (matriz de transbordos agencia×agencia) — es rápido de calcular
con lo que ya existe en `edges.parquet` (`edge_type == "transbordo"`),
y su resultado alimenta directamente el Paso 4.
