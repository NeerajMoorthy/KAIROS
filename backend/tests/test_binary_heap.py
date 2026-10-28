import random

from app.ds.binary_heap import BinaryMaxHeap


def test_insert_peek_extract():
    h = BinaryMaxHeap()
    for pr, name in [(3, "c"), (9, "a"), (5, "b")]:
        h.insert(pr, name)
    assert len(h) == 3
    assert h.peek() == "a"
    assert len(h) == 3                    # peek does not mutate
    assert h.extract_max() == "a"
    assert h.extract_max() == "b"
    assert h.extract_max() == "c"
    assert h.extract_max() is None
    assert h.is_empty()


def test_heap_property_maintained_on_every_insert():
    rng = random.Random(5)
    h = BinaryMaxHeap()
    for _ in range(400):
        h.insert(rng.random() * 100, "x")
        assert h.is_valid_heap()


def test_heap_property_maintained_on_every_extract():
    rng = random.Random(6)
    h = BinaryMaxHeap()
    for i in range(300):
        h.insert(rng.randint(0, 999), i)
    while len(h) > 0:
        h.extract_max()
        assert h.is_valid_heap()


def test_extraction_order_is_descending():
    rng = random.Random(1)
    priorities = [rng.randint(0, 500) for _ in range(200)]
    h = BinaryMaxHeap()
    for p in priorities:
        h.insert(p, p)
    out = [pr for pr, _ in h.drain_sorted()]
    assert out == sorted(priorities, reverse=True)


def test_build_heap_floyd():
    rng = random.Random(2)
    items = [(rng.randint(0, 100), f"i{i}") for i in range(101)]
    h = BinaryMaxHeap()
    h.build_heap(items)
    assert h.is_valid_heap()
    assert len(h) == 101
    assert h.peek_with_priority()[0] == max(p for p, _ in items)


def test_ties_broken_by_insertion_order():
    h = BinaryMaxHeap()
    h.insert(10, "first")
    h.insert(10, "second")
    h.insert(10, "third")
    assert [h.extract_max() for _ in range(3)] == ["first", "second", "third"]


def test_top_k_is_non_destructive():
    h = BinaryMaxHeap()
    for i in range(20):
        h.insert(i, f"task{i}")
    top = h.top_k(3)
    assert [p for p, _ in top] == [19.0, 18.0, 17.0]
    assert len(h) == 20                   # original heap untouched


def test_top_k_larger_than_heap():
    h = BinaryMaxHeap()
    h.insert(1, "a")
    assert len(h.top_k(10)) == 1


def test_remove_by_predicate_reheapifies():
    h = BinaryMaxHeap()
    for i in range(30):
        h.insert(i, i)
    removed = h.remove_by(lambda payload: payload % 2 == 0)
    assert removed == 15
    assert len(h) == 15
    assert h.is_valid_heap()
    assert all(p % 2 == 1 for _, p in h.to_list())


def test_peek_on_empty_heap():
    h = BinaryMaxHeap()
    assert h.peek() is None
    assert h.peek_with_priority() is None
    assert h.is_valid_heap()


def test_snapshot_is_independent():
    h = BinaryMaxHeap()
    for i in range(10):
        h.insert(i, i)
    clone = h.snapshot_heap()
    clone.extract_max()
    assert len(h) == 10 and len(clone) == 9
