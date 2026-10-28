"""
Heapsort — explicit, in-place, built on our own sift-down.

`sorted()` / `list.sort()` / `heapq` are NOT used. KAIROS calls
`heapsort_desc()` to produce the final ranked resource list shown in the UI.

Algorithm
---------
1. Build a max-heap over the whole array bottom-up (Floyd, O(n)).
2. Repeatedly swap array[0] (the max) with the last unsorted slot, shrink the
   heap by one, and sift the new root back down.
   After the loop the array is sorted ASCENDING in place.
3. A descending ranking is produced by negating the sort key before step 1, so
   equal-scoring items keep their original relative order (reversing the
   ascending output would flip ties, which looks wrong in a ranked list).

Complexity: O(n log n) worst / average / best. Space: O(1) auxiliary.
Stability: heapsort is NOT stable, so we make the comparison key a total order
by appending the original index — ties then resolve to insertion order.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Sequence, Tuple


SortRecord = Tuple[float, int, Any]  # (key, tiebreak_index, payload)


class HeapsortStats:
    __slots__ = ("comparisons", "swaps", "n")

    def __init__(self) -> None:
        self.comparisons = 0
        self.swaps = 0
        self.n = 0

    def as_dict(self) -> dict:
        return {"n": self.n, "comparisons": self.comparisons, "swaps": self.swaps}


def _less(a: SortRecord, b: SortRecord, stats: HeapsortStats) -> bool:
    """a < b under the total order (key asc, then tiebreak index asc)."""
    stats.comparisons += 1
    if a[0] != b[0]:
        return a[0] < b[0]
    return a[1] < b[1]  # earlier original index sorts first -> stable


def _sift_down(arr: List[SortRecord], i: int, end: int, stats: HeapsortStats) -> None:
    """Push arr[i] down within arr[0:end] to restore the max-heap property."""
    while True:
        l, r = 2 * i + 1, 2 * i + 2
        largest = i
        if l < end and _less(arr[largest], arr[l], stats):
            largest = l
        if r < end and _less(arr[largest], arr[r], stats):
            largest = r
        if largest == i:
            return
        arr[i], arr[largest] = arr[largest], arr[i]
        stats.swaps += 1
        i = largest


def _build_max_heap(arr: List[SortRecord], stats: HeapsortStats) -> None:
    n = len(arr)
    for i in range(n // 2 - 1, -1, -1):
        _sift_down(arr, i, n, stats)


def heapsort_records(records: List[SortRecord], stats: HeapsortStats) -> List[SortRecord]:
    """In-place heapsort producing ASCENDING order. O(n log n)."""
    arr = records
    stats.n = len(arr)
    _build_max_heap(arr, stats)
    for end in range(len(arr) - 1, 0, -1):
        arr[0], arr[end] = arr[end], arr[0]  # largest to its final slot
        stats.swaps += 1
        _sift_down(arr, 0, end, stats)
    return arr


# ---------------------------------------------------------------------- #
# public helpers
# ---------------------------------------------------------------------- #
def heapsort_asc(
    items: Sequence[Any],
    key: Callable[[Any], float],
    stats: Optional[HeapsortStats] = None,
) -> List[Any]:
    """Ascending sort by `key`, via heapsort. Pass `stats` to collect counters."""
    stats = stats if stats is not None else HeapsortStats()
    records: List[SortRecord] = [(float(key(x)), i, x) for i, x in enumerate(items)]
    heapsort_records(records, stats)
    out = [rec[2] for rec in records]
    return out


def heapsort_desc(
    items: Sequence[Any],
    key: Callable[[Any], float],
    stats: Optional[HeapsortStats] = None,
) -> List[Any]:
    """Descending sort by `key`: heapsort on the negated key. O(n log n)."""
    stats = stats if stats is not None else HeapsortStats()
    records: List[SortRecord] = [(-float(key(x)), i, x) for i, x in enumerate(items)]
    heapsort_records(records, stats)
    out = [rec[2] for rec in records]
    return out


def last_run_is_sorted(values: Sequence[float]) -> bool:
    """Utility used by the tests."""
    return all(values[i] <= values[i + 1] for i in range(len(values) - 1))
