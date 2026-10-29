"""
KAIROS API — local backend for the KAIROS study-planning app.

Product areas
-------------
Tasks            create, edit, complete, search and filter tasks; deadline and
                 priority views; the single most urgent open task
Knowledge Vault  index folders the student chooses, keep them current
                 (rescan / remove), search with explained match points,
                 optional public web suggestions
Planning         deadline risk, the recommended next action, and a day-by-day
                 plan that fits remaining effort into available hours
Focus            one focus session at a time; finishing a session records time
                 and updates task progress
Progress         effort-weighted progress, planned vs recorded hours
Settings         daily availability; example data; local snapshot status

Endpoints
---------
GET    /api/dashboard                 summary, recommended next action, deadline risks
GET    /api/tasks                     tasks by deadline or by priority, with filters
POST   /api/tasks                     create a task
GET    /api/tasks/next                the most urgent open task
GET    /api/tasks/{id}                one task
PATCH  /api/tasks/{id}                edit, set progress or status, complete
DELETE /api/tasks/{id}                delete a task
POST   /api/resources/index           index a chosen folder (refresh + prune deleted files)
GET    /api/resources/folders         library folders with file counts
POST   /api/resources/folders/rescan  rescan one folder (path) or all folders
DELETE /api/resources/folders         forget a folder; files on disk are untouched
GET    /api/resources/search          ranked search with match reasons (web optional)
GET    /api/resources/autocomplete    keyword suggestions for a prefix
GET    /api/resources                 browse indexed files
GET    /api/workspace/{task_id}       one task with its relevant resources
POST   /api/plan                      day-by-day plan within daily and weekly hours
GET    /api/progress                  progress summary
GET    /api/deadline-risk             workload-based deadline risk per open task
GET    /api/focus/sessions            current and recent focus sessions
POST   /api/focus/sessions            start a focus session
PATCH  /api/focus/sessions/{id}       pause, resume or finish a session
GET    /api/settings, PATCH           daily availability
GET    /api/snapshot/status           snapshot file and autosave state
POST   /api/snapshot/save | load      save now / reload from disk
POST   /api/demo/seed | reset         example data / clear the workspace
POST   /api/auth/signup | login       create an account or log in; returns a token
POST   /api/auth/logout               end this login session
GET    /api/auth/me                   who is logged in, and whether login is required

Compatibility endpoints, not used by the interface: /api/learning* (self-rated
concept confidence and a weighted study plan), /api/reminders, /api/schedule
(capacity-limited task selection with a timeline).

While the server runs, every successful POST/PUT/PATCH/DELETE that can change
data is followed by an atomic snapshot save (see persistence.autosave).

Accounts: a request with "Authorization: Bearer <token>" works on that user's
private workspace. Without a token it uses the shared local workspace, unless
KAIROS_REQUIRE_LOGIN=1 (set on the hosted server), in which case every
data endpoint answers 401 until the user logs in.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import date
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import (
    Credentials,
    FocusSessionStart,
    FocusSessionUpdate,
    FolderRescanRequest,
    IndexFolderRequest,
    MasteryUpdate,
    AdaptivePlanRequest,
    ScheduleRequest,
    SettingsUpdate,
    TaskCreate,
    TaskUpdate,
)
from .services import adaptive, focus, insights, persistence, reminders, resource_service, scheduler, storage, workspace
from .services.accounts import AccountError, AccountService
from .services.store import KairosStore, build_task, now_iso
from .services.store import store as local_store
from .services.task_analyzer import FORMULA, analyze

APP_NAME = "KAIROS"
APP_TAGLINE = "Knowledge Acquisition, Indexing, Ranking & Optimized Scheduling"

REQUIRE_LOGIN = os.environ.get("KAIROS_REQUIRE_LOGIN", "").strip().lower() in {"1", "true", "yes", "on"}

# Set per request by the middleware below: the logged-in user (or None) and
# the workspace this request reads and changes.
_current_user: ContextVar[Optional[str]] = ContextVar("kairos_user", default=None)
_current_store: ContextVar[KairosStore] = ContextVar("kairos_store", default=local_store)


class _CurrentStore:
    """Stands in for the store in every endpoint and forwards to the current
    request's workspace, so endpoint code stays the same for every user."""

    def __getattr__(self, name: str) -> Any:
        return getattr(_current_store.get(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(_current_store.get(), name, value)


store: Any = _CurrentStore()
_accounts: Optional[AccountService] = None


def accounts() -> AccountService:
    global _accounts
    if _accounts is None:
        _accounts = AccountService(storage.from_environment())
    return _accounts


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    # startup: best-effort restore of the last JSON snapshot (see
    # services/persistence.py) so uvicorn --reload and normal restarts don't
    # erase the store
    persistence.autoload_on_startup(local_store)
    persistence.set_autosave(persistence.autosave_requested())
    try:
        yield
    finally:
        persistence.set_autosave(False)
        # shutdown: best-effort save, mirroring the restore above
        persistence.autosave_on_shutdown(local_store)


app = FastAPI(
    title=f"{APP_NAME} API", version="1.0.0", description=__doc__, lifespan=_lifespan
)

# POST endpoints that only compute and never change stored data. Everything
# else that writes (POST/PUT/PATCH/DELETE) is followed by an autosave, so a
# new mutating endpoint is persisted by default rather than by remembering to.
_READ_ONLY_POSTS = ("/api/plan", "/api/schedule", "/api/snapshot/", "/api/auth/")
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_PUBLIC_PATHS = ("/api/health", "/api/auth/")


def _bearer_token(request: Request) -> Optional[str]:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


@app.middleware("http")
async def _workspace_and_autosave(request: Request, call_next):
    path = request.url.path
    token = _bearer_token(request)
    user = await run_in_threadpool(accounts().user_for_token, token) if token else None
    if path.startswith("/api/") and not path.startswith(_PUBLIC_PATHS) and request.method != "OPTIONS":
        if token and not user:
            return JSONResponse({"detail": "Your login has expired. Please log in again."}, status_code=401)
        if REQUIRE_LOGIN and not user:
            return JSONResponse({"detail": "Please log in to use KAIROS."}, status_code=401)

    workspace_store = await run_in_threadpool(accounts().workspace, user) if user else local_store
    user_token = _current_user.set(user)
    store_token = _current_store.set(workspace_store)
    try:
        response = await call_next(request)
    finally:
        _current_user.reset(user_token)
        _current_store.reset(store_token)

    if (
        request.method in _WRITE_METHODS
        and path.startswith("/api/")
        and response.status_code < 400
        and not path.startswith(_READ_ONLY_POSTS)
    ):
        if user:
            await run_in_threadpool(accounts().save_workspace, user)
        else:
            await run_in_threadpool(persistence.autosave, local_store)
    return response


# Extra allowed origins (comma-separated), e.g. a hosted frontend such as
# KAIROS_CORS_ORIGINS=https://kairos-study-planner.netlify.app
_EXTRA_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.environ.get("KAIROS_CORS_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", *_EXTRA_ORIGINS],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# ---------------------------------------------------------------------- #
# meta
# ---------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "name": APP_NAME,
        "tagline": APP_TAGLINE,
        "version": app.version,
        "tasks": store.task_index.size,
        "resources": store.resource_index.size,
        "urgency_formula": FORMULA,
        "login_required": REQUIRE_LOGIN,
    }


# ---------------------------------------------------------------------- #
# accounts
# ---------------------------------------------------------------------- #
@app.post("/api/auth/signup")
def sign_up(body: Credentials) -> Dict[str, Any]:
    try:
        return accounts().sign_up(body.username, body.password)
    except AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/auth/login")
def log_in(body: Credentials) -> Dict[str, Any]:
    try:
        return accounts().log_in(body.username, body.password)
    except AccountError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@app.post("/api/auth/logout")
def log_out(request: Request) -> Dict[str, str]:
    token = _bearer_token(request)
    if token:
        accounts().log_out(token)
    return {"status": "logged out"}


@app.get("/api/auth/me")
def me(request: Request) -> Dict[str, Any]:
    token = _bearer_token(request)
    username = accounts().user_for_token(token) if token else None
    return {"username": username, "login_required": REQUIRE_LOGIN}


@app.get("/api/dashboard")
def dashboard() -> Dict[str, Any]:
    return reminders.dashboard_summary(store)


# ---------------------------------------------------------------------- #
# tasks
# ---------------------------------------------------------------------- #
@app.post("/api/tasks", status_code=201)
def create_task(payload: TaskCreate) -> Dict[str, Any]:
    task = build_task(
        store.next_task_id(),
        payload.title,
        (payload.category or payload.topic or "General").strip() or "General",
        payload.deadline,
        payload.priority.value,
        payload.estimated_hours,
        project=payload.project.strip() if payload.project else None,
        description=payload.description or payload.notes or "",
    )
    store.add_task(task)
    return {"task": task, "concepts": adaptive.concepts_for(task["topic"])}


@app.get("/api/tasks")
def list_tasks(
    view: str = Query("deadline", pattern="^(deadline|priority)$"),
    include_completed: bool = True,
    q: str = Query("", max_length=200),
    status: Optional[str] = Query(None, pattern="^(todo|in_progress|completed)$"),
    project: Optional[str] = Query(None, max_length=160),
    category: Optional[str] = Query(None, max_length=120),
    sort_by: Optional[str] = Query(None, pattern="^(title|deadline|priority|progress)$"),
) -> Dict[str, Any]:
    tasks = store.tasks_by_deadline() if view == "deadline" else store.tasks_by_priority()
    if not include_completed:
        tasks = [t for t in tasks if not t.get("completed")]
    if q.strip():
        needle = q.strip().casefold()
        tasks = [
            t for t in tasks
            if needle in " ".join(str(t.get(k) or "") for k in ("title", "topic", "category", "project", "description")).casefold()
        ]
    if status:
        tasks = [t for t in tasks if t.get("status", "todo") == status]
    if project:
        tasks = [t for t in tasks if str(t.get("project") or "").casefold() == project.casefold()]
    if category:
        tasks = [t for t in tasks if str(t.get("category") or t.get("topic") or "").casefold() == category.casefold()]
    if sort_by:
        priorities = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        keys = {
            "title": lambda t: str(t.get("title", "")).casefold(),
            "deadline": lambda t: str(t.get("deadline", "")),
            "priority": lambda t: priorities.get(str(t.get("priority", "MEDIUM")), 1),
            "progress": lambda t: float(t.get("progress", 0)),
        }
        tasks = sorted(tasks, key=keys[sort_by], reverse=(sort_by in {"priority", "progress"}))
    return {"view": view, "tasks": tasks}


@app.get("/api/tasks/next")
def next_task() -> Dict[str, Any]:
    return {"task": store.peek_top_task()}


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> Dict[str, Any]:
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"No task {task_id}")
    return {"task": task}


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, payload: TaskUpdate) -> Dict[str, Any]:
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"No task {task_id}")
    raw = payload.model_dump(exclude_unset=True)
    updates: Dict[str, Any] = {}
    for key, value in raw.items():
        if key == "deadline" and value is not None:
            updates[key] = value.isoformat()
        elif key == "priority" and value is not None:
            updates[key] = value.value
        elif key == "status" and value is not None:
            updates[key] = value.value
        elif key in {"title", "topic", "category", "project", "description", "notes", "estimated_hours", "actual_hours", "progress"}:
            if value is not None:
                updates[key] = value
            elif key in {"category", "project"}:
                updates[key] = None
            elif key in {"description", "notes"}:
                updates[key] = ""

    # `notes` is the older name for `description`; keep the two in step.
    if "notes" in updates and "description" not in updates:
        updates["description"] = updates["notes"]
    if "description" in updates and "notes" not in updates:
        updates["notes"] = updates["description"]
    if "category" in updates and "topic" not in updates:
        updates["topic"] = updates["category"] or "General"
    if "topic" in updates and "category" not in updates:
        updates["category"] = updates["topic"] or None

    # Work out completion, progress and status together. Precedence: an
    # explicit `completed` flag, then an explicit `status`, then `progress`.
    # (Before, these were applied one after another and later rules silently
    # undid earlier ones, e.g. status=in_progress on a finished task kept its
    # progress at 100% with 0 h remaining.)
    completed_value = raw.get("completed")
    requested_status = updates.get("status")
    was_completed = bool(task.get("completed", False))
    progress_given = "progress" in updates
    progress = float(updates.get("progress", task.get("progress", 0)))

    if completed_value is not None:
        completed = bool(completed_value)
    elif requested_status is not None:
        completed = requested_status == "completed"
    elif progress_given:
        completed = progress >= 100
    else:
        completed = was_completed

    if completed:
        progress = 100.0
        status = "completed"
    else:
        if requested_status == "todo" or (was_completed and not progress_given):
            # moved back to "to do", or reopened without a new progress value
            progress = 0.0
        progress = min(progress, 100.0)
        if requested_status in {"todo", "in_progress"}:
            status = requested_status
        else:
            status = "in_progress" if progress > 0 else "todo"

    effort = float(updates.get("estimated_hours", task.get("estimated_hours", 0)))
    updates["completed"] = completed
    updates["progress"] = progress
    updates["status"] = status
    updates["remaining_hours"] = 0.0 if completed else round(effort * (1 - progress / 100), 2)

    deadline = updates.get("deadline", task["deadline"])
    priority = updates.get("priority", task["priority"])
    due = date.fromisoformat(str(deadline)[:10])
    score, breakdown = analyze(due, priority, updates["remaining_hours"])
    updates["urgency_score"] = score
    updates["score_breakdown"] = breakdown
    updates["updated_at"] = now_iso()
    updated = store.update_task(task_id, updates)
    return {"task": updated}


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str) -> Dict[str, Any]:
    if not store.delete_task(task_id):
        raise HTTPException(status_code=404, detail=f"No task {task_id}")
    return {"deleted": task_id}


# ---------------------------------------------------------------------- #
# resources
# ---------------------------------------------------------------------- #
@app.post("/api/resources/index")
def index_folder(req: IndexFolderRequest) -> Dict[str, Any]:
    try:
        result = resource_service.index_folder(
            store,
            req.path,
            tags=req.tags,
            recursive=req.recursive,
            read_contents=req.read_contents,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {**result, "library_keywords": store.keyword_trie.word_count}


@app.get("/api/resources/folders")
def library_folders() -> Dict[str, Any]:
    return resource_service.list_folders(store)


@app.post("/api/resources/folders/rescan")
def rescan_library_folders(req: FolderRescanRequest) -> Dict[str, Any]:
    if req.path is None:
        return resource_service.rescan_all(store)
    try:
        return resource_service.rescan_folder(store, req.path)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/api/resources/folders")
def remove_library_folder(path: str = Query(..., min_length=1, max_length=1024)) -> Dict[str, Any]:
    try:
        return resource_service.remove_folder(store, path)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/resources/autocomplete")
def autocomplete(prefix: str = Query(..., min_length=1, max_length=80), limit: int = Query(10, ge=1, le=20)) -> Dict[str, Any]:
    return {
        "prefix": prefix,
        "suggestions": store.keyword_trie.prefix_search(prefix, limit=limit),
    }


@app.get("/api/resources/search")
def search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(8, ge=1, le=50),
    web: bool = False,
) -> Dict[str, Any]:
    return resource_service.search_resources(store, q, top_k=top_k, include_web=web)


@app.get("/api/resources")
def list_resources(limit: int = Query(300, ge=1, le=5000)) -> Dict[str, Any]:
    return {
        "resources": store.all_resources()[:limit],
        "count": store.resource_index.size,
    }


@app.get("/api/resources/{resource_id}")
def get_resource(resource_id: str) -> Dict[str, Any]:
    r = store.get_resource(resource_id)
    if r is None:
        raise HTTPException(status_code=404, detail=f"No resource {resource_id}")
    return {"resource": r}


# ---------------------------------------------------------------------- #
# workspace
# ---------------------------------------------------------------------- #
@app.get("/api/workspace/{task_id}")
def get_workspace(
    task_id: str, top_k: int = Query(6, ge=1, le=20), web: bool = False
) -> Dict[str, Any]:
    ws = workspace.build_workspace(store, task_id, top_k=top_k, include_web=web)
    if ws is None:
        raise HTTPException(status_code=404, detail=f"No task {task_id}")
    return ws


# ---------------------------------------------------------------------- #
# self-rated concept confidence (compatibility; not shown in the interface)
# ---------------------------------------------------------------------- #
@app.get("/api/learning")
def learning_overview() -> Dict[str, Any]:
    return adaptive.learning_overview(store)


@app.get("/api/learning/{task_id}")
def learning_for_task(task_id: str) -> Dict[str, Any]:
    progress = adaptive.get_progress(store, task_id)
    if progress is None:
        raise HTTPException(status_code=404, detail=f"No task {task_id}")
    return progress


@app.put("/api/learning/{task_id}")
def record_mastery(task_id: str, payload: MasteryUpdate) -> Dict[str, Any]:
    progress = adaptive.set_mastery(store, task_id, payload.concept, payload.mastery)
    if progress is None:
        raise HTTPException(status_code=404, detail=f"No task {task_id}")
    return progress


@app.get("/api/learning/{task_id}/plan")
def learning_plan(task_id: str, hours: Optional[float] = None) -> Dict[str, Any]:
    plan = adaptive.study_plan(store, task_id, hours)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"No task {task_id}")
    return plan


@app.get("/api/progress")
def progress_overview() -> Dict[str, Any]:
    return insights.progress_summary(store)


@app.get("/api/deadline-risk")
def deadline_risk() -> Dict[str, Any]:
    return {"risks": insights.all_task_risks(store)}


@app.get("/api/focus/sessions")
def focus_sessions() -> Dict[str, Any]:
    return focus.list_sessions(store)


@app.post("/api/focus/sessions", status_code=201)
def focus_start(payload: FocusSessionStart) -> Dict[str, Any]:
    try:
        return {"session": focus.start_session(store, payload.task_id, payload.objective)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.patch("/api/focus/sessions/{session_id}")
def focus_update(session_id: str, payload: FocusSessionUpdate) -> Dict[str, Any]:
    try:
        session = focus.update_session(store, session_id, payload.action, payload.progress)
        return {"session": session, "task": store.get_task(session["task_id"])}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/api/settings")
def get_settings() -> Dict[str, Any]:
    return dict(store.settings)


@app.patch("/api/settings")
def update_settings(payload: SettingsUpdate) -> Dict[str, Any]:
    store.settings.update(payload.model_dump(exclude_unset=True))
    return dict(store.settings)


# ---------------------------------------------------------------------- #
# planning
# ---------------------------------------------------------------------- #
@app.post("/api/schedule")
def build_schedule(req: ScheduleRequest) -> Dict[str, Any]:
    fn = scheduler.ALGORITHMS.get(req.algorithm)
    if fn is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown algorithm '{req.algorithm}'. "
            f"Choose one of: {', '.join(scheduler.ALGORITHMS)}",
        )
    tasks = [t for t in store.tasks_by_deadline() if not t.get("completed")]
    items = scheduler.to_items(tasks)
    effective_capacity = min(req.capacity_hours, req.daily_hours * 7)
    extra: List[Dict[str, Any]] = []
    if req.include_revision and effective_capacity > 0:
        budget = effective_capacity
        for block in adaptive.revision_blocks(store):
            if budget <= 0:
                break
            hours = min(float(block.get("hours", 0)), budget)
            if hours > 0:
                extra.append({**block, "hours": hours})
                budget -= hours
    revision_capacity = sum(float(block.get("hours", 0)) for block in extra)
    run = fn(items, max(0.0, effective_capacity - revision_capacity))
    timeline = scheduler.build_timeline(
        tasks, run["selected_ids"], daily_hours=req.daily_hours, extra_blocks=extra
    )
    chosen = set(run["selected_ids"])
    return {
        "run": run,
        "timeline": timeline,
        "deferred": [
            {"id": t["id"], "title": t["title"], "hours": t["estimated_hours"],
             "urgency": t["urgency_score"], "deadline": t["deadline"]}
            for t in tasks if t["id"] not in chosen
        ],
        "revision_blocks": extra,
        "capacity_hours": round(effective_capacity, 2),
        "daily_hours": req.daily_hours,
    }


@app.post("/api/plan")
def build_adaptive_plan(req: AdaptivePlanRequest) -> Dict[str, Any]:
    tasks = [task for task in store.tasks_by_deadline() if not task.get("completed")]
    plan = scheduler.adaptive_plan(
        tasks,
        capacity_hours=req.capacity_hours,
        daily_hours=req.daily_hours,
        horizon_days=req.horizon_days,
    )
    risk_by_id = {risk["task_id"]: risk for risk in insights.all_task_risks(store)}
    plan["deferred"] = [
        {**task, "risk": risk_by_id.get(task["id"])} for task in plan["deferred"]
    ]
    return plan


# ---------------------------------------------------------------------- #
# reminders (compatibility endpoint; the dashboard carries deadline risk)
# ---------------------------------------------------------------------- #
@app.get("/api/reminders")
def get_reminders(limit: int = Query(8, ge=1, le=50)) -> Dict[str, Any]:
    return {"reminders": reminders.build_reminders(store, limit=limit)}


# ---------------------------------------------------------------------- #
# demo helpers
# ---------------------------------------------------------------------- #
@app.post("/api/demo/seed")
def seed() -> Dict[str, Any]:
    result = workspace.seed_demo(store)
    sample_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "sample_resources", "demo"
    )
    if os.path.isdir(sample_dir):
        result["resources"] = resource_service.index_folder(
            store, sample_dir, tags=["coursework"]
        )
    return result


@app.post("/api/demo/reset")
def reset() -> Dict[str, str]:
    store.reset()
    return {"status": "reset"}


# ---------------------------------------------------------------------- #
# snapshot — manual save/load on top of the automatic startup/shutdown hooks
# ---------------------------------------------------------------------- #
@app.get("/api/snapshot/status")
def snapshot_status() -> Dict[str, Any]:
    user = _current_user.get()
    return accounts().workspace_status(user) if user else persistence.status()


@app.post("/api/snapshot/save")
def snapshot_save() -> Dict[str, Any]:
    user = _current_user.get()
    if user:
        data = accounts().save_workspace(user)
        return {"path": "your account", "saved_at": data["saved_at"], "tasks": len(data["tasks"])}
    return persistence.save(local_store)


@app.post("/api/snapshot/load")
def snapshot_load() -> Dict[str, Any]:
    if _current_user.get():
        raise HTTPException(status_code=400, detail="Your account is saved automatically; there is no file to load.")
    try:
        return persistence.restore(local_store)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not restore snapshot: {exc}")
