"""
Tests for file *content* indexing and for result ranking: what a file says is
searchable, not just what it is called, and the ranking keeps its promises
(the student's own files first, stronger matches higher).
"""

import os

import pytest

from app.services.resource_service import (
    extract_text_keywords,
    index_folder,
    score_resource,
)
from app.services.store import KairosStore, tokenize

# --------------------------------------------------------------------- #
# Gap A — indexing what a file SAYS, not just what it is called
# --------------------------------------------------------------------- #
@pytest.fixture
def corpus(tmp_path):
    """Three files whose names deliberately hide their subject matter."""
    (tmp_path / "notes_week4.md").write_text(
        "# Shortest paths\n\n"
        "Dijkstra relaxes edges from the frontier. Dijkstra needs "
        "non-negative weights. Bellman-Ford handles negative weights.\n",
        encoding="utf-8",
    )
    (tmp_path / "week5.txt").write_text(
        "Kruskal sorts edges and uses union-find. Prim grows one tree.\n",
        encoding="utf-8",
    )
    (tmp_path / "dijkstra_impl.py").write_text(
        "# heap based implementation\ndef shortest(g, s):\n    return {}\n",
        encoding="utf-8",
    )
    (tmp_path / "diagram.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    return tmp_path


def test_extract_text_keywords_reads_the_body_and_a_snippet(corpus):
    kws, snippet = extract_text_keywords(str(corpus / "notes_week4.md"), ".md")
    assert "dijkstra" in kws
    assert "bellman" in kws or "ford" in kws
    # the heading is the first meaningful line, with markdown stripped
    assert snippet.lower().startswith("shortest paths")
    assert "#" not in snippet


def test_extract_text_ranks_by_frequency(corpus):
    """Dijkstra appears twice, Bellman-Ford once — frequency decides order.

    The ranking runs through our own hash table and our own heapsort, so this
    also guards that path against being quietly replaced by Counter/sorted().
    """
    kws, _ = extract_text_keywords(str(corpus / "notes_week4.md"), ".md")
    assert kws.index("dijkstra") < kws.index("weights")


def test_extract_text_skips_binary_and_unknown_extensions(corpus):
    assert extract_text_keywords(str(corpus / "diagram.png"), ".png") == ([], "")


def test_stopwords_never_become_keywords(corpus):
    kws, _ = extract_text_keywords(str(corpus / "notes_week4.md"), ".md")
    assert not ({"the", "and", "from", "with"} & set(kws))


def test_index_folder_reads_contents_by_default(corpus):
    store = KairosStore()
    res = index_folder(store, str(corpus), tags=["notes"])
    assert res["indexed"] == 4
    assert res["text_indexed"] == 3          # the PNG is not text
    by_title = {r["title"]: r for r in store.all_resources()}
    assert "kruskal" in by_title["week5.txt"]["content_keywords"]
    assert by_title["diagram.png"]["content_keywords"] == []


def test_content_keywords_do_not_duplicate_filename_keywords(corpus):
    store = KairosStore()
    index_folder(store, str(corpus))
    impl = next(r for r in store.all_resources() if r["title"].startswith("dijkstra"))
    assert "dijkstra" in impl["keywords"]
    assert "dijkstra" not in impl["content_keywords"]


def test_read_contents_false_falls_back_to_names_only(corpus):
    store = KairosStore()
    res = index_folder(store, str(corpus), read_contents=False)
    assert res["text_indexed"] == 0
    assert all(r["content_keywords"] == [] for r in store.all_resources())


def test_a_word_only_inside_a_file_still_finds_it(corpus):
    """The gap this closes: "kruskal" is in no filename anywhere."""
    store = KairosStore()
    index_folder(store, str(corpus))
    hits = []
    for r in store.all_resources():
        score, reasons = score_resource(r, tokenize("kruskal"), "kruskal")
        if any("inside the file text" in why for why in reasons):
            hits.append(r["title"])
    assert hits == ["week5.txt"]


def test_content_keywords_are_reachable_through_the_trie(corpus):
    store = KairosStore()
    index_folder(store, str(corpus))
    assert store.keyword_trie.starts_with("krus")
    assert store.keyword_trie.search_payloads("kruskal")


def test_a_filename_match_outranks_a_passing_mention(corpus):
    """Deliberate weighting: a file *about* Dijkstra beats one that name-drops it."""
    store = KairosStore()
    index_folder(store, str(corpus))
    scored = {
        r["title"]: score_resource(r, tokenize("dijkstra"), "dijkstra")[0]
        for r in store.all_resources()
    }
    assert scored["dijkstra_impl.py"] > scored["notes_week4.md"]
    assert scored["notes_week4.md"] > scored["week5.txt"]


def test_unreadable_file_does_not_break_indexing(tmp_path):
    p = tmp_path / "broken.md"
    p.write_bytes(b"\xff\xfe\x00 invalid utf-8 \xff heapsort\n")
    store = KairosStore()
    res = index_folder(store, str(tmp_path))     # errors="ignore", must not raise
    assert res["indexed"] == 1


# --------------------------------------------------------------------- #
# ranking: the Resources page promises "your own files first, the web second"
# --------------------------------------------------------------------- #
def test_local_files_outrank_web_suggestions_even_on_a_content_only_match(corpus):
    """A web stub titled "<query> — Wikipedia" scores higher than a content
    match. It must still rank below the student's own file, because the page
    promises local material first."""
    from app.services.resource_service import fetch_web_resources, rank_resources

    store = KairosStore()
    index_folder(store, str(corpus))
    local = [r for r in store.all_resources() if "kruskal" in r["content_keywords"]]
    web = fetch_web_resources(store, "kruskal", limit=3)
    assert local and web

    ranked = rank_resources(store, local + web, "kruskal", top_k=10)
    sources = [item["resource"]["source"] for item in ranked]
    assert sources[0] == "local"
    assert sources == sorted(sources, key=lambda s: 0 if s == "local" else 1)
    # ...and the displayed score is untouched by the tiering
    assert ranked[0]["score"] < ranked[1]["score"]


def test_scores_still_descend_within_each_tier(corpus):
    from app.services.resource_service import fetch_web_resources, rank_resources

    store = KairosStore()
    index_folder(store, str(corpus))
    candidates = store.all_resources() + fetch_web_resources(store, "dijkstra", limit=3)
    ranked = rank_resources(store, candidates, "dijkstra", top_k=20)
    for source in ("local", "web"):
        scores = [i["score"] for i in ranked if i["resource"]["source"] == source]
        assert scores == sorted(scores, reverse=True)
