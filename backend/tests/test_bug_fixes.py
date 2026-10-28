"""Regression tests for the bugs fixed in the 28 October 2026 audit."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import reminders, resource_service, scheduler
from app.services.store import store

client = TestClient(app)
TODAY = date.today()


@pytest.fixture(autouse=True)
def clean_store():
    store.reset()
    yield
    store.reset()


def create_task(title="Report", days=3, hours=4, priority="MEDIUM"):
    response = client.post(
        "/api/tasks",
        json={
            "title": title,
            "category": "Writing",
            "deadline": (TODAY + timedelta(days=days)).isoformat(),
            "priority": priority,
            "estimated_hours": hours,
        },
    )
    assert response.status_code == 201
    return response.json()["task"]


def test_urgency_is_recomputed_when_the_day_changes():
    """A score computed days ago must not keep ranking a now-urgent task low."""
    soon = create_task("Due soon", days=5, hours=1)
    later = create_task("Due later", days=2, hours=1, priority="HIGH")
    assert store.peek_top_task()["id"] == later["id"]

    # Pretend four days have passed: "Due soon" is due tomorrow, "Due later"
    # is overdue. Scores must follow the calendar, not the creation day.
    store.refresh_urgency_scores(today=TODAY + timedelta(days=4))
    refreshed = store.get_task(soon["id"])
    assert refreshed["score_breakdown"]["days_to_deadline"] == 1
    overdue = store.get_task(later["id"])
    assert overdue["score_breakdown"]["overdue_penalty"] == 40
    assert store.task_heap.is_valid_heap()


def test_scores_refresh_automatically_after_midnight():
    task = create_task(days=3)
    store._scored_on = TODAY - timedelta(days=2)  # scores are two days old
    store.task_index.search(task["id"])["urgency_score"] = 0.0
    listed = client.get("/api/tasks?view=priority").json()["tasks"]
    assert listed[0]["urgency_score"] > 0


def test_dp_never_books_more_hours_than_capacity():
    items = [scheduler.Item(f"T{i}", f"t{i}", 10.0, 0.7, "2026-12-01") for i in range(3)]
    run = scheduler.dynamic_programming(items, 1.5)
    assert run["total_hours"] <= 1.5


def test_reopening_a_task_with_status_resets_progress():
    task = create_task(hours=4)
    client.patch(f"/api/tasks/{task['id']}", json={"completed": True})
    reopened = client.patch(f"/api/tasks/{task['id']}", json={"status": "in_progress"}).json()["task"]
    assert reopened["completed"] is False
    assert reopened["status"] == "in_progress"
    assert reopened["progress"] == 0
    assert reopened["remaining_hours"] == 4


def test_explicit_status_completed_wins_over_partial_progress():
    task = create_task(hours=4)
    done = client.patch(
        f"/api/tasks/{task['id']}", json={"status": "completed", "progress": 40}
    ).json()["task"]
    assert done["completed"] is True and done["progress"] == 100 and done["remaining_hours"] == 0


def test_web_suggestions_are_not_added_to_the_library():
    before = store.resource_index.size
    web = resource_service.fetch_web_resources(store, "graph theory", limit=3)
    assert web and all(r["source"] == "web" for r in web)
    assert store.resource_index.size == before
    assert store.keyword_trie.prefix_search("web") == []


def test_reminder_workload_follows_task_progress():
    task = create_task(hours=10)
    client.patch(f"/api/tasks/{task['id']}", json={"progress": 80})
    reminder = reminders.build_reminders(store)[0]
    assert reminder["remaining_hours"] == 2


def test_hosted_server_only_indexes_allowed_folders(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    (allowed / "notes.md").write_text("graph notes")
    monkeypatch.setenv("KAIROS_ALLOWED_ROOTS", str(allowed))
    assert client.post("/api/resources/index", json={"path": str(allowed)}).status_code == 200
    outside = client.post("/api/resources/index", json={"path": str(tmp_path)})
    assert outside.status_code == 400
