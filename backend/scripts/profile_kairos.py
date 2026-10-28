"""
Reproducible performance profile for KAIROS.

What it measures
----------------
1. Folder indexing throughput on a generated corpus of small text files:
   * a cold index into an empty library,
   * a re-index of the same, unchanged folder (every file should be skipped),
   * a cold index of a second folder into a library that already holds the
     first one (this is where a per-file scan of the whole library shows up).
2. In-process API latency for the main product endpoints, called through
   FastAPI's TestClient against a seeded store (N tasks, M indexed files).

What it does NOT measure
------------------------
* Network or browser time. TestClient runs the ASGI app in-process, so the
  numbers are server-side handling time plus TestClient overhead.
* Behaviour on another machine. Timings depend on CPU, disk, Python version
  and background load. Re-run the script on the machine you report on.

Usage (from the backend folder):

    python scripts/profile_kairos.py                # defaults below
    python scripts/profile_kairos.py --files 2000 --tasks 200 --repeat 30
    python scripts/profile_kairos.py --json profile.json

Nothing is written outside a temporary directory unless --json is given.
The KAIROS snapshot path is redirected to that temporary directory, so the
run never touches your real workspace data.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import statistics
import sys
import tempfile
import time
from datetime import date, timedelta
from typing import Any, Callable, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

WORDS = (
    "analysis report draft review citation method results discussion figure "
    "table appendix outline survey dataset experiment hypothesis summary "
    "lecture notes chapter revision exam practice problem solution design "
    "implementation testing deployment schedule milestone presentation slide"
).split()


def make_corpus(root: str, count: int, seed: int) -> None:
    """Write `count` small, deterministic text files across nested folders."""
    rng = random.Random(seed)
    for i in range(count):
        sub = os.path.join(root, f"unit_{i % 20:02d}", f"week_{(i // 20) % 10:02d}")
        os.makedirs(sub, exist_ok=True)
        name = f"{rng.choice(WORDS)}_{rng.choice(WORDS)}_{i:05d}.md"
        body = " ".join(rng.choice(WORDS) for _ in range(rng.randint(80, 240)))
        with open(os.path.join(sub, name), "w", encoding="utf-8") as fh:
            fh.write(f"# {name}\n\n{body}\n")


def timed(fn: Callable[[], Any]) -> float:
    start = time.perf_counter()
    fn()
    return (time.perf_counter() - start) * 1000


def latency(fn: Callable[[], Any], repeat: int, warmup: int = 3) -> Dict[str, float]:
    for _ in range(warmup):
        fn()
    samples = [timed(fn) for _ in range(repeat)]
    samples.sort()
    p95_index = max(0, int(round(0.95 * len(samples))) - 1)
    return {
        "mean_ms": round(statistics.fmean(samples), 2),
        "p50_ms": round(statistics.median(samples), 2),
        "p95_ms": round(samples[p95_index], 2),
        "max_ms": round(samples[-1], 2),
        "n": len(samples),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--files", type=int, default=1500, help="files per generated folder")
    parser.add_argument("--tasks", type=int, default=150, help="tasks seeded for API latency")
    parser.add_argument("--repeat", type=int, default=25, help="timed calls per endpoint")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--json", dest="json_path", default=None, help="also write results here")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="kairos-profile-") as tmp:
        # Keep the profile away from the user's real snapshot.
        os.environ["KAIROS_SNAPSHOT_PATH"] = os.path.join(tmp, "profile_snapshot.json")

        from fastapi.testclient import TestClient

        from app.main import app
        from app.services import resource_service
        from app.services.store import store

        folder_a = os.path.join(tmp, "folder_a")
        folder_b = os.path.join(tmp, "folder_b")
        make_corpus(folder_a, args.files, args.seed)
        make_corpus(folder_b, args.files, args.seed + 1)

        store.reset()
        results: Dict[str, Any] = {
            "environment": {
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
                "platform": platform.platform(),
                "machine": platform.machine(),
                "processor": platform.processor() or "unknown",
                "cpu_count": os.cpu_count(),
            },
            "parameters": vars(args),
        }

        # ---------------------------------------------------------------- #
        # 1. indexing
        # ---------------------------------------------------------------- #
        indexing: Dict[str, Any] = {}
        out: Dict[str, Any] = {}

        def run(path: str) -> None:
            out.clear()
            out.update(resource_service.index_folder(store, path, tags=["profile"]))

        ms = timed(lambda: run(folder_a))
        indexing["cold_index_empty_library"] = {
            "ms": round(ms, 1), "files": args.files,
            "files_per_s": round(args.files / (ms / 1000), 1), "result": dict(out),
        }
        ms = timed(lambda: run(folder_a))
        indexing["reindex_unchanged"] = {
            "ms": round(ms, 1), "files": args.files,
            "files_per_s": round(args.files / (ms / 1000), 1), "result": dict(out),
        }
        ms = timed(lambda: run(folder_b))
        indexing["cold_index_second_folder"] = {
            "ms": round(ms, 1), "files": args.files,
            "library_size_before": args.files,
            "files_per_s": round(args.files / (ms / 1000), 1), "result": dict(out),
        }
        results["indexing"] = indexing

        # ---------------------------------------------------------------- #
        # 2. API latency
        # ---------------------------------------------------------------- #
        client = TestClient(app)
        rng = random.Random(args.seed)
        priorities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        today = date.today()
        for i in range(args.tasks):
            response = client.post("/api/tasks", json={
                "title": f"{rng.choice(WORDS).title()} {rng.choice(WORDS)} {i}",
                "category": rng.choice(WORDS),
                "deadline": (today + timedelta(days=rng.randint(-2, 40))).isoformat(),
                "priority": rng.choice(priorities),
                "estimated_hours": rng.choice([1, 2, 3, 4, 5, 6, 8]),
            })
            response.raise_for_status()

        endpoints: List[tuple] = [
            ("GET /api/dashboard", lambda: client.get("/api/dashboard")),
            ("GET /api/tasks?view=deadline", lambda: client.get("/api/tasks?view=deadline")),
            ("GET /api/tasks?view=priority", lambda: client.get("/api/tasks?view=priority")),
            ("GET /api/progress", lambda: client.get("/api/progress")),
            ("GET /api/deadline-risk", lambda: client.get("/api/deadline-risk")),
            ("POST /api/plan", lambda: client.post("/api/plan", json={"capacity_hours": 21, "daily_hours": 3})),
            ("GET /api/resources/search?q=report draft",
             lambda: client.get("/api/resources/search", params={"q": "report draft", "top_k": 8})),
            ("GET /api/resources/autocomplete?prefix=re",
             lambda: client.get("/api/resources/autocomplete", params={"prefix": "re"})),
        ]
        api: Dict[str, Any] = {}
        for label, call in endpoints:
            status = call().status_code
            if status >= 400:
                raise SystemExit(f"{label} returned HTTP {status}")
            api[label] = latency(call, args.repeat)
        results["api_latency"] = api

        # ---------------------------------------------------------------- #
        # 3. persistence cost at this library size
        # ---------------------------------------------------------------- #
        from app.services import persistence

        snap = os.path.join(tmp, "profile_snapshot.json")
        save_cost = latency(lambda: persistence.save(store, snap), max(5, args.repeat // 3), warmup=1)
        save_cost["snapshot_bytes"] = os.path.getsize(snap)
        persist: Dict[str, Any] = {"snapshot_save": save_cost}
        if hasattr(persistence, "set_autosave"):
            task_id = store.tasks_by_deadline()[0]["id"]
            flip = {"p": 10}

            def patch_task() -> None:
                flip["p"] = 30 if flip["p"] == 10 else 10
                client.patch(f"/api/tasks/{task_id}", json={"progress": flip["p"]}).raise_for_status()

            persistence.set_autosave(False)
            persist["PATCH /api/tasks/{id} autosave off"] = latency(patch_task, args.repeat)
            persistence.set_autosave(True)
            persist["PATCH /api/tasks/{id} autosave on"] = latency(patch_task, args.repeat)
            persistence.set_autosave(False)
        results["persistence"] = persist
        results["store"] = {
            "tasks": store.task_index.size,
            "resources": store.resource_index.size,
            "trie_words": store.keyword_trie.word_count,
        }
        store.reset()

    text = json.dumps(results, indent=2)
    print(text)
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
