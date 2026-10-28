"""End-to-end API tests covering the whole KAIROS workflow."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.store import store


@pytest.fixture(autouse=True)
def clean_store():
    store.reset()
    yield
    store.reset()


client = TestClient(app)
TODAY = date.today()


def make_task(title="Assignment", topic="avl tree", days=3, priority="HIGH", hours=4):
    return client.post(
        "/api/tasks",
        json={
            "title": title,
            "topic": topic,
            "deadline": (TODAY + timedelta(days=days)).isoformat(),
            "priority": priority,
            "estimated_hours": hours,
        },
    )


# --------------------------------------------------------------------- #
# meta
# --------------------------------------------------------------------- #
def test_health_reports_identity():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["name"] == "KAIROS"
    assert "urgency" in body["urgency_formula"]


def test_no_trace_endpoint_remains():
    assert client.get("/api/trace").status_code == 404


# --------------------------------------------------------------------- #
# tasks
# --------------------------------------------------------------------- #
def test_create_task_returns_score_and_concepts():
    body = make_task().json()
    assert body["task"]["urgency_score"] > 0
    assert body["task"]["score_breakdown"]["days_to_deadline"] == 3
    assert len(body["concepts"]) == 5          # AVL concept chain


def test_deadline_view_is_sorted_by_deadline():
    make_task(title="C", days=10)
    make_task(title="A", days=1)
    make_task(title="B", days=5)
    body = client.get("/api/tasks?view=deadline").json()
    assert [t["title"] for t in body["tasks"]] == ["A", "B", "C"]


def test_priority_view_is_sorted_by_urgency_desc():
    make_task(title="low", days=30, priority="LOW", hours=1)
    make_task(title="crit", days=0, priority="CRITICAL", hours=10)
    make_task(title="mid", days=7, priority="MEDIUM", hours=3)
    body = client.get("/api/tasks?view=priority").json()
    scores = [t["urgency_score"] for t in body["tasks"]]
    assert scores == sorted(scores, reverse=True)
    assert body["tasks"][0]["title"] == "crit"


def test_both_views_hold_the_same_tasks():
    for i in range(6):
        make_task(title=f"t{i}", days=i * 2)
    d = client.get("/api/tasks?view=deadline").json()["tasks"]
    p = client.get("/api/tasks?view=priority").json()["tasks"]
    assert {t["id"] for t in d} == {t["id"] for t in p}


def test_next_task_is_heap_peek():
    make_task(title="calm", days=40, priority="LOW", hours=1)
    make_task(title="urgent", days=0, priority="CRITICAL", hours=9)
    body = client.get("/api/tasks/next").json()
    assert body["task"]["title"] == "urgent"


def test_complete_task_leaves_priority_queue_but_stays_in_avl():
    tid = make_task().json()["task"]["id"]
    make_task(title="other", days=9)
    client.patch(f"/api/tasks/{tid}", json={"completed": True})
    assert client.get(f"/api/tasks/{tid}").json()["task"]["completed"] is True
    priority_ids = [t["id"] for t in client.get("/api/tasks?view=priority").json()["tasks"]]
    deadline_ids = [t["id"] for t in client.get("/api/tasks?view=deadline").json()["tasks"]]
    assert tid not in priority_ids
    assert tid in deadline_ids
    # un-completing puts it back on the heap
    client.patch(f"/api/tasks/{tid}", json={"completed": False})
    assert tid in [t["id"] for t in client.get("/api/tasks?view=priority").json()["tasks"]]


def test_delete_task_removes_from_every_structure():
    tid = make_task().json()["task"]["id"]
    assert client.delete(f"/api/tasks/{tid}").status_code == 200
    assert client.get(f"/api/tasks/{tid}").status_code == 404
    assert client.get("/api/tasks?view=deadline").json()["tasks"] == []
    assert client.get("/api/tasks?view=priority").json()["tasks"] == []


def test_avl_stays_balanced_after_many_api_inserts():
    for i in range(40):
        make_task(title=f"t{i}", days=i)   # strictly increasing deadlines
    tree = store.task_tree
    assert tree.is_balanced() and tree.is_bst()
    assert tree.size == 40
    assert tree.height <= 8                # an unbalanced tree would be 40 deep


# --------------------------------------------------------------------- #
# resources
# --------------------------------------------------------------------- #
def test_index_folder_and_autocomplete():
    r = client.post(
        "/api/resources/index",
        json={"path": "sample_resources", "tags": ["coursework"], "recursive": True},
    ).json()
    assert r["indexed"] >= 8
    assert r["library_keywords"] > 0
    ac = client.get("/api/resources/autocomplete?prefix=hea").json()
    assert "heapsort" in ac["suggestions"]


def test_index_bad_folder_returns_400():
    assert client.post("/api/resources/index", json={"path": "/nope/here"}).status_code == 400


def test_reindexing_skips_duplicates():
    client.post("/api/resources/index", json={"path": "sample_resources"})
    first = client.get("/api/resources").json()["count"]
    again = client.post("/api/resources/index", json={"path": "sample_resources"}).json()
    assert again["indexed"] == 0
    assert client.get("/api/resources").json()["count"] == first


def test_search_ranks_local_resources_descending():
    client.post("/api/resources/index", json={"path": "sample_resources"})
    body = client.get("/api/resources/search?q=avl%20tree&top_k=5&web=false").json()
    assert body["web_matches"] == 0 and body["local_matches"] > 0
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)
    assert "AVL" in body["results"][0]["resource"]["title"]
    assert body["results"][0]["reasons"]


def test_search_with_no_matches():
    body = client.get("/api/resources/search?q=zzzznothing&web=false").json()
    assert body["results"] == [] and body["local_matches"] == 0


def test_web_fetch_returns_attributed_links():
    body = client.get("/api/resources/search?q=binary+search+tree&web=true").json()
    web = [r["resource"] for r in body["results"] if r["resource"]["source"] == "web"]
    assert body["web_matches"] >= 3
    assert all(r["location"].startswith("http") for r in web)


# --------------------------------------------------------------------- #
# workspace
# --------------------------------------------------------------------- #
def test_workspace_splits_local_and_web_and_includes_plan():
    tid = make_task(title="ADSA Review", topic="avl tree").json()["task"]["id"]
    client.post("/api/resources/index", json={"path": "sample_resources"})
    ws = client.get(f"/api/workspace/{tid}?top_k=6&web=false").json()
    assert ws["task"]["id"] == tid
    assert ws["local_resources"] and ws["web_resources"] == []
    assert [r["score"] for r in ws["resources"]] == sorted(
        [r["score"] for r in ws["resources"]], reverse=True
    )
    assert len(ws["progress"]["concepts"]) == 5
    assert ws["study_plan"]["blocks"]


def test_workspace_unknown_task():
    assert client.get("/api/workspace/T9999").status_code == 404


# --------------------------------------------------------------------- #
# adaptive learning
# --------------------------------------------------------------------- #
def test_record_mastery_and_detect_weak_area():
    tid = make_task(topic="avl tree rotations").json()["task"]["id"]
    client.put(f"/api/learning/{tid}", json={"concept": "Rotations", "mastery": 40})
    client.put(f"/api/learning/{tid}", json={"concept": "Insertion", "mastery": 95})
    p = client.get(f"/api/learning/{tid}").json()
    by_concept = {c["concept"]: c for c in p["concepts"]}
    assert by_concept["Rotations"]["status"] == "weak"
    assert by_concept["Insertion"]["status"] == "strong"
    assert "Rotations" in p["weak_areas"]


def test_study_plan_gives_weak_concepts_more_time():
    tid = make_task(topic="avl tree", hours=10).json()["task"]["id"]
    for concept, m in [("Binary Search Tree", 95), ("Rotations", 30)]:
        client.put(f"/api/learning/{tid}", json={"concept": concept, "mastery": m})
    plan = client.get(f"/api/learning/{tid}/plan").json()
    blocks = {b["concept"]: b for b in plan["blocks"]}
    assert blocks["Rotations"]["hours"] > blocks["Binary Search Tree"]["hours"]
    assert plan["blocks"][0]["concept"] == "Rotations"     # weakest first
    assert abs(plan["allocated_hours"] - 10) < 1.5


def test_mastery_clamped_and_unknown_task_404():
    tid = make_task().json()["task"]["id"]
    p = client.put(f"/api/learning/{tid}", json={"concept": "Rotations", "mastery": 100}).json()
    assert max(c["mastery"] for c in p["concepts"]) == 100
    assert client.put("/api/learning/T999", json={"concept": "x", "mastery": 5}).status_code == 404
    assert client.put(f"/api/learning/{tid}", json={"concept": "x", "mastery": 500}).status_code == 422


def test_learning_overview_aggregates():
    tid = make_task(topic="heap heapsort").json()["task"]["id"]
    client.put(f"/api/learning/{tid}", json={"concept": "Sift-Up", "mastery": 20})
    body = client.get("/api/learning").json()
    assert body["tracked_concepts"] == 1
    assert body["weak_areas"][0]["concept"] == "Sift-Up"


# --------------------------------------------------------------------- #
# scheduling
# --------------------------------------------------------------------- #
def test_schedule_builds_a_timeline_within_daily_capacity():
    for i in range(5):
        make_task(title=f"t{i}", days=i + 1, hours=3)
    body = client.post(
        "/api/schedule",
        json={"capacity_hours": 12, "algorithm": "dp", "daily_hours": 4},
    ).json()
    assert body["run"]["algorithm"] == "Dynamic Programming"
    assert body["timeline"]
    for day in body["timeline"]:
        assert day["hours"] <= 4 + 1e-9
        assert day["blocks"]
    scheduled = sum(b["hours"] for d in body["timeline"] for b in d["blocks"])
    assert abs(scheduled - body["run"]["total_hours"]) < 1e-6


def test_schedule_rejects_unknown_algorithm():
    make_task()
    assert client.post("/api/schedule", json={"algorithm": "magic"}).status_code == 400


def test_weak_concepts_add_revision_blocks_to_the_timeline():
    tid = make_task(topic="avl tree", days=2, hours=2).json()["task"]["id"]
    client.put(f"/api/learning/{tid}", json={"concept": "Rotations", "mastery": 25})
    body = client.post(
        "/api/schedule",
        json={"capacity_hours": 20, "algorithm": "greedy", "include_revision": True},
    ).json()
    assert body["revision_blocks"]
    kinds = [b["kind"] for d in body["timeline"] for b in d["blocks"]]
    assert "revision" in kinds


# --------------------------------------------------------------------- #
# reminders and dashboard
# --------------------------------------------------------------------- #
def test_reminders_are_specific_and_ranked():
    make_task(title="Far away", days=20, priority="LOW", hours=1)
    make_task(title="Due today", days=0, priority="CRITICAL", hours=6)
    body = client.get("/api/reminders").json()["reminders"]
    assert body[0]["title"] == "Due today"
    assert body[0]["level"] == "urgent"
    assert "h of work remain" in body[0]["message"]


def test_reminder_mentions_the_weak_area():
    tid = make_task(title="AVL lab", topic="avl tree", days=1).json()["task"]["id"]
    client.put(f"/api/learning/{tid}", json={"concept": "Rotations", "mastery": 20})
    msg = client.get("/api/reminders").json()["reminders"][0]["message"]
    assert "Rotations" in msg


def test_dashboard_summarises_everything():
    make_task(title="overdue", days=-2)
    make_task(title="today", days=0)
    make_task(title="later", days=5)
    body = client.get("/api/dashboard").json()
    assert body["open_tasks"] == 3
    assert body["overdue"] == 1 and body["due_today"] == 1
    assert body["next_task"] is not None
    assert body["reminders"]


def test_internal_indexes_stay_consistent_after_api_use():
    make_task()
    client.post("/api/resources/index", json={"path": "sample_resources"})
    s = store.stats()
    assert s["avl"]["balanced"] is True
    assert s["heap"]["valid_max_heap"] is True
    assert "chaining" in s["task_hash_table"]["strategy"]
    assert s["resource_hash_table"]["size"] > 0
    assert s["trie"]["words"] > 0
    assert s["resource_location_table"]["size"] == s["resource_hash_table"]["size"]


def test_removed_developer_endpoints_are_gone():
    for path in ("/api/structures", "/api/lab/defaults"):
        assert client.get(path).status_code == 404
    assert client.post("/api/lab/benchmark", json={}).status_code == 404
    assert client.post("/api/schedule/compare", json={"capacity_hours": 5}).status_code == 404


def test_seed_demo_populates_a_demo_ready_state():
    body = client.post("/api/demo/seed").json()
    assert body["count"] == 7
    assert body["resources"]["indexed"] > 0
    assert client.get("/api/learning").json()["tracked_concepts"] == 5
    assert client.get("/api/dashboard").json()["open_tasks"] == 7


def test_validation_rejects_bad_payloads():
    assert client.post("/api/tasks", json={"title": ""}).status_code == 422
    assert client.get("/api/tasks?view=nonsense").status_code == 422


def test_delete_task_cleans_up_orphaned_mastery_records():
    tid = make_task(topic="avl tree").json()["task"]["id"]
    client.put(f"/api/learning/{tid}", json={"concept": "Rotations", "mastery": 50})
    assert client.get("/api/learning").json()["tracked_concepts"] == 1
    client.delete(f"/api/tasks/{tid}")
    assert client.get("/api/learning").json()["tracked_concepts"] == 0


def test_score_resource_with_naive_modified_datetime():
    from app.services.resource_service import score_resource
    res = {
        "title": "Naive Timestamp Note",
        "kind": "notes",
        "source": "local",
        "keywords": ["test"],
        "modified": "2026-09-01T12:00:00",
    }
    score, reasons = score_resource(res, ["test"], "test")
    assert score > 0
    assert any("modified" in r for r in reasons)
