# Benchmarks (ms, menor es mejor)

Python 3.15.0 · semilla fija · una medición por celda (orden de magnitud, no estadística fina).

## 1. Cola de triaje: n inserciones + n extracciones del mínimo

| n | Min-Max heap | Lista + min() | Lista ordenada (insort) | Lista/heap |
|---|---|---|---|---|
| 500 | 4.5 | 5.9 | 0.7 | 1x |
| 2,000 | 24.7 | 60.4 | 1.0 | 2x |
| 8,000 | 66.6 | 943.8 | 9.6 | 14x |

Nota: en CPython `bisect.insort` + `pop(0)` usa memmove en C, por lo que gana con n pequeño pese a ser O(n) por operación. Con n grande el costo cuadrático domina:

| n | Min-Max heap | Lista ordenada (insort) | insort/heap |
|---|---|---|---|
| 32,000 | 366 | 176 | 0.5x |
| 128,000 | 2132 | 2545 | 1.2x |
| 512,000 | 12753 | 110260 | 8.6x |

## 2. Consulta de rango por caducidad (300 ventanas de 7 días)

| n lotes | AVL | Recorrido lineal | Lineal/AVL |
|---|---|---|---|
| 2,000 | 3.7 | 42.1 | 11x |
| 20,000 | 17.5 | 273.5 | 16x |
| 100,000 | 150.3 | 1870.3 | 12x |

## 3. Búsqueda por identificador (2.000 consultas)

| n lotes | Hash map | Búsqueda lineal | Lineal/hash |
|---|---|---|---|
| 1,000 | 0.12 | 39.3 | 336x |
| 10,000 | 0.12 | 331.6 | 2674x |
| 50,000 | 0.40 | 1597.1 | 3971x |

## 4. Camino mínimo desde un origen (grafo disperso, E ≈ 3V)

| V | Dijkstra con heap | Dijkstra con arreglo O(V²) | Arreglo/heap |
|---|---|---|---|
| 500 | 7.1 | 8.8 | 1.2x |
| 2,000 | 33.0 | 95.7 | 2.9x |
| 5,000 | 69.8 | 594.8 | 8.5x |

## 5. A* vs Dijkstra punto a punto (grafo geométrico de 2.500 nodos, 30 consultas, heurística euclidiana)

Dijkstra: 248 ms · A*: 80 ms · nodos alcanzados por consulta (aprox.): Dijkstra 1,268 vs A* expandidos 399.
