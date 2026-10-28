"""
AVL Tree — self-balancing binary search tree.

Used by KAIROS to organise tasks by deadline. The key is the tuple
    (deadline_iso_string, task_id)
so that deadlines sort chronologically (ISO-8601 strings sort lexicographically
in chronological order) and the task id breaks ties deterministically.

Implemented from scratch: no `sorted()`, no `bisect`, no library tree.

Complexity
----------
insert / delete / search : O(log n)   (height is bounded by 1.44*log2(n+2))
in-order traversal       : O(n)

The four rebalancing cases are detected explicitly and recorded in `last_rotations`:
    LL  -> single right rotation
    RR  -> single left rotation
    LR  -> left rotation on child, then right rotation on node
    RL  -> right rotation on child, then left rotation on node
"""

from __future__ import annotations

from typing import Any, Callable, Iterator, List, Optional, Tuple


Key = Tuple[Any, ...]


class AVLNode:
    __slots__ = ("key", "value", "left", "right", "height")

    def __init__(self, key: Key, value: Any) -> None:
        self.key: Key = key
        self.value: Any = value
        self.left: Optional["AVLNode"] = None
        self.right: Optional["AVLNode"] = None
        self.height: int = 1  # leaf height == 1

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"AVLNode(key={self.key!r}, h={self.height})"


class AVLTree:
    """AVL tree keyed by an arbitrary orderable tuple."""

    def __init__(self) -> None:
        self.root: Optional[AVLNode] = None
        self._size = 0
        # cumulative key comparisons performed by search() — read by tests
        # to check that lookups stay logarithmic
        self.comparisons = 0
        # rotations performed during the most recent insert/delete
        self.last_rotations: List[str] = []

    # ------------------------------------------------------------------ #
    # basic helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _height(node: Optional[AVLNode]) -> int:
        return node.height if node else 0

    @classmethod
    def _update_height(cls, node: AVLNode) -> None:
        node.height = 1 + max(cls._height(node.left), cls._height(node.right))

    @classmethod
    def balance_factor(cls, node: Optional[AVLNode]) -> int:
        """height(left) - height(right). AVL invariant: |bf| <= 1."""
        if node is None:
            return 0
        return cls._height(node.left) - cls._height(node.right)

    def __len__(self) -> int:
        return self._size

    @property
    def size(self) -> int:
        return self._size

    @property
    def height(self) -> int:
        return self._height(self.root)

    # ------------------------------------------------------------------ #
    # rotations
    # ------------------------------------------------------------------ #
    def _rotate_right(self, z: AVLNode) -> AVLNode:
        """
              z                 y
             / \\               / \\
            y   T4     ->      x   z
           / \\                   / \\
          x   T3                T3  T4
        """
        y = z.left
        assert y is not None
        t3 = y.right
        y.right = z
        z.left = t3
        self._update_height(z)
        self._update_height(y)
        return y

    def _rotate_left(self, z: AVLNode) -> AVLNode:
        """
            z                     y
           / \\                   / \\
          T1  y        ->        z   x
             / \\               / \\
            T2  x             T1  T2
        """
        y = z.right
        assert y is not None
        t2 = y.left
        y.left = z
        z.right = t2
        self._update_height(z)
        self._update_height(y)
        return y

    def _rebalance(self, node: AVLNode) -> AVLNode:
        """Restore the AVL property at `node`, recording which case fired."""
        bf = self.balance_factor(node)

        # Left heavy
        if bf > 1:
            if self.balance_factor(node.left) >= 0:
                self.last_rotations.append("LL")
                return self._rotate_right(node)
            self.last_rotations.append("LR")
            node.left = self._rotate_left(node.left)  # type: ignore[arg-type]
            return self._rotate_right(node)

        # Right heavy
        if bf < -1:
            if self.balance_factor(node.right) <= 0:
                self.last_rotations.append("RR")
                return self._rotate_left(node)
            self.last_rotations.append("RL")
            node.right = self._rotate_right(node.right)  # type: ignore[arg-type]
            return self._rotate_left(node)

        return node

    # ------------------------------------------------------------------ #
    # insert
    # ------------------------------------------------------------------ #
    def insert(self, key: Key, value: Any) -> None:
        """Insert (or overwrite the value of) `key`. O(log n)."""
        self.last_rotations = []
        self.root = self._insert(self.root, key, value)

    def _insert(self, node: Optional[AVLNode], key: Key, value: Any) -> AVLNode:
        if node is None:
            self._size += 1
            return AVLNode(key, value)

        if key < node.key:
            node.left = self._insert(node.left, key, value)
        elif key > node.key:
            node.right = self._insert(node.right, key, value)
        else:
            node.value = value  # duplicate key -> update in place
            return node

        self._update_height(node)
        return self._rebalance(node)

    # ------------------------------------------------------------------ #
    # search
    # ------------------------------------------------------------------ #
    def search(self, key: Key) -> Optional[Any]:
        """Return the value stored at `key`, or None. O(log n)."""
        node = self.root
        comparisons = 0
        while node is not None:
            comparisons += 1
            if key == node.key:
                self.comparisons += comparisons
                return node.value
            node = node.left if key < node.key else node.right
        self.comparisons += comparisons
        return None

    def contains(self, key: Key) -> bool:
        return self.search(key) is not None

    # ------------------------------------------------------------------ #
    # delete
    # ------------------------------------------------------------------ #
    def delete(self, key: Key) -> bool:
        """Delete `key`. Returns True if something was removed. O(log n)."""
        self.last_rotations = []
        before = self._size
        self.root = self._delete(self.root, key)
        return self._size < before

    def _delete(self, node: Optional[AVLNode], key: Key) -> Optional[AVLNode]:
        if node is None:
            return None

        if key < node.key:
            node.left = self._delete(node.left, key)
        elif key > node.key:
            node.right = self._delete(node.right, key)
        else:
            # found it — three classic cases
            if node.left is None:
                self._size -= 1
                return node.right
            if node.right is None:
                self._size -= 1
                return node.left
            # two children: replace with in-order successor (min of right subtree)
            succ = self._min_node(node.right)
            node.key, node.value = succ.key, succ.value
            node.right = self._delete(node.right, succ.key)

        self._update_height(node)
        return self._rebalance(node)

    @staticmethod
    def _min_node(node: AVLNode) -> AVLNode:
        while node.left is not None:
            node = node.left
        return node

    def min_key(self) -> Optional[Key]:
        return self._min_node(self.root).key if self.root else None

    # ------------------------------------------------------------------ #
    # traversals
    # ------------------------------------------------------------------ #
    def in_order(self) -> List[Any]:
        """Values sorted ascending by key — i.e. tasks sorted by deadline. O(n)."""
        out: List[Any] = []
        self._in_order(self.root, out)
        return out

    def _in_order(self, node: Optional[AVLNode], out: List[Any]) -> None:
        if node is None:
            return
        self._in_order(node.left, out)
        out.append(node.value)
        self._in_order(node.right, out)

    def in_order_items(self) -> List[Tuple[Key, Any]]:
        """(key, value) pairs in ascending key order (no trace noise)."""
        out: List[Tuple[Key, Any]] = []

        def walk(n: Optional[AVLNode]) -> None:
            if n is None:
                return
            walk(n.left)
            out.append((n.key, n.value))
            walk(n.right)

        walk(self.root)
        return out

    def pre_order_keys(self) -> List[Key]:
        out: List[Key] = []

        def walk(n: Optional[AVLNode]) -> None:
            if n is None:
                return
            out.append(n.key)
            walk(n.left)
            walk(n.right)

        walk(self.root)
        return out

    def range_query(self, low: Key, high: Key) -> List[Any]:
        """All values with low <= key <= high. O(log n + k)."""
        out: List[Any] = []

        def walk(n: Optional[AVLNode]) -> None:
            if n is None:
                return
            if n.key > low:
                walk(n.left)
            if low <= n.key <= high:
                out.append(n.value)
            if n.key < high:
                walk(n.right)

        walk(self.root)
        return out

    # ------------------------------------------------------------------ #
    # debug view
    # ------------------------------------------------------------------ #
    def debug_tree(self) -> Optional[dict]:
        """Nested dict of the tree with per-node height and balance factor."""

        def node_dict(n: Optional[AVLNode]) -> Optional[dict]:
            if n is None:
                return None
            return {
                "key": [str(part) for part in n.key],
                "height": n.height,
                "balance_factor": self.balance_factor(n),
                "label": self._label(n.value),
                "left": node_dict(n.left),
                "right": node_dict(n.right),
            }

        return node_dict(self.root)

    @staticmethod
    def _label(value: Any) -> str:
        for attr in ("title", "name", "id"):
            if isinstance(value, dict) and attr in value:
                return str(value[attr])
            if hasattr(value, attr):
                return str(getattr(value, attr))
        return str(value)

    # ------------------------------------------------------------------ #
    # invariant checking (used by the unit tests)
    # ------------------------------------------------------------------ #
    def is_balanced(self) -> bool:
        """True iff every node has |balance factor| <= 1 and heights are correct."""

        def check(n: Optional[AVLNode]) -> Tuple[bool, int]:
            if n is None:
                return True, 0
            ok_l, hl = check(n.left)
            ok_r, hr = check(n.right)
            h = 1 + max(hl, hr)
            ok = ok_l and ok_r and abs(hl - hr) <= 1 and n.height == h
            return ok, h

        return check(self.root)[0]

    def is_bst(self) -> bool:
        keys = [k for k, _ in self.in_order_items()]
        return all(keys[i] < keys[i + 1] for i in range(len(keys) - 1))

    def __iter__(self) -> Iterator[Any]:
        for _, v in self.in_order_items():
            yield v
