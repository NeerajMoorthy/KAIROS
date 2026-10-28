from datetime import date, timedelta

from app.services.task_analyzer import PRIORITY_WEIGHT, analyze, days_to_deadline


TODAY = date(2026, 8, 18)


def test_days_to_deadline():
    assert days_to_deadline(TODAY, TODAY) == 0
    assert days_to_deadline(TODAY + timedelta(days=5), TODAY) == 5
    assert days_to_deadline(TODAY - timedelta(days=2), TODAY) == -2


def test_formula_components_add_up():
    score, b = analyze(TODAY + timedelta(days=1), "HIGH", 4, today=TODAY)
    assert b["priority_component"] == 30.0        # HIGH = 3 -> 30
    assert b["deadline_component"] == 50.0        # 100 / (1 + 1)
    assert b["workload_component"] == 8.0         # 4h * 2
    assert b["overdue_penalty"] == 0.0
    assert score == 88.0


def test_due_today_is_max_deadline_pressure():
    _, b = analyze(TODAY, "LOW", 0, today=TODAY)
    assert b["deadline_component"] == 100.0


def test_overdue_gets_penalty():
    score_over, b = analyze(TODAY - timedelta(days=3), "MEDIUM", 1, today=TODAY)
    assert b["overdue_penalty"] == 40.0
    assert b["deadline_component"] == 100.0       # max(days,0) clamps to today
    assert score_over == 20 + 100 + 2 + 40


def test_higher_priority_scores_higher_all_else_equal():
    d = TODAY + timedelta(days=7)
    scores = [analyze(d, p, 3, today=TODAY)[0] for p in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]]
    assert scores == sorted(scores)
    assert len(set(scores)) == 4


def test_nearer_deadline_scores_higher():
    near = analyze(TODAY + timedelta(days=1), "MEDIUM", 3, today=TODAY)[0]
    far = analyze(TODAY + timedelta(days=30), "MEDIUM", 3, today=TODAY)[0]
    assert near > far


def test_more_hours_scores_higher():
    small = analyze(TODAY + timedelta(days=5), "MEDIUM", 1, today=TODAY)[0]
    big = analyze(TODAY + timedelta(days=5), "MEDIUM", 20, today=TODAY)[0]
    assert big > small


def test_unknown_priority_defaults_to_medium():
    a = analyze(TODAY, "WEIRD", 1, today=TODAY)[0]
    b = analyze(TODAY, "MEDIUM", 1, today=TODAY)[0]
    assert a == b


def test_priority_weights_are_documented():
    assert PRIORITY_WEIGHT == {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 5}
