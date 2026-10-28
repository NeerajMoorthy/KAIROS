from app.ds.trie import Trie


def build(words):
    t = Trie()
    for w in words:
        t.insert(w, payload=f"res::{w}")
    return t


def test_insert_and_exact_search():
    t = build(["graph", "graphs", "greedy", "heap"])
    assert t.search("graph") is True
    assert t.search("grap") is False       # prefix is not a word
    assert t.search("heap") is True
    assert t.search("heapsort") is False
    assert len(t) == 4


def test_case_and_whitespace_normalised():
    t = Trie()
    t.insert("  Dijkstra  ")
    assert t.search("dijkstra") is True
    assert t.search("DIJKSTRA") is True


def test_starts_with():
    t = build(["avl", "avltree", "array"])
    assert t.starts_with("av") is True
    assert t.starts_with("z") is False


def test_prefix_search_returns_lexicographic_matches():
    t = build(["heap", "heapsort", "hash", "hashing", "trie"])
    assert t.prefix_search("h") == ["hash", "hashing", "heap", "heapsort"]
    assert t.prefix_search("hea") == ["heap", "heapsort"]
    assert t.prefix_search("zzz") == []


def test_prefix_search_limit():
    t = build([f"word{i}" for i in range(50)])
    assert len(t.prefix_search("word", limit=5)) == 5


def test_payloads_exact_and_prefix():
    t = Trie()
    t.insert("graph", "r1")
    t.insert("graph", "r2")
    t.insert("graphql", "r3")
    assert t.search_payloads("graph") == ["r1", "r2"]
    assert t.prefix_payloads("gra") == ["r1", "r2", "r3"]
    assert t.search_payloads("missing") == []


def test_duplicate_payload_not_added_twice():
    t = Trie()
    t.insert("sort", "r1")
    t.insert("sort", "r1")
    assert t.search_payloads("sort") == ["r1"]
    assert len(t) == 1


def test_delete_word_only_removes_that_word():
    t = build(["heap", "heapsort"])
    assert t.delete("heap") is True
    assert t.search("heap") is False
    assert t.search("heapsort") is True    # shared prefix survives
    assert len(t) == 1


def test_delete_prunes_dead_nodes():
    t = build(["heapsort"])
    nodes_before = t.node_count
    assert t.delete("heapsort") is True
    assert t.node_count < nodes_before
    assert t.node_count == 1               # only the root remains
    assert t.prefix_search("h") == []


def test_delete_missing_word():
    t = build(["trie"])
    assert t.delete("tree") is False
    assert len(t) == 1


def test_empty_and_blank_inserts_ignored():
    t = Trie()
    t.insert("")
    t.insert("   ")
    assert len(t) == 0


def test_all_words_round_trip():
    words = ["binary", "binarysearch", "bfs", "dfs"]
    t = build(words)
    assert sorted(t.all_words()) == sorted(words)


def test_stats_documents_child_storage():
    t = build(["a"])
    assert "no dict" in t.stats()["children_storage"]


def test_many_payloads_stay_unique_and_ordered_past_the_index_threshold():
    from app.ds.trie import PAYLOAD_INDEX_THRESHOLD

    t = Trie()
    ids = [f"R{i:04d}" for i in range(PAYLOAD_INDEX_THRESHOLD * 5)]
    for rid in ids:
        t.insert("notes", rid)
    for rid in ids:  # duplicates are ignored once the hash index exists
        t.insert("notes", rid)
    assert t.search_payloads("notes") == ids

    assert t.remove_payload("notes", ids[3]) is True
    assert t.remove_payload("notes", ids[3]) is False
    t.insert("notes", ids[3])  # re-added at the end, not lost
    assert t.search_payloads("notes")[-1] == ids[3]
    assert len(t.search_payloads("notes")) == len(ids)


def test_word_deleted_and_reinserted_does_not_keep_a_stale_payload_index():
    from app.ds.trie import PAYLOAD_INDEX_THRESHOLD

    t = Trie()
    ids = [f"R{i}" for i in range(PAYLOAD_INDEX_THRESHOLD + 4)]
    for rid in ids:
        t.insert("tag", rid)
    for rid in ids:
        t.remove_payload("tag", rid)
    assert t.search("tag") is False
    t.insert("tag", ids[0])
    assert t.search_payloads("tag") == [ids[0]]
