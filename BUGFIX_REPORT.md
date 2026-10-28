# KAIROS bug-fix report (28 October 2026)

All 197 existing backend tests passed before and after the changes. 7 new
regression tests in `backend/tests/test_bug_fixes.py` fail on the old code and
pass now (204 total). TypeScript check, production build and the
`e2e/demo-flow.mjs` browser walk-through (14 steps) all pass.

A copy of the original source is in `_backup_before_fixes/kairos_src_backup.tgz`.
Files that were removed as unused are in `_backup_before_fixes/removed_unused/`.

## Bugs fixed

### 1. Urgency scores went stale every day (backend, high impact)
**Symptom:** the "By priority" order, the dashboard's "next task" and the
recommended next action ranked tasks by how urgent they were *on the day they
were created*. A task created "due in 5 days" kept that low score even when it
was due today, and overdue tasks never got the +40 overdue penalty.
**Root cause:** `urgency = ... + 100 / (1 + days_to_deadline) ...` depends on
today's date, but the score was computed once at create/edit time and stored in
the task and the heap. Snapshots restored on a later day kept old scores too.
**Fix:** `KairosStore.refresh_urgency_scores()` recomputes all open tasks and
rebuilds the heap. It runs automatically the first time tasks are read on a new
day, and after every snapshot restore. (`services/store.py`, `services/persistence.py`)

### 2. Dynamic-programming scheduler could overbook hours (backend)
**Root cause:** hours were converted to 0.5 h units with `round()`, so a 0.7 h
task counted as 0.5 h; three of them "fit" into 1.5 h but really need 2.1 h.
**Fix:** task hours round **up** and capacity rounds **down**, so DP never
selects more real hours than available. (`services/scheduler.py`)

### 3. Editing a task's status/progress could leave it in an impossible state (backend)
**Symptom:** setting a completed task back to "in progress" kept progress at
100% and 0 h remaining; sending `status=completed` together with a progress
value below 100 silently un-completed it.
**Root cause:** `PATCH /api/tasks/{id}` applied `status`, then `progress`, then
`completed` one after another, and later rules overwrote earlier ones.
**Fix:** one clear precedence: explicit `completed` → explicit `status` →
`progress`. Reopening without a new progress value resets progress to 0.
(`main.py`)

### 4. Web suggestions polluted the library (backend)
**Symptom:** each search with "Public web" on added Wikipedia links to the
library: the dashboard's "files in your selected folders" count grew,
autocomplete offered words like "web"/"article" that local search could never
return, and the links were saved in the snapshot forever.
**Root cause:** `fetch_web_resources` inserted web results into the resource
hash table and keyword Trie, while `search_resources` only ever returns local
files from the Trie.
**Fix:** web suggestions are returned per search and never stored; old
snapshots drop stored web entries on load. (`services/resource_service.py`,
`services/persistence.py`)

### 5. Reminder workload ignored task progress (backend)
**Root cause:** reminders computed "hours remaining" only from self-rated
concept mastery (usually 0), so an 80%-done task still showed its full estimate.
**Fix:** use the task's own remaining hours (mastery can only lower it).
Reminders and the dashboard also read tasks through the refreshed path from #1.
(`services/reminders.py`)

### 6. Focus timer counted time twice after a reload (frontend, high impact)
**Symptom:** opening the Focus page during a running session showed roughly
double the real elapsed time.
**Root cause:** the server's `elapsed_seconds` already includes the active time
up to the response, and the page added `now - started_at` on top of it.
**Fix:** the page adds only the time since the response arrived. (`pages/Focus.tsx`)

### 7. "By priority" tab on Tasks did nothing (frontend)
**Root cause:** the page always re-sorted the list client-side, defaulting to
"Sort: deadline", which threw away the server's urgency-heap order.
**Fix:** new default "tab order" sort keeps the server's order; the other sort
options still work. (`pages/Tasks.tsx`)

### 8. Smaller frontend fixes
- "Can't reach the backend" banner never cleared once shown; it now retries every 10 s. (`App.tsx`)
- Dashboard and Progress pages stayed on an error after one failed load; errors now clear on the next successful load.
- "Recent sessions" on Focus showed an empty box (no message) when only an active session existed.
- A malformed web link (`new URL(...)` throwing) crashed the whole results list; now handled.
- Validation errors (HTTP 422) were shown as raw JSON; now shown as "field: message".
- Task details page built its own search query instead of using the workspace endpoint, so its "relevant resources" differed from Dashboard/Focus; it now uses the same endpoint.

## Deployment note (Netlify)
The Netlify site only hosts the frontend. Without `VITE_API_BASE` set at build
time, it sends `/api/...` to Netlify itself, so it can only ever show "Can't
reach the backend". The backend also only allowed `localhost:5173` for CORS. I
added `KAIROS_CORS_ORIGINS` (comma-separated) to the backend and documented both
settings in the README. You still need to host the FastAPI backend somewhere and
rebuild the frontend with its URL. I could not open the live site from here to
check it directly.

## Clean-up
- `create_task` and the example-data seeder built the same task record twice; both now use `store.build_task()`.
- Risk badge colours were copied into 3 pages and the `Metric` tile into 3 pages; now `RISK_STYLES` in `lib/format.ts` and `components/Metric.tsx`.
- Removed unused API client methods (learning, mastery, schedule, reminders) and types, unused format helpers, unused variables in `hash_table.py` and `resource_service.py`, and a redundant notes/description sync in `main.py`.
- Moved unused files to `_backup_before_fixes/removed_unused/`: UI components `checkbox`, `scroll-area`, `slider`, `table`, and `assets/react.svg`, `vite.svg`, `hero.png`.

## Not changed (worth knowing)
- Leftover `pytest-cache-files-*` and `.pytest-tmp` folders at the project root, plus `KAIROS.zip` and an empty `frontend/src/assets` folder, are safe to delete by hand.
- `@radix-ui/react-scroll-area` and `@radix-ui/react-switch` in `package.json` are now unused. I left them so `package-lock.json` stays in sync; remove them with `npm uninstall` if you like.
