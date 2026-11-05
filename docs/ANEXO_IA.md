# Anexo de transparencia técnica — uso de Inteligencia Artificial

## Link del repositorio
https://github.com/depcito/EDA-parcial03/tree/main

## 1. Herramienta

Asistente de código generativo (Claude, a través de Claude Code) para generar el esqueleto del proyecto, la implementación de las estructuras de datos, los datos sintéticos, las pruebas y el borrador de este informe a partir del enunciado de la evaluación.

## 2. Prompts relevantes

 Requerimientos principales:
 
Fuente de datos: identifica y utiliza la fuente de datos indicada en el enunciado. Explica brevemente su procedencia, contenido y relevancia para el análisis. No utilices fuentes de datos alternativas sin justificación ni inventes información que no esté respaldada por los datos disponibles.

Análisis de la información: realiza el procesamiento y análisis necesario para responder las preguntas planteadas en el parcial. Entre los aspectos que se deben contemplar se encuentran:

- ¿Cuántas personas se encuentran heridas?

- ¿Cuáles son las zonas geográficas más afectadas?

- ¿Cómo se distribuyen los afectados según la información disponible?

- ¿Qué patrones, tendencias o concentraciones relevantes pueden identificarse en los datos?

Resolución de las preguntas: responde de manera clara, precisa y sustentada cada una de las preguntas del enunciado. No te limites a presentar resultados numéricos; explica qué significan y qué conclusiones pueden extraerse de ellos.

Resultados y visualizaciones: incluye tablas, gráficos o representaciones que faciliten la comprensión de los resultados, siempre que aporten valor al análisis. Cada visualización debe contar con un título y una interpretación.

Conclusiones: presenta conclusiones basadas exclusivamente en los resultados obtenidos, destacando los hallazgos más importantes y su relevancia.

Consideraciones importantes

Omite las fechas específicas mencionadas en el documento adjunto. No las utilices como restricciones temporales ni como parte de los criterios del análisis. Sin embargo, conserva y cumple los demás requerimientos del enunciado.

No omitas ninguna pregunta, actividad o entregable solicitado.

No inventes cifras, resultados, fuentes ni conclusiones.

Si algún dato necesario no está disponible, indícalo explícitamente y explica cómo afecta el análisis.

Mantén coherencia entre la fuente de datos, la metodología utilizada, los resultados y las conclusiones.

Utiliza un lenguaje académico, técnico y claro, apropiado para la presentación de un parcial universitario.» | Arquitectura por fases, datos sintéticos, sistema, GUI, pruebas, informe |


## 3. Decisiones arquitecturales generadas o refinadas por el modelo y su justificación técnica

| Decisión | Alternativa descartada | Justificación |
|---|---|---|
| Python, solo biblioteca estándar (`unittest`, `tkinter`, `csv`, `json`) | Java/C#, frameworks web | Cero dependencias: el profesor ejecuta con un solo comando; Tkinter evita servidores |
| Entidades `@dataclass(frozen=True)` con validación en `__post_init__` | Diccionarios sueltos | Inmutabilidad, tipado estricto y un solo punto de validación; los cambios de estado de un lote (`Lot.take`) devuelven un lote nuevo |
| **Datos sintéticos deterministas** con semilla | Datos reales de la UNGRD/DANE | El enunciado pide sintéticos realistas; reproducibilidad; se documentan supuestos y qué es aproximado |
| `dict` como hash map con llaves compuestas | Implementar tabla hash propia | `dict` ya cumple O(1) amortizado; el aporte está en el diseño de llaves `(centro, categoría)` |
| **Min-Max heap propio** para la cola de triaje | `heapq` (solo mínimo) | Permite extraer la solicitud más urgente y también la de menor prioridad en O(log n) con una estructura |
| **AVL propio** con consulta de rango y claves compuestas `(fecha, id)` | Rojo-negro, `sortedcontainers` | Balanceo estricto para lectura intensiva; claves compuestas garantizan unicidad por lote sin listas por fecha |
| FEFO como política de elección de lote | FIFO | Minimiza pérdidas por vencimiento (objetivo del enunciado) |
| Dijkstra con cache por municipio y A* con heurística geodésica/80 km/h | Floyd-Warshall | O((V+E) log V) por origen basta; A* admisible porque km = 1,3·geodésica + 0,5 y velocidad ≤ 80 |
| Cadena de frío: máx. 12 h de ruta | Ignorarla | Modela la restricción del enunciado («condición de frío») con un parámetro explícito |
| Cierre de vías → municipios «aislados» sin despacho terrestre y alerta crítica | Asignar igual | Evita prometer entregas imposibles; evidencia la necesidad de puente aéreo |
| `RLock` global en `DonationSystem`; GUI con hilos + cola | Un lock por estructura | Simplicidad y consistencia del inventario; las operaciones son cortas |
| Lógica de formulario en `forms.py` fuera de Tkinter | Validar en los widgets | Se puede probar sin ventana |

## 4. Verificación independiente realizada

- Se ejecutó la suite completa (65 pruebas) y los benchmarks; los resultados reportados en el informe provienen de esas ejecuciones.
- Una discrepancia que apareció en los benchmarks se reportó tal cual: `bisect.insort` supera al heap con n pequeño en CPython (memmove en C), y la ventaja del heap aparece con n grande.
- Todas las cifras de las preguntas del reto se calculan en código (`analysis.py`) y no están escritas a mano en los datos.

## 5. preguntas de sustentación (preguntas que el equipo debe saber responder)

1. ¿Por qué el hash map da O(1) amortizado y qué pasa con las colisiones?
2. En el Min-Max heap, ¿en qué nivel están los máximos? ¿Por qué `pop_max` mira solo los índices 1 y 2?
3. ¿Qué rotación corrige un desbalanceo izquierda-derecha en el AVL? ¿Por qué `remove` ajusta `_size` dos veces?
4. ¿Por qué la heurística de A* es admisible y qué pasaría si no lo fuera?
5. ¿Por qué se usan entradas obsoletas en la cola de Dijkstra en vez de «decrease-key»?
6. ¿Qué garantiza que `recibido = disponible + despachado + vencido`?
7. ¿Qué hace FEFO y cómo lo implementa el AVL por (centro, categoría)?
8. ¿Por qué un municipio puede quedar «aislado» y cómo se detecta (`reachable_from`)?
9. ¿Cuándo gana `bisect.insort` al heap y cuándo pierde? ¿Qué muestran los benchmarks?
10. ¿Qué parte de los datos es aproximada y cuál es ficticia?

## 6. Responsabilidad

El equipo es el único responsable del diseño final.
Integrantes: Samuel Hernando Echeverri Castrillon, Emanuel Ossa, Sebastian Augusto Gudiño Pachon, Jerónimo Machado Leal

