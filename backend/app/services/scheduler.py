"""
Scheduling module — capacity-limited task selection and the day-by-day plan.

Four strategies solve the SAME selection problem, so their results can be
compared honestly in tests.

THE PROBLEM
-----------
You have a limited number of study hours before your horizon (say 20 hours this
week). Each task has an urgency value (from the Task Analyzer) and an estimated
cost in hours. Which subset of tasks do you commit to in order to maximise total
urgency value without exceeding the available hours?

That is a 0/1 knapsack: value = urgency_score, weight = estimated_hours,
capacity = available hours. Four classic strategies are implemented:

  Greedy            O(n log n)      fast, not always optimal
  Dynamic Programming O(n·W)        optimal, pseudo-polynomial in the capacity
  Backtracking      O(2^n)          optimal, exhaustive with capacity pruning
  Branch & Bound    O(2^n) worst    optimal, prunes with a fractional upper bound

Every run reports its measured wall-clock time and the number of nodes/states it
explored, so tests compare real measurements rather than folklore.

Hours are discretised to 0.5 h units (`UNIT`) so the DP table stays small.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..ds.binary_heap import BinaryMaxHeap
from ..ds.heapsort import heapsort_desc

UNIT = 0.5  # hours per DP unit
BACKTRACK_LIMIT = 22  # 2^22 states is already ~4M; refuse beyond this


@dataclass
class Item:
    id: str
    title: str
    value: float
    hours: float
    deadline: str

    @property
    def units(self) -> int:
        # Round UP so the DP never books more real hours than the capacity:
        # with round(), a 0.7 h task counted as 0.5 h and three of them
        # "fit" into 1.5 h.
        return max(1, math.ceil(self.hours / UNIT - 1e-9))

    @property
    def density(self) -> float:
        return self.value / self.hours if self.hours > 0 else float("inf")


def to_items(tasks: List[Dict[str, Any]]) -> List[Item]:
    return [
        Item(
            id=t["id"],
            title=t["title"],
            value=float(t["urgency_score"]),
            hours=max(0.01, float(t.get("remaining_hours", t["estimated_hours"]))),
            deadline=str(t["deadline"]),
        )
        for t in tasks
        if not t.get("completed") and float(t.get("remaining_hours", t["estimated_hours"])) > 0
    ]


def _result(
    name: str,
    complexity: str,
    optimal: bool,
    chosen: List[Item],
    elapsed_ms: float,
    nodes: int,
    note: str = "",
) -> Dict[str, Any]:
    return {
        "algorithm": name,
        "complexity": complexity,
        "optimal": optimal,
        "selected_ids": [i.id for i in chosen],
        "selected": [
            {"id": i.id, "title": i.title, "value": round(i.value, 2), "hours": i.hours}
            for i in chosen
        ],
        "total_value": round(sum(i.value for i in chosen), 2),
        "total_hours": round(sum(i.hours for i in chosen), 2),
        "runtime_ms": round(elapsed_ms, 4),
        "nodes_explored": nodes,
        "note": note,
    }


# ---------------------------------------------------------------------- #
# 1. Greedy — value density, highest first
# ---------------------------------------------------------------------- #
def greedy(items: List[Item], capacity_hours: float) -> Dict[str, Any]:
    t0 = time.perf_counter()
    ordered = heapsort_desc(items, key=lambda i: i.density)  # our own heapsort
    chosen: List[Item] = []
    remaining = capacity_hours
    steps = 0
    for item in ordered:
        steps += 1
        if item.hours <= remaining:
            chosen.append(item)
            remaining -= item.hours
    elapsed = (time.perf_counter() - t0) * 1000
    return _result(
        "Greedy",
        "O(n log n)",
        False,
        chosen,
        elapsed,
        steps,
        "Sorts by urgency-per-hour and takes what fits. Fast, but can miss the "
        "optimal combination when one large task blocks several small ones.",
    )


# ---------------------------------------------------------------------- #
# 2. Dynamic Programming — 0/1 knapsack tabulation
# ---------------------------------------------------------------------- #
def dynamic_programming(items: List[Item], capacity_hours: float) -> Dict[str, Any]:
    t0 = time.perf_counter()
    n = len(items)
    W = max(0, math.floor(capacity_hours / UNIT + 1e-9))
    # table[i][w] = best value using the first i items within w units
    table = [[0.0] * (W + 1) for _ in range(n + 1)]
    states = 0
    for i in range(1, n + 1):
        wi = items[i - 1].units
        vi = items[i - 1].value
        row, prev = table[i], table[i - 1]
        for w in range(W + 1):
            states += 1
            if wi > w:
                row[w] = prev[w]
            else:
                take = prev[w - wi] + vi
                skip = prev[w]
                row[w] = take if take > skip else skip
    # walk the table backwards to recover which items were taken
    chosen: List[Item] = []
    w = W
    for i in range(n, 0, -1):
        if table[i][w] != table[i - 1][w]:
            chosen.append(items[i - 1])
            w -= items[i - 1].units
    chosen.reverse()
    elapsed = (time.perf_counter() - t0) * 1000
    return _result(
        "Dynamic Programming",
        "O(n·W)",
        True,
        chosen,
        elapsed,
        states,
        f"0/1 knapsack over a {n}×{W + 1} table ({UNIT} h per unit). Always optimal; "
        "cost grows with the capacity, not just the task count.",
    )


# ---------------------------------------------------------------------- #
# 3. Backtracking — exhaustive include/exclude with capacity pruning
# ---------------------------------------------------------------------- #
def backtracking(items: List[Item], capacity_hours: float) -> Dict[str, Any]:
    t0 = time.perf_counter()
    n = len(items)
    if n > BACKTRACK_LIMIT:
        return _result(
            "Backtracking",
            "O(2^n)",
            True,
            [],
            (time.perf_counter() - t0) * 1000,
            0,
            f"Skipped: {n} tasks would mean up to 2^{n} states. "
            f"Backtracking is only run for ≤ {BACKTRACK_LIMIT} tasks.",
        )

    best_value = -1.0
    best_set: List[int] = []
    nodes = 0

    def explore(i: int, remaining: float, value: float, picked: List[int]) -> None:
        nonlocal best_value, best_set, nodes
        nodes += 1
        if value > best_value:
            best_value = value
            best_set = list(picked)
        if i == n:
            return
        # branch 1: take item i, if it fits (this is the pruning step)
        if items[i].hours <= remaining:
            picked.append(i)
            explore(i + 1, remaining - items[i].hours, value + items[i].value, picked)
            picked.pop()
        # branch 2: skip item i
        explore(i + 1, remaining, value, picked)

    explore(0, capacity_hours, 0.0, [])
    chosen = [items[i] for i in best_set]
    elapsed = (time.perf_counter() - t0) * 1000
    return _result(
        "Backtracking",
        "O(2^n)",
        True,
        chosen,
        elapsed,
        nodes,
        "Explores every include/exclude combination, pruning branches that "
        "overflow the available hours. Optimal but exponential.",
    )


# ---------------------------------------------------------------------- #
# 4. Branch & Bound — best-first search with a fractional upper bound
# ---------------------------------------------------------------------- #
def branch_and_bound(items: List[Item], capacity_hours: float) -> Dict[str, Any]:
    t0 = time.perf_counter()
    n = len(items)
    if n == 0:
        return _result("Branch & Bound", "O(2^n) worst case", True, [], 0.0, 0)

    # Process in density order so the fractional bound is tight.
    order = heapsort_desc(list(range(n)), key=lambda idx: items[idx].density)
    ordered = [items[i] for i in order]

    def upper_bound(level: int, value: float, remaining: float) -> float:
        """Relax to fractional knapsack — always ≥ the true best completion."""
        bound = value
        cap = remaining
        i = level
        while i < n and ordered[i].hours <= cap:
            cap -= ordered[i].hours
            bound += ordered[i].value
            i += 1
        if i < n and cap > 0:
            bound += ordered[i].density * cap  # the fractional part
        return bound

    best_value = 0.0
    best_set: List[int] = []
    nodes = 0
    pruned = 0

    # Best-first: our own max-heap keyed on the optimistic bound.
    frontier = BinaryMaxHeap(name="BranchAndBoundFrontier")
    frontier.insert(upper_bound(0, 0.0, capacity_hours), (0, 0.0, capacity_hours, []))

    while len(frontier) > 0:
        popped = frontier.extract_max_with_priority()
        if popped is None:
            break
        bound, (level, value, remaining, picked) = popped
        nodes += 1
        if bound <= best_value:
            pruned += 1
            continue  # this whole subtree cannot beat what we already have
        if level == n:
            continue
        # branch: take
        if ordered[level].hours <= remaining:
            nv = value + ordered[level].value
            nr = remaining - ordered[level].hours
            np = picked + [level]
            if nv > best_value:
                best_value, best_set = nv, np
            b = upper_bound(level + 1, nv, nr)
            if b > best_value:
                frontier.insert(b, (level + 1, nv, nr, np))
            else:
                pruned += 1
        # branch: skip
        b = upper_bound(level + 1, value, remaining)
        if b > best_value:
            frontier.insert(b, (level + 1, value, remaining, picked))
        else:
            pruned += 1

    chosen = [ordered[i] for i in best_set]
    elapsed = (time.perf_counter() - t0) * 1000
    return _result(
        "Branch & Bound",
        "O(2^n) worst case, far less in practice",
        True,
        chosen,
        elapsed,
        nodes,
        f"Best-first search over a max-heap of optimistic (fractional-knapsack) "
        f"bounds; {pruned} branch(es) pruned without being explored.",
    )


ALGORITHMS = {
    "greedy": greedy,
    "dp": dynamic_programming,
    "backtracking": backtracking,
    "branch_and_bound": branch_and_bound,
}

LABELS = {
    "greedy": "Greedy",
    "dp": "Dynamic Programming",
    "backtracking": "Backtracking",
    "branch_and_bound": "Branch & Bound",
}


# ---------------------------------------------------------------------- #
# Timeline: turn a chosen set of tasks into day-by-day study blocks
# ---------------------------------------------------------------------- #
def build_timeline(
    tasks: List[Dict[str, Any]],
    selected_ids: List[str],
    daily_hours: float = 3.0,
    start: Optional[date] = None,
    extra_blocks: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Lay the selected tasks out over days, earliest deadline first.

    Earliest-deadline-first is the classic greedy ordering for minimising
    lateness once the set of tasks is fixed. Each day is filled up to
    `daily_hours`; a task longer than one day spills into following days.
    """
    start = start or date.today()
    if daily_hours <= 0:
        return []
    by_id = {t["id"]: t for t in tasks}
    chosen = [by_id[i] for i in selected_ids if i in by_id]
    # earliest deadline first (ties broken by higher urgency)
    chosen = heapsort_desc(
        chosen, key=lambda t: -_date_ordinal(t["deadline"]) * 1000 + t["urgency_score"] / 1000
    )

    days: List[Dict[str, Any]] = []
    day_index = 0
    remaining_today = daily_hours
    current: Dict[str, Any] = {"date": start.isoformat(), "blocks": [], "hours": 0.0}

    def push_day() -> None:
        nonlocal current, day_index, remaining_today
        days.append(current)
        day_index += 1
        remaining_today = daily_hours
        current = {
            "date": (start + timedelta(days=day_index)).isoformat(),
            "blocks": [],
            "hours": 0.0,
        }

    for task in chosen:
        left = max(0.0, float(task.get("remaining_hours", task["estimated_hours"])))
        while left > 0:
            if remaining_today <= 0:
                push_day()
            slice_hours = min(left, remaining_today)
            current["blocks"].append(
                {
                    "task_id": task["id"],
                    "title": task["title"],
                    "topic": task["topic"],
                    "hours": round(slice_hours, 2),
                    "deadline": task["deadline"],
                    "kind": "task",
                    "overdue": current["date"] > str(task["deadline"]),
                }
            )
            current["hours"] = round(current["hours"] + slice_hours, 2)
            left -= slice_hours
            remaining_today -= slice_hours

    for block in extra_blocks or []:
        if remaining_today <= 0:
            push_day()
        hours = min(float(block.get("hours", 0.5)), max(remaining_today, 0.0))
        if hours <= 0:
            continue
        current["blocks"].append({**block, "hours": round(hours, 2), "kind": "revision"})
        current["hours"] = round(current["hours"] + hours, 2)
        remaining_today -= hours

    if current["blocks"]:
        days.append(current)
    return days


def adaptive_plan(
    tasks: List[Dict[str, Any]],
    capacity_hours: float,
    daily_hours: float,
    horizon_days: int = 7,
    start: Optional[date] = None,
) -> Dict[str, Any]:
    """Allocate task effort across a bounded horizon without overbooking.

    Work is split into daily blocks and ordered by deadline, then current
    urgency. If capacity runs out, the unscheduled remainder stays explicit in
    `deferred`; it is not copied forward as if it had already been planned.
    """
    start = start or date.today()
    horizon_days = max(1, int(horizon_days))
    daily_hours = max(0.0, float(daily_hours))
    capacity = max(0.0, min(float(capacity_hours), daily_hours * horizon_days))

    open_tasks = [
        task for task in tasks
        if not task.get("completed")
        and float(task.get("remaining_hours", task.get("estimated_hours", 0))) > 0
    ]
    ordered = heapsort_desc(
        open_tasks,
        key=lambda task: -_date_ordinal(str(task["deadline"])) * 1000
        + float(task.get("urgency_score", 0)) / 1000,
    )
    remaining = {
        task["id"]: max(0.0, float(task.get("remaining_hours", task.get("estimated_hours", 0))))
        for task in ordered
    }
    scheduled_by_id: Dict[str, float] = {task["id"]: 0.0 for task in ordered}
    timeline: List[Dict[str, Any]] = []
    weekly_remaining = capacity

    for day_index in range(horizon_days):
        day_date = start + timedelta(days=day_index)
        day_remaining = min(daily_hours, weekly_remaining)
        if day_remaining <= 0:
            break
        blocks: List[Dict[str, Any]] = []
        for task in ordered:
            if day_remaining <= 1e-9:
                break
            left = remaining[task["id"]]
            if left <= 1e-9:
                continue
            hours = min(left, day_remaining)
            blocks.append({
                "task_id": task["id"],
                "title": task["title"],
                "topic": task.get("category") or task.get("topic", ""),
                "hours": round(hours, 2),
                "deadline": task["deadline"],
                "kind": "task",
                "overdue": _date_ordinal(str(task["deadline"])) < day_date.toordinal(),
            })
            remaining[task["id"]] = max(0.0, left - hours)
            scheduled_by_id[task["id"]] += hours
            day_remaining -= hours
            weekly_remaining -= hours
        if blocks:
            day_total = round(sum(block["hours"] for block in blocks), 2)
            timeline.append({"date": day_date.isoformat(), "hours": day_total, "blocks": blocks})

    deferred = []
    for task in ordered:
        left = remaining[task["id"]]
        if left > 1e-6:
            deferred.append({
                "id": task["id"],
                "title": task["title"],
                "deadline": task["deadline"],
                "priority": task.get("priority", "MEDIUM"),
                "hours": round(left, 2),
                "scheduled_hours": round(scheduled_by_id[task["id"]], 2),
                "reason": "Remaining effort exceeds the hours available in this plan.",
            })

    scheduled = round(sum(scheduled_by_id.values()), 2)
    return {
        "timeline": timeline,
        "scheduled_hours": scheduled,
        "capacity_hours": round(capacity, 2),
        "daily_hours": round(daily_hours, 2),
        "horizon_days": horizon_days,
        "task_count": len(open_tasks),
        "selected": [
            {"id": task["id"], "title": task["title"], "hours": round(scheduled_by_id[task["id"]], 2)}
            for task in ordered if scheduled_by_id[task["id"]] > 0
        ],
        "deferred": deferred,
    }


def _date_ordinal(iso: str) -> int:
    date_part = str(iso).split("T")[0].split(" ")[0]
    y, m, d = (int(p) for p in date_part.split("-"))
    return date(y, m, d).toordinal()
