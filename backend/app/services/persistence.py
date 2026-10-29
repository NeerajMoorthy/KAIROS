"""
Lightweight state persistence — a JSON snapshot of the whole store.

This is deliberately NOT the "add a database" item from the README's Known
Limitations. There is no schema, no migrations, no query engine — it is a
full save/restore of exactly what the store already knows how to hand back
through its own structures (task_index, resource_index, mastery_index all
expose `.values()`; nothing here re-derives or re-shapes a record). A real
database is still the right next step for concurrent users, partial
queries, or history — this module removes the single sharpest edge of an
in-memory demo instead: restarting the server (including uvicorn's own
--reload, which respawns the process on every code change) no longer
erases a student's tasks.

Restore rebuilds through the store's own add_task / add_resource / mastery
insert calls, so the AVL tree, heap, hash tables and trie are all
repopulated from scratch — this is a real restore, not a pickle of
internal node objects, so it survives the data-structure code itself
changing between a save and a load.

Durability
----------
While the server runs (between FastAPI startup and shutdown), every
successful request that can change data triggers `autosave` — see the
middleware in main.py. Each save writes a complete snapshot to a temporary
file and atomically replaces the previous one, so an abrupt stop loses at
most the request that was in flight, never the whole session. Saves are
serialised with a lock because FastAPI runs sync endpoints on a thread pool.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .adaptive import _key as mastery_key
from .store import KairosStore, now_iso

SNAPSHOT_VERSION = 3
SUPPORTED_VERSIONS = {1, 2, SNAPSHOT_VERSION}
DEFAULT_SNAPSHOT_PATH = os.environ.get("KAIROS_SNAPSHOT_PATH", "kairos_snapshot.json")

_save_lock = threading.Lock()
# Autosave is switched on by the app's startup hook, so importing the app in
# tests or scripts never writes a snapshot as a side effect.
_autosave = {"enabled": False, "last_saved_at": None, "last_error": None, "saves": 0}


def _resolve(path: Optional[str]) -> str:
    """Read the default at call time so tests and scripts can redirect it."""
    return path or DEFAULT_SNAPSHOT_PATH


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def snapshot(store: KairosStore) -> Dict[str, Any]:
    """Collect the store's records into a plain JSON-serializable dict.

    Tasks and resources are already JSON-friendly by the time they reach the
    store (main.py stores deadlines as ISO strings, not date objects), so
    this does no re-shaping — it just reads what `.values()` returns.
    """
    return {
        "version": SNAPSHOT_VERSION,
        "saved_at": _now_iso(),
        "tasks": store.task_index.values(),
        "resources": store.resource_index.values(),
        "mastery": store.mastery_index.values(),
        "focus_sessions": store.focus_sessions(),
        "folders": store.folders(),
        "settings": store.settings,
    }


def save(store: KairosStore, path: Optional[str] = None) -> Dict[str, Any]:
    """Write a snapshot to disk. Writes to a temp file and renames over the
    target, so a crash mid-write never leaves a half-written, corrupt
    snapshot behind — the rename is atomic on both POSIX and Windows."""
    path = _resolve(path)
    with _save_lock:
        data = snapshot(store)
        text = json.dumps(data, indent=2)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    return {
        "path": os.path.abspath(path),
        "saved_at": data["saved_at"],
        "tasks": len(data["tasks"]),
        "resources": len(data["resources"]),
        "mastery": len(data["mastery"]),
        "focus_sessions": len(data["focus_sessions"]),
        "folders": len(data["folders"]),
    }


def autosave(store: KairosStore, path: Optional[str] = None) -> bool:
    """Save after a change if autosave is on. Never raises: a failed save is
    recorded and reported by status(), and the request that triggered it
    still succeeds. Returns True when a snapshot was written."""
    if not _autosave["enabled"]:
        return False
    try:
        result = save(store, path)
    except Exception as exc:  # disk full, permissions, path is a folder...
        _autosave["last_error"] = f"{type(exc).__name__}: {exc}"
        return False
    _autosave["last_saved_at"] = result["saved_at"]
    _autosave["last_error"] = None
    _autosave["saves"] += 1
    return True


def set_autosave(enabled: bool) -> None:
    _autosave["enabled"] = bool(enabled)


def autosave_requested() -> bool:
    """KAIROS_AUTOSAVE=0 (or false/off/no) turns per-change saving off."""
    return os.environ.get("KAIROS_AUTOSAVE", "1").strip().lower() not in {"0", "false", "off", "no"}


def autosave_status() -> Dict[str, Any]:
    return dict(_autosave)


def status(path: Optional[str] = None) -> Dict[str, Any]:
    """Report what is on disk without touching the live store."""
    path = _resolve(path)
    if not os.path.exists(path):
        return {"path": os.path.abspath(path), "exists": False, "autosave": autosave_status()}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "path": os.path.abspath(path), "exists": True, "readable": False,
            "reason": str(exc), "autosave": autosave_status(),
        }
    return {
        "path": os.path.abspath(path),
        "exists": True,
        "readable": True,
        "saved_at": data.get("saved_at"),
        "tasks": len(data.get("tasks", [])),
        "resources": len(data.get("resources", [])),
        "mastery": len(data.get("mastery", [])),
        "focus_sessions": len(data.get("focus_sessions", [])),
        "folders": len(data.get("folders", [])),
        "autosave": autosave_status(),
    }


def restore(store: KairosStore, path: Optional[str] = None) -> Dict[str, Any]:
    """Replace the store's contents with what is on disk."""
    path = _resolve(path)
    if not os.path.exists(path):
        return {"path": os.path.abspath(path), "loaded": False, "reason": "no snapshot file"}

    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    apply_snapshot(store, data)

    return {
        "path": os.path.abspath(path),
        "loaded": True,
        "saved_at": data.get("saved_at"),
        "tasks": len(data.get("tasks", [])),
        "resources": len(data.get("resources", [])),
        "mastery": len(data.get("mastery", [])),
        "focus_sessions": len(data.get("focus_sessions", [])),
        "folders": len(data.get("folders", [])),
    }


def apply_snapshot(store: KairosStore, data: Any) -> None:
    """Replace the store's contents with a snapshot dict (from a file or an
    account's saved workspace). Raises ValueError for an invalid snapshot."""
    if not isinstance(data, dict) or data.get("version", 1) not in SUPPORTED_VERSIONS:
        raise ValueError("Unsupported or invalid KAIROS snapshot.")
    for key in ("tasks", "resources", "mastery", "focus_sessions", "folders"):
        if key in data and not isinstance(data[key], list):
            raise ValueError(f"Snapshot field '{key}' must be a list.")
    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        raise ValueError("Snapshot settings must be an object.")

    # Build and validate a replacement before mutating the live store, so a
    # malformed record cannot leave only part of the user's data restored.
    replacement = KairosStore()
    for task in data.get("tasks", []):
        replacement.add_task(task)
    for resource in data.get("resources", []):
        # older versions stored web suggestions in the library; drop them
        if resource.get("source") == "web":
            continue
        replacement.add_resource(resource)
    for record in data.get("mastery", []):
        replacement.mastery_index.insert(mastery_key(record["task_id"], record["concept"]), record)
    saved_at = data.get("saved_at") or now_iso()
    saved_time = datetime.fromisoformat(saved_at)
    if saved_time.tzinfo is None:
        saved_time = saved_time.replace(tzinfo=timezone.utc)
    for raw_session in data.get("focus_sessions", []):
        session = dict(raw_session)
        if session.get("status") == "active" and session.get("started_at"):
            started = datetime.fromisoformat(session["started_at"])
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            session["elapsed_seconds"] = int(max(
                0,
                int(session.get("elapsed_seconds", 0))
                + (saved_time - started).total_seconds(),
            ))
            session["status"] = "paused"
            session["started_at"] = None
            session["paused_at"] = saved_at
        replacement.add_focus_session(session)
    for folder in data.get("folders", []):
        if not isinstance(folder, dict) or not folder.get("path"):
            raise ValueError("Snapshot folder records need a path.")
        replacement.upsert_folder(dict(folder))
    replacement.settings.update(settings)
    replacement.sync_sequences()
    # scores in the file were computed on the day it was saved
    replacement.refresh_urgency_scores()
    store.__dict__.clear()
    store.__dict__.update(replacement.__dict__)


def autoload_on_startup(store: KairosStore, path: Optional[str] = None) -> Dict[str, Any]:
    """Best-effort restore at process start. Never raises — a missing or
    corrupt snapshot must not stop the server from starting; it just starts
    empty, exactly as it always did before this module existed."""
    path = _resolve(path)
    try:
        if os.path.exists(path):
            return restore(store, path)
    except Exception as exc:  # pragma: no cover - defensive, see docstring
        return {"path": os.path.abspath(path), "loaded": False, "reason": str(exc)}
    return {"path": os.path.abspath(path), "loaded": False, "reason": "no snapshot file"}


def autosave_on_shutdown(store: KairosStore, path: Optional[str] = None) -> None:
    """Best-effort save at process stop. Never raises — a failed save on the
    way out must not turn a clean shutdown into a crash."""
    try:
        save(store, path)
    except Exception:  # pragma: no cover - defensive, see docstring
        pass
