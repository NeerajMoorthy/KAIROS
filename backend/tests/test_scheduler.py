import random

import pytest

from app.services import scheduler
from app.services.scheduler import Item


def items(spec):
    """spec: list of (value, hours)"""
    return [
        Item(id=f"T{i}", title=f"t{i}", value=v, hours=h, deadline="2026-12-31")
        for i, (v, h) in enumerate(spec)
    ]


ALL = [scheduler.greedy, scheduler.dynamic_programming,
       scheduler.backtracking, scheduler.branch_and_bound]
EXACT = [scheduler.dynamic_programming, scheduler.backtracking, scheduler.branch_and_bound]


def test_every_algorithm_respects_capacity():
    data = items([(10, 3), (20, 5), (5, 1), (30, 8), (12, 2)])
    for fn in ALL:
        run = fn(data, 10)
        assert run["total_hours"] <= 10 + 1e-9
        assert run["runtime_ms"] >= 0


def test_exact_methods_agree_on_the_optimum():
    rng = random.Random(5)
    for trial in range(15):
        data = items([(rng.randint(5, 60), rng.choice([1, 1.5, 2, 3, 4])) for _ in range(10)])
        cap = rng.choice([5, 8, 12])
        values = {fn(data, cap)["total_value"] for fn in EXACT}
        assert len(values) == 1, f"exact methods disagreed on trial {trial}: {values}"


def test_greedy_never_beats_the_optimum():
    rng = random.Random(11)
    for _ in range(20):
        data = items([(rng.randint(5, 80), rng.choice([1, 2, 3, 5])) for _ in range(9)])
        cap = rng.choice([6, 9, 14])
        g = scheduler.greedy(data, cap)["total_value"]
        opt = scheduler.dynamic_programming(data, cap)["total_value"]
        assert g <= opt + 1e-9


def test_greedy_can_be_suboptimal_classic_case():
    # Capacity 10 h. Densities: 35/5h = 7.0, 40/6h = 6.67, 60/10h = 6.0.
    # Greedy grabs the densest (35, 5h), after which neither remaining item fits,
    # so it finishes on 35. The optimum is simply the single 60-value, 10 h task.
    data = items([(60, 10), (40, 6), (35, 5)])
    g = scheduler.greedy(data, 10)
    opt = scheduler.dynamic_programming(data, 10)
    assert g["total_value"] == 35
    assert opt["total_value"] == 60
    assert g["total_value"] < opt["total_value"]
    assert g["optimal"] is False and opt["optimal"] is True


def test_everything_fits_selects_everything():
    data = items([(10, 1), (20, 2), (30, 3)])
    for fn in ALL:
        run = fn(data, 100)
        assert len(run["selected_ids"]) == 3
        assert run["total_value"] == 60


def test_nothing_fits_selects_nothing():
    data = items([(10, 5), (20, 6)])
    for fn in ALL:
        run = fn(data, 1)
        assert run["selected_ids"] == []
        assert run["total_value"] == 0


def test_empty_input():
    for fn in ALL:
        run = fn([], 10)
        assert run["selected_ids"] == [] and run["total_value"] == 0


def test_branch_and_bound_explores_fewer_nodes_than_backtracking():
    rng = random.Random(3)
    data = items([(rng.randint(10, 90), rng.choice([1, 2, 3, 4])) for _ in range(16)])
    bt = scheduler.backtracking(data, 12)
    bb = scheduler.branch_and_bound(data, 12)
    assert bb["total_value"] == bt["total_value"]
    assert bb["nodes_explored"] < bt["nodes_explored"]


def test_backtracking_refuses_oversized_input():
    data = items([(1, 1)] * (scheduler.BACKTRACK_LIMIT + 1))
    run = scheduler.backtracking(data, 5)
    assert "Skipped" in run["note"]
    assert run["nodes_explored"] == 0


def test_completed_tasks_are_excluded():
    tasks = [
        {"id": "T1", "title": "a", "urgency_score": 10, "estimated_hours": 1,
         "deadline": "2026-01-01", "completed": True},
        {"id": "T2", "title": "b", "urgency_score": 20, "estimated_hours": 1,
         "deadline": "2026-01-02", "completed": False},
    ]
    assert [i.id for i in scheduler.to_items(tasks)] == ["T2"]


# --------------------------------------------------------------------- #
# timeline
# --------------------------------------------------------------------- #
def _tasks(spec):
    return [
        {"id": tid, "title": tid, "topic": "x", "urgency_score": v,
         "estimated_hours": h, "deadline": d, "completed": False}
        for tid, v, h, d in spec
    ]


def test_timeline_respects_daily_capacity_and_conserves_hours():
    tasks = _tasks([("A", 50, 5, "2026-09-01"), ("B", 40, 3, "2026-09-02")])
    days = scheduler.build_timeline(tasks, ["A", "B"], daily_hours=3)
    for d in days:
        assert d["hours"] <= 3 + 1e-9
    assert abs(sum(b["hours"] for d in days for b in d["blocks"]) - 8) < 1e-9


def test_timeline_is_earliest_deadline_first():
    tasks = _tasks([("Late", 90, 1, "2026-09-20"), ("Early", 10, 1, "2026-09-01")])
    days = scheduler.build_timeline(tasks, ["Late", "Early"], daily_hours=8)
    order = [b["task_id"] for d in days for b in d["blocks"]]
    assert order == ["Early", "Late"]


def test_timeline_splits_a_long_task_across_days():
    tasks = _tasks([("Big", 10, 7, "2026-09-10")])
    days = scheduler.build_timeline(tasks, ["Big"], daily_hours=3)
    assert len(days) == 3
    assert [d["hours"] for d in days] == [3.0, 3.0, 1.0]


def test_timeline_ignores_unknown_ids_and_empty_selection():
    tasks = _tasks([("A", 10, 1, "2026-09-01")])
    assert scheduler.build_timeline(tasks, []) == []
    assert scheduler.build_timeline(tasks, ["ghost"]) == []


def test_timeline_appends_revision_blocks():
    tasks = _tasks([("A", 10, 2, "2026-09-01")])
    days = scheduler.build_timeline(
        tasks, ["A"], daily_hours=6,
        extra_blocks=[{"title": "Revise: Rotations", "hours": 0.75, "task_id": "A"}],
    )
    kinds = [b["kind"] for d in days for b in d["blocks"]]
    assert kinds == ["task", "revision"]


def test_date_ordinal_handles_iso_timestamps():
    assert scheduler._date_ordinal("2026-10-15") == scheduler._date_ordinal("2026-10-15T10:00:00")
    assert scheduler._date_ordinal("2026-10-15") == scheduler._date_ordinal("2026-10-15 08:30:00")
