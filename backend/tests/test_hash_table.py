import random

from app.ds.hash_table import HashTable, djb2


def test_insert_and_search():
    h = HashTable()
    h.insert("t1", {"title": "Assignment"})
    assert h.search("t1") == {"title": "Assignment"}
    assert h.search("nope") is None
    assert h.contains("t1")


def test_overwrite_does_not_grow_size():
    h = HashTable()
    h.insert("k", 1)
    h.insert("k", 2)
    assert len(h) == 1
    assert h.search("k") == 2


def test_delete():
    h = HashTable()
    h.insert("a", 1)
    assert h.delete("a") is True
    assert h.search("a") is None
    assert len(h) == 0
    assert h.delete("a") is False


def test_djb2_is_deterministic_and_nonnegative():
    assert djb2("hello") == djb2("hello")
    assert djb2("hello") != djb2("world")
    assert djb2("") == 5381
    assert djb2("x") >= 0


def test_collision_handling_via_chaining():
    # capacity 4 with 3 keys guarantees at least one collision by pigeonhole
    h = HashTable(capacity=4)
    h.MAX_LOAD_FACTOR = 10  # disable resize so collisions are observable
    keys = [f"key{i}" for i in range(12)]
    for k in keys:
        h.insert(k, k.upper())
    assert h.collisions > 0
    assert h.stats()["max_chain_length"] > 1
    # every key still retrievable despite sharing buckets
    for k in keys:
        assert h.search(k) == k.upper()


def test_delete_from_middle_of_chain():
    h = HashTable(capacity=2)
    h.MAX_LOAD_FACTOR = 100
    for i in range(10):
        h.insert(f"k{i}", i)
    assert h.delete("k5") is True
    assert h.search("k5") is None
    for i in range(10):
        if i != 5:
            assert h.search(f"k{i}") == i
    assert len(h) == 9


def test_resize_preserves_all_entries():
    h = HashTable(capacity=4)
    for i in range(200):
        h.insert(f"id{i}", i)
    assert h.resizes > 0
    assert h.capacity > 4
    assert h.load_factor <= h.MAX_LOAD_FACTOR
    for i in range(200):
        assert h.search(f"id{i}") == i
    assert len(h) == 200


def test_keys_values_items_round_trip():
    h = HashTable()
    data = [(f"r{i}", i * 2) for i in range(30)]
    for k, v in data:
        h.insert(k, v)
    assert sorted(h.keys()) == sorted(k for k, _ in data)
    assert sorted(h.values()) == sorted(v for _, v in data)
    assert sorted(h.items()) == sorted(data)


def test_randomised_against_reference_semantics():
    """dict is used ONLY as a test oracle here, never in the implementation."""
    rng = random.Random(3)
    h = HashTable(capacity=8)
    oracle = {}
    for _ in range(2000):
        k = f"k{rng.randint(0, 120)}"
        op = rng.random()
        if op < 0.6:
            v = rng.randint(0, 1000)
            h.insert(k, v)
            oracle[k] = v
        elif op < 0.8:
            assert h.delete(k) == (k in oracle)
            oracle.pop(k, None)
        else:
            assert h.search(k) == oracle.get(k)
    assert len(h) == len(oracle)


def test_stats_reports_strategy():
    h = HashTable()
    assert "chaining" in h.stats()["strategy"]
