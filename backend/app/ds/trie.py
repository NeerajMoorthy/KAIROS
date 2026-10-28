"""
Trie (prefix tree) for resource keyword / filename / tag search.

Design notes
------------
* Children are stored as an explicit association list of (char, TrieNode)
  pairs kept in sorted order, NOT a Python dict. A linear scan over a handful
  of children is cheap, insertion keeps the list sorted so that traversals
  emit results in lexicographic order, and it keeps the structure honest for
  a DSA review. `_find_child` is a binary search over that list.
* Each terminal node carries a list of *payload ids* (resource ids), so the
  same keyword can point at several resources.

Complexity (m = length of the word/prefix, k = number of matches,
            L = total length of matched words)
------------------------------------------------------------------------
insert                 : O(m)
exact search           : O(m)
prefix search (walk)   : O(m) to reach the prefix node + O(L) to collect
delete                 : O(m)
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

from .hash_table import HashTable

# A word node keeps its payloads in a list (insertion order is the search
# order). Checking "is this payload already here?" by scanning that list is
# O(k); for a word shared by thousands of files (a tag, a file kind, an
# extension) that made indexing quadratic. Once a node holds more than this
# many payloads it also keeps a hash-table membership index: O(1) average.
PAYLOAD_INDEX_THRESHOLD = 16



class TrieNode:
    __slots__ = ("char", "children", "is_word", "payloads", "payload_index", "word")

    def __init__(self, char: str = "") -> None:
        self.char = char
        # association list of (char, node), kept sorted by char
        self.children: List[Tuple[str, "TrieNode"]] = []
        self.is_word: bool = False
        self.payloads: List[Any] = []
        # built lazily, only for nodes with many payloads (see threshold)
        self.payload_index: Optional[HashTable] = None
        self.word: Optional[str] = None

    # -- payload membership -------------------------------------------------
    def has_payload(self, payload: Any) -> bool:
        if self.payload_index is not None:
            return self.payload_index.contains(payload)
        return payload in self.payloads

    def add_payload(self, payload: Any) -> bool:
        """Append unless already present. O(1) average once indexed."""
        if self.has_payload(payload):
            return False
        self.payloads.append(payload)
        if self.payload_index is not None:
            self.payload_index.insert(payload, True)
        elif len(self.payloads) > PAYLOAD_INDEX_THRESHOLD:
            self.payload_index = HashTable(capacity=64, name="TriePayloadIndex")
            for existing in self.payloads:
                self.payload_index.insert(existing, True)
        return True

    def discard_payload(self, payload: Any) -> bool:
        if not self.has_payload(payload):
            return False
        self.payloads.remove(payload)
        if self.payload_index is not None:
            self.payload_index.delete(payload)
        return True

    # -- child access ---------------------------------------------------
    def find_child(self, ch: str) -> Optional["TrieNode"]:
        """Binary search the sorted association list."""
        lo, hi = 0, len(self.children) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            c = self.children[mid][0]
            if c == ch:
                return self.children[mid][1]
            if c < ch:
                lo = mid + 1
            else:
                hi = mid - 1
        return None

    def add_child(self, ch: str) -> "TrieNode":
        node = TrieNode(ch)
        # insert keeping the list sorted
        i = 0
        while i < len(self.children) and self.children[i][0] < ch:
            i += 1
        self.children.insert(i, (ch, node))
        return node

    def remove_child(self, ch: str) -> None:
        for i, (c, _) in enumerate(self.children):
            if c == ch:
                self.children.pop(i)
                return

    def __repr__(self) -> str:  # pragma: no cover
        return f"TrieNode({self.char!r}, word={self.is_word})"


class Trie:
    def __init__(self) -> None:
        self.root = TrieNode()
        self._word_count = 0
        self._node_count = 1
        # cumulative character steps taken by _walk() — the m in O(m)
        self.char_steps = 0

    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize(word: str) -> str:
        return word.strip().lower()

    def __len__(self) -> int:
        return self._word_count

    @property
    def word_count(self) -> int:
        return self._word_count

    @property
    def node_count(self) -> int:
        return self._node_count

    # ------------------------------------------------------------------ #
    # insert
    # ------------------------------------------------------------------ #
    def insert(self, word: str, payload: Any = None) -> None:
        """Insert `word`, attaching `payload` (e.g. a resource id). O(m)."""
        w = self._normalize(word)
        if not w:
            return
        node = self.root
        created = 0
        for ch in w:
            child = node.find_child(ch)
            if child is None:
                child = node.add_child(ch)
                created += 1
                self._node_count += 1
            node = child
        new_word = not node.is_word
        if new_word:
            self._word_count += 1
        node.is_word = True
        node.word = w
        if payload is not None:
            node.add_payload(payload)

    # ------------------------------------------------------------------ #
    # traversal helper
    # ------------------------------------------------------------------ #
    def _walk(self, s: str) -> Optional[TrieNode]:
        node = self.root
        for ch in s:
            self.char_steps += 1
            node = node.find_child(ch)  # type: ignore[assignment]
            if node is None:
                return None
        return node

    # ------------------------------------------------------------------ #
    # exact search
    # ------------------------------------------------------------------ #
    def search(self, word: str) -> bool:
        """Exact keyword match. O(m)."""
        w = self._normalize(word)
        node = self._walk(w)
        hit = node is not None and node.is_word
        return hit

    def search_payloads(self, word: str) -> List[Any]:
        """Payloads attached to an exact keyword. O(m)."""
        w = self._normalize(word)
        node = self._walk(w)
        payloads = list(node.payloads) if node is not None and node.is_word else []
        return payloads

    # ------------------------------------------------------------------ #
    # prefix search / autocomplete
    # ------------------------------------------------------------------ #
    def starts_with(self, prefix: str) -> bool:
        p = self._normalize(prefix)
        return self._walk(p) is not None

    def prefix_search(self, prefix: str, limit: int = 20) -> List[str]:
        """Autocomplete: all words under `prefix`, lexicographic. O(m + L)."""
        p = self._normalize(prefix)
        node = self._walk(p)
        results: List[str] = []
        if node is not None:
            self._collect_words(node, results, limit)
        return results

    def prefix_payloads(self, prefix: str, limit: int = 200) -> List[Any]:
        """All payloads under `prefix`, de-duplicated, order preserved. O(m + L)."""
        p = self._normalize(prefix)
        node = self._walk(p)
        out: List[Any] = []
        if node is not None:
            self._collect_payloads(node, out, limit)
        return out

    def _collect_words(self, node: TrieNode, out: List[str], limit: int) -> None:
        if len(out) >= limit:
            return
        if node.is_word and node.word:
            out.append(node.word)
        for _, child in node.children:
            if len(out) >= limit:
                return
            self._collect_words(child, out, limit)

    def _collect_payloads(self, node: TrieNode, out: List[Any], limit: int) -> None:
        if len(out) >= limit:
            return
        if node.is_word:
            for p in node.payloads:
                if p not in out:
                    out.append(p)
                    if len(out) >= limit:
                        return
        for _, child in node.children:
            if len(out) >= limit:
                return
            self._collect_payloads(child, out, limit)

    # ------------------------------------------------------------------ #
    # delete
    # ------------------------------------------------------------------ #
    def delete(self, word: str) -> bool:
        """Remove a word, pruning now-useless nodes on the way back up. O(m)."""
        w = self._normalize(word)
        removed = self._delete(self.root, w, 0)
        if removed:
            self._word_count -= 1
        return removed

    def remove_payload(self, word: str, payload: Any) -> bool:
        """Remove one payload while preserving other resources for the word."""
        w = self._normalize(word)
        node = self._walk(w)
        if node is None or not node.is_word or not node.discard_payload(payload):
            return False
        if not node.payloads:
            self.delete(w)
        return True

    def _delete(self, node: TrieNode, word: str, depth: int) -> bool:
        if depth == len(word):
            if not node.is_word:
                return False
            node.is_word = False
            node.word = None
            node.payloads = []
            node.payload_index = None
            return True

        ch = word[depth]
        child = node.find_child(ch)
        if child is None:
            return False
        removed = self._delete(child, word, depth + 1)
        # prune the child if it is now a dead end
        if removed and not child.is_word and not child.children:
            node.remove_child(ch)
            self._node_count -= 1
        return removed

    # ------------------------------------------------------------------ #
    def all_words(self) -> List[str]:
        out: List[str] = []
        self._collect_words(self.root, out, 10**9)
        return out

    def stats(self) -> dict:
        return {
            "words": self._word_count,
            "nodes": self._node_count,
            "children_storage": "sorted association list + binary search (no dict)",
        }
