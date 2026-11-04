"""Montículo Min-Max (Atkinson et al., 1986) sobre arreglo dinámico.

Niveles pares guardan mínimos locales y niveles impares máximos locales:
  - peek_min / peek_max: O(1)
  - push, pop_min, pop_max: O(log n)
Cada entrada es (clave, secuencia, item); la secuencia desempata de forma estable
y evita comparar items arbitrarios.
"""
from __future__ import annotations

from itertools import count
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class MinMaxHeap(Generic[T]):
    __slots__ = ("_a", "_seq")

    def __init__(self) -> None:
        self._a: list[tuple[Any, int, T]] = []
        self._seq = count()

    def __len__(self) -> int:
        return len(self._a)

    def __bool__(self) -> bool:
        return bool(self._a)

    @staticmethod
    def _is_min_level(i: int) -> bool:
        return (i + 1).bit_length() % 2 == 1

    def push(self, key: Any, item: T) -> None:
        self._a.append((key, next(self._seq), item))
        self._bubble_up(len(self._a) - 1)

    def peek_min(self) -> tuple[Any, T]:
        k, _, v = self._a[0]
        return k, v

    def peek_max(self) -> tuple[Any, T]:
        k, _, v = self._a[self._max_index()]
        return k, v

    def pop_min(self) -> tuple[Any, T]:
        k, _, v = self._remove_at(0)
        return k, v

    def pop_max(self) -> tuple[Any, T]:
        k, _, v = self._remove_at(self._max_index())
        return k, v

    def _max_index(self) -> int:
        a = self._a
        if not a:
            raise IndexError("montículo vacío")
        if len(a) == 1:
            return 0
        if len(a) == 2:
            return 1
        return 1 if a[1] > a[2] else 2

    def _remove_at(self, i: int) -> tuple[Any, int, T]:
        a = self._a
        if not a:
            raise IndexError("montículo vacío")
        item = a[i]
        last = a.pop()
        if i < len(a):
            a[i] = last
            self._trickle_down(i)
        return item

    def _bubble_up(self, i: int) -> None:
        a = self._a
        if i == 0:
            return
        p = (i - 1) // 2
        if self._is_min_level(i):
            if a[i] > a[p]:
                a[i], a[p] = a[p], a[i]
                self._bubble_up_max(p)
            else:
                self._bubble_up_min(i)
        else:
            if a[i] < a[p]:
                a[i], a[p] = a[p], a[i]
                self._bubble_up_min(p)
            else:
                self._bubble_up_max(i)

    def _bubble_up_min(self, i: int) -> None:
        a = self._a
        while i >= 3:
            gp = ((i - 1) // 2 - 1) // 2
            if a[i] < a[gp]:
                a[i], a[gp] = a[gp], a[i]
                i = gp
            else:
                break

    def _bubble_up_max(self, i: int) -> None:
        a = self._a
        while i >= 3:
            gp = ((i - 1) // 2 - 1) // 2
            if a[i] > a[gp]:
                a[i], a[gp] = a[gp], a[i]
                i = gp
            else:
                break

    def _trickle_down(self, i: int) -> None:
        if self._is_min_level(i):
            self._trickle(i, minimum=True)
        else:
            self._trickle(i, minimum=False)

    def _trickle(self, i: int, minimum: bool) -> None:
        a = self._a
        n = len(a)
        better = (lambda x, y: x < y) if minimum else (lambda x, y: x > y)
        while True:
            cands = [c for c in (2 * i + 1, 2 * i + 2) if c < n]
            cands += [g for g in range(4 * i + 3, 4 * i + 7) if g < n]
            if not cands:
                return
            m = cands[0]
            for c in cands[1:]:
                if better(a[c], a[m]):
                    m = c
            if m > 2 * i + 2:  # nieto
                if not better(a[m], a[i]):
                    return
                a[m], a[i] = a[i], a[m]
                p = (m - 1) // 2
                if better(a[p], a[m]):
                    a[m], a[p] = a[p], a[m]
                i = m
            else:  # hijo
                if better(a[m], a[i]):
                    a[m], a[i] = a[i], a[m]
                return
