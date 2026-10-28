import random

import pytest

from app.ds.avl_tree import AVLTree


def make_tree(keys):
    t = AVLTree()
    for k in keys:
        t.insert((k,), f"v{k}")
    return t


def test_insert_and_search():
    t = make_tree([10, 20, 30, 5, 1])
    assert len(t) == 5
    assert t.search((20,)) == "v20"
    assert t.search((99,)) is None
    assert t.contains((1,))


def test_duplicate_key_updates_value_not_size():
    t = AVLTree()
    t.insert(("a",), 1)
    t.insert(("a",), 2)
    assert len(t) == 1
    assert t.search(("a",)) == 2


def test_ll_rotation():
    # descending inserts force a right rotation at the root (LL case)
    t = make_tree([30, 20, 10])
    assert t.last_rotations == ["LL"]
    assert t.pre_order_keys() == [(20,), (10,), (30,)]
    assert t.is_balanced()


def test_rr_rotation():
    t = make_tree([10, 20, 30])
    assert t.last_rotations == ["RR"]
    assert t.pre_order_keys() == [(20,), (10,), (30,)]
    assert t.is_balanced()


def test_lr_rotation():
    t = make_tree([30, 10, 20])
    assert t.last_rotations == ["LR"]
    assert t.pre_order_keys() == [(20,), (10,), (30,)]


def test_rl_rotation():
    t = make_tree([10, 30, 20])
    assert t.last_rotations == ["RL"]
    assert t.pre_order_keys() == [(20,), (10,), (30,)]


def test_in_order_is_sorted():
    keys = list(range(50))
    random.Random(7).shuffle(keys)
    t = make_tree(keys)
    assert [k for k, _ in t.in_order_items()] == [(k,) for k in range(50)]
    assert t.in_order() == [f"v{k}" for k in range(50)]


def test_balance_property_held_after_many_inserts():
    rng = random.Random(42)
    t = AVLTree()
    for i in range(500):
        t.insert((rng.randint(0, 10_000), i), i)
        assert t.is_balanced(), "AVL invariant broken during insertion"
    assert t.is_bst()


def test_height_is_logarithmic():
    t = make_tree(range(1023))  # sorted inserts: worst case for a plain BST
    # AVL height bound: h <= 1.44 * log2(n + 2)
    import math

    assert t.height <= 1.44 * math.log2(len(t) + 2)
    assert t.height < 20


def test_delete_leaf_one_child_two_children():
    t = make_tree([20, 10, 30, 5, 15, 25, 35, 1])
    assert t.delete((1,)) is True          # leaf
    assert t.delete((5,)) is True          # (now) leaf / one child
    assert t.delete((20,)) is True         # two children -> successor swap
    assert t.search((20,)) is None
    assert t.is_balanced() and t.is_bst()
    assert len(t) == 5


def test_delete_missing_key_returns_false():
    t = make_tree([1, 2, 3])
    assert t.delete((99,)) is False
    assert len(t) == 3


def test_balance_property_held_after_random_deletes():
    rng = random.Random(11)
    keys = [(i,) for i in range(300)]
    t = AVLTree()
    for k in keys:
        t.insert(k, k)
    rng.shuffle(keys)
    for k in keys:
        assert t.delete(k) is True
        assert t.is_balanced(), "AVL invariant broken during deletion"
        assert t.is_bst()
    assert len(t) == 0
    assert t.root is None


def test_deadline_then_id_tiebreak_ordering():
    t = AVLTree()
    t.insert(("2026-01-01", "t2"), "b")
    t.insert(("2026-01-01", "t1"), "a")
    t.insert(("2025-12-31", "t9"), "z")
    assert t.in_order() == ["z", "a", "b"]


def test_range_query():
    t = make_tree(range(20))
    assert t.range_query((5,), (9,)) == [f"v{i}" for i in range(5, 10)]


def test_debug_tree_exposes_height_and_balance_factor():
    t = make_tree([10, 20, 30])
    d = t.debug_tree()
    assert d["height"] == 2
    assert d["balance_factor"] == 0
    assert d["left"]["height"] == 1


def test_empty_tree():
    t = AVLTree()
    assert len(t) == 0
    assert t.in_order() == []
    assert t.search((1,)) is None
    assert t.is_balanced()
    assert t.min_key() is None
