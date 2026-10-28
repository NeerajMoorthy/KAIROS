"""
Workspace Assembly.

A workspace is everything you need to actually sit down and do one task:

    Task details
    ├── Local Resources      (Trie -> HashTable -> Heap -> Heapsort)
    ├── Web Resources        (Wikipedia OpenSearch, same ranking pipeline)
    ├── Concept Progress     (adaptive planning)    
    └── Study Plan           (hours reallocated towards weak concepts)

The task itself is fetched from the HashTable in O(1), so one workspace request
exercises every structure in the system.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from . import adaptive
from .resource_service import search_resources
from .store import KairosStore, build_task, tokenize


def build_workspace(
    store: KairosStore,
    task_id: str,
    top_k: int = 6,
    include_web: bool = False,
) -> Optional[Dict[str, Any]]:
    task = store.task_index.search(task_id)   # HashTable O(1)
    if task is None:
        return None

    # The query is the task category, enriched with distinctive title tokens.
    category = task.get("category") or task.get("topic") or ""
    topic_tokens = tokenize(category)
    title_tokens = [t for t in tokenize(task["title"]) if t not in topic_tokens]
    query = " ".join([category] + title_tokens[:3]).strip()

    found = search_resources(store, query, top_k=top_k, include_web=include_web)
    ranked = found["results"]

    return {
        "task": task,
        "top_k": top_k,
        "query": query,
        "resources": ranked,
        "local_resources": [r for r in ranked if r["resource"]["source"] == "local"],
        "web_resources": [r for r in ranked if r["resource"]["source"] == "web"],
        "progress": adaptive.get_progress(store, task_id),
        "study_plan": adaptive.study_plan(store, task_id),
    }


def seed_demo(store: KairosStore) -> Dict[str, Any]:
    """Populate tasks and some assessed concepts so a live demo has substance."""
    today = date.today()
    days_to_friday = (4 - today.weekday()) % 7 or 7
    samples = [
        ("Project Report", "Research and writing", days_to_friday, "HIGH", 5),
        ("Research Assignment", "Literature review", days_to_friday + 3, "HIGH", 4),
        ("Presentation", "Project update", days_to_friday + 5, "MEDIUM", 3),
        ("Lab Work", "Experiment and report", days_to_friday + 2, "HIGH", 4),
        ("Exam Preparation", "Weekly review", days_to_friday + 8, "MEDIUM", 5),
        ("Project Implementation", "Feature delivery", days_to_friday + 7, "MEDIUM", 6),
        ("Reading Notes", "Course reading", days_to_friday + 10, "LOW", 2),
    ]
    created: List[str] = []
    existing_titles = {str(t.get("title", "")).casefold() for t in store.task_index.values()}
    for title, topic, offset, priority, hours in samples:
        if title.casefold() in existing_titles:
            continue
        task = build_task(
            store.next_task_id(),
            title,
            topic,
            today + timedelta(days=offset),
            priority,
            hours,
            project="Final Project" if title in {"Project Report", "Project Implementation"} else None,
        )
        store.add_task(task)
        created.append(task["id"])
        existing_titles.add(title.casefold())

    # Keep the legacy mastery data populated for internal regression coverage;
    # it is no longer presented as the product's progress model.
    if created:
        first_id = created[0]
        for concept, mastery in [("Planning", 90), ("Research", 85), ("Drafting", 48), ("Review", 72), ("Citations", 55)]:
            adaptive.set_mastery(store, first_id, concept, mastery)

    return {"created": created, "count": len(created)}
