"""Explainable task progress, workload risk, and next-action guidance."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from ..ds.binary_heap import BinaryMaxHeap
from .store import KairosStore

RISK_LEVELS = ("Low", "Moderate", "High", "Critical")


def remaining_hours(task: Dict[str, Any]) -> float:
    if "remaining_hours" in task:
        return max(0.0, float(task["remaining_hours"]))
    effort = max(0.0, float(task.get("estimated_hours", 0)))
    progress = min(100.0, max(0.0, float(task.get("progress", 0))))
    return round(effort * (1 - progress / 100), 2)


def days_to_deadline(task: Dict[str, Any], today: Optional[date] = None) -> int:
    today = today or date.today()
    try:
        return (date.fromisoformat(str(task["deadline"])[:10]) - today).days
    except (KeyError, ValueError, TypeError):
        return 0


def risk_for_task(
    task: Dict[str, Any], available_hours_per_day: float, today: Optional[date] = None
) -> Dict[str, Any]:
    """Compare remaining work with the time available before the due date.

    The result is a workload estimate, not a probability. The available window
    counts today and the deadline day; overdue work has no remaining window.
    """
    days = days_to_deadline(task, today)
    remaining = remaining_hours(task)
    available = max(0.0, float(available_hours_per_day)) * max(0, days + 1)
    ratio = remaining / available if available > 0 else (float("inf") if remaining else 0.0)
    priority = str(task.get("priority", "MEDIUM")).upper()

    if remaining <= 0:
        level = "Low"
    elif days < 0 or available <= 0 or ratio >= 2:
        level = "Critical"
    elif ratio > 1:
        level = "High"
    elif ratio >= 0.75 or days <= 1:
        level = "Moderate"
    else:
        level = "Low"

    # Priority raises a near-capacity deadline by one band, while the workload
    # ratio remains the central signal.
    if priority in {"HIGH", "CRITICAL"} and level == "Moderate" and ratio >= 0.9:
        level = "High"

    if remaining <= 0:
        explanation = "No estimated work remains."
    elif days < 0:
        explanation = f"{level} risk: about {remaining:g} h remain and the deadline is overdue."
    elif available <= 0:
        explanation = f"{level} risk: about {remaining:g} h remain, with no available hours before the deadline."
    else:
        explanation = (
            f"{level} risk: about {remaining:g} h remain, with "
            f"{available:g} h available before the deadline."
        )
    if priority in {"HIGH", "CRITICAL"} and remaining > 0:
        explanation += f" Priority is {priority.lower()}."

    return {
        "task_id": task["id"],
        "title": task["title"],
        "level": level,
        "days_to_deadline": days,
        "remaining_hours": round(remaining, 2),
        "available_hours_before_deadline": round(available, 2),
        "workload_ratio": round(ratio, 2) if ratio != float("inf") else None,
        "explanation": explanation,
    }


def all_task_risks(store: KairosStore) -> List[Dict[str, Any]]:
    available_per_day = float(store.settings.get("available_hours_per_day", 3.0))
    risks = [
        risk_for_task(task, available_per_day)
        for task in store.tasks_by_deadline()
        if not task.get("completed")
    ]
    rank = {"Low": 0, "Moderate": 1, "High": 2, "Critical": 3}
    return sorted(
        risks,
        key=lambda risk: (
            -rank[risk["level"]],
            risk["days_to_deadline"],
            -risk["remaining_hours"],
        ),
    )


def recommended_next_action(store: KairosStore) -> Optional[Dict[str, Any]]:
    available_now = max(0.0, float(store.settings.get("available_hours_per_day", 3.0)))
    if available_now <= 0:
        return None

    risks = {r["task_id"]: r for r in all_task_risks(store)}
    risk_weight = {"Low": 0, "Moderate": 100, "High": 200, "Critical": 300}
    heap = BinaryMaxHeap(name="NextActionHeap")
    for task in store.tasks_by_deadline():
        if task.get("completed") or remaining_hours(task) <= 0:
            continue
        risk = risks[task["id"]]
        score = risk_weight[risk["level"]] + float(task.get("urgency_score", 0))
        heap.insert(score, task)

    task = heap.peek()
    if task is None:
        return None

    risk = risks[task["id"]]
    remaining = remaining_hours(task)
    session_minutes = int(max(1, min(90, available_now * 60, remaining * 60)))
    why = [
        f"{risk['level'].lower()} deadline risk",
        f"{remaining:g} h of estimated work remains",
        risk["explanation"],
        f"{float(task.get('progress', 0)):g}% complete",
        f"{task.get('priority', 'MEDIUM').lower()} priority",
    ]
    return {
        "task": task,
        "risk": risk,
        "available_hours_now": available_now,
        "recommended_session_minutes": session_minutes,
        "reasons": why,
        "label": "Recommended next action",
    }


def progress_summary(store: KairosStore) -> Dict[str, Any]:
    tasks = store.tasks_by_deadline()
    open_tasks = [task for task in tasks if not task.get("completed")]
    completed_tasks = [task for task in tasks if task.get("completed")]
    total_effort = sum(max(0.0, float(task.get("estimated_hours", 0))) for task in tasks)
    weighted_done = sum(
        max(0.0, float(task.get("estimated_hours", 0)))
        * min(100.0, max(0.0, float(task.get("progress", 0)))) / 100
        for task in tasks
    )
    average = (
        weighted_done / total_effort * 100
        if total_effort > 0
        else (100.0 if tasks and len(completed_tasks) == len(tasks) else 0.0)
    )
    risk_by_id = {r["task_id"]: r for r in all_task_risks(store)}
    rows = []
    for task in tasks:
        rows.append({
            **task,
            "risk": risk_by_id.get(task["id"]),
            "remaining_hours": remaining_hours(task),
        })

    return {
        "overall_progress": round(average, 1),
        "completed_tasks": len(completed_tasks),
        "remaining_tasks": len(open_tasks),
        "planned_hours": round(sum(float(t.get("estimated_hours", 0)) for t in tasks), 1),
        "actual_hours": round(sum(float(t.get("actual_hours", 0)) for t in tasks), 1),
        "remaining_hours": round(sum(remaining_hours(t) for t in open_tasks), 1),
        "tasks": rows,
    }
