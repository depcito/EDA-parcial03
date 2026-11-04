# Sistema de donaciones post-sismo (Colombia)

Evaluación Práctica 3 — Estructuras de Datos y Algoritmos (EAFIT). Gestión de donaciones, triaje por urgencia municipal y rutas de despacho, con datos **sintéticos**.

Requisitos: Python 3.10+ (solo biblioteca estándar; Tkinter para la GUI).

```bash
python main.py                                    # panel gráfico
python main.py --cli                              # respuestas a las preguntas del reto en consola
python -m unittest discover -s tests -t . -v      # 65 pruebas
python benchmarks/run_benchmarks.py               # regenera docs/BENCHMARKS.md
python -m donaciones.analysis --out docs/RESULTADOS.md
python scripts/generar_datos.py                   # regenera data/ (determinista)
```

## Contenido

| Ruta | Descripción |
|---|---|
| `docs/INFORME.md` | Informe: **fuente de datos**, **preguntas y respuestas** (¿cuánta gente hay herida?, ¿qué zonas están más afectadas?…), diseño, complejidad, pruebas |
| `docs/ANEXO_IA.md` | Anexo de transparencia sobre el uso de IA (completar con prompts propios) |
| `docs/RESULTADOS.md` | Salida completa del análisis |
| `docs/BENCHMARKS.md` | Estructuras elegidas vs alternativas ingenuas |
| `donaciones/` | Código: modelos, E/S, sistema, estructuras (`heap`, `avl`, `graph`), formulario, análisis, GUI |
| `data/` | CSV/JSON sintéticos |
| `tests/` | Pruebas unitarias, de borde, concurrencia, rendimiento y GUI |

## Estructuras de datos

Hash maps (`dict`) para acceso O(1) · Min-Max heap propio para la cola de triaje · AVL propio para FEFO y consultas de rango por caducidad/monto · grafo con Dijkstra y A* para las rutas.

## Aviso sobre los datos

Municipios con población y coordenadas **aproximadas**; el sismo, las víctimas, necesidades, donantes y donaciones son **ficticios**. No usar para decisiones reales.
