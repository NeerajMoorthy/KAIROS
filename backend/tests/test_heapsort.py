import random

from app.ds.heapsort import (
    HeapsortStats,
    heapsort_asc,
    heapsort_desc,
    heapsort_records,
)


def test_ascending_sort():
    data = [5, 3, 9, 1, 7]
    assert heapsort_asc(data, key=lambda x: x) == [1, 3, 5, 7, 9]


def test_descending_sort():
    data = [5, 3, 9, 1, 7]
    assert heapsort_desc(data, key=lambda x: x) == [9, 7, 5, 3, 1]


def test_sorts_dicts_by_score():
    resources = [
        {"id": "a", "score": 2.5},
        {"id": "b", "score": 9.0},
        {"id": "c", "score": 4.25},
    ]
    ranked = heapsort_desc(resources, key=lambda r: r["score"])
    assert [r["id"] for r in ranked] == ["b", "c", "a"]


def test_empty_and_single():
    assert heapsort_asc([], key=lambda x: x) == []
    assert heapsort_desc([], key=lambda x: x) == []
    assert heapsort_asc([42], key=lambda x: x) == [42]


def test_already_sorted_and_reversed():
    assert heapsort_asc(list(range(50)), key=lambda x: x) == list(range(50))
    assert heapsort_asc(list(range(50, 0, -1)), key=lambda x: x) == list(range(1, 51))


def test_all_equal_keys_preserve_input_order():
    items = [f"item{i}" for i in range(10)]
    assert heapsort_asc(items, key=lambda x: 1.0) == items
    assert heapsort_desc(items, key=lambda x: 1.0) == items


def test_random_matches_reference_ordering():
    """sorted() is used ONLY as a test oracle, never inside the implementation."""
    rng = random.Random(13)
    for n in (0, 1, 2, 3, 17, 64, 257):
        data = [rng.randint(-500, 500) for _ in range(n)]
        assert heapsort_asc(data, key=lambda x: x) == sorted(data)
        assert heapsort_desc(data, key=lambda x: x) == sorted(data, reverse=True)


def test_negative_and_float_keys():
    data = [-2.5, 0.0, 3.75, -10.0]
    assert heapsort_asc(data, key=lambda x: x) == [-10.0, -2.5, 0.0, 3.75]


def test_stats_recorded():
    stats = HeapsortStats()
    records = [(float(v), i, v) for i, v in enumerate([4, 1, 8, 2, 6])]
    heapsort_records(records, stats)
    assert stats.n == 5
    assert stats.comparisons > 0
    assert stats.swaps > 0
    assert [r[0] for r in records] == [1.0, 2.0, 4.0, 6.0, 8.0]


def test_complexity_is_n_log_n_ish():
    """Comparison count should grow ~n log n, not ~n^2."""
    import math

    rng = random.Random(4)
    stats = HeapsortStats()
    n = 1024
    records = [(float(rng.random()), i, i) for i in range(n)]
    heapsort_records(records, stats)
    # generous bound: heapsort does < 4 n log2 n comparisons
    assert stats.comparisons < 4 * n * math.log2(n)
