"""Benchmarks: estructuras seleccionadas vs alternativas ingenuas. Escribe docs/BENCHMARKS.md.

Uso:  python benchmarks/run_benchmarks.py
"""
import bisect
import math
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from donaciones.estructuras import AVLTree, Graph, MinMaxHeap  # noqa: E402

rng = random.Random(7)


def timed(fn):
    t = time.perf_counter()
    fn()
    return (time.perf_counter() - t) * 1000


def triage_large(n):
    keys = [(rng.randint(1, 5), rng.random()) for _ in range(n)]

    def heap():
        h = MinMaxHeap()
        for k in keys:
            h.push(k, None)
        while h:
            h.pop_min()

    def sorted_insert():
        a = []
        for k in keys:
            bisect.insort(a, k)
        while a:
            a.pop(0)

    return timed(heap), timed(sorted_insert)


def triage(n):
    keys = [(rng.randint(1, 5), rng.random()) for _ in range(n)]

    def heap():
        h = MinMaxHeap()
        for k in keys:
            h.push(k, None)
        while h:
            h.pop_min()

    def linear_list():  # cola como lista sin ordenar: extraer = min() + remove(): O(n) cada una
        a = list(keys)
        while a:
            a.remove(min(a))

    def sorted_insert():  # lista ordenada con bisect.insort: insertar O(n)
        a = []
        for k in keys:
            bisect.insort(a, k)
        while a:
            a.pop(0)

    return timed(heap), timed(linear_list), timed(sorted_insert)


def range_queries(n, q=300):
    base = date(2026, 3, 1)
    lots = [(base + timedelta(days=rng.randint(0, 2000)), i) for i in range(n)]
    tree = AVLTree()
    for d, i in lots:
        tree.insert((d.toordinal(), i), i)
    windows = [(base + timedelta(days=rng.randint(0, 1990))) for _ in range(q)]

    def avl():
        for w in windows:
            list(tree.range((w.toordinal(), -1), ((w + timedelta(days=7)).toordinal(), n)))

    def scan():
        for w in windows:
            hi = w + timedelta(days=7)
            [x for x in lots if w <= x[0] <= hi]

    return timed(avl), timed(scan)


def lookups(n, q=2000):
    ids = [f"L-{i:07d}" for i in range(n)]
    d = {k: i for i, k in enumerate(ids)}
    pairs = list(zip(ids, range(n)))
    targets = [rng.choice(ids) for _ in range(q)]

    def hashmap():
        for t in targets:
            d[t]

    def scan():
        for t in targets:
            next(v for k, v in pairs if k == t)

    return timed(hashmap), timed(scan)


def random_graph(v):
    g = Graph()
    for i in range(1, v):
        g.add_edge(i, rng.randrange(i), rng.uniform(1, 10))
    for _ in range(v * 2):
        a, b = rng.randrange(v), rng.randrange(v)
        if a != b:
            g.add_edge(a, b, rng.uniform(1, 10))
    return g


def dijkstra_array(g, src):  # O(V^2): extracción lineal del mínimo
    dist = {u: math.inf for u in g.nodes()}
    dist[src] = 0.0
    todo = set(dist)
    while todo:
        u = min(todo, key=dist.__getitem__)
        todo.remove(u)
        if dist[u] == math.inf:
            break
        for v, w in g.adj[u].items():
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w


def shortest(v):
    g = random_graph(v)
    return timed(lambda: g.dijkstra(0)), timed(lambda: dijkstra_array(g, 0))


def astar_geometric(n=2500):
    pts = [(rng.random(), rng.random()) for _ in range(n)]
    g = Graph()
    for i, p in enumerate(pts):
        near = sorted(range(n), key=lambda j: (pts[j][0] - p[0]) ** 2 + (pts[j][1] - p[1]) ** 2)[1:5]
        for j in near:
            g.add_edge(i, j, math.dist(p, pts[j]) * rng.uniform(1.0, 1.3))
    h = lambda a, b: math.dist(pts[a], pts[b])
    pairs = [(rng.randrange(n), rng.randrange(n)) for _ in range(30)]
    td = timed(lambda: [g.dijkstra(s, t) for s, t in pairs])
    ta = timed(lambda: [g.astar(s, t, h) for s, t in pairs])
    exp = sum(g.astar(s, t, h)[2] for s, t in pairs) / len(pairs)
    dj = 0
    for s_, t_ in pairs:
        d, _ = g.dijkstra(s_, t_)
        dj += len(d)
    return td, ta, exp, dj / len(pairs)


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main():
    L = ["# Benchmarks (ms, menor es mejor)\n",
         f"Python {sys.version.split()[0]} · semilla fija · una medición por celda (orden de magnitud, no estadística fina).\n",
         "## 1. Cola de triaje: n inserciones + n extracciones del mínimo\n"]
    rows = []
    for n in (500, 2000, 8000):
        h, l, s = triage(n)
        rows.append([f"{n:,}", f"{h:.1f}", f"{l:.1f}", f"{s:.1f}", f"{l / h:.0f}x"])
    L.append(table(["n", "Min-Max heap", "Lista + min()", "Lista ordenada (insort)", "Lista/heap"], rows))
    rows = []
    for n in (32000, 128000, 512000):
        h, i = triage_large(n)
        rows.append([f"{n:,}", f"{h:.0f}", f"{i:.0f}", f"{i / h:.1f}x"])
    L.append("\nNota: en CPython `bisect.insort` + `pop(0)` usa memmove en C, por lo que gana con n pequeño pese a ser O(n) por operación. "
             "Con n grande el costo cuadrático domina:\n")
    L.append(table(["n", "Min-Max heap", "Lista ordenada (insort)", "insort/heap"], rows))
    L.append("\n## 2. Consulta de rango por caducidad (300 ventanas de 7 días)\n")
    rows = []
    for n in (2000, 20000, 100000):
        a, s = range_queries(n)
        rows.append([f"{n:,}", f"{a:.1f}", f"{s:.1f}", f"{s / a:.0f}x"])
    L.append(table(["n lotes", "AVL", "Recorrido lineal", "Lineal/AVL"], rows))
    L.append("\n## 3. Búsqueda por identificador (2.000 consultas)\n")
    rows = []
    for n in (1000, 10000, 50000):
        d, s = lookups(n)
        rows.append([f"{n:,}", f"{d:.2f}", f"{s:.1f}", f"{s / max(d, 0.001):.0f}x"])
    L.append(table(["n lotes", "Hash map", "Búsqueda lineal", "Lineal/hash"], rows))
    L.append("\n## 4. Camino mínimo desde un origen (grafo disperso, E ≈ 3V)\n")
    rows = []
    for v in (500, 2000, 5000):
        a, b = shortest(v)
        rows.append([f"{v:,}", f"{a:.1f}", f"{b:.1f}", f"{b / a:.1f}x"])
    L.append(table(["V", "Dijkstra con heap", "Dijkstra con arreglo O(V²)", "Arreglo/heap"], rows))
    td, ta, exp, dj = astar_geometric()
    L.append("\n## 5. A* vs Dijkstra punto a punto (grafo geométrico de 2.500 nodos, 30 consultas, heurística euclidiana)\n")
    L.append(f"Dijkstra: {td:.0f} ms · A*: {ta:.0f} ms · nodos alcanzados por consulta (aprox.): Dijkstra {dj:,.0f} "
             f"vs A* expandidos {exp:,.0f}.\n")
    out = ROOT / "docs" / "BENCHMARKS.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
