import math
import random
import unittest

from donaciones.estructuras import AVLTree, Graph, MinMaxHeap


class HeapTests(unittest.TestCase):
    def test_empty_raises(self):
        h = MinMaxHeap()
        for f in (h.pop_min, h.pop_max, h.peek_min, h.peek_max):
            with self.assertRaises(IndexError):
                f()

    def test_matches_sorted_for_random_input(self):
        rng = random.Random(1)
        for n in (1, 2, 3, 7, 50, 500):
            keys = [rng.randint(0, 100) for _ in range(n)]
            h = MinMaxHeap()
            for k in keys:
                h.push(k, k)
            self.assertEqual(h.peek_min()[0], min(keys))
            self.assertEqual(h.peek_max()[0], max(keys))
            out = [h.pop_min()[0] for _ in range(n)]
            self.assertEqual(out, sorted(keys))

    def test_mixed_pop_min_max_stays_consistent(self):
        rng = random.Random(2)
        ref, h = [], MinMaxHeap()
        for _ in range(3000):
            op = rng.random()
            if op < 0.5 or not ref:
                k = rng.randint(0, 1000)
                h.push(k, None)
                ref.append(k)
            elif op < 0.75:
                self.assertEqual(h.pop_min()[0], min(ref))
                ref.remove(min(ref))
            else:
                self.assertEqual(h.pop_max()[0], max(ref))
                ref.remove(max(ref))
            self.assertEqual(len(h), len(ref))

    def test_ties_are_stable_and_items_never_compared(self):
        h = MinMaxHeap()
        for name in ("a", "b", "c", object()):
            h.push(1, name)
        self.assertEqual([h.pop_min()[1] for _ in range(3)], ["a", "b", "c"])

    def test_tuple_keys_priority(self):
        h = MinMaxHeap()
        h.push((-3, 10), "urgente")
        h.push((-5, 99), "mas urgente")
        h.push((-3, 2), "urgente, caduca antes")
        self.assertEqual([h.pop_min()[1] for _ in range(3)], ["mas urgente", "urgente, caduca antes", "urgente"])


class AVLTests(unittest.TestCase):
    def test_insert_remove_keep_balance(self):
        rng = random.Random(3)
        t, ref = AVLTree(), set()
        for _ in range(2000):
            k = rng.randint(0, 400)
            if rng.random() < 0.6:
                t.insert(k, k)
                ref.add(k)
            else:
                self.assertEqual(t.remove(k), k in ref)
                ref.discard(k)
            self.assertEqual(len(t), len(ref))
        self.assertTrue(t.is_balanced())
        self.assertEqual([k for k, _ in t.items()], sorted(ref))

    def test_height_is_logarithmic_for_sorted_inserts(self):
        t = AVLTree()
        n = 4096
        for i in range(n):
            t.insert(i)
        self.assertLessEqual(t.height, 1.45 * math.log2(n + 2))

    def test_range_query_inclusive(self):
        t = AVLTree()
        for i in range(0, 100, 5):
            t.insert(i, str(i))
        self.assertEqual([k for k, _ in t.range(10, 30)], [10, 15, 20, 25, 30])
        self.assertEqual([k for k, _ in t.range(None, 10)], [0, 5, 10])
        self.assertEqual(list(t.range(101, 200)), [])
        self.assertEqual(t.min_item()[0], 0)
        self.assertEqual(t.max_item()[0], 95)

    def test_duplicate_key_replaces_value_and_empty_errors(self):
        t = AVLTree()
        t.insert(1, "a")
        t.insert(1, "b")
        self.assertEqual((len(t), t.get(1)), (1, "b"))
        t.remove(1)
        with self.assertRaises(KeyError):
            t.min_item()
        self.assertFalse(t.remove(99))


class GraphTests(unittest.TestCase):
    def build(self):
        g = Graph()
        for u, v, w in [("A", "B", 4), ("A", "C", 1), ("C", "B", 2), ("B", "D", 5), ("C", "D", 8)]:
            g.add_edge(u, v, w)
        g.add_node("Z")
        return g

    def test_shortest_path(self):
        cost, path = self.build().shortest_path("A", "D")
        self.assertEqual((cost, path), (8, ["A", "C", "B", "D"]))

    def test_unreachable_and_unknown(self):
        g = self.build()
        self.assertEqual(g.shortest_path("A", "Z"), (math.inf, []))
        self.assertEqual(g.shortest_path("A", "nope"), (math.inf, []))

    def test_same_node(self):
        self.assertEqual(self.build().shortest_path("A", "A"), (0.0, ["A"]))

    def test_negative_weight_rejected(self):
        with self.assertRaises(ValueError):
            Graph().add_edge("a", "b", -1)

    def test_astar_equals_dijkstra_on_random_geometric_graph(self):
        rng = random.Random(4)
        pts = {i: (rng.random() * 100, rng.random() * 100) for i in range(120)}
        g = Graph()
        for i in pts:
            near = sorted(pts, key=lambda j: math.dist(pts[i], pts[j]))[1:5]
            for j in near:
                g.add_edge(i, j, math.dist(pts[i], pts[j]) * rng.uniform(1.0, 1.5))
        h = lambda u, v: math.dist(pts[u], pts[v])
        for _ in range(40):
            s, t = rng.sample(list(pts), 2)
            c1, p1 = g.shortest_path(s, t)
            c2, p2, _ = g.astar(s, t, h)
            self.assertAlmostEqual(c1, c2)

    def test_reachable(self):
        self.assertNotIn("Z", self.build().reachable_from(["A"]))


if __name__ == "__main__":
    unittest.main()
