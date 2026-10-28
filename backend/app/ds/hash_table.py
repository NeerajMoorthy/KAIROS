"""
Hash Table with SEPARATE CHAINING.

Collision strategy (documented choice)
--------------------------------------
Separate chaining. Each bucket holds a singly linked list of (key, value)
nodes. Chaining was chosen over open addressing because:
  * deletion is trivial (unlink a node) with no tombstone bookkeeping;
  * the load factor may exceed 1 without a hard failure, so a resize is a
    performance decision rather than a correctness requirement;
  * the chain length per bucket is directly observable, which makes the
    collision behaviour easy to *show* in the Algorithm Trace panel.

The table grows (doubling the bucket count and rehashing everything) once the
load factor n/m exceeds 0.75, which keeps the expected chain length O(1).

Hash function: a djb2-style polynomial rolling hash over the UTF-8 bytes of
`str(key)`, masked to 64 bits. Python's built-in `hash()` is deliberately NOT
used, and no `dict` appears anywhere in this module.

Complexity
----------
insert / search / delete : O(1) average, O(n) worst case (all keys collide)
resize                   : O(n), amortised O(1) per insert
"""

from __future__ import annotations

from typing import Any, Iterator, List, Optional, Tuple


_MASK64 = (1 << 64) - 1


def djb2(text: str) -> int:
    """Classic djb2 string hash: h = h*33 + c, seeded at 5381."""
    h = 5381
    for byte in text.encode("utf-8"):
        h = ((h * 33) + byte) & _MASK64
    return h


class HashNode:
    """A node in a bucket's collision chain."""

    __slots__ = ("key", "value", "next")

    def __init__(self, key: Any, value: Any, nxt: Optional["HashNode"] = None) -> None:
        self.key = key
        self.value = value
        self.next: Optional["HashNode"] = nxt


class HashTable:
    DEFAULT_CAPACITY = 16
    MAX_LOAD_FACTOR = 0.75

    def __init__(
        self,
        capacity: int = DEFAULT_CAPACITY,
        name: str = "HashTable",
    ) -> None:
        self._capacity = max(4, capacity)
        self._buckets: List[Optional[HashNode]] = [None] * self._capacity
        self._size = 0
        self.collisions = 0        # lifetime count of insert-time collisions
        self.resizes = 0
        # cumulative chain nodes visited by search() — one "probe" each
        self.probes = 0
        self.name = name

    # ------------------------------------------------------------------ #
    def _index(self, key: Any) -> int:
        return djb2(str(key)) % self._capacity

    def __len__(self) -> int:
        return self._size

    @property
    def size(self) -> int:
        return self._size

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def load_factor(self) -> float:
        return self._size / self._capacity

    # ------------------------------------------------------------------ #
    # insert
    # ------------------------------------------------------------------ #
    def insert(self, key: Any, value: Any) -> None:
        """Insert or overwrite. O(1) average."""
        idx = self._index(key)
        head = self._buckets[idx]

        # walk the chain looking for an existing key
        node = head
        while node is not None:
            if node.key == key:
                node.value = value
                return
            node = node.next

        collided = head is not None
        if collided:
            self.collisions += 1
        self._buckets[idx] = HashNode(key, value, head)
        self._size += 1

        if self.load_factor > self.MAX_LOAD_FACTOR:
            self._resize(self._capacity * 2)

    # ------------------------------------------------------------------ #
    # search
    # ------------------------------------------------------------------ #
    def search(self, key: Any) -> Optional[Any]:
        """Return value for key or None. O(1) average."""
        idx = self._index(key)
        node = self._buckets[idx]
        probes = 0
        while node is not None:
            probes += 1
            if node.key == key:
                self.probes += probes
                return node.value
            node = node.next
        self.probes += probes
        return None

    def get(self, key: Any, default: Any = None) -> Any:
        found = self.search(key)
        return default if found is None else found

    def contains(self, key: Any) -> bool:
        idx = self._index(key)
        node = self._buckets[idx]
        while node is not None:
            if node.key == key:
                return True
            node = node.next
        return False

    # ------------------------------------------------------------------ #
    # delete
    # ------------------------------------------------------------------ #
    def delete(self, key: Any) -> bool:
        """Unlink key from its chain. O(1) average."""
        idx = self._index(key)
        prev: Optional[HashNode] = None
        node = self._buckets[idx]
        while node is not None:
            if node.key == key:
                if prev is None:
                    self._buckets[idx] = node.next
                else:
                    prev.next = node.next
                self._size -= 1
                return True
            prev, node = node, node.next
        return False

    # ------------------------------------------------------------------ #
    # resize / rehash
    # ------------------------------------------------------------------ #
    def _resize(self, new_capacity: int) -> None:
        old_buckets = self._buckets
        self._capacity = new_capacity
        self._buckets = [None] * new_capacity
        for head in old_buckets:
            node = head
            while node is not None:
                nxt = node.next
                idx = self._index(node.key)
                node.next = self._buckets[idx]
                self._buckets[idx] = node
                node = nxt
        self.resizes += 1

    # ------------------------------------------------------------------ #
    # iteration / stats
    # ------------------------------------------------------------------ #
    def _chain_length(self, idx: int) -> int:
        n, node = 0, self._buckets[idx]
        while node is not None:
            n += 1
            node = node.next
        return n

    def keys(self) -> List[Any]:
        out: List[Any] = []
        for head in self._buckets:
            node = head
            while node is not None:
                out.append(node.key)
                node = node.next
        return out

    def values(self) -> List[Any]:
        out: List[Any] = []
        for head in self._buckets:
            node = head
            while node is not None:
                out.append(node.value)
                node = node.next
        return out

    def items(self) -> List[Tuple[Any, Any]]:
        out: List[Tuple[Any, Any]] = []
        for head in self._buckets:
            node = head
            while node is not None:
                out.append((node.key, node.value))
                node = node.next
        return out

    def __iter__(self) -> Iterator[Any]:
        return iter(self.keys())

    def stats(self) -> dict:
        lengths = [self._chain_length(i) for i in range(self._capacity)]
        used = sum(1 for l in lengths if l > 0)
        return {
            "size": self._size,
            "capacity": self._capacity,
            "load_factor": round(self.load_factor, 3),
            "collisions": self.collisions,
            "resizes": self.resizes,
            "used_buckets": used,
            "max_chain_length": max(lengths) if lengths else 0,
            "strategy": "separate chaining (singly linked lists)",
            "hash": "djb2 polynomial rolling hash, 64-bit",
            "bucket_chain_lengths": lengths,
        }
