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

### Paso 3 — ✅ Completado

Matriz de transbordos agencia×agencia. Ejecutado como parte de
`phase_4_analysis.py`.

**Hallazgos:**
- 1,240 aristas de transbordo (transbordo) en total
- Matriz 9×9 (agencias en la matriz de transbordo; INTERURBANO tiene 0 transferencias)
- **CC ↔ RTP: 302 edges** (conexión dominante)
- **RTP ↔ TROLE: 59 edges** (segunda conexión más fuerte)
- PUMABUS: solo 1 arista de transbordo (aislado de red)

### Paso 4 — ✅ Completado

Mapa interactivo con `folium`. Ejecutado como parte de `phase_4_analysis.py`.

**Hallazgos:**
- 8,722 nodos distribuidos por 10 agencias (incluida INTERURBANO, no
  anticipada en inicialmente en conteo de 9).
- **481 estaciones de transbordo** (station_id con >=2 agencies) — puntos
  grandes con borde destacado en el mapa.
- Mapa centrado en CDMX, zoom 11, visualmente coherente: METRO en corredores
  centrales, RTP disperso en periferia, INTERURBANO en bordes, CC/MB en
  cobertura urbana.
- Salida: `figures/interactive_map.html` (interactivo, zoomeable, con popups
  por nodo mostrando station_id/agency_id/stop_name).

---

## Dónde vive esto

- `phase_4_analysis.py` — Módulo consolidado que contiene todos los pasos:
  - Paso 1: estadísticas por consola + 4 gráficas PNG (degree distribution, headway, edge count, travel time)
  - Paso 3: matriz agencia×agencia, exporta CSV
  - Paso 4: mapa folium interactivo (HTML)
- Paso 2 se resolvió con exploración directa + ediciones a
  `manual_overrides/station_merge_overrides.csv` + re-corridas de
  `deduplication.py`/`build_graph.py` — no generó un script propio.
- `figures/` poblado con: 4 PNGs (estadísticas) + 1 HTML (mapa interactivo)

## Ejecución

```bash
cd python
# Ejecutar todos los pasos (Paso 1 + Paso 3 + Paso 4)
python src/phase_4_analysis.py

# O ejecutar pasos específicos
python src/phase_4_analysis.py --steps 1        # Solo gráficas y estadísticas
python src/phase_4_analysis.py --steps 3        # Solo matriz de transbordos
python src/phase_4_analysis.py --steps 1,3      # Pasos 1 y 3, sin mapa
```
