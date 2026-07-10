# Fase 5 — Guía de planeación

## Objetivo

Estudiar resiliencia dinámica y propagación de cascadas de fallos sobre
el grafo multiplex ya construido (Fase 3), usando el modelo
carga-capacidad tipo Motter & Lai (2002), con acoplamiento inter-capa
ya resuelto estructuralmente por las aristas de transbordo de Fase 3
(no hace falta un modelo de interdependencia aparte tipo Buldyrev —
ya está codificado como aristas reales en el grafo).

## Prerrequisitos que ya tenemos

- Grafo multiplex completo: `data/processed/nodes.parquet` /
  `edges.parquet` (8,722 nodos, 23,790 aristas).
- `headway_secs` por arista de servicio — insumo directo para capacidad.
- Estadísticas de Fase 4 (Paso 1) ya cuantifican la jerarquía de
  frecuencia por agencia — punto de partida para calibrar supuestos.
- **Advertencia metodológica confirmada en Fase 4**: el grado crudo
  (conteo de aristas) está sesgado hacia las capas más grandes (CC,
  RTP) por su densidad espacial, no por importancia real de transporte.
  Fase 5 NO debe usar grado/betweenness topológico puro como proxy de
  carga sin corregir por esto — ver Paso 2.

---

## Pasos

### Paso 0 — Tabla de capacidad por vehículo (supuesto documentado)

No es un dato medido, es una asunción explícita que hay que fijar antes
de calcular nada. Un valor razonable por agencia (pasajeros/vehículo):

| Agencia | Capacidad aprox./vehículo |
|---|---|
| METRO | ~1,200–1,500 (tren completo) |
| MB (Metrobús articulado) | ~160 |
| TROLE | ~90 |
| CBB (Cablebús) | ~10 (por cabina) |
| RTP / CC | ~80 |
| TL, SUB, INTERURBANO | por definir (revisar composición real del tren) |

Este supuesto debe quedar registrado en el mismo lugar que
`KNOWN_GAPS` de `validate_graph.py` — es información que cualquiera que
use los resultados después necesita ver, no algo que se pierda en un
comentario de código.

### Paso 1 — Capacidad por nodo (`C_i`)

```
C_i = Σ (rutas que pasan por i) (3600 / headway_secs) × capacidad_por_vehículo(agencia)
```

Directo desde `edges.parquet` (aristas de servicio, agrupadas por
nodo). Nodos sin `headway_secs` conocido (rutas sin `frequencies.txt`,
documentado desde Fase 1) quedan con `C_i` indeterminado — decidir
explícitamente si se excluyen del análisis o se les asigna un valor por
defecto documentado, no una imputación silenciosa.

### Paso 2 — Carga inicial (`L_i`) — dos variantes, no una

**Variante A — topológica (betweenness clásico):** referencia de
comparación, rápida de calcular, pero ya sabemos que sobre-representa
CC/RTP por su densidad.

**Variante B — de flujo (random-walk betweenness, Newman 2005):**
requiere la matriz de transición sesgada `P_ij ∝ w_ij^β` con `w_ij` =
frecuencia de servicio — que es la **misma pieza que necesita Fase 6**
(caminata aleatoria sesgada). Construir esto una vez, usarlo en ambas
fases. La distribución estacionaria `π_i` de esta caminata, escalada,
es `L_i` de flujo.

**El objetivo explícito de tener ambas variantes:** correr la cascada
con cada una y comparar si el ranking de nodos críticos cambia. Dado el
sesgo CC/RTP confirmado en Fase 4, es probable que sí cambie — ese
contraste es en sí mismo un resultado, no un paso intermedio a
descartar.

### Paso 3 — Regla de cascada (Motter-Lai)

- `C_i = (1 + α) · L_i`, con `α` como parámetro de tolerancia a barrer
  (ver Paso 5).
- Al fallar un nodo, su carga se redistribuye a vecinos proporcional al
  peso de la arista hacia cada uno.
- Si `L_j > C_j` en algún vecino tras la redistribución, ese nodo
  también falla — cascada iterativa hasta que nadie más supere su
  capacidad.
- Nodos de transbordo (edge_type=`transbordo`) participan en la
  redistribución igual que los de servicio — son el mecanismo real de
  propagación inter-capa.

### Paso 4 — Métricas de salida

- **Tamaño de componente gigante** `S(t)/S(0)` — señal más directa de
  colapso tipo percolación (caída abrupta, no gradual).
- **Eficiencia global** `E = promedio(1/d_ij)` sobre pares alcanzables
  — más sensible a degradación parcial que `S(t)`.
- **Flujo varado** — fracción de `π_i` (masa de la caminata, Paso 2B)
  atrapada en nodos fallidos o desconectados. La métrica más
  interpretable para "¿el sistema absorbió la falla o colapsó?".
- **Tamaño de cascada** — nodos/aristas fallidos como fracción del
  total, al terminar la propagación.

### Paso 5 — Barrido de tolerancia (el resultado con forma de paper)

Correr Pasos 3-4 para un rango de `α` (ej. 0 a 2, en pasos finos cerca
de donde se sospeche la transición). Buscar `α_crítico`: el punto donde
una falla puntual deja de ser absorbida y se vuelve cascada global.
Comparar `α_crítico` entre:
- Variante topológica vs. variante de flujo (Paso 2).
- Ataque aleatorio vs. dirigido (por grado, por `L_i`, por si es nodo
  de transbordo).
- Por capa/agencia — ¿el sistema es igual de frágil si falla primero
  METRO que si falla primero RTP?

### Paso 6 — Validación de sanity antes de reportar nada

- ¿El tamaño de cascada crece monótonamente al bajar `α`? (si no, algo
  está mal en la regla de redistribución).
- ¿Los nodos identificados como más críticos coinciden con intuición de
  dominio? (Pantitlán, Indios Verdes deberían aparecer arriba en la
  variante de flujo; si no aparecen, revisar antes de confiar en el
  resultado).

---

## Python vs. Julia en esta fase

Aquí sí cambia el balance respecto a Fases 1-4 (que fueron 100% Python):

- **Julia** para el Paso 3-5 (simulación Monte Carlo del barrido de
  `α` — muchas repeticiones, rendimiento importa). `Graphs.jl` +
  `MetaGraphsNext.jl` para cargar `nodes.parquet`/`edges.parquet`
  (`Arrow.jl`/`Parquet2.jl`), figuras finales con `CairoMakie`
  (theme de paper ya configurado en el skill `makie-figures`).
- **Python** se queda para Pasos 0-2 (preparación de datos, ya es
  territorio conocido) y para prototipar/validar la regla de cascada
  en chico antes de escalarla en Julia.

## Estado actual

Nada iniciado — esta fase completa está pendiente. El prerrequisito
compartido con Fase 6 (matriz de transición sesgada) es buen punto de
partida porque desbloquea ambas fases a la vez.

## Próximo paso sugerido

Paso 0 + Paso 1 (tabla de capacidad + cálculo de `C_i`) — es la parte
más mecánica y no depende de decisiones de diseño todavía abiertas
(a diferencia del Paso 2, que si se hace mal sesga todo lo demás).
