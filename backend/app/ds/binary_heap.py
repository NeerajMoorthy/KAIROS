"""
Binary MAX-heap backed by an explicit array (Python list used purely as the
array primitive — every heap operation is hand-written; `heapq` is never
imported).

Array layout for the node at index i:
    parent(i) = (i - 1) // 2
    left(i)   = 2i + 1
    right(i)  = 2i + 2

Each element is stored as a (priority, sequence, payload) record. `sequence`
is a monotonically increasing counter that makes the ordering *stable* and
total, so two items with equal priority never need their payloads compared.

Complexity
----------
peek         : O(1)
insert       : O(log n)   sift-up
extract_max  : O(log n)   sift-down
build_heap   : O(n)       Floyd's bottom-up heapify
"""

from __future__ import annotations

import itertools
from typing import Any, Callable, Iterable, List, Optional, Tuple


HeapRecord = Tuple[float, int, Any]


class BinaryMaxHeap:
    def __init__(
        self,
        name: str = "BinaryMaxHeap",
    ) -> None:
        self._array: List[HeapRecord] = []
        self._counter = itertools.count()
        self.name = name
        self.last_swaps = 0

    # ------------------------------------------------------------------ #
    # index arithmetic
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parent(i: int) -> int:
        return (i - 1) // 2

    @staticmethod
    def _left(i: int) -> int:
        return 2 * i + 1

    @staticmethod
    def _right(i: int) -> int:
        return 2 * i + 2

    def __len__(self) -> int:
        return len(self._array)

    @property
    def size(self) -> int:
        return len(self._array)

    def is_empty(self) -> bool:
        return not self._array

    # ------------------------------------------------------------------ #
    # ordering: strictly greater-than on (priority, -sequence)
    # ------------------------------------------------------------------ #
    def _higher(self, a: HeapRecord, b: HeapRecord) -> bool:
        if a[0] != b[0]:
            return a[0] > b[0]
        return a[1] < b[1]  # earlier insertion wins ties (stable)

    def _swap(self, i: int, j: int) -> None:
        self._array[i], self._array[j] = self._array[j], self._array[i]
        self.last_swaps += 1

    # ------------------------------------------------------------------ #
    # sift up / down
    # ------------------------------------------------------------------ #
    def _sift_up(self, i: int) -> int:
        swaps = 0
        while i > 0:
            p = self._parent(i)
            if self._higher(self._array[i], self._array[p]):
                self._swap(i, p)
                swaps += 1
                i = p
            else:
                break
        return swaps

    def _sift_down(self, i: int, end: Optional[int] = None) -> int:
        n = len(self._array) if end is None else end
        swaps = 0
        while True:
            l, r = self._left(i), self._right(i)
            largest = i
            if l < n and self._higher(self._array[l], self._array[largest]):
                largest = l
            if r < n and self._higher(self._array[r], self._array[largest]):
                largest = r
            if largest == i:
                return swaps
            self._swap(i, largest)
            swaps += 1
            i = largest

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def insert(self, priority: float, payload: Any) -> None:
        """Push an item. O(log n)."""
        self.last_swaps = 0
        self._array.append((float(priority), next(self._counter), payload))
        self._sift_up(len(self._array) - 1)

    push = insert

    def peek(self) -> Optional[Any]:
        """Highest-priority payload without removing it. O(1)."""
        if not self._array:
            return None
        pr, _, payload = self._array[0]
        return payload

    def peek_with_priority(self) -> Optional[Tuple[float, Any]]:
        if not self._array:
            return None
        pr, _, payload = self._array[0]
        return pr, payload

    def extract_max(self) -> Optional[Any]:
        """Remove and return the highest-priority payload. O(log n)."""
        item = self.extract_max_with_priority()
        return None if item is None else item[1]

    def extract_max_with_priority(self) -> Optional[Tuple[float, Any]]:
        if not self._array:
            return None
        self.last_swaps = 0
        top = self._array[0]
        last = self._array.pop()
        if self._array:
            self._array[0] = last
            self._sift_down(0)
        return top[0], top[2]

    pop = extract_max

    def build_heap(self, items: Iterable[Tuple[float, Any]]) -> None:
        """Floyd's bottom-up heapify of an arbitrary array. O(n)."""
        self._array = [
            (float(pr), next(self._counter), payload) for pr, payload in items
        ]
        self.last_swaps = 0
        n = len(self._array)
        for i in range(n // 2 - 1, -1, -1):
            self._sift_down(i)

    def clear(self) -> None:
        self._array = []

    # ------------------------------------------------------------------ #
    # convenience
    # ------------------------------------------------------------------ #
    def top_k(self, k: int) -> List[Tuple[float, Any]]:
        """Top-K by repeated extract-max on a COPY. O(n + k log n)."""
        clone = self.snapshot_heap()
        out: List[Tuple[float, Any]] = []
        while clone._array and len(out) < k:
            item = clone.extract_max_with_priority()
            if item is None:
                break
            out.append(item)
        return out

    def drain_sorted(self) -> List[Tuple[float, Any]]:
        """Destructively extract everything in descending priority order."""
        out: List[Tuple[float, Any]] = []
        while self._array:
            item = self.extract_max_with_priority()
            if item is None:
                break
            out.append(item)
        return out

    def snapshot_heap(self) -> "BinaryMaxHeap":
        """An independent structural copy."""
        clone = BinaryMaxHeap(name=self.name)
        clone._array = list(self._array)
        return clone

    def to_list(self) -> List[Tuple[float, Any]]:
        """Raw array order (level order) — useful for a debug view."""
        return [(pr, payload) for pr, _, payload in self._array]

    def remove_by(self, predicate: Callable[[Any], bool]) -> int:
        """Remove all payloads matching a predicate and re-heapify. O(n)."""
        before = len(self._array)
        self._array = [rec for rec in self._array if not predicate(rec[2])]
        for i in range(len(self._array) // 2 - 1, -1, -1):
            self._sift_down(i)
        return before - len(self._array)

    # ------------------------------------------------------------------ #
    def is_valid_heap(self) -> bool:
        """Max-heap property check, used by the unit tests."""
        n = len(self._array)
        for i in range(n):
            for c in (self._left(i), self._right(i)):
                if c < n and self._higher(self._array[c], self._array[i]):
                    return False
        return True
