# Informe — Sistema Integral de Gestión y Distribución de Donaciones Post-Sismo (Colombia)

**Asignatura:** Estructuras de Datos y Algoritmos · Universidad EAFIT
**Equipo:** _(completar: nombres de los integrantes, máximo 4)_

> Resultados numéricos: se obtienen ejecutando `python -m donaciones.analysis` (archivo completo en [RESULTADOS.md](RESULTADOS.md)). Rendimiento: [BENCHMARKS.md](BENCHMARKS.md). Transparencia sobre IA: [ANEXO_IA.md](ANEXO_IA.md).

---

## 1. Resumen

Se implementó en Python 3 (solo biblioteca estándar) un sistema que modela donantes, lotes de ayuda, centros de acopio, municipios afectados y la red vial; registra y busca donaciones; asigna recursos por triaje de urgencia; calcula rutas de despacho; emite informes y alertas; y ofrece un panel gráfico (Tkinter). Responde con datos las preguntas del reto: **¿cuánta gente hay herida?, ¿qué zonas están más afectadas?, ¿qué municipios están incomunicados?, ¿qué tan cubierta está la necesidad?** (sección 3).

## 2. Fuente de datos

### 2.1 Naturaleza y origen

**Los datos son sintéticos** — como pide la Fase 1 («datos sintéticos realistas del contexto geográfico colombiano») — y se generan de forma determinista con `scripts/generar_datos.py` (semilla fija), por lo que cualquiera reproduce exactamente los mismos archivos de `data/`.

| Componente | Origen | Qué es real y qué no |
|---|---|---|
| Municipios (45) | Lista curada de municipios del Eje Cafetero, Valle, Tolima, Antioquia y capitales | Nombres, departamentos, **población y coordenadas aproximadas** (redondeadas, sin cifras oficiales DANE). Los identificadores `M-001…` son internos, no códigos DANE |
| Sismo | Escenario ficticio: epicentro (4.40, −75.75), M 6.8, fecha simulada `2026-03-01` | Ficticio por completo; no corresponde a un evento real |
| Víctimas y daños | Modelo de atenuación: tasa de heridos = 2,5 % · exp(−d/35 km) · vulnerabilidad aleatoria (0,6–1,5; ×1,3 en municipios < 20 000 hab.). Fallecidos 8–16 % de heridos, desaparecidos 2–8 %, desplazados 15 % · exp(−d/40) · vulnerabilidad | Cifras simuladas; sirven para ejercitar el sistema, **no son estimaciones de riesgo reales** |
| Nivel de urgencia (1–5) | Umbrales sobre el índice de severidad (sección 3.2) | Regla propia del modelo |
| Necesidades | Heridos·1,5 + fallecidos·0,2 kits médicos; 45 L de agua, 9 raciones, ¼ kit de refugio y 200 000 COP por desplazado; 1 herramienta de rescate por 8 viviendas dañadas | Supuestos de dimensionamiento propios |
| Centros de acopio (9) | Aeropuertos, puertos y acopios regionales plausibles | Ubicaciones y capacidades aproximadas |
| Red vial (77 tramos) | Cada nodo se une a sus 2 vecinos más cercanos y se unen componentes aisladas; km = distancia geodésica·1,3; velocidad 50–80 km/h; estado (abierta/restringida/cerrada) con probabilidad decreciente con la cercanía al epicentro | Topología simplificada; no es el mapa vial oficial |
| Donantes (24) y lotes (251) | Donantes **ficticios** (nombres inventados); cantidades ajustadas para cubrir 55 %–115 % de la necesidad por categoría, con perecederos de caducidad corta y lotes en cadena de frío | Ficticios |

Antes de asignar, la ayuda recibida cubre: médico 57 %, víveres 91 %, agua 115 %, refugio 70 %, rescate 80 %, fondos 85 % de la necesidad. Esa brecha es deliberada para que el triaje tenga sentido.

### 2.2 Esquema y persistencia

Archivos en `data/` (CSV con encabezado, UTF-8; el evento en JSON; los lotes también se exportan/importan en JSON):

| Archivo | Entidad | Campos principales |
|---|---|---|
| `event.json` | Evento | nombre, fecha, epicentro, magnitud |
| `donors.csv` | Donante | id, nombre, tipo (PERSONA/ONG/EMPRESA/INTERNACIONAL/GOBIERNO), origen |
| `hubs.csv` | Centro de acopio | id, nombre, departamento, tipo, lat, lon, capacidad m³ |
| `municipalities.csv` | Municipio | id, zona, población, urgencia 1–5, heridos, fallecidos, desaparecidos, desplazados, viviendas dañadas, `need_<categoría>` |
| `roads.csv` | Carretera | a, b, km, velocidad, estado |
| `lots.csv` | Lote de ayuda | id, donante, categoría, cantidad, unidad, peso, volumen, centro, recepción, caducidad, cadena de frío, disponible, estado |

**Validación (Fase 1).** Las entidades son `dataclass(frozen=True)` (inmutables) que validan en su constructor: tipos estrictos (un `bool` no es entero), cantidades ≥ 0, valores finitos, coordenadas dentro de Colombia, urgencia 1–5, víctimas ≤ población, `disponible ≤ cantidad`, caducidad posterior a la recepción. El cargador agrega validaciones **entre registros** (duplicados, donante o centro inexistente, carretera con nodo inexistente) y de **coherencia temporal** (recepción desde el evento y caducidad posterior al evento). Un registro malo se informa con archivo y línea y se omite (`strict=True` lo eleva como excepción); los fallos de I/O se envuelven en `DataSourceError`. Cobertura: `tests/test_models_io.py`.

## 3. Preguntas del reto y respuestas

Valores obtenidos con los datos sintéticos incluidos (reproducibles con `python -m donaciones.analysis`).

### 3.1 ¿Cuánta gente hay herida?

**26.312 heridos**, además de 3.301 fallecidos, 1.048 desaparecidos, 189.007 desplazados y 54.213 viviendas dañadas. 31 de los 45 municipios tienen urgencia ≥ 3. Los municipios con más heridos son **Armenia (6.262), Pereira (3.431), Ibagué (1.640), Dosquebradas (1.378), Tuluá (1.359), Calarcá (1.243) y La Tebaida (1.228)**.

### 3.2 ¿Qué zonas están más afectadas?

Se define el **índice de severidad** = (5·fallecidos + 3·desaparecidos + 2·heridos + desplazados) por cada 1.000 habitantes. Mide impacto relativo; por eso se muestra junto a la cifra absoluta de heridos (una ciudad grande puede tener muchos heridos y baja severidad).

| Zona | Heridos | Heridos/10 mil hab. | Severidad |
|---|---|---|---|
| **Quindío** | 10.738 | 187,7 | **171** |
| **Norte del Valle** | 2.754 | 96,6 | 91 |
| Risaralda | 5.398 | 65,6 | 65 |
| Tolima | 2.033 | 31,0 | 32 |
| Caldas | 1.451 | 24,0 | 26 |
| Centro del Valle | 2.769 | 9,7 | 11 |

**Quindío es la zona más afectada** (10.738 heridos, 41 % del total, y sus 12 municipios con urgencia ≥ 4). Los municipios más críticos en términos relativos son Buenavista (373), La Tebaida (247), Córdoba-Quindío (225), Caicedonia (217) y Armenia (189). Risaralda concentra el segundo mayor número absoluto de heridos (Pereira, Dosquebradas) aunque con menor severidad per cápita.

### 3.3 ¿Qué municipios están incomunicados?

Cuatro, sin ninguna ruta transitable desde un centro de acopio (96.000 habitantes y 988 heridos): **Circasia, Filandia, Salento (Quindío) y Zarzal (Norte del Valle)**, todos de urgencia 4. El despacho terrestre no puede atenderlos: requieren puente aéreo o reapertura de vías (el sistema los marca como alerta crítica).

### 3.4 ¿Qué tan cubierta queda la necesidad?

Tras ejecutar la asignación automática (324 asignaciones; ETA media 3,7 h, máxima 19,6 h):

| Categoría | Cobertura de la necesidad | Observación |
|---|---|---|
| Agua | 96 % | Sobra stock total, pero parte queda en centros lejanos o sin ruta |
| Víveres | 70 % | |
| Refugio | 69 % | Stock casi agotado (327 kits) → alerta crítica |
| Fondos | 67 % | |
| Rescate | 40 % | |
| **Médico** | **39 %** | Alerta crítica; buena parte del stock restante es de cadena de frío |

De las 134 solicitudes no cubiertas (total o parcialmente): 85 por stock insuficiente, 25 por restricción de cadena de frío (ruta > 12 h) y 24 por aislamiento. 13 municipios de urgencia ≥ 4 conservan necesidades pendientes. Los 6 lotes perecederos con caducidad ≤ 7 días generan alertas de vencimiento antes de asignar y son despachados primero (FEFO).

### 3.5 Limitaciones de las respuestas

Las cifras dependen del modelo de simulación (sección 2.1); la metodología y el sistema son los entregables, no las cifras. Con datos reales bastaría reemplazar los CSV conservando el esquema.

## 4. Diseño por fases

```
donaciones/
  models.py      entidades inmutables + validación           (Fase 1)
  io_data.py     lectura CSV/JSON, validación, serialización  (Fase 1)
  system.py      registro, búsqueda, asignación, informes     (Fases 2 y 3)
  estructuras/   heap.py (Min-Max), avl.py, graph.py          (Fase 3)
  forms.py       validación del formulario                    (Fases 2 y 4)
  analysis.py    respuestas a las preguntas del reto
  gui.py         panel de control Tkinter                     (Fase 4)
```

El dominio (`models`) no depende de E/S ni de la interfaz; la GUI solo llama a `DonationSystem` y a `forms`, de modo que la lógica es comprobable sin ventana.

**Operaciones (Fase 2).** `register_donation` (valida y clasifica por centro/categoría), `search` (multinivel: elige el índice más selectivo —rango de caducidad, centro+categoría, donante o categoría— y filtra el resto), `allocate` (triaje), `stock_balance`, `dispatch_summary`, `alerts` (desabastecimiento, vencimiento, aislamiento, capacidad del centro) y `route`.

**Asignación.** (1) Se construye una cola de prioridad con una solicitud por (municipio, categoría) con necesidad pendiente; clave `(−urgencia, días a la caducidad más próxima de esa categoría, −severidad, id)`. (2) Se extrae la solicitud más prioritaria. (3) Dijkstra desde el municipio da el tiempo a cada centro; se recorren centros de menor a mayor tiempo. (4) En cada centro se toman lotes en orden **FEFO** (primero en caducar, primero en salir) desde el AVL de (centro, categoría), omitiendo lotes en cadena de frío si el tiempo supera 12 h. (5) Se registran `Allocation` con ruta y ETA; un lote agotado pasa a `ASIGNADO` y sale de los índices. Los municipios sin ruta quedan como «AISLADO». Como las categorías no compiten entre sí por stock, la prioridad entre municipios de una misma categoría (urgencia, luego severidad) determina quién recibe si hay escasez.

**Concurrencia.** Todas las operaciones públicas se ejecutan bajo un `RLock`; la GUI lanza asignación y análisis en hilos y recibe resultados por cola (`after`), sin congelar la ventana.

## 5. Estructuras de datos y complejidad (Fase 3)

Sea *n* el número de lotes, *m* el de municipios, *h* el de centros, *V*/*E* nodos/aristas del grafo, *k* el tamaño de una respuesta.

| Estructura | Uso | Operación | Complejidad |
|---|---|---|---|
| Hash map (`dict`) | Donantes, lotes por id, centros, municipios, `(centro, categoría)→AVL`, `(municipio, categoría)→recibido`, índices por categoría/donante | acceso/inserción | O(1) amortizado, espacio O(n) |
| Min-Max heap | Cola de triaje; también la cola de Dijkstra/A* | push / pop_min / pop_max | O(log n); peek O(1) |
| AVL | FEFO por (centro, categoría); lotes por caducidad; aportes por monto | insertar / borrar / buscar | O(log n) |
| AVL | Consulta de rango (caducidad en [a,b]; monto en [x,y]) | rango | O(log n + k) |
| Grafo (listas de adyacencia) | Red vial: nodos = centros + municipios; peso = horas; tramos cerrados excluidos | Dijkstra con heap | O((V+E) log V), espacio O(V+E) |
| Grafo | A* con heurística admisible | peor caso igual que Dijkstra | en la práctica expande muchos menos nodos (BENCHMARKS §5) |

### 5.1 Justificaciones y demostraciones breves

**Hash map — O(1).** Con función de hash uniforme y factor de carga acotado por redimensionamiento geométrico, la longitud esperada de cada cadena/secuencia de sondeo es O(1); el costo de los redimensionamientos se amortiza: duplicar la tabla cuesta O(n) cada n inserciones ⇒ O(1) amortizado por inserción. Se usa `dict` de Python (tabla hash con direccionamiento abierto). Las llaves compuestas `(centro, categoría)` son tuplas inmutables y hashables.

**Min-Max heap — O(log n).** Es un árbol binario completo en arreglo de altura ⌊log₂ n⌋; los niveles pares cumplen la propiedad de mínimo respecto de sus descendientes y los impares la de máximo. `push` agrega al final y sube a lo sumo ⌊log₂ n⌋/2 pasos de abuelo más un intercambio con el padre; `pop_min`/`pop_max` reemplazan la raíz (o el mayor de los dos hijos de la raíz) por el último elemento y la «hunden» comparando hijos y nietos (≤ 6 comparaciones por nivel de dos pasos), O(log n). Se eligió sobre un heap binario simple porque el triaje necesita **ambos extremos** (extraer la solicitud más urgente y poder descartar/inspeccionar la de menor prioridad) con una sola estructura; ordenar toda la lista cada vez costaría O(n log n) por extracción. El desempate por contador de inserción hace el orden estable y evita comparar objetos arbitrarios.

**AVL — O(log n).** Cada nodo mantiene |altura(izq) − altura(der)| ≤ 1. Sea N(h) el mínimo de nodos de un AVL de altura h: N(h) = 1 + N(h−1) + N(h−2) ≥ φ^h (φ ≈ 1,618, como Fibonacci) ⇒ h ≤ 1,44·log₂(n+2). Inserción y borrado recorren un camino raíz-hoja y reequilibran con a lo sumo una rotación simple o doble en inserción y O(log n) en borrado ⇒ O(log n). La consulta de rango visita los O(log n) nodos del camino a los extremos más los *k* nodos del resultado ⇒ O(log n + k). La prueba `test_height_is_logarithmic_for_sorted_inserts` verifica la cota con inserciones ordenadas (el peor caso de un BST sin balanceo, que daría altura n). Se eligió AVL (y no rojo-negro) por su balanceo más estricto: el inventario tiene muchas más lecturas/rangos que escrituras.

**Dijkstra — O((V+E) log V).** Cada nodo se fija una vez (V extracciones de O(log V)); cada arista relaja a lo sumo una vez por extremo (E inserciones de O(log V)) con la técnica de «entradas obsoletas» (se descartan al extraer). Correcto por pesos ≥ 0 (el constructor rechaza pesos negativos). **A\*** es óptimo si la heurística h(u) = distancia geodésica / 80 km/h es **admisible** (nunca sobrestima): toda carretera es más larga que la línea recta (km = 1,3·geodésica + 0,5) y ninguna velocidad supera 80 km/h; además es consistente (desigualdad triangular), por lo que cada nodo se expande una sola vez. La prueba `test_astar_matches_dijkstra_on_real_network` lo comprueba para todos los municipios.

**Costo de `allocate`.** Construir la cola: O(m·6·log(m·6)). Por solicitud: Dijkstra O((V+E) log V) (cacheado por municipio, ≤ m ejecuciones en total), ordenar centros O(h log h), recorrer el AVL de cada centro leyendo solo los lotes necesarios (cada lote consumido cuesta O(log n) en retirarse/reinsertarse). Total ≈ O(m·(V+E) log V + L log n) donde L es el número de lotes tocados — sin ningún O(n²).

### 5.2 Benchmarks frente a alternativas ingenuas

Ver [BENCHMARKS.md](BENCHMARKS.md). Resumen (medido en este equipo):

- **Hash vs búsqueda lineal por id:** 336× (n=1.000) a ~4.000× (n=50.000) más rápido.
- **AVL vs recorrido lineal en consultas de rango:** 11×–16×.
- **Cola de triaje:** frente a «lista + `min()`» el heap es 14× más rápido con n=8.000. Frente a lista ordenada con `bisect.insort`, esta gana con n pequeño (opera en C con `memmove`) pero se degrada de forma cuadrática: a n=512.000 el heap es 8,6× más rápido. Se reporta tal cual: la ventaja asintótica aparece con volúmenes grandes; con los volúmenes del caso (cientos de solicitudes) ambas son suficientes y el heap se justifica por su comportamiento garantizado y por el acceso a ambos extremos.
- **Dijkstra con heap vs arreglo O(V²):** 8,5× con V=5.000.
- **A\* vs Dijkstra punto a punto:** ≈3× menos tiempo y ≈3× menos nodos expandidos.

## 6. Plan de pruebas y resultados

`python -m unittest discover -s tests -t . -v` → **65 pruebas, todas pasan** (≈4 s).

| Fase | Archivo | Qué valida |
|---|---|---|
| 1 | `test_models_io.py` | Inmutabilidad; cantidades negativas; `disponible ≤ cantidad`; parsing de valores nulos/vacíos/no numéricos/fechas mal formadas/enums inválidos; CSV con campos faltantes o sobrantes, duplicados, donante inexistente, caducidad anterior al evento; JSON mal formado o con elementos no objeto; archivo inexistente/vacío; ida y vuelta CSV y JSON; error de escritura |
| 2 | `test_system.py` | Una donación asignada **no queda disponible**; **conservación del inventario** (`recibido = disponible + despachado + vencido`) tras asignaciones y tras 2.000 registros secuenciales y registros/asignaciones en **hilos concurrentes**; nunca se entrega más de lo necesitado; aislados sin despacho; prioridad por urgencia bajo escasez; FEFO; límite de cadena de frío; vencimiento; cierre de vías; alertas; validación del formulario |
| 3 | `test_structures.py`, `test_performance.py` | Heap contra `sorted` (aleatorio y mezcla pop_min/pop_max); estabilidad; AVL aleatorio con balance, rango y altura logarítmica; Dijkstra/A*, inalcanzables, pesos negativos; heap vs lista, AVL vs recorrido y AVL con inserciones ordenadas |
| 4 | `test_gui.py` | Panel poblado; asignación asíncrona que actualiza tablas; errores visuales del formulario; registro válido; filtro inválido; ruta inalcanzable; eventos concurrentes (asignación + análisis + búsqueda) |
| — | `test_analysis.py` | Totales y rankings coherentes con los datos |

Casos de borde cubiertos: cola/AVL vacíos, claves duplicadas, origen = destino, nodos desconocidos, cantidades 0 y negativas, fechas inválidas, JSON no lista, fila con columnas de más o de menos.

## 7. Interfaz gráfica (Fase 4)

`python main.py` abre un panel con seis pestañas diferenciadas, pensadas para reducir carga cognitiva (lo crítico arriba, color solo con significado):

1. **Panel:** indicadores clave (heridos, fallecidos, desplazados, municipios aislados, lotes, asignaciones), alertas ordenadas con críticas primero (rojo/naranja) y balance de stock por categoría.
2. **Inventario:** tabla filtrable por categoría, centro, vencimiento ≤ N días e id de lote (usa los índices AVL/hash).
3. **Nueva donación:** formulario validado; cada error aparece en rojo junto al campo, y los datos fuera de rango se rechazan antes de llegar al sistema.
4. **Despacho:** vista previa de la cola de prioridad, ejecución de la asignación en un **hilo** con barra de progreso, tabla de asignaciones (origen, ETA, ruta) y tabla de solicitudes sin cubrir con el motivo.
5. **Rutas:** mapa dibujado sobre un `Canvas` (municipios coloreados por urgencia, vías abiertas/restringidas/cerradas, ruta resaltada) con Dijkstra o A*.
6. **Análisis:** genera las respuestas de la sección 3 en un hilo.

## 8. Limitaciones y trabajo futuro

- Las cantidades se asignan sin capacidad de vehículos ni consolidación de cargas (el peso y el volumen se registran por asignación, pero no limitan el viaje).
- Un solo origen por asignación parcial; no se optimiza el reparto conjunto (sería un problema de flujo de costo mínimo).
- Los fondos se tratan como una categoría con monto en COP; no se modelan compras reales.
- La red vial es sintética y estática salvo `set_road_status`; no hay actualización en tiempo real desde fuentes externas.
- La GUI usa Tkinter por portabilidad (cero dependencias); un panel web permitiría uso multiusuario.
