"""Grafo no dirigido ponderado con Dijkstra y A*."""
from __future__ import annotations

import math
from typing import Callable, Hashable, Iterable

from .heap import MinMaxHeap

Node = Hashable


class Graph:
    def __init__(self) -> None:
        self.adj: dict[Node, dict[Node, float]] = {}

    def add_node(self, u: Node) -> None:
        self.adj.setdefault(u, {})

    def add_edge(self, u: Node, v: Node, w: float) -> None:
        if w < 0:
            raise ValueError("peso negativo no permitido")
        self.add_node(u)
        self.add_node(v)
        self.adj[u][v] = w
        self.adj[v][u] = w

    def remove_edge(self, u: Node, v: Node) -> None:
        self.adj.get(u, {}).pop(v, None)
        self.adj.get(v, {}).pop(u, None)

    def __contains__(self, u: Node) -> bool:
        return u in self.adj

    def nodes(self) -> Iterable[Node]:
        return self.adj.keys()

    def edge_count(self) -> int:
        return sum(len(n) for n in self.adj.values()) // 2

    def dijkstra(self, source: Node, target: Node | None = None):
        """Costos mínimos desde `source` (se detiene en `target` si se da). O((V+E) log V)."""
        dist = {source: 0.0}
        prev: dict[Node, Node] = {}
        done: set[Node] = set()
        heap: MinMaxHeap = MinMaxHeap()
        heap.push(0.0, source)
        while heap:
            d, u = heap.pop_min()
            if u in done:
                continue
            done.add(u)
            if u == target:
                break
            for v, w in self.adj[u].items():
                nd = d + w
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    prev[v] = u
                    heap.push(nd, v)
        return dist, prev

    @staticmethod
    def path_from(prev: dict, source: Node, target: Node) -> list[Node]:
        if target != source and target not in prev:
            return []
        path = [target]
        while path[-1] != source:
            path.append(prev[path[-1]])
        path.reverse()
        return path

    def shortest_path(self, source: Node, target: Node):
        if source not in self.adj or target not in self.adj:
            return math.inf, []
        dist, prev = self.dijkstra(source, target)
        if target not in dist:
            return math.inf, []
        return dist[target], self.path_from(prev, source, target)

    def astar(self, source: Node, target: Node, heuristic: Callable[[Node, Node], float]):
        """A*: óptimo si `heuristic` es admisible (nunca sobrestima el costo restante)."""
        if source not in self.adj or target not in self.adj:
            return math.inf, [], 0
        g = {source: 0.0}
        prev: dict[Node, Node] = {}
        closed: set[Node] = set()
        heap: MinMaxHeap = MinMaxHeap()
        heap.push(heuristic(source, target), source)
        expanded = 0
        while heap:
            _, u = heap.pop_min()
            if u in closed:
                continue
            closed.add(u)
            expanded += 1
            if u == target:
                return g[u], self.path_from(prev, source, target), expanded
            for v, w in self.adj[u].items():
                ng = g[u] + w
                if ng < g.get(v, math.inf):
                    g[v] = ng
                    prev[v] = u
                    heap.push(ng + heuristic(v, target), v)
        return math.inf, [], expanded

    def reachable_from(self, sources: Iterable[Node]) -> set[Node]:
        seen = {s for s in sources if s in self.adj}
        stack = list(seen)
        while stack:
            u = stack.pop()
            for v in self.adj[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        return seen
