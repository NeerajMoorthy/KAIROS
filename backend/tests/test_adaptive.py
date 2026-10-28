from datetime import date, timedelta

import pytest

from app.services import adaptive, reminders
from app.services.store import KairosStore, now_iso
from app.services.task_analyzer import analyze


@pytest.fixture
def store():
    s = KairosStore()
    return s


def add_task(store, title="AVL Lab", topic="avl tree rotations", days=3, hours=5,
             priority="HIGH"):
    deadline = date.today() + timedelta(days=days)
    score, breakdown = analyze(deadline, priority, hours)
    task = {
        "id": store.next_task_id(),
        "title": title,
        "topic": topic,
        "deadline": deadline.isoformat(),
        "priority": priority,
        "estimated_hours": float(hours),
        "notes": "",
        "urgency_score": score,
        "score_breakdown": breakdown,
        "created_at": now_iso(),
        "completed": False,
    }
    store.add_task(task)
    return task


# --------------------------------------------------------------------- #
# concept mapping
# --------------------------------------------------------------------- #
def test_known_topics_get_their_concept_chain():
    assert adaptive.concepts_for("avl tree rotations")[0] == "Binary Search Tree"
    assert "Rotations" in adaptive.concepts_for("avl")
    assert adaptive.concepts_for("heap heapsort")[-1] == "Heapsort"
    assert "BCNF" in adaptive.concepts_for("database normalization")


def test_unknown_topic_falls_back_to_a_generic_chain():
    concepts = adaptive.concepts_for("basket weaving")
    assert len(concepts) == 5
    assert all(c.startswith("Basket Weaving") for c in concepts)


def test_empty_topic_is_handled():
    assert len(adaptive.concepts_for("")) == 5


# --------------------------------------------------------------------- #
# mastery
# --------------------------------------------------------------------- #
def test_new_task_starts_unassessed(store):
    task = add_task(store)
    p = adaptive.get_progress(store, task["id"])
    assert p["assessed_count"] == 0
    assert p["overall_mastery"] == 0
    assert p["weak_areas"] == []                 # unknown is not the same as weak
    assert all(c["status"] == "unassessed" for c in p["concepts"])


def test_recording_mastery_classifies_status(store):
    task = add_task(store)
    adaptive.set_mastery(store, task["id"], "Rotations", 45)
    adaptive.set_mastery(store, task["id"], "Insertion", 70)
    adaptive.set_mastery(store, task["id"], "Deletion", 92)
    by = {c["concept"]: c for c in adaptive.get_progress(store, task["id"])["concepts"]}
    assert by["Rotations"]["status"] == "weak"
    assert by["Insertion"]["status"] == "developing"
    assert by["Deletion"]["status"] == "strong"


def test_overall_mastery_averages_only_assessed_concepts(store):
    task = add_task(store)
    adaptive.set_mastery(store, task["id"], "Rotations", 40)
    adaptive.set_mastery(store, task["id"], "Insertion", 80)
    assert adaptive.get_progress(store, task["id"])["overall_mastery"] == 60


def test_mastery_is_clamped_and_overwritten(store):
    task = add_task(store)
    adaptive.set_mastery(store, task["id"], "Rotations", 500)
    adaptive.set_mastery(store, task["id"], "Rotations", -20)
    by = {c["concept"]: c for c in adaptive.get_progress(store, task["id"])["concepts"]}
    assert by["Rotations"]["mastery"] == 0
    assert store.mastery_index.size == 1          # overwritten, not duplicated


def test_unknown_task_returns_none(store):
    assert adaptive.get_progress(store, "T999") is None
    assert adaptive.set_mastery(store, "T999", "x", 50) is None
    assert adaptive.study_plan(store, "T999") is None


# --------------------------------------------------------------------- #
# study plan
# --------------------------------------------------------------------- #
def test_plan_allocates_more_time_to_weaker_concepts(store):
    task = add_task(store, hours=10)
    adaptive.set_mastery(store, task["id"], "Rotations", 20)
    adaptive.set_mastery(store, task["id"], "Binary Search Tree", 95)
    plan = adaptive.study_plan(store, task["id"])
    by = {b["concept"]: b for b in plan["blocks"]}
    assert by["Rotations"]["hours"] > by["Binary Search Tree"]["hours"]
    assert plan["blocks"][0]["concept"] == "Rotations"      # weakest first


def test_plan_total_is_close_to_the_requested_hours(store):
    task = add_task(store, hours=8)
    plan = adaptive.study_plan(store, task["id"], hours=6)
    assert plan["total_hours"] == 6
    assert abs(plan["allocated_hours"] - 6) <= 0.75         # rounding to 15 min


def test_plan_is_even_when_nothing_is_assessed(store):
    task = add_task(store, hours=10)
    hours = [b["hours"] for b in adaptive.study_plan(store, task["id"])["blocks"]]
    assert max(hours) == min(hours)


def test_mastered_concepts_still_get_a_refresher(store):
    task = add_task(store, hours=10)
    for c in adaptive.concepts_for(task["topic"]):
        adaptive.set_mastery(store, task["id"], c, 100)
    plan = adaptive.study_plan(store, task["id"])
    assert all(b["hours"] > 0 for b in plan["blocks"])
    assert all(b["reason"] == "quick refresher" for b in plan["blocks"])


# --------------------------------------------------------------------- #
# revision blocks + overview
# --------------------------------------------------------------------- #
def test_revision_blocks_are_worst_first(store):
    task = add_task(store)
    adaptive.set_mastery(store, task["id"], "Rotations", 25)
    adaptive.set_mastery(store, task["id"], "Deletion", 55)
    adaptive.set_mastery(store, task["id"], "Insertion", 90)
    blocks = adaptive.revision_blocks(store)
    assert [b["concept"] for b in blocks] == ["Rotations", "Deletion"]
    assert blocks[0]["hours"] >= blocks[1]["hours"]         # worse -> longer


def test_overview_aggregates_across_tasks(store):
    a = add_task(store, title="AVL", topic="avl tree")
    b = add_task(store, title="Heaps", topic="heap heapsort")
    adaptive.set_mastery(store, a["id"], "Rotations", 30)
    adaptive.set_mastery(store, b["id"], "Sift-Up", 80)
    body = adaptive.learning_overview(store)
    assert len(body["tasks"]) == 2
    assert body["tracked_concepts"] == 2
    assert body["average_mastery"] == 55
    assert body["weak_areas"][0]["concept"] == "Rotations"


# --------------------------------------------------------------------- #
# reminders
# --------------------------------------------------------------------- #
def test_reminder_levels_track_deadline_proximity(store):
    add_task(store, title="Overdue", days=-1)
    add_task(store, title="Today", days=0)
    add_task(store, title="Soon", days=2)
    add_task(store, title="Later", days=10)
    levels = {r["title"]: r["level"] for r in reminders.build_reminders(store)}
    assert levels == {
        "Overdue": "overdue", "Today": "urgent", "Soon": "soon", "Later": "info"
    }


def test_reminder_reduces_remaining_hours_as_mastery_grows(store):
    task = add_task(store, hours=10)
    before = reminders.build_reminders(store)[0]["remaining_hours"]
    for c in adaptive.concepts_for(task["topic"]):
        adaptive.set_mastery(store, task["id"], c, 80)
    after = reminders.build_reminders(store)[0]["remaining_hours"]
    assert after < before
    assert after == 2.0                       # 10 h × (1 − 0.8)


def test_reminders_skip_completed_tasks(store):
    task = add_task(store)
    task["completed"] = True
    assert reminders.build_reminders(store) == []


def test_dashboard_counts(store):
    add_task(store, title="overdue", days=-3)
    add_task(store, title="today", days=0)
    add_task(store, title="week", days=4)
    add_task(store, title="far", days=40)
    body = reminders.dashboard_summary(store)
    assert body["open_tasks"] == 4
    assert body["overdue"] == 1
    assert body["due_today"] == 1
    assert body["due_this_week"] == 2         # today + day 4
    assert body["next_task"]["title"] == "overdue"
