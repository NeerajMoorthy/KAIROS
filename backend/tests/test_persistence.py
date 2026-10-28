"""
Tests for the JSON snapshot layer added on top of the in-memory store.

The claim under test is narrow but real: a save followed by a restore must
reproduce the store closely enough that every structure the API depends on
(AVL order, heap top, hash lookup, trie search, mastery lookup) still works
identically afterwards — not just that the JSON round-trips.
"""

import json
import os

from app.services import adaptive, persistence
from app.services.resource_service import index_folder
from app.services.store import KairosStore


def _make_task(store: KairosStore, **overrides):
    task = {
        "id": store.next_task_id(),
        "title": overrides.get("title", "Revise AVL rotations"),
        "topic": overrides.get("topic", "avl tree"),
        "deadline": overrides.get("deadline", "2026-12-01"),
        "priority": overrides.get("priority", "HIGH"),
        "estimated_hours": overrides.get("estimated_hours", 4.0),
        "notes": overrides.get("notes", ""),
        "urgency_score": overrides.get("urgency_score", 42.5),
        "score_breakdown": {
            "priority_component": 30.0,
            "deadline_component": 10.0,
            "workload_component": 8.0,
            "overdue_penalty": 0.0,
            "days_to_deadline": 30,
            "formula": "x",
        },
        "created_at": "2026-09-01T00:00:00+00:00",
        "completed": False,
    }
    store.add_task(task)
    return task


def test_save_writes_a_readable_json_file(tmp_path):
    store = KairosStore()
    _make_task(store)
    path = str(tmp_path / "snap.json")

    result = persistence.save(store, path)
    assert os.path.exists(path)
    assert result["tasks"] == 1

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["version"] == persistence.SNAPSHOT_VERSION
    assert len(data["tasks"]) == 1


def test_save_is_atomic_and_leaves_no_tmp_file(tmp_path):
    store = KairosStore()
    _make_task(store)
    path = str(tmp_path / "snap.json")
    persistence.save(store, path)
    assert not os.path.exists(path + ".tmp")


def test_restore_rebuilds_a_working_store(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = KairosStore()
    t1 = _make_task(store, title="A", deadline="2026-10-01")
    _make_task(store, title="B", deadline="2026-11-01")
    index_folder(store, os.path.join(os.path.dirname(__file__), "..", "sample_resources"))
    adaptive.set_mastery(store, t1["id"], "Balance Factor", 20)

    path = str(tmp_path / "snap.json")
    saved = persistence.save(store, path)
    assert saved["tasks"] == 2
    assert saved["resources"] > 0
    assert saved["mastery"] == 1

    fresh = KairosStore()
    result = persistence.restore(fresh, path)
    assert result["loaded"] is True
    assert result["tasks"] == 2

    # AVL order survived
    assert [t["title"] for t in fresh.tasks_by_deadline()] == ["A", "B"]
    # heap survived
    assert fresh.peek_top_task() is not None
    # hash lookup survived
    assert fresh.get_task(t1["id"])["title"] == "A"
    # trie / resource search survived
    assert fresh.all_resources()
    # mastery survived and is readable through the normal API path
    progress = adaptive.get_progress(fresh, t1["id"])
    assert progress["overall_mastery"] == 20


def test_restore_replaces_rather_than_merges(tmp_path):
    store = KairosStore()
    _make_task(store, title="Keep me out")
    path = str(tmp_path / "snap.json")
    persistence.save(store, path)

    live = KairosStore()
    _make_task(live, title="Should be gone after restore")
    persistence.restore(live, path)

    titles = [t["title"] for t in live.tasks_by_deadline()]
    assert titles == ["Keep me out"]


def test_restore_missing_file_is_a_no_op_not_a_crash(tmp_path):
    store = KairosStore()
    _make_task(store, title="Untouched")
    result = persistence.restore(store, str(tmp_path / "does-not-exist.json"))
    assert result["loaded"] is False
    assert [t["title"] for t in store.tasks_by_deadline()] == ["Untouched"]


def test_autoload_on_startup_never_raises_on_a_corrupt_file(tmp_path):
    bad = tmp_path / "corrupt.json"
    bad.write_text("{not valid json", encoding="utf-8")
    store = KairosStore()
    result = persistence.autoload_on_startup(store, str(bad))
    assert result["loaded"] is False       # did not raise, store stays empty
    assert store.all_resources() == []


def test_autosave_on_shutdown_never_raises_on_an_unwritable_path():
    store = KairosStore()
    _make_task(store)
    # a directory as a "file" path is never writable — must not raise
    persistence.autosave_on_shutdown(store, path="/")


def test_status_reports_without_mutating_the_live_store(tmp_path):
    store = KairosStore()
    _make_task(store, title="Original")
    path = str(tmp_path / "snap.json")
    persistence.save(store, path)

    info = persistence.status(path)
    assert info["exists"] is True
    assert info["tasks"] == 1
    # calling status must not have touched the live store
    assert [t["title"] for t in store.tasks_by_deadline()] == ["Original"]


def test_status_on_missing_file():
    info = persistence.status("/tmp/definitely-not-a-kairos-snapshot.json")
    assert info["exists"] is False


def test_restore_syncs_id_sequences_avoiding_collisions(tmp_path):
    store = KairosStore()
    t1 = _make_task(store, title="Task 1")
    path = str(tmp_path / "snap.json")
    persistence.save(store, path)

    fresh = KairosStore()
    persistence.restore(fresh, path)
    next_id = fresh.next_task_id()
    assert next_id != t1["id"]
    assert int(next_id[1:]) > int(t1["id"][1:])


def test_restore_does_not_insert_completed_tasks_into_heap(tmp_path):
    store = KairosStore()
    task = _make_task(store, title="Completed Task")
    task["completed"] = True
    store.task_heap.remove_by(lambda tid: tid == task["id"])
    path = str(tmp_path / "snap.json")
    persistence.save(store, path)

    fresh = KairosStore()
    persistence.restore(fresh, path)
    assert fresh.peek_top_task() is None
    assert fresh.tasks_by_priority() == []
