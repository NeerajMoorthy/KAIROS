"""
In-memory application store.

Everything KAIROS knows lives inside the five hand-written data structures
below. There is no database (a documented mid-review limitation — see README
"Known limitations"). The store is the ONLY place that knows about all of them
at once, which lets the scheduling and adaptive planning modules plug in
without restructuring the data layer.

Structure -> responsibility
---------------------------
AVLTree      tasks ordered by (deadline, task_id)  -> "by deadline" view
BinaryMaxHeap tasks ordered by urgency score       -> "by priority" view
HashTable    task_id -> Task           (O(1) lookup)
HashTable    resource_id -> Resource   (O(1) lookup)
HashTable    location -> resource_id   (O(1) duplicate check while indexing)
HashTable    folder key -> library folder record (folders the user chose)
Trie         keyword/filename/tag -> resource ids  (prefix + exact search)
"""

from __future__ import annotations

import itertools
import os
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from ..ds.avl_tree import AVLTree
from ..ds.binary_heap import BinaryMaxHeap
from ..ds.hash_table import HashTable
from ..ds.trie import Trie
from .task_analyzer import analyze

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    """Split arbitrary text into lowercase alphanumeric keyword tokens."""
    return [t for t in _TOKEN_RE.findall(str(text).lower()) if len(t) > 1]


class KairosStore:
    def __init__(self) -> None:
        # --- the five required structures ---------------------------------
        self.task_tree = AVLTree()
        self.task_heap = BinaryMaxHeap(name="TaskPriorityHeap")
        self.task_index = HashTable(name="TaskHashTable")
        self.resource_index = HashTable(name="ResourceHashTable")
        # Secondary index over the same records: location -> resource id.
        # Indexing checks every walked file against the library; without this
        # table that check was a scan of every stored resource per file.
        self.location_index = HashTable(name="ResourceLocationTable")
        # Folders the user explicitly added to the library, keyed by
        # folder_key(path). Holds the options needed to rescan a folder.
        self.folder_index = HashTable(name="LibraryFolderTable")
        self.keyword_trie = Trie()
        # self-rated concept confidence for adaptive planning, keyed "taskId::concept"
        self.mastery_index = HashTable(name="MasteryHashTable")
        self.focus_session_index = HashTable(name="FocusSessionHashTable")
        self.settings: Dict[str, Any] = {"available_hours_per_day": 3.0}
        # Urgency depends on "days until the deadline", so a stored score goes
        # stale at midnight. This records the day the scores were computed for.
        self._scored_on: date = date.today()

        self._task_seq = itertools.count(1)
        self._resource_seq = itertools.count(1)
        self._session_seq = itertools.count(1)

    # ------------------------------------------------------------------ #
    # id generation
    # ------------------------------------------------------------------ #
    def next_task_id(self) -> str:
        return f"T{next(self._task_seq):04d}"

    def next_resource_id(self) -> str:
        return f"R{next(self._resource_seq):04d}"

    def next_focus_session_id(self) -> str:
        return f"FS{next(self._session_seq):04d}"

    def sync_sequences(self) -> None:
        """Advance sequence counters beyond existing IDs to avoid collision after restore."""
        max_t = 0
        for task in self.task_index.values():
            tid = str(task.get("id", ""))
            if tid.startswith("T") and tid[1:].isdigit():
                max_t = max(max_t, int(tid[1:]))
        self._task_seq = itertools.count(max_t + 1)

        max_r = 0
        for res in self.resource_index.values():
            rid = str(res.get("id", ""))
            if rid.startswith("R") and rid[1:].isdigit():
                max_r = max(max_r, int(rid[1:]))
        self._resource_seq = itertools.count(max_r + 1)

        max_s = 0
        for session in self.focus_session_index.values():
            sid = str(session.get("id", ""))
            if sid.startswith("FS") and sid[2:].isdigit():
                max_s = max(max_s, int(sid[2:]))
        self._session_seq = itertools.count(max_s + 1)

    # ------------------------------------------------------------------ #
    # tasks
    # ------------------------------------------------------------------ #
    @staticmethod
    def task_key(task: Dict[str, Any]):
        """AVL key: deadline first (ISO strings sort chronologically), id breaks ties."""
        return (str(task["deadline"]), task["id"])

    def add_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # Migrate older JSON snapshots as they enter the live indexes.
        task.setdefault("topic", task.get("category") or "General")
        task.setdefault("category", task.get("topic") or None)
        task.setdefault("project", None)
        task.setdefault("description", task.get("notes", ""))
        task.setdefault("notes", task.get("description", ""))
        task.setdefault("updated_at", task.get("created_at", now_iso()))
        task.setdefault("progress", 100.0 if task.get("completed") else 0.0)
        task.setdefault(
            "status",
            "completed" if task.get("completed") else ("in_progress" if task.get("progress", 0) else "todo"),
        )
        task.setdefault("actual_hours", 0.0)
        task.setdefault(
            "remaining_hours",
            round(float(task.get("estimated_hours", 0)) * (1 - float(task.get("progress", 0)) / 100), 2),
        )
        self.task_index.insert(task["id"], task)
        self.task_tree.insert(self.task_key(task), task)
        if not task.get("completed"):
            self.task_heap.insert(task["urgency_score"], task["id"])
        return task

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a task and keep all task indexes consistent."""
        task = self.task_index.search(task_id)
        if task is None:
            return None
        self.task_tree.delete(self.task_key(task))
        self.task_heap.remove_by(lambda tid: tid == task_id)
        task.update(updates)
        self.task_tree.insert(self.task_key(task), task)
        if not task.get("completed"):
            self.task_heap.insert(float(task.get("urgency_score", 0)), task_id)
        return task

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.task_index.search(task_id)

    def delete_task(self, task_id: str) -> bool:
        task = self.task_index.search(task_id)
        if task is None:
            return False
        self.task_tree.delete(self.task_key(task))
        self.task_index.delete(task_id)
        self.task_heap.remove_by(lambda tid: tid == task_id)
        # clean up any concept mastery records for this task
        prefix = f"{task_id}::"
        to_delete = [k for k in self.mastery_index.keys() if str(k).startswith(prefix)]
        for k in to_delete:
            self.mastery_index.delete(k)
        for session in self.focus_session_index.values():
            if session.get("task_id") == task_id:
                self.focus_session_index.delete(session["id"])
        return True

    def refresh_urgency_scores(self, today: Optional[date] = None) -> None:
        """Recompute every open task's urgency for `today` and rebuild the heap.

        The deadline component of the score is 100 / (1 + days_left), so a
        score computed when the task was created is wrong a day later: a task
        due "in 5 days" that is now due today kept its old, lower score and
        sank in the priority heap. O(n) — run once per day, not per request.
        """
        today = today or date.today()
        self.task_heap.clear()
        for task in self.task_index.values():
            if task.get("completed"):
                continue
            try:
                due = date.fromisoformat(str(task["deadline"])[:10])
            except (KeyError, ValueError):
                continue
            remaining = float(task.get("remaining_hours", task.get("estimated_hours", 0)))
            score, breakdown = analyze(due, task.get("priority", "MEDIUM"), remaining, today=today)
            task["urgency_score"] = score
            task["score_breakdown"] = breakdown
            self.task_heap.insert(score, task["id"])
        self._scored_on = today

    def _ensure_current_scores(self) -> None:
        if self._scored_on != date.today():
            self.refresh_urgency_scores()

    def tasks_by_deadline(self) -> List[Dict[str, Any]]:
        """AVL in-order traversal — O(n), already sorted by deadline."""
        self._ensure_current_scores()
        return self.task_tree.in_order()

    def tasks_by_priority(self) -> List[Dict[str, Any]]:
        """Repeated extract-max on a snapshot of the heap — O(n log n)."""
        self._ensure_current_scores()
        snapshot = self.task_heap.snapshot_heap()
        ordered: List[Dict[str, Any]] = []
        while len(snapshot) > 0:
            item = snapshot.extract_max_with_priority()
            if item is None:
                break
            task = self.task_index.search(item[1])
            if task is not None:
                ordered.append(task)
        return ordered

    def peek_top_task(self) -> Optional[Dict[str, Any]]:
        self._ensure_current_scores()
        tid = self.task_heap.peek()
        return self.task_index.search(tid) if tid else None

    # ------------------------------------------------------------------ #
    # resources
    # ------------------------------------------------------------------ #
    def add_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Store in the hash table and index every keyword into the trie.

        Both the filename/tag keywords and the keywords extracted from the
        file's text go into the same Trie, so one prefix search reaches a file
        by what it is called AND by what it says. The scorer weights the two
        differently; the index does not need to.
        """
        self.resource_index.insert(resource["id"], resource)
        if resource.get("location"):
            self.location_index.insert(resource["location"], resource["id"])
        for kw in resource.get("keywords", []):
            self.keyword_trie.insert(kw, resource["id"])
        for kw in resource.get("content_keywords", []):
            self.keyword_trie.insert(kw, resource["id"])
        return resource

    def remove_resource(self, resource_id: str) -> bool:
        """Remove a resource and only its payloads from the shared keyword trie."""
        resource = self.resource_index.search(resource_id)
        if resource is None:
            return False
        keywords = set(resource.get("keywords", []))
        keywords.update(resource.get("content_keywords", []))
        for keyword in keywords:
            self.keyword_trie.remove_payload(keyword, resource_id)
        location = resource.get("location")
        if location and self.location_index.search(location) == resource_id:
            self.location_index.delete(location)
        return self.resource_index.delete(resource_id)

    def get_resource(self, resource_id: str) -> Optional[Dict[str, Any]]:
        return self.resource_index.search(resource_id)

    def all_resources(self) -> List[Dict[str, Any]]:
        return self.resource_index.values()

    def find_resource_by_location(self, location: str) -> Optional[Dict[str, Any]]:
        """O(1) average: location table -> id -> resource table."""
        resource_id = self.location_index.search(location)
        if resource_id is None:
            return None
        return self.resource_index.search(resource_id)

    # ------------------------------------------------------------------ #
    # library folders
    # ------------------------------------------------------------------ #
    def upsert_folder(self, folder: Dict[str, Any]) -> Dict[str, Any]:
        self.folder_index.insert(folder_key(folder["path"]), folder)
        return folder

    def get_folder(self, path: str) -> Optional[Dict[str, Any]]:
        return self.folder_index.search(folder_key(path))

    def remove_folder_record(self, path: str) -> bool:
        return self.folder_index.delete(folder_key(path))

    def folders(self) -> List[Dict[str, Any]]:
        return self.folder_index.values()

    # ------------------------------------------------------------------ #
    # focus sessions
    # ------------------------------------------------------------------ #
    def add_focus_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        self.focus_session_index.insert(session["id"], session)
        return session

    def get_focus_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.focus_session_index.search(session_id)

    def focus_sessions(self) -> List[Dict[str, Any]]:
        return self.focus_session_index.values()

    # ------------------------------------------------------------------ #
    # stats
    # ------------------------------------------------------------------ #
    def stats(self) -> Dict[str, Any]:
        return {
            "avl": {
                "size": self.task_tree.size,
                "height": self.task_tree.height,
                "balanced": self.task_tree.is_balanced(),
                "root_balance_factor": self.task_tree.balance_factor(
                    self.task_tree.root
                ),
            },
            "heap": {
                "size": self.task_heap.size,
                "valid_max_heap": self.task_heap.is_valid_heap(),
                "array": [
                    {"priority": pr, "task_id": tid}
                    for pr, tid in self.task_heap.to_list()
                ],
            },
            "task_hash_table": self.task_index.stats(),
            "resource_hash_table": self.resource_index.stats(),
            "resource_location_table": self.location_index.stats(),
            "library_folder_table": self.folder_index.stats(),
            "trie": self.keyword_trie.stats(),
            "mastery_hash_table": self.mastery_index.stats(),
            "focus_sessions": self.focus_session_index.size,
        }

    def reset(self) -> None:
        self.__init__()  # type: ignore[misc]


# module-level singleton used by the FastAPI app
store = KairosStore()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_task(
    task_id: str,
    title: str,
    category: str,
    deadline: date,
    priority: str,
    estimated_hours: float,
    project: Optional[str] = None,
    description: str = "",
) -> Dict[str, Any]:
    """A new, open task record with its urgency score.

    Shared by the create endpoint and the example-data seeder so both produce
    exactly the same shape.
    """
    score, breakdown = analyze(deadline, priority, estimated_hours)
    stamp = now_iso()
    return {
        "id": task_id,
        "title": title,
        "topic": category,
        "category": category,
        "project": project,
        "description": description,
        "deadline": deadline.isoformat(),
        "priority": priority,
        "estimated_hours": float(estimated_hours),
        "remaining_hours": round(float(estimated_hours), 2),
        "actual_hours": 0.0,
        "progress": 0.0,
        "status": "todo",
        "notes": description,
        "urgency_score": score,
        "score_breakdown": breakdown,
        "created_at": stamp,
        "updated_at": stamp,
        "completed": False,
    }


def folder_key(path: str) -> str:
    """Stable key for a folder path: absolute, normalised, case-folded where
    the OS is case-insensitive (Windows), without a trailing separator."""
    return os.path.normcase(os.path.normpath(os.path.abspath(os.path.expanduser(path))))
