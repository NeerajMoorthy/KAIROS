"""Small, persistent focus-session lifecycle tied to task progress."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .store import KairosStore, now_iso
from .task_analyzer import analyze


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def elapsed_seconds(session: Dict[str, Any], now: Optional[datetime] = None) -> int:
    seconds = max(0, int(session.get("elapsed_seconds", 0)))
    if session.get("status") == "active" and session.get("started_at"):
        seconds += max(0, int(((now or _now()) - _parse_time(session["started_at"])).total_seconds()))
    return seconds


def present(session: Dict[str, Any]) -> Dict[str, Any]:
    return {**session, "elapsed_seconds": elapsed_seconds(session)}


def list_sessions(store: KairosStore) -> Dict[str, Any]:
    sessions = [present(item) for item in store.focus_sessions()]
    sessions.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    current = next((item for item in sessions if item["status"] in {"active", "paused"}), None)
    return {"current": current, "sessions": sessions[:50]}


def start_session(store: KairosStore, task_id: str, objective: str = "") -> Dict[str, Any]:
    task = store.get_task(task_id)
    if task is None:
        raise LookupError("Task not found.")
    if task.get("completed"):
        raise ValueError("A completed task cannot start a focus session.")
    if any(s.get("status") in {"active", "paused"} for s in store.focus_sessions()):
        raise ValueError("Finish or resume the current focus session first.")

    stamp = now_iso()
    session = {
        "id": store.next_focus_session_id(),
        "task_id": task_id,
        "task_title": task["title"],
        "objective": objective.strip() or task.get("description") or task["title"],
        "status": "active",
        "created_at": stamp,
        "started_at": stamp,
        "paused_at": None,
        "completed_at": None,
        "elapsed_seconds": 0,
    }
    store.add_focus_session(session)
    if task.get("status") != "in_progress":
        store.update_task(task_id, {"status": "in_progress", "updated_at": stamp})
    return present(session)


def update_session(
    store: KairosStore,
    session_id: str,
    action: str,
    progress: Optional[float] = None,
) -> Dict[str, Any]:
    session = store.get_focus_session(session_id)
    if session is None:
        raise LookupError("Focus session not found.")

    stamp = now_iso()
    now = _now()
    status = session.get("status")
    if action == "pause":
        if status != "active":
            raise ValueError("Only an active session can be paused.")
        session["elapsed_seconds"] = elapsed_seconds(session, now)
        session["status"] = "paused"
        session["started_at"] = None
        session["paused_at"] = stamp
    elif action == "resume":
        if status != "paused":
            raise ValueError("Only a paused session can be resumed.")
        session["status"] = "active"
        session["started_at"] = stamp
        session["paused_at"] = None
    elif action == "complete":
        if status not in {"active", "paused"}:
            raise ValueError("This session has already ended.")
        total_seconds = elapsed_seconds(session, now)
        session["elapsed_seconds"] = total_seconds
        session["status"] = "completed"
        session["started_at"] = None
        session["completed_at"] = stamp

        task = store.get_task(session["task_id"])
        if task is not None:
            actual_hours = round(float(task.get("actual_hours", 0)) + total_seconds / 3600, 4)
            already_completed = bool(task.get("completed"))
            if already_completed:
                new_progress = 100.0
            elif progress is None:
                estimated = max(0.01, float(task.get("estimated_hours", 0.01)))
                new_progress = min(100.0, float(task.get("progress", 0)) + total_seconds / 3600 / estimated * 100)
            else:
                new_progress = float(progress)
            completed = new_progress >= 100
            remaining = round(float(task.get("estimated_hours", 0)) * (1 - new_progress / 100), 2)
            due = datetime.fromisoformat(str(task["deadline"])[:10]).date()
            urgency, breakdown = analyze(due, task["priority"], remaining)
            store.update_task(session["task_id"], {
                "progress": round(new_progress, 1),
                "remaining_hours": remaining,
                "actual_hours": actual_hours,
                "completed": completed,
                "status": "completed" if completed else "in_progress",
                "updated_at": stamp,
                "urgency_score": urgency,
                "score_breakdown": breakdown,
            })
    else:
        raise ValueError("Action must be pause, resume, or complete.")

    # HashTable insertion replaces the current value under this id.
    store.add_focus_session(session)
    return present(session)
