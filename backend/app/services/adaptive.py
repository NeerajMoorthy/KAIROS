"""
Adaptive planning from self-rated concept confidence.

Breaks a task's topic into an ordered chain of concepts, tracks how well the
student knows each one, detects weak areas, and reallocates study time towards
them. This is what turns a static timetable into an adaptive one.

Mastery is stored in our own HashTable (key `"<task_id>::<concept>"`), not a
dict, so the same structure that powers task lookup also powers progress
tracking.

Time reallocation
-----------------
Each concept gets a weight
        weight = (100 − mastery) + BASE
so a concept at 50% mastery pulls roughly twice the time of one at 90%, and a
fully mastered concept still gets a small refresher slice (BASE). Weights are
normalised over the available hours, and the resulting blocks are ordered by
weight using our own heapsort — weakest first.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..ds.heapsort import heapsort_desc
from .store import KairosStore, tokenize

BASE_WEIGHT = 12.0
WEAK_THRESHOLD = 60
STRONG_THRESHOLD = 85
# A concept you have never been assessed on is not *known* to be weak. It is
# treated as an unknown at this baseline so it still earns study time, but never
# outranks a concept you have actually tested badly on.
UNASSESSED_BASELINE = 50

# topic keyword -> ordered concept chain
CONCEPT_MAP: List[tuple] = [
    (("avl", "balance", "rotation"),
     ["Binary Search Tree", "Balance Factor", "Rotations", "Insertion", "Deletion"]),
    (("heap", "heapsort", "priority"),
     ["Heap Property", "Sift-Up", "Sift-Down", "Build-Heap", "Heapsort"]),
    (("trie", "prefix", "autocomplete"),
     ["Trie Nodes", "Insertion", "Prefix Search", "Exact Search", "Deletion & Pruning"]),
    (("hash", "hashing", "collision"),
     ["Hash Functions", "Collision Handling", "Load Factor", "Resizing", "Complexity Analysis"]),
    (("graph", "bfs", "dfs", "dijkstra", "shortest"),
     ["Representation", "BFS", "DFS", "Shortest Paths", "Minimum Spanning Tree"]),
    (("sort", "sorting", "merge", "quick"),
     ["Comparison Model", "Insertion Sort", "Merge Sort", "Quicksort", "Lower Bounds"]),
    (("dynamic", "dp", "knapsack", "greedy", "backtracking"),
     ["Problem Modelling", "Recurrence", "Memoisation", "Tabulation", "Complexity"]),
    (("database", "normalization", "sql", "dbms"),
     ["Functional Dependencies", "1NF", "2NF", "3NF", "BCNF"]),
    (("operating", "paging", "memory", "process", "scheduling"),
     ["Virtual Memory", "Page Tables", "FIFO Replacement", "LRU Replacement", "Thrashing"]),
    (("compiler", "lexical", "parsing", "grammar"),
     ["Lexical Analysis", "Regular Expressions", "Grammars", "Parsing", "Symbol Tables"]),
    (("linear", "algebra", "matrix", "vector"),
     ["Vectors", "Matrix Operations", "Determinants", "Eigenvalues", "Applications"]),
    (("network", "tcp", "routing", "protocol"),
     ["Layering", "Addressing", "Routing", "Transport", "Congestion Control"]),
]

GENERIC = ["Fundamentals", "Core Theory", "Worked Examples", "Practice Problems", "Revision"]


def concepts_for(topic: str) -> List[str]:
    """Ordered concept chain for a topic, from the map or a generic fallback."""
    tokens = tokenize(topic)
    for keywords, concepts in CONCEPT_MAP:
        if any(t in keywords for t in tokens):
            return list(concepts)
    label = topic.strip().title() if topic.strip() else "Topic"
    return [f"{label}: {c}" for c in GENERIC]


def _key(task_id: str, concept: str) -> str:
    return f"{task_id}::{concept}"


def get_progress(store: KairosStore, task_id: str) -> Optional[Dict[str, Any]]:
    task = store.task_index.search(task_id)
    if task is None:
        return None
    concepts = concepts_for(task["topic"])
    rows: List[Dict[str, Any]] = []
    for c in concepts:
        stored = store.mastery_index.search(_key(task_id, c))
        assessed = stored is not None
        mastery = int(stored["mastery"]) if assessed else 0
        rows.append(
            {
                "concept": c,
                "mastery": mastery,
                "status": (
                    "unassessed" if not assessed
                    else "weak" if mastery < WEAK_THRESHOLD
                    else "strong" if mastery >= STRONG_THRESHOLD
                    else "developing"
                ),
                "assessed": assessed,
                "effective": mastery if assessed else UNASSESSED_BASELINE,
            }
        )
    assessed = [r for r in rows if r["assessed"]]
    overall = (
        round(sum(r["mastery"] for r in assessed) / len(assessed)) if assessed else 0
    )
    # only a concept you have actually been assessed on counts as a weak area
    weak = [r["concept"] for r in assessed if r["mastery"] < WEAK_THRESHOLD]
    return {
        "task_id": task_id,
        "task_title": task["title"],
        "topic": task["topic"],
        "concepts": rows,
        "overall_mastery": overall,
        "assessed_count": len(assessed),
        "weak_areas": weak,
        "weak_threshold": WEAK_THRESHOLD,
    }


def set_mastery(
    store: KairosStore, task_id: str, concept: str, mastery: int
) -> Optional[Dict[str, Any]]:
    if store.task_index.search(task_id) is None:
        return None
    mastery = max(0, min(100, int(mastery)))
    store.mastery_index.insert(
        _key(task_id, concept), {"task_id": task_id, "concept": concept, "mastery": mastery}
    )
    return get_progress(store, task_id)


def study_plan(
    store: KairosStore, task_id: str, hours: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """Allocate study hours across concepts, weighted towards weak areas."""
    task = store.task_index.search(task_id)
    if task is None:
        return None
    progress = get_progress(store, task_id)
    assert progress is not None

    total_hours = float(hours if hours is not None else task["estimated_hours"])
    rows = progress["concepts"]
    weights = [(100 - r["effective"]) + BASE_WEIGHT for r in rows]
    total_weight = sum(weights) or 1.0

    blocks = []
    for r, w in zip(rows, weights):
        allocated = round(total_hours * w / total_weight * 4) / 4  # nearest 15 min
        blocks.append(
            {
                "concept": r["concept"],
                "mastery": r["mastery"],
                "status": r["status"],
                "hours": allocated,
                "weight": round(w, 1),
                "reason": (
                    "weak area — extra time allocated" if r["status"] == "weak"
                    else "not assessed yet — study to find out" if r["status"] == "unassessed"
                    else "needs consolidation" if r["status"] == "developing"
                    else "quick refresher"
                ),
            }
        )

    # weakest first, ordered by our own heapsort
    ordered = heapsort_desc(blocks, key=lambda b: b["weight"])
    allocated_total = round(sum(b["hours"] for b in ordered), 2)

    return {
        "task_id": task_id,
        "task_title": task["title"],
        "topic": task["topic"],
        "total_hours": total_hours,
        "allocated_hours": allocated_total,
        "overall_mastery": progress["overall_mastery"],
        "weak_areas": progress["weak_areas"],
        "blocks": ordered,
        "explanation": (
            f"weight = (100 − mastery) + {BASE_WEIGHT:.0f}, normalised over "
            f"{total_hours:g} h. Unassessed concepts count as {UNASSESSED_BASELINE}%. "
            f"Assessed concepts below {WEAK_THRESHOLD}% are flagged weak."
        ),
    }


def revision_blocks(store: KairosStore, limit: int = 4) -> List[Dict[str, Any]]:
    """Weak concepts across all tasks, worst first — fed into the timeline."""
    rows: List[Dict[str, Any]] = []
    for record in store.mastery_index.values():
        if record["mastery"] < WEAK_THRESHOLD:
            task = store.task_index.search(record["task_id"])
            if task is None:
                continue
            rows.append(
                {
                    "task_id": record["task_id"],
                    "title": f"Revise: {record['concept']}",
                    "topic": task["topic"],
                    "concept": record["concept"],
                    "mastery": record["mastery"],
                    "hours": 0.75 if record["mastery"] < 40 else 0.5,
                }
            )
    ordered = heapsort_desc(rows, key=lambda r: 100 - r["mastery"])
    return ordered[:limit]


def learning_overview(store: KairosStore) -> Dict[str, Any]:
    """Mastery snapshot across every task, for the Learning page."""
    tasks = store.task_tree.in_order()
    per_task = []
    all_weak: List[Dict[str, Any]] = []
    for t in tasks:
        p = get_progress(store, t["id"])
        if p is None:
            continue
        per_task.append(
            {
                "task_id": t["id"],
                "title": t["title"],
                "topic": t["topic"],
                "overall_mastery": p["overall_mastery"],
                "assessed_count": p["assessed_count"],
                "concept_count": len(p["concepts"]),
                "weak_count": len(p["weak_areas"]),
            }
        )
        for row in p["concepts"]:
            if row["assessed"] and row["mastery"] < WEAK_THRESHOLD:
                all_weak.append(
                    {
                        "task_id": t["id"],
                        "task_title": t["title"],
                        "concept": row["concept"],
                        "mastery": row["mastery"],
                    }
                )
    assessed = [p for p in per_task if p["assessed_count"] > 0]
    avg = (
        round(sum(p["overall_mastery"] for p in assessed) / len(assessed))
        if assessed
        else 0
    )
    return {
        "tasks": per_task,
        "average_mastery": avg,
        "weak_areas": heapsort_desc(all_weak, key=lambda w: 100 - w["mastery"])[:10],
        "tracked_concepts": store.mastery_index.size,
    }
