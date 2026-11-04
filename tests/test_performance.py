"""Pruebas de rendimiento contrastadas: estructura elegida vs alternativa ingenua (márgenes holgados)."""
import random
import time
import unittest

from donaciones.estructuras import AVLTree, MinMaxHeap


def elapsed(fn):
    t = time.perf_counter()
    fn()
    return time.perf_counter() - t


class PerformanceTests(unittest.TestCase):
    def test_heap_beats_linear_list_for_triage(self):
        rng = random.Random(1)
        keys = [(rng.randint(1, 5), rng.random()) for _ in range(6000)]

        def heap():
            h = MinMaxHeap()
            for k in keys:
                h.push(k, None)
            while h:
                h.pop_min()

        def naive():
            a = list(keys)
            while a:
                a.remove(min(a))

        self.assertLess(elapsed(heap) * 3, elapsed(naive))

    def test_avl_range_beats_scan(self):
        n = 40000
        tree = AVLTree()
        for i in range(n):
            tree.insert((i, i), i)
        data = list(range(n))
        windows = list(range(0, n - 20, 200))

        def avl():
            for w in windows:
                list(tree.range((w, -1), (w + 10, n)))

        def scan():
            for w in windows:
                [x for x in data if w <= x <= w + 10]

        self.assertLess(elapsed(avl) * 5, elapsed(scan))

    def test_sorted_inserts_do_not_degrade_avl(self):
        t = AVLTree()
        start = time.perf_counter()
        for i in range(20000):
            t.insert(i)
        self.assertLess(time.perf_counter() - start, 2.0)  # un BST sin balanceo haría O(n^2)
        self.assertLessEqual(t.height, 22)


if __name__ == "__main__":
    unittest.main()
