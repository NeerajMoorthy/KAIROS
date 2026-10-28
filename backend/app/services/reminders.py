"""
Reminder service.

Not "assignment due tomorrow". A reminder is built from three signals the system
already computes:

  * deadline proximity      (days_to_deadline, from the Task Analyzer)
  * remaining workload      (estimated hours × how much is still unmastered)
  * the current weak area   (from adaptive planning)

Reminders are ranked by urgency using our own binary max-heap, so the most
important one surfaces first — the same structure that drives the priority view.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from ..ds.binary_heap import BinaryMaxHeap
from .adaptive import WEAK_THRESHOLD, get_progress
from . import insights
from .store import KairosStore

LEVELS = ("info", "soon", "urgent", "overdue")


def _humanise_days(days: int) -> str:
    if days < 0:
        return f"{-days} day{'s' if days != -1 else ''} overdue"
    if days == 0:
        return "due today"
    if days == 1:
        return "due tomorrow"
    return f"due in {days} days"


def _current_days_to_deadline(task: Dict[str, Any], today: date) -> int:
    try:
        clean = str(task["deadline"]).split("T")[0].split(" ")[0]
        y, m, d = (int(p) for p in clean.split("-"))
        return (date(y, m, d) - today).days
    except Exception:
        return task.get("score_breakdown", {}).get("days_to_deadline", 0)


def build_reminders(store: KairosStore, limit: int = 8) -> List[Dict[str, Any]]:
    today = date.today()
    heap = BinaryMaxHeap(name="ReminderHeap")

    for task in store.tasks_by_deadline():
        if task.get("completed"):
            continue
        days = _current_days_to_deadline(task, today)
        progress = get_progress(store, task["id"])
        mastery = progress["overall_mastery"] if progress else 0
        weak = progress["weak_areas"] if progress else []

        # Remaining work is the task's own remaining effort (it already follows
        # progress and focus sessions); self-rated mastery can only lower it.
        remaining = round(min(
            insights.remaining_hours(task),
            float(task["estimated_hours"]) * (1 - mastery / 100),
        ), 1)

        if days < 0:
            level = "overdue"
        elif days == 0:
            level = "urgent"
        elif days <= 2:
            level = "soon"
        else:
            level = "info"

        parts = [f"{task['title']} is {_humanise_days(days)}."]
        if remaining > 0:
            parts.append(f"About {remaining:g} h of work remain.")
        else:
            parts.append("You have covered this material — a quick review should do.")
        if weak and level in ("overdue", "urgent", "soon"):
            parts.append(f"Start with your weak area: {weak[0]}.")

        # urgency = the analyzer's score, boosted by how much work is left
        score = float(task["urgency_score"]) + remaining * 3
        heap.insert(
            score,
            {
                "task_id": task["id"],
                "title": task["title"],
                "topic": task["topic"],
                "deadline": task["deadline"],
                "days_to_deadline": days,
                "level": level,
                "remaining_hours": remaining,
                "mastery": mastery,
                "weak_area": weak[0] if weak else None,
                "message": " ".join(parts),
                "urgency": round(score, 2),
            },
        )

    return [payload for _, payload in heap.top_k(limit)]


def dashboard_summary(store: KairosStore) -> Dict[str, Any]:
    """Everything the home screen needs, in one call."""
    all_tasks = store.tasks_by_deadline()
    tasks = [t for t in all_tasks if not t.get("completed")]
    done = [t for t in all_tasks if t.get("completed")]
    today = date.today()

    overdue = [t for t in tasks if _current_days_to_deadline(t, today) < 0]
    due_today = [t for t in tasks if _current_days_to_deadline(t, today) == 0]
    this_week = [t for t in tasks if 0 <= _current_days_to_deadline(t, today) <= 7]

    next_task = store.peek_top_task()
    reminders = build_reminders(store, limit=4)

    total_hours = round(sum(insights.remaining_hours(t) for t in tasks), 1)
    week_hours = round(sum(insights.remaining_hours(t) for t in this_week), 1)
    risk_rows = insights.all_task_risks(store)
    progress = insights.progress_summary(store)

    return {
        "today": today.isoformat(),
        "open_tasks": len(tasks),
        "completed_tasks": len(done),
        "overdue": len(overdue),
        "due_today": len(due_today),
        "due_this_week": len(this_week),
        "total_hours": total_hours,
        "week_hours": week_hours,
        "next_task": next_task,
        "recommended_action": insights.recommended_next_action(store),
        "deadline_risks": risk_rows[:5],
        "high_risk_count": sum(r["level"] in {"High", "Critical"} for r in risk_rows),
        "overall_progress": progress["overall_progress"],
        "actual_hours": progress["actual_hours"],
        "remaining_hours": progress["remaining_hours"],
        "available_hours_per_day": float(store.settings.get("available_hours_per_day", 3.0)),
        "upcoming": tasks[:5],
        "reminders": reminders,
        "resources_indexed": store.resource_index.size,
        "keywords_indexed": store.keyword_trie.word_count,
    }
