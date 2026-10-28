"""Regression coverage for KAIROS v1.0's task-to-focus workflow."""

from datetime import date, datetime, timedelta, timezone
import os
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import insights, persistence
from app.services.store import store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_store():
    store.reset()
    yield
    store.reset()


def create_task(title="Project Report", days=3, hours=5, priority="HIGH"):
    response = client.post(
        "/api/tasks",
        json={
            "title": title,
            "category": "Research and writing",
            "project": "Final Project",
            "description": "Draft, cite, and review the report.",
            "deadline": (date.today() + timedelta(days=days)).isoformat(),
            "priority": priority,
            "estimated_hours": hours,
        },
    )
    assert response.status_code == 201
    return response.json()["task"]


def test_task_edit_progress_and_search_keep_indexes_consistent():
    task = create_task()
    response = client.patch(
        f"/api/tasks/{task['id']}",
        json={
            "title": "Final Project Report",
            "deadline": (date.today() + timedelta(days=1)).isoformat(),
            "priority": "CRITICAL",
            "estimated_hours": 6,
            "progress": 50,
        },
    )
    assert response.status_code == 200
    updated = response.json()["task"]
    assert updated["remaining_hours"] == 3
    assert updated["status"] == "in_progress"
    assert updated["project"] == "Final Project"
    found = client.get("/api/tasks?view=deadline&q=final%20project&status=in_progress").json()["tasks"]
    assert [row["id"] for row in found] == [task["id"]]

    completed = client.patch(f"/api/tasks/{task['id']}", json={"completed": True}).json()["task"]
    assert completed["progress"] == 100
    assert completed["remaining_hours"] == 0
    assert client.get("/api/tasks?view=priority").json()["tasks"] == []

    reopened = client.patch(f"/api/tasks/{task['id']}", json={"completed": False}).json()["task"]
    assert reopened["status"] == "todo"
    assert reopened["progress"] == 0
    assert reopened["remaining_hours"] == 6
    assert client.get("/api/tasks?view=priority").json()["tasks"][0]["id"] == task["id"]


def test_task_validation_rejects_blank_titles_invalid_dates_and_effort():
    assert client.post("/api/tasks", json={"title": "  "}).status_code == 422
    base = {
        "title": "Review",
        "deadline": "not-a-date",
        "estimated_hours": 1,
    }
    assert client.post("/api/tasks", json=base).status_code == 422
    base["deadline"] = (date.today() + timedelta(days=1)).isoformat()
    base["estimated_hours"] = -1
    assert client.post("/api/tasks", json=base).status_code == 422


def test_risk_states_compare_effort_with_hours_before_deadline():
    today = date(2026, 10, 8)
    task = {
        "id": "T-RISK", "title": "Project Report", "deadline": "2026-10-09",
        "priority": "HIGH", "progress": 0, "estimated_hours": 6,
        "remaining_hours": 6, "completed": False,
    }
    high = insights.risk_for_task(task, 2, today)
    assert high["level"] == "High"
    assert high["available_hours_before_deadline"] == 4
    assert "6 h remain" in high["explanation"] and "4 h available" in high["explanation"]
    assert insights.risk_for_task(task, 0, today)["level"] == "Critical"
    overdue = {**task, "deadline": "2026-10-07"}
    assert insights.risk_for_task(overdue, 5, today)["level"] == "Critical"
    low = {**task, "remaining_hours": 2, "deadline": "2026-10-15"}
    assert insights.risk_for_task(low, 3, today)["level"] == "Low"


def test_dashboard_recommends_an_action_and_explains_the_factors():
    task = create_task(days=1, hours=5)
    client.patch("/api/settings", json={"available_hours_per_day": 1.5})
    dashboard = client.get("/api/dashboard").json()
    action = dashboard["recommended_action"]
    assert action["task"]["id"] == task["id"]
    assert action["risk"]["level"] == "High"
    assert action["available_hours_now"] == 1.5
    assert action["recommended_session_minutes"] == 90
    assert any("priority" in reason for reason in action["reasons"])
    assert dashboard["deadline_risks"][0]["task_id"] == task["id"]


def test_zero_and_limited_availability_never_overbook_the_plan():
    task = create_task(hours=5)
    empty = client.post(
        "/api/schedule",
        json={"capacity_hours": 0, "daily_hours": 0, "include_revision": False},
    ).json()
    assert empty["run"]["total_hours"] == 0
    assert empty["timeline"] == []
    assert [row["id"] for row in empty["deferred"]] == [task["id"]]

    limited = client.post(
        "/api/schedule",
        json={"capacity_hours": 500, "daily_hours": 1, "include_revision": False},
    ).json()
    assert limited["capacity_hours"] == 7
    assert limited["run"]["total_hours"] <= 7
    assert all(day["hours"] <= 1 for day in limited["timeline"])
    assert len(limited["timeline"]) <= 7

    adaptive = client.post(
        "/api/plan",
        json={"capacity_hours": 10.5, "daily_hours": 1.5, "horizon_days": 7},
    ).json()
    assert adaptive["scheduled_hours"] == 5
    assert all(day["hours"] <= 1.5 for day in adaptive["timeline"])
    assert adaptive["deferred"] == []


def test_adaptive_plan_schedules_only_time_available_before_capacity_runs_out():
    task = create_task(days=1, hours=5)
    client.patch("/api/settings", json={"available_hours_per_day": 1.5})
    plan = client.post(
        "/api/plan",
        json={"capacity_hours": 10.5, "daily_hours": 1.5},
    ).json()
    assert plan["scheduled_hours"] == 5
    assert len(plan["timeline"]) == 4
    assert all(day["hours"] <= 1.5 for day in plan["timeline"])
    # The planner keeps working on an overdue task and marks blocks after its due date.
    assert plan["timeline"][-1]["blocks"][0]["task_id"] == task["id"]
    assert plan["timeline"][-1]["blocks"][0]["overdue"] is True


def test_focus_session_lifecycle_updates_actual_effort_progress_and_plan():
    task = create_task(hours=4)
    started = client.post("/api/focus/sessions", json={"task_id": task["id"], "objective": "Draft the findings"})
    assert started.status_code == 201
    session = started.json()["session"]
    assert session["status"] == "active"
    assert client.get(f"/api/tasks/{task['id']}").json()["task"]["status"] == "in_progress"
    assert client.post("/api/focus/sessions", json={"task_id": task["id"]}).status_code == 409

    paused = client.patch(f"/api/focus/sessions/{session['id']}", json={"action": "pause"}).json()["session"]
    assert paused["status"] == "paused"
    assert client.patch(f"/api/focus/sessions/{session['id']}", json={"action": "resume"}).json()["session"]["status"] == "active"

    stored = store.get_focus_session(session["id"])
    stored["started_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    finished = client.patch(
        f"/api/focus/sessions/{session['id']}",
        json={"action": "complete", "progress": 40},
    )
    assert finished.status_code == 200
    assert finished.json()["session"]["status"] == "completed"
    updated = finished.json()["task"]
    assert updated["actual_hours"] == 1
    assert updated["progress"] == 40
    assert updated["remaining_hours"] == 2.4
    assert client.get("/api/focus/sessions").json()["current"] is None

    plan = client.post("/api/schedule", json={"capacity_hours": 20, "daily_hours": 4, "include_revision": False}).json()
    assert plan["run"]["total_hours"] == 2.4


def test_focus_rejects_missing_and_completed_tasks():
    assert client.post("/api/focus/sessions", json={"task_id": "missing"}).status_code == 404
    task = create_task()
    client.patch(f"/api/tasks/{task['id']}", json={"completed": True})
    assert client.post("/api/focus/sessions", json={"task_id": task["id"]}).status_code == 409


def test_progress_summary_tracks_effort_and_workload_risk():
    first = create_task(hours=4)
    second = create_task(title="Presentation", hours=2, priority="MEDIUM")
    client.patch(f"/api/tasks/{first['id']}", json={"progress": 50})
    client.patch(f"/api/tasks/{second['id']}", json={"completed": True})
    summary = client.get("/api/progress").json()
    assert summary["completed_tasks"] == 1
    assert summary["remaining_tasks"] == 1
    assert summary["planned_hours"] == 6
    assert summary["remaining_hours"] == 2
    assert summary["overall_progress"] == 66.7
    assert client.get("/api/deadline-risk").json()["risks"][0]["task_id"] == first["id"]


def test_docx_and_pptx_content_is_indexed_from_the_selected_folder(tmp_path):
    docx_path = tmp_path / "report.docx"
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr("word/document.xml", "<document><p>citation methodology appendix</p></document>")
    pptx_path = tmp_path / "slides.pptx"
    with zipfile.ZipFile(pptx_path, "w") as archive:
        archive.writestr("ppt/slides/slide1.xml", "<slide><p>research presentation rehearsal</p></slide>")

    result = client.post("/api/resources/index", json={"path": str(tmp_path)})
    assert result.status_code == 200
    resources = client.get("/api/resources").json()["resources"]
    by_name = {item["title"]: item for item in resources}
    assert "citation" in by_name["report.docx"]["content_keywords"]
    assert "research" in by_name["slides.pptx"]["content_keywords"]
    assert client.get("/api/resources/search?q=citation&web=false").json()["results"][0]["resource"]["title"] == "report.docx"


def test_reindex_refreshes_changed_file_keywords_without_stale_trie_payloads(tmp_path):
    notes = tmp_path / "reading.md"
    notes.write_text("citation methodology", encoding="utf-8")
    first = client.post("/api/resources/index", json={"path": str(tmp_path)}).json()
    assert first["indexed"] == 1
    assert client.get("/api/resources/search?q=citation&web=false").json()["local_matches"] == 1

    notes.write_text("budget timeline planning", encoding="utf-8")
    second = client.post("/api/resources/index", json={"path": str(tmp_path)}).json()
    assert second["updated"] == 1
    assert second["indexed"] == 0
    assert client.get("/api/resources/search?q=citation&web=false").json()["local_matches"] == 0
    refreshed = client.get("/api/resources/search?q=timeline&web=false").json()
    assert refreshed["local_matches"] == 1
    assert "timeline" in refreshed["results"][0]["resource"]["content_keywords"]


def test_snapshot_round_trips_settings_and_focus_sessions(tmp_path):
    task = create_task()
    store.settings["available_hours_per_day"] = 1.5
    session = client.post("/api/focus/sessions", json={"task_id": task["id"]}).json()["session"]
    path = str(tmp_path / "v1.json")
    persistence.save(store, path)

    restored = type(store)()
    result = persistence.restore(restored, path)
    assert result["loaded"] is True
    assert restored.settings["available_hours_per_day"] == 1.5
    assert restored.get_focus_session(session["id"])["task_id"] == task["id"]
    assert restored.get_task(task["id"])["remaining_hours"] == 5


def test_end_to_end_project_report_flow_replans_after_a_focus_session():
    task = create_task(days=1, hours=5)
    indexed = client.post(
        "/api/resources/index",
        json={"path": "sample_resources/demo", "tags": ["project"]},
    )
    assert indexed.status_code == 200 and indexed.json()["indexed"] >= 1
    found = client.get("/api/resources/search?q=project%20report&web=false").json()
    assert found["local_matches"] >= 1
    assert found["results"][0]["reasons"]

    client.patch("/api/settings", json={"available_hours_per_day": 1.5})
    before = client.post("/api/plan", json={"capacity_hours": 10.5, "daily_hours": 1.5}).json()
    assert before["scheduled_hours"] == 5
    assert client.get("/api/dashboard").json()["recommended_action"]["task"]["id"] == task["id"]

    session = client.post("/api/focus/sessions", json={"task_id": task["id"], "objective": "Draft the report"}).json()["session"]
    store.get_focus_session(session["id"])["started_at"] = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
    finished = client.patch(
        f"/api/focus/sessions/{session['id']}",
        json={"action": "complete", "progress": 30},
    ).json()
    assert finished["task"]["remaining_hours"] == 3.5
    after = client.post("/api/plan", json={"capacity_hours": 10.5, "daily_hours": 1.5}).json()
    assert after["scheduled_hours"] == 3.5
    assert client.get("/api/deadline-risk").json()["risks"][0]["task_id"] == task["id"]
