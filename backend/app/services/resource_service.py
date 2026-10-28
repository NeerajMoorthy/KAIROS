"""
Resource service.

Responsibilities
----------------
1. INDEX a local folder: walk the files, derive keywords from the filename,
   extension and any user-supplied tags, then push each resource into
       * the ResourceHashTable  (resource_id -> resource, O(1) lookup)
       * the keyword Trie       (keyword -> resource ids, prefix search)
2. FETCH 3-5 supplementary web resources for a topic from a public API
   (Wikipedia's OpenSearch endpoint — no API key, tiny JSON payload).
3. SCORE every candidate resource against the query.
4. RANK them through the Binary Max-Heap (Top-K retrieval) and then Heapsort
   (final display order). `sorted()` is never used on this path.
"""

from __future__ import annotations

import os
import re
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote
from xml.etree import ElementTree

from ..ds.binary_heap import BinaryMaxHeap
from ..ds.hash_table import HashTable, djb2
from ..ds.heapsort import heapsort_desc
from .store import KairosStore, folder_key, tokenize

# ---------------------------------------------------------------------- #
# file kinds
# ---------------------------------------------------------------------- #
KIND_BY_EXT: List[Tuple[Tuple[str, ...], str]] = [
    ((".pdf",), "pdf"),
    ((".md", ".txt", ".rst"), "notes"),
    ((".doc", ".docx", ".odt"), "document"),
    ((".ppt", ".pptx", ".odp"), "slides"),
    ((".xls", ".xlsx", ".csv"), "dataset"),
    ((".py", ".c", ".cpp", ".java", ".js", ".ts", ".ipynb"), "code"),
    ((".png", ".jpg", ".jpeg", ".gif", ".svg"), "image"),
    ((".mp4", ".mkv", ".mov", ".webm"), "video"),
    ((".zip", ".tar", ".gz", ".7z", ".rar"), "archive"),
]

KIND_WEIGHT: Dict[str, float] = {
    "pdf": 6.0,
    "notes": 5.0,
    "slides": 5.0,
    "document": 4.0,
    "code": 4.0,
    "dataset": 3.0,
    "video": 3.0,
    "image": 1.0,
    "archive": 0.5,
    "article": 4.0,
    "file": 1.0,
}

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", "dist", "build"}
MAX_FILES = 2000


def classify(ext: str) -> str:
    ext = ext.lower()
    for exts, kind in KIND_BY_EXT:
        if ext in exts:
            return kind
    return "file"


def split_filename(stem: str) -> List[str]:
    """'AVL_Tree-notes v2' -> ['avl', 'tree', 'notes', 'v2'] (+ camelCase split)."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", stem)
    return tokenize(spaced)


# ---------------------------------------------------------------------- #
# 1a. simple text extraction
# ---------------------------------------------------------------------- #
# Text formats are read directly. DOCX/PPTX are ZIP containers with XML text;
# PDFs use pypdf when the optional dependency is installed.
TEXT_EXTS = {
    ".md", ".txt", ".rst", ".csv", ".tsv", ".json", ".yaml", ".yml",
    ".py", ".c", ".h", ".cpp", ".java", ".js", ".ts", ".tsx", ".sql",
    ".html", ".htm", ".tex", ".log", ".ini", ".cfg", ".docx", ".pptx", ".pdf",
}

MAX_TEXT_BYTES = 64 * 1024   # read at most the first 64 KB of any file
MAX_CONTENT_KEYWORDS = 40    # keep the Trie from drowning in one large file
MAX_PDF_BYTES = 20 * 1024 * 1024

# Words that carry no retrieval signal. Kept deliberately short — this is a
# stop-list, not a linguistic model.
STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had", "her",
    "was", "one", "our", "out", "day", "get", "has", "him", "his", "how", "its",
    "new", "now", "old", "see", "two", "way", "who", "boy", "did", "use", "man",
    "this", "that", "with", "from", "they", "will", "your", "have", "been",
    "were", "said", "each", "which", "their", "them", "then", "than", "when",
    "what", "would", "there", "about", "into", "more", "some", "these", "also",
    "just", "only", "over", "such", "like", "here", "very", "much", "most",
    "using", "used", "given", "where", "while", "both", "same", "other",
}


def _term_frequencies(tokens: List[str]) -> List[Tuple[str, int]]:
    """Count term frequencies in OUR OWN hash table — no collections.Counter.

    The counting itself is O(n) with O(1)-average updates, which is exactly what
    the hash table is for; ordering the result by frequency then reuses our
    heapsort. Nothing on this path touches a Python dict.
    """
    table = HashTable(capacity=128, name="TermFrequencyTable")
    for t in tokens:
        current = table.search(t)
        table.insert(t, (current or 0) + 1)
    return table.items()


def extract_text_keywords(
    path: str, ext: str, limit: int = MAX_CONTENT_KEYWORDS
) -> Tuple[List[str], str]:
    """Read the head of a text file and return (content_keywords, snippet).

    Returns ([], "") for binary or unreadable files, so indexing never fails on
    a file it cannot parse.
    """
    ext = ext.lower()
    if ext not in TEXT_EXTS:
        return [], ""
    try:
        if ext in {".docx", ".pptx"}:
            head = _office_text(path, ext)
        elif ext == ".pdf":
            head = _pdf_text(path)
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                head = fh.read(MAX_TEXT_BYTES)
    except (OSError, ValueError, zipfile.BadZipFile, ElementTree.ParseError):
        return [], ""
    if not head.strip():
        return [], ""

    # snippet: the first non-empty, non-heading-marker line, trimmed
    snippet = ""
    for line in head.splitlines():
        cleaned = line.strip().lstrip("#").lstrip("*").strip()
        if len(cleaned) >= 12:
            snippet = cleaned[:160]
            break

    tokens = [t for t in tokenize(head) if len(t) > 2 and t not in STOPWORDS]
    if not tokens:
        return [], snippet

    # rank terms by frequency with our own heapsort, then keep the top `limit`
    ranked = heapsort_desc(_term_frequencies(tokens), key=lambda pair: pair[1])
    return [term for term, _count in ranked[:limit]], snippet


def _office_text(path: str, ext: str) -> str:
    """Extract bounded text from Word/PowerPoint XML without loading the file."""
    prefix = "word/document.xml" if ext == ".docx" else "ppt/slides/slide"
    parts: List[str] = []
    total = 0
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if ext == ".docx":
            selected = [prefix] if prefix in names else []
        else:
            selected = [
                name for name in names
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
            ]
            selected.sort(key=lambda name: int(re.search(r"slide(\d+)", name).group(1)))
        for name in selected:
            with archive.open(name) as member:
                data = member.read(MAX_TEXT_BYTES)
            root = ElementTree.fromstring(data)
            for value in root.itertext():
                clean = value.strip()
                if clean:
                    parts.append(clean)
                    total += len(clean)
                    if total >= MAX_TEXT_BYTES:
                        return " ".join(parts)[:MAX_TEXT_BYTES]
    return " ".join(parts)[:MAX_TEXT_BYTES]


def _pdf_text(path: str) -> str:
    """Read a few pages from a small PDF if pypdf is available."""
    if os.path.getsize(path) > MAX_PDF_BYTES:
        return ""
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    reader = PdfReader(path, strict=False)
    parts: List[str] = []
    total = 0
    for page in reader.pages[:5]:
        text = page.extract_text() or ""
        parts.append(text)
        total += len(text)
        if total >= MAX_TEXT_BYTES:
            break
    return " ".join(parts)[:MAX_TEXT_BYTES]


# ---------------------------------------------------------------------- #
# 1b. local folder indexing
# ---------------------------------------------------------------------- #
def allowed_roots() -> List[str]:
    """Folders a hosted server may index (KAIROS_ALLOWED_ROOTS, comma-separated).

    Unset (the default, running on your own computer) means any folder you
    choose. On a public server it must be set, or anyone could index and read
    snippets from any folder on that machine.
    """
    raw = os.environ.get("KAIROS_ALLOWED_ROOTS", "")
    return [
        os.path.realpath(os.path.abspath(os.path.expanduser(p.strip())))
        for p in raw.split(",") if p.strip()
    ]


def _within(path: str, root: str) -> bool:
    """True when `path` is `root` or inside it (case-insensitive on Windows)."""
    try:
        a, b = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))
        return os.path.commonpath([a, b]) == b
    except ValueError:  # different drives on Windows
        return False


def _covered_by(path: str, folder: Dict[str, Any]) -> bool:
    """Would a scan of this registered folder reach `path`?"""
    root = folder.get("path", "")
    if not _within(path, root):
        return False
    if folder.get("recursive", True):
        return True
    return folder_key(os.path.dirname(path)) == folder_key(root)


def _covered_by_other_folder(store: KairosStore, path: str, root: str) -> bool:
    own = folder_key(root)
    return any(
        folder_key(f["path"]) != own and _covered_by(path, f) for f in store.folders()
    )


def index_folder(
    store: KairosStore,
    path: str,
    tags: Optional[List[str]] = None,
    recursive: bool = True,
    read_contents: bool = True,
) -> Dict[str, Any]:
    """Index (or re-index) one folder the user chose.

    Re-indexing is incremental: unchanged files are skipped, changed files are
    refreshed, and library entries for files that were deleted from disk -- or
    that this folder's scan no longer reaches -- are removed. The folder is
    recorded in the library so it can be rescanned or removed later.
    """
    tags = [t.strip().lower() for t in (tags or []) if t.strip()]
    root = os.path.realpath(os.path.abspath(os.path.expanduser(path)))
    if not os.path.isdir(root):
        raise FileNotFoundError(f"Not a directory: {path}")
    if os.path.islink(os.path.abspath(os.path.expanduser(path))):
        raise ValueError("Choose a real folder, not a symbolic link.")
    allowed = allowed_roots()
    if allowed and not any(_within(root, a) for a in allowed):
        raise ValueError(
            "This server only indexes its own sample folders; local folders "
            "can be indexed when KAIROS runs on your computer."
        )

    indexed, updated, skipped, text_indexed, processed = 0, 0, 0, 0, 0
    truncated = False
    # Every location this scan reached, including unchanged files. Used after
    # the walk to find library entries the scan no longer reaches.
    seen = HashTable(capacity=256, name="IndexWalkSeenTable")
    if recursive:
        walker = os.walk(root)
    else:
        # os.listdir also returns sub-folders; a non-recursive scan indexes
        # only the files directly inside the chosen folder.
        top_files = [n for n in os.listdir(root) if os.path.isfile(os.path.join(root, n))]
        walker = [(root, [], top_files)]

    for dirpath, dirnames, filenames in walker:
        if processed >= MAX_FILES:
            truncated = True
            break
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".")
            and not os.path.islink(os.path.join(dirpath, d))
        ]
        for fname in filenames:
            if fname.startswith("."):
                skipped += 1
                continue
            if processed >= MAX_FILES:
                truncated = True
                break
            full = os.path.join(dirpath, fname)
            if os.path.islink(full):
                skipped += 1
                continue
            try:
                common = os.path.commonpath([root, os.path.realpath(full)])
                if os.path.normcase(common) != os.path.normcase(root):
                    skipped += 1
                    continue
            except ValueError:
                skipped += 1
                continue
            try:
                st = os.stat(full)
            except OSError:
                # Present but unreadable right now: keep any existing entry.
                seen.insert(full, True)
                skipped += 1
                continue
            processed += 1
            seen.insert(full, True)

            existing = store.find_resource_by_location(full)
            is_update = existing is not None
            if existing is not None:
                unchanged = (
                    existing.get("size_bytes") == st.st_size
                    and existing.get("modified_ns") == st.st_mtime_ns
                    and existing.get("tags", []) == tags
                    and existing.get("contents_indexed", True) == read_contents
                )
                if unchanged:
                    skipped += 1
                    continue

            stem, ext = os.path.splitext(fname)
            kind = classify(ext)
            folder_tokens = tokenize(os.path.basename(dirpath))
            name_tokens = split_filename(stem)
            keywords: List[str] = []
            for kw in name_tokens + folder_tokens + tags + [kind, ext.lstrip(".").lower()]:
                if kw and kw not in keywords:
                    keywords.append(kw)

            # simple text extraction: index what is INSIDE the file, not just
            # what it happens to be called
            content_keywords: List[str] = []
            snippet = ""
            if read_contents:
                content_keywords, snippet = extract_text_keywords(full, ext)
                # a term already covered by the filename is not repeated
                content_keywords = [c for c in content_keywords if c not in keywords]
                if content_keywords:
                    text_indexed += 1

            resource = {
                "id": store.next_resource_id(),
                "title": fname,
                "source": "local",
                "kind": kind,
                "location": full,
                "tags": list(tags),
                "keywords": keywords,
                "content_keywords": content_keywords,
                "size_bytes": st.st_size,
                "modified_ns": st.st_mtime_ns,
                "contents_indexed": read_contents,
                "modified": datetime.fromtimestamp(
                    st.st_mtime, tz=timezone.utc
                ).isoformat(timespec="microseconds"),
                "snippet": snippet or f"Local {kind} in {os.path.basename(dirpath)}/",
            }
            if existing is not None:
                store.remove_resource(existing["id"])
            store.add_resource(resource)
            if is_update:
                updated += 1
            else:
                indexed += 1

    # Register (or refresh) the folder before pruning, so the "covered by
    # another folder" check below never mistakes this folder for another one.
    previous = store.get_folder(root)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    store.upsert_folder({
        "path": root,
        "tags": list(tags),
        "recursive": recursive,
        "read_contents": read_contents,
        "added_at": (previous or {}).get("added_at", stamp),
        "last_indexed_at": stamp,
    })

    removed = _prune_unreached(store, root, seen, truncated)

    result = {
        "indexed": indexed,
        "updated": updated,
        "removed": removed,
        "skipped": skipped,
        "text_indexed": text_indexed,
        "truncated": truncated,
        "path": root,
    }
    folder = store.get_folder(root)
    if folder is not None:
        folder["last_result"] = {k: v for k, v in result.items() if k != "path"}
    return result


def _prune_unreached(
    store: KairosStore, root: str, seen: HashTable, truncated: bool
) -> int:
    """Remove library entries under `root` that this scan did not reach.

    * A file that no longer exists on disk is always removed.
    * A file that exists but was not reached (now hidden, inside a skipped
      folder, or below a folder that is no longer scanned recursively) is
      removed unless another registered folder still covers it.
    * If the scan stopped early at MAX_FILES, only deleted files are removed:
      an unreached file might simply be past the cut-off.
    """
    stale: List[str] = []
    for resource in store.all_resources():
        location = resource.get("location", "")
        if resource.get("source") != "local" or not _within(location, root):
            continue
        if seen.contains(location):
            continue
        if not os.path.exists(location):
            stale.append(resource["id"])
        elif not truncated and not _covered_by_other_folder(store, location, root):
            stale.append(resource["id"])
    for resource_id in stale:
        store.remove_resource(resource_id)
    return len(stale)


# ---------------------------------------------------------------------- #
# 1c. library folder management
# ---------------------------------------------------------------------- #
def list_folders(store: KairosStore) -> Dict[str, Any]:
    """Registered folders with how many library files each one covers."""
    local = [r for r in store.all_resources() if r.get("source") == "local"]
    folders = sorted(store.folders(), key=lambda f: folder_key(f["path"]))
    rows: List[Dict[str, Any]] = []
    for folder in folders:
        count = sum(1 for r in local if _covered_by(r.get("location", ""), folder))
        rows.append({
            **folder,
            "resource_count": count,
            "exists": os.path.isdir(folder["path"]),
        })
    unmanaged = sum(
        1 for r in local
        if not any(_covered_by(r.get("location", ""), f) for f in folders)
    )
    return {"folders": rows, "unmanaged_count": unmanaged}


def rescan_folder(store: KairosStore, path: str) -> Dict[str, Any]:
    """Re-index one registered folder with the options it was added with."""
    folder = store.get_folder(path)
    if folder is None:
        raise LookupError(f"This folder is not in your library: {path}")
    if not os.path.isdir(folder["path"]):
        raise FileNotFoundError(
            f"Folder no longer exists: {folder['path']}. Remove it from the library instead."
        )
    return index_folder(
        store,
        folder["path"],
        tags=folder.get("tags", []),
        recursive=folder.get("recursive", True),
        read_contents=folder.get("read_contents", True),
    )


def rescan_all(store: KairosStore) -> Dict[str, Any]:
    """Rescan every registered folder; one missing folder does not stop the rest."""
    results: List[Dict[str, Any]] = []
    for folder in sorted(store.folders(), key=lambda f: folder_key(f["path"])):
        try:
            results.append({"ok": True, **rescan_folder(store, folder["path"])})
        except (FileNotFoundError, LookupError, OSError, ValueError) as exc:
            results.append({"ok": False, "path": folder["path"], "error": str(exc)})
    totals = {
        key: sum(int(r.get(key, 0)) for r in results if r["ok"])
        for key in ("indexed", "updated", "removed", "skipped")
    }
    return {"results": results, **totals}


def remove_folder(store: KairosStore, path: str) -> Dict[str, Any]:
    """Forget a folder: drop it and the library entries only it covered.

    Files on disk are never touched. Entries also covered by another
    registered folder (for example a parent folder) stay in the library.
    """
    folder = store.get_folder(path)
    if folder is None:
        raise LookupError(f"This folder is not in your library: {path}")
    store.remove_folder_record(folder["path"])
    remaining = store.folders()
    stale = [
        r["id"] for r in store.all_resources()
        if r.get("source") == "local"
        and _covered_by(r.get("location", ""), folder)
        and not any(_covered_by(r.get("location", ""), f) for f in remaining)
    ]
    for resource_id in stale:
        store.remove_resource(resource_id)
    return {"path": folder["path"], "removed": len(stale)}


# ---------------------------------------------------------------------- #
# 2. web supplementary fetch
# ---------------------------------------------------------------------- #
WIKI_ENDPOINT = "https://en.wikipedia.org/w/api.php"


def fetch_web_resources(
    store: KairosStore, topic: str, limit: int = 5, timeout: float = 6.0
) -> List[Dict[str, Any]]:
    """Pull 3-5 supplementary resources for `topic` from Wikipedia OpenSearch.

    Falls back to deterministic study-portal links if the network is
    unavailable, so the demo never breaks in an offline review room.
    """
    topic = topic.strip()
    if not topic:
        return []

    results: List[Dict[str, Any]] = []
    error: Optional[str] = None
    try:
        import httpx

        params = {
            "action": "opensearch",
            "search": topic,
            "limit": str(limit),
            "namespace": "0",
            "format": "json",
        }
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(
                WIKI_ENDPOINT,
                params=params,
                headers={"User-Agent": "KAIROS/0.1 (DSA course project)"},
            )
            resp.raise_for_status()
            data = resp.json()
        titles, descriptions, urls = data[1], data[2], data[3]
        for title, desc, url in zip(titles, descriptions, urls):
            results.append(
                {
                    "title": title,
                    "snippet": desc or f"Wikipedia article on {title}",
                    "url": url,
                }
            )
    except Exception as exc:  # offline / API change / timeout
        error = f"{type(exc).__name__}: {exc}"

    if not results:
        q = quote(topic)
        results = [
            {
                "title": f"{topic} — Wikipedia search",
                "snippet": "Encyclopaedic overview and references.",
                "url": f"https://en.wikipedia.org/w/index.php?search={q}",
            },
            {
                "title": f"{topic} — GeeksforGeeks",
                "snippet": "Worked examples and implementation walkthroughs.",
                "url": f"https://www.geeksforgeeks.org/?s={q}",
            },
            {
                "title": f"{topic} — MIT OpenCourseWare",
                "snippet": "Lecture notes and problem sets.",
                "url": f"https://ocw.mit.edu/search/?q={q}",
            },
        ]

    # Web suggestions are returned for this search only. They used to be added
    # to the library (hash table + Trie), which made every web search grow
    # the "files in your folders" count, filled autocomplete with words that
    # only web links matched (and local search never returns web links), and
    # saved them into the snapshot forever.
    out: List[Dict[str, Any]] = []
    for item in results[:limit]:
        keywords: List[str] = []
        for kw in tokenize(item["title"])[:8] + tokenize(topic)[:4] + ["web", "article"]:
            if kw not in keywords:
                keywords.append(kw)
        resource = {
            "id": f"W{djb2(item['url']) & 0xFFFFFFFF:08x}",
            "title": item["title"],
            "source": "web",
            "kind": "article",
            "location": item["url"],
            "tags": ["web", topic.lower()],
            "keywords": keywords,
            "size_bytes": None,
            "modified": None,
            "snippet": item["snippet"],
        }
        out.append(resource)

    return out


# ---------------------------------------------------------------------- #
# 3. scoring
# ---------------------------------------------------------------------- #
def score_resource(
    resource: Dict[str, Any], query_tokens: List[str], query: str
) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []
    kws = resource.get("keywords", [])
    content = resource.get("content_keywords", [])
    tags = resource.get("tags", [])
    # normalise the title so "AVL_Tree_Notes.md" still matches the query "avl tree"
    title_l = " ".join(tokenize(resource.get("title", "")))
    q = " ".join(tokenize(query))

    # Each component is capped so that one very long query cannot let a single
    # signal dominate the ranking.
    exact = sum(1 for t in query_tokens if t in kws)
    if exact:
        pts = 30.0 * min(exact, 3)
        score += pts
        reasons.append(f"{exact} exact keyword match(es) (+{pts:.0f})")

    prefix = sum(
        1 for t in query_tokens if any(k.startswith(t) and k != t for k in kws)
    )
    if prefix:
        pts = 12.0 * min(prefix, 3)
        score += pts
        reasons.append(f"{prefix} prefix match(es) (+{pts:.0f})")

    tag_hits = sum(1 for t in query_tokens if t in tags)
    if tag_hits:
        pts = 18.0 * min(tag_hits, 2)
        score += pts
        reasons.append(f"{tag_hits} tag match(es) (+{pts:.0f})")

    # A term found in the file's TEXT is real evidence, but weaker than the same
    # term in its name — a passing mention should not outrank a file about it.
    body = sum(1 for t in query_tokens if t in content)
    if body:
        pts = 8.0 * min(body, 3)
        score += pts
        reasons.append(f"{body} match(es) inside the file text (+{pts:.0f})")

    if q and q in title_l:
        score += 25.0
        reasons.append("query appears in title (+25)")

    kw = KIND_WEIGHT.get(resource.get("kind", "file"), 1.0)
    score += kw
    reasons.append(f"kind={resource.get('kind')} (+{kw:.0f})")

    if resource.get("source") == "local":
        score += 15.0
        reasons.append("your own material (+15)")
    else:
        score += 4.0
        reasons.append("supplementary web resource (+4)")

    modified = resource.get("modified")
    if modified:
        try:
            dt = datetime.fromisoformat(modified)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - dt).days
            if age_days <= 30:
                score += 6.0
                reasons.append("modified in the last 30 days (+6)")
            elif age_days <= 180:
                score += 3.0
                reasons.append("modified in the last 6 months (+3)")
        except (ValueError, TypeError):
            pass

    return round(score, 2), reasons


# ---------------------------------------------------------------------- #
# 4. ranking pipeline: Trie -> Heap (Top-K) -> Heapsort (display order)
# ---------------------------------------------------------------------- #
# Local files rank above web suggestions regardless of score. The web results
# are supplementary links, not competitors: a file already on the student's
# disk that mentions the topic is more useful than a generic "<query> —
# Wikipedia" link that scores well only because the query is in its title.
# This is a tier, not a bonus — it never changes the score that is displayed,
# so the "why" line stays an honest account of how the score was reached.
LOCAL_TIER = 1000.0


def rank_key(item: Dict[str, Any]) -> float:
    """Ordering key: local tier first, score within the tier."""
    tier = LOCAL_TIER if item["resource"].get("source") == "local" else 0.0
    return tier + item["score"]


def rank_resources(
    store: KairosStore,
    candidates: List[Dict[str, Any]],
    query: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    query_tokens = tokenize(query)
    scored: List[Dict[str, Any]] = []
    for r in candidates:
        score, reasons = score_resource(r, query_tokens, query)
        scored.append({"resource": r, "score": score, "reasons": reasons})

    # (a) Binary max-heap for Top-K retrieval: O(n) build + O(k log n) extracts
    heap = BinaryMaxHeap(name="ResourceRankHeap")
    heap.build_heap([(rank_key(item), item) for item in scored])
    top = [payload for _, payload in heap.top_k(top_k)]

    # (b) Heapsort for the final displayed order: O(k log k), no sorted()
    ranked = heapsort_desc(top, key=rank_key)
    return ranked


def search_resources(
    store: KairosStore,
    query: str,
    top_k: int = 5,
    include_web: bool = False,
) -> Dict[str, Any]:
    """Full search: Trie prefix + exact lookup, optional web fetch, then ranking."""
    query_tokens = tokenize(query)

    # Trie: collect candidate resource ids from every query token
    candidate_ids: List[str] = []
    for token in query_tokens or [query.strip().lower()]:
        for rid in store.keyword_trie.prefix_payloads(token):
            if rid not in candidate_ids:
                candidate_ids.append(rid)

    # HashTable: O(1) hydration of each id into the full resource record
    local: List[Dict[str, Any]] = []
    for rid in candidate_ids:
        r = store.resource_index.search(rid)
        if r is not None and r.get("source") == "local":
            local.append(r)

    web: List[Dict[str, Any]] = []
    if include_web:
        web = fetch_web_resources(store, query, limit=5)

    candidates = local + web
    ranked = rank_resources(store, candidates, query, top_k=top_k)

    autocomplete = store.keyword_trie.prefix_search(
        (query_tokens[-1] if query_tokens else query.strip().lower()), limit=10
    )

    return {
        "query": query,
        "autocomplete": autocomplete,
        "local_matches": len(local),
        "web_matches": len(web),
        "results": ranked,
    }
