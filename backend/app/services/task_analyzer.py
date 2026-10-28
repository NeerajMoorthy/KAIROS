"""
Task Analyzer — turns a task's attributes into a single urgency/workload score.

THE FORMULA (deliberately simple and fully documented, because this number is
what the Binary Max-Heap orders tasks by):

    urgency = priority_component
            + deadline_component
            + workload_component
            + overdue_penalty

  priority_component = PRIORITY_WEIGHT[priority] * 10
        LOW = 1, MEDIUM = 2, HIGH = 3, CRITICAL = 5   ->   10 / 20 / 30 / 50

  deadline_component = 100 / (1 + max(days_to_deadline, 0))
        A hyperbola: due today -> 100, tomorrow -> 50, in a week -> 12.5,
        in a month -> ~3.2. Urgency rises sharply as the deadline approaches,
        which is the behaviour a student actually experiences.

  workload_component = remaining_hours * 2
        Larger remaining jobs get a mild urgency boost so they start earlier.

  overdue_penalty    = 40 if the deadline has already passed, else 0
        Overdue work jumps the queue.

The score is rounded to 2 decimals. Everything is pure and side-effect free, so
the analyzer is trivially unit-testable and can later be swapped for the
adaptive planning module without touching the data layer.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, Tuple

PRIORITY_WEIGHT: Dict[str, int] = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 5,
}

FORMULA = (
    "urgency = 10*priority_weight + 100/(1 + max(days_to_deadline,0)) "
    "+ 2*remaining_hours + (40 if overdue else 0)"
)


def days_to_deadline(deadline: date, today: date | None = None) -> int:
    today = today or date.today()
    return (deadline - today).days


def analyze(
    deadline: date,
    priority: str,
    estimated_hours: float,
    today: date | None = None,
) -> Tuple[float, Dict[str, float | int | str]]:
    """Return (urgency_score, breakdown)."""
    days = days_to_deadline(deadline, today)

    weight = PRIORITY_WEIGHT.get(str(priority).upper(), 2)
    priority_component = weight * 10.0
    deadline_component = 100.0 / (1 + max(days, 0))
    workload_component = float(estimated_hours) * 2.0
    overdue_penalty = 40.0 if days < 0 else 0.0

    score = (
        priority_component
        + deadline_component
        + workload_component
        + overdue_penalty
    )

    breakdown = {
        "priority_component": round(priority_component, 2),
        "deadline_component": round(deadline_component, 2),
        "workload_component": round(workload_component, 2),
        "overdue_penalty": round(overdue_penalty, 2),
        "days_to_deadline": days,
        "formula": FORMULA,
    }
    return round(score, 2), breakdown
