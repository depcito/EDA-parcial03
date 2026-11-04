"""Árbol AVL: búsqueda/inserción/borrado O(log n) y consultas de rango O(log n + k)."""
from __future__ import annotations

from typing import Any, Iterator, Optional


class _Node:
    __slots__ = ("key", "value", "left", "right", "height")

    def __init__(self, key: Any, value: Any) -> None:
        self.key = key
        self.value = value
        self.left: Optional[_Node] = None
        self.right: Optional[_Node] = None
        self.height = 1


def _h(n: Optional[_Node]) -> int:
    return n.height if n else 0


def _update(n: _Node) -> None:
    n.height = 1 + max(_h(n.left), _h(n.right))


def _rot_right(y: _Node) -> _Node:
    x = y.left
    y.left = x.right
    x.right = y
    _update(y)
    _update(x)
    return x


def _rot_left(x: _Node) -> _Node:
    y = x.right
    x.right = y.left
    y.left = x
    _update(x)
    _update(y)
    return y


def _rebalance(n: _Node) -> _Node:
    _update(n)
    bal = _h(n.left) - _h(n.right)
    if bal > 1:
        if _h(n.left.left) < _h(n.left.right):
            n.left = _rot_left(n.left)
        return _rot_right(n)
    if bal < -1:
        if _h(n.right.right) < _h(n.right.left):
            n.right = _rot_right(n.right)
        return _rot_left(n)
    return n


class AVLTree:
    def __init__(self) -> None:
        self._root: Optional[_Node] = None
        self._size = 0

    def __len__(self) -> int:
        return self._size

    def __bool__(self) -> bool:
        return self._size > 0

    def __contains__(self, key: Any) -> bool:
        return self._find(key) is not None

    def _find(self, key: Any) -> Optional[_Node]:
        n = self._root
        while n:
            if key == n.key:
                return n
            n = n.left if key < n.key else n.right
        return None

    def get(self, key: Any, default: Any = None) -> Any:
        n = self._find(key)
        return n.value if n else default

    def insert(self, key: Any, value: Any = None) -> None:
        self._root = self._insert(self._root, key, value)

    def _insert(self, n: Optional[_Node], key: Any, value: Any) -> _Node:
        if n is None:
            self._size += 1
            return _Node(key, value)
        if key == n.key:
            n.value = value
            return n
        if key < n.key:
            n.left = self._insert(n.left, key, value)
        else:
            n.right = self._insert(n.right, key, value)
        return _rebalance(n)

    def remove(self, key: Any) -> bool:
        before = self._size
        self._root = self._remove(self._root, key)
        return self._size < before

    def _remove(self, n: Optional[_Node], key: Any) -> Optional[_Node]:
        if n is None:
            return None
        if key < n.key:
            n.left = self._remove(n.left, key)
        elif key > n.key:
            n.right = self._remove(n.right, key)
        else:
            self._size -= 1
            if n.left is None:
                return n.right
            if n.right is None:
                return n.left
            s = n.right
            while s.left:
                s = s.left
            n.key, n.value = s.key, s.value
            self._size += 1  # la llamada siguiente vuelve a descontar el sucesor
            n.right = self._remove(n.right, s.key)
        return _rebalance(n)

    def min_item(self) -> tuple[Any, Any]:
        n = self._root
        if n is None:
            raise KeyError("árbol vacío")
        while n.left:
            n = n.left
        return n.key, n.value

    def max_item(self) -> tuple[Any, Any]:
        n = self._root
        if n is None:
            raise KeyError("árbol vacío")
        while n.right:
            n = n.right
        return n.key, n.value

    def items(self) -> Iterator[tuple[Any, Any]]:
        """Recorrido in-order perezoso (ascendente)."""
        return self.range(None, None)

    def range(self, lo: Any = None, hi: Any = None) -> Iterator[tuple[Any, Any]]:
        """Pares con lo <= clave <= hi (extremos None = sin cota), en orden."""
        return self._range(self._root, lo, hi)

    def _range(self, n: Optional[_Node], lo: Any, hi: Any) -> Iterator[tuple[Any, Any]]:
        if n is None:
            return
        if lo is None or lo < n.key:
            yield from self._range(n.left, lo, hi)
        if (lo is None or lo <= n.key) and (hi is None or n.key <= hi):
            yield n.key, n.value
        if hi is None or n.key < hi:
            yield from self._range(n.right, lo, hi)

    @property
    def height(self) -> int:
        return _h(self._root)

    def is_balanced(self) -> bool:
        """Verifica el invariante AVL y el orden BST (usado en pruebas)."""

        def check(n: Optional[_Node], lo: Any, hi: Any) -> int:
            if n is None:
                return 0
            if (lo is not None and not lo < n.key) or (hi is not None and not n.key < hi):
                return -1
            lh, rh = check(n.left, lo, n.key), check(n.right, n.key, hi)
            if lh < 0 or rh < 0 or abs(lh - rh) > 1 or n.height != 1 + max(lh, rh):
                return -1
            return 1 + max(lh, rh)

        return check(self._root, None, None) >= 0
