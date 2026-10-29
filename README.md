# KAIROS v1.0

**Knowledge Acquisition, Indexing, Ranking & Optimized Scheduling**

KAIROS is a subject-independent academic productivity and knowledge-management system. It helps users organize work, find relevant files from folders they choose, plan around deadlines and available time, choose a next action, focus, track progress, and adapt remaining work.

Users work with tasks, resources, plans, and deadlines; implementation details stay out of the interface.

## Product workflow

```text
Task → Context → Relevant resources → Priority → Plan → Focus
     → Progress → Deadline risk → Replanning → Next action
```

## v1.0 capabilities

- **Smart Tasks:** create, edit, complete, delete, search, filter, and sort tasks with a project/category, deadline, priority, effort, status, and progress.
- **Knowledge Vault:** explicitly index a folder path that the user chooses. KAIROS stores references and metadata; source files stay in place. Added folders are listed in the library, where each can be rescanned or removed; a rescan drops entries for files that were deleted from disk.
- **Resource Search:** search file names, tags, folder names, and extracted text with match reasons and deterministic relevance points.
- **Adaptive Planner:** plan remaining effort against weekly and daily availability; completed focus time and task progress change future workload.
- **Recommended next action:** rank open tasks using urgency and deadline risk, and explain the selected task, remaining effort, and suggested session length.
- **Focus Sessions:** start, pause, resume, and finish one session at a time. Session duration contributes to actual effort; progress can be set at the end or estimated from focused time.
- **Progress:** see effort-weighted task progress, completed tasks, planned effort, recorded effort, and remaining workload.
- **Deadline Risk:** compare remaining task effort with the available hours before the due date. States are Low, Moderate, High, and Critical; they are workload estimates, not probabilities.

## Run locally

Requirements: Python 3.10+, Node.js 18+, and npm.

### Backend

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

The API listens on loopback at <http://127.0.0.1:8000>. API documentation is at <http://127.0.0.1:8000/docs>.

### Frontend

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` requests to the local backend.

### Hosted frontend (for example Netlify)

A static host serves only the frontend; the API still has to run somewhere. Build with the backend's address, and allow the hosted origin on the backend:

```powershell
# frontend build
$env:VITE_API_BASE = "https://your-backend.example.com"; npm run build
# backend
$env:KAIROS_CORS_ORIGINS = "https://kairos-study-planner.netlify.app"
```

Without `VITE_API_BASE`, a hosted build sends `/api` requests to the static host itself and shows "Can't reach the backend".

To host the backend on Render, push the project to GitHub and create a Blueprint from `render.yaml`. A hosted backend can index only the folders in `KAIROS_ALLOWED_ROOTS` (the sample files), keeps one shared workspace for everyone who opens the site, and on the free plan sleeps when idle and loses saved data when it restarts.

### Tests and checks

```powershell
cd backend
python -m pytest -q
```

Frontend type-check and production build:

```powershell
cd frontend
npx tsc -b --noEmit
npm run build
```

Browser walk-through of the demo flow (optional; needs Playwright, which is not a project dependency). It refuses to run unless the backend workspace is empty, so point the backend at a throwaway snapshot first:

```powershell
# terminal 1, backend folder
$env:KAIROS_SNAPSHOT_PATH = "$env:TEMP\kairos_e2e.json"; Remove-Item $env:KAIROS_SNAPSHOT_PATH -ErrorAction Ignore
python -m uvicorn app.main:app --port 8000
# terminal 2, frontend folder
npm run dev
# terminal 3, frontend folder
npm install --no-save playwright
npx playwright install chromium
node e2e/demo-flow.mjs
```

Performance profile (indexing throughput, in-process API latency, autosave cost) on generated data in a temporary folder:

```powershell
cd backend
python scripts/profile_kairos.py --json profile.json
```

## Walkthrough demo

1. Open **Settings → Load example data**. This creates generic work such as a Project Report due Friday, Research Assignment, Presentation, and Lab Work. It also indexes the sample project files under `backend/sample_resources/demo`.
2. Set **Hours available per day** to 1.5. The dashboard compares the Project Report’s remaining effort with the time available through its Friday deadline and shows a risk state and explanation.
3. Open **Knowledge** and search for “project report” or “research”. Results show the file path, file type, match points, and why each file matched. Public web suggestions start off; enabling them sends the search terms to Wikipedia. The **Your library** panel lists the example folder; add another folder, delete a file from it on disk, and press **Rescan** to see the entry removed. **Remove** forgets a folder's entries without touching the files.
4. Open **Plan**, review the week plan, and change daily or total availability. No task is scheduled beyond the stated total capacity or daily hours.
5. On the dashboard, start the **recommended focus session** for the Project Report. Pause/resume if needed, then finish the session. KAIROS records actual hours and updates estimated progress and remaining effort. Enter a progress percentage at completion if you want to replace the time-based estimate.
6. Return to **Dashboard** or **Plan**. Deadline risk and the plan are recalculated from the updated progress and availability.

## Architecture

```text
React + TypeScript + Vite
        │ /api (same-origin Vite proxy)
        ▼
FastAPI + Pydantic
        ├── task and scheduling services
        ├── resource indexing and ranking
        ├── progress, deadline-risk, and focus services
        └── JSON snapshot persistence
```

The current persistence layer is a versioned JSON snapshot, not a database. It restores on startup and, while the server runs, saves after every successful change (task, focus session, setting, or library update). Each save writes a temporary file and atomically replaces the previous snapshot, so an abrupt stop loses at most the request in flight. A final save also runs on graceful shutdown. Set `KAIROS_SNAPSHOT_PATH` to choose a snapshot path, or `KAIROS_AUTOSAVE=0` to save only on shutdown. **Settings → Saving** shows the snapshot path, the last save time, and any save error. The application is designed for a local, single-user workflow; it has no authentication or cloud sync.

## API overview

- `GET /api/dashboard` — summary, recommended next action, upcoming tasks, and deadline risks.
- `GET/POST /api/tasks`, `GET/PATCH/DELETE /api/tasks/{id}` — task operations. Listing supports deadline/priority view, text query, status, project, and category filters.
- `POST /api/resources/index` — explicitly index a supplied folder path and add it to the library. Re-indexing refreshes changed files and removes entries for files that are gone.
- `GET /api/resources/folders` — library folders with file counts, scan options, last result, and whether each still exists on disk.
- `POST /api/resources/folders/rescan` — rescan one folder (`{"path": ...}`) with its saved options, or all folders (`{}`).
- `DELETE /api/resources/folders?path=...` — forget a folder and the entries only it covers. Files on disk are not touched.
- `GET /api/resources/search`, `GET /api/resources/autocomplete`, `GET /api/resources` — search and browse indexed references.
- `POST /api/plan` — generate the primary adaptive plan within total, daily, and deadline-aware availability.
- `GET /api/progress`, `GET /api/deadline-risk` — task progress and explainable risk.
- `GET/POST /api/focus/sessions`, `PATCH /api/focus/sessions/{id}` — focus-session lifecycle.
- `GET/PATCH /api/settings` — daily availability.
- `GET/POST /api/snapshot/*` — inspect, save, or restore the local JSON snapshot. Status includes the autosave state.

Compatibility endpoints that the interface does not use: `/api/learning*` (self-rated concept confidence and a weighted study plan), `/api/reminders`, and `/api/schedule` (capacity-limited task selection with a timeline). The benchmarking, structure-inspection, and strategy-comparison endpoints were removed on 25 October 2026.

## Implementation notes

Maintainer-level notes on how tasks, the file library, search, and planning are implemented internally, with their costs, are in [docs/ADSA.md](docs/ADSA.md). They are technical working notes, not product documentation.

## Resource formats and privacy

- Text and source files are read up to 64 KB for keywords/snippets.
- DOCX and PPTX text is read from bounded XML members. PDF extraction uses pypdf for files up to 20 MB and up to the first five pages.
- KAIROS indexes at most 2,000 files from one explicitly supplied folder request. It skips hidden and common dependency/build folders and does not follow symbolic links.
- Re-indexing a folder skips unchanged files, refreshes changed file contents/tags, and removes entries for files deleted from disk or no longer reached by the scan (for example after switching to top-level only). If a scan stops at the 2,000-file limit, only entries for deleted files are removed.
- Removing a folder from the library drops the entries only that folder covers; entries also covered by another library folder stay.
- Files are referenced by path; they are not copied or sent to a remote service.
- Web suggestions are off by default. If enabled, the search terms are sent to Wikipedia; local file contents are not sent.
- CORS is restricted to the local Vite development origins. Keep the backend on loopback and do not expose this local-file API to an untrusted network.

## Known limitations

- JSON snapshot persistence is single-process. Every change rewrites the whole snapshot, which costs tens of milliseconds per change once the library holds thousands of files (see the profile script). There is no transactional database or multi-user support. Public web suggestions are returned with each search only; they are not stored in the library or the snapshot.
- PDF extraction depends on pypdf; scanned image PDFs do not receive OCR.
- The risk estimate assumes the configured daily availability is similar through the deadline. It does not connect to a calendar and is not a probability.
- Time-based progress after a focus session is an estimate. Users can replace it with a self-reported progress value.
- Search uses bounded keyword extraction and deterministic weights, not semantic embeddings or TF-IDF.
- Folder indexing is initiated by entering an explicit local path; there is no OS-native folder picker. Folders indexed before folder tracking existed are counted as unmanaged until they are indexed again.
- Nested library folders with different tags share file entries; rescanning each one re-tags the shared files with that folder's tags.
- Self-rated concept confidence, the weighted study plan built from it, and the reminder list exist only as compatibility endpoints; the interface does not show them. Deadline-related prompts in the interface are the dashboard's deadline-risk list, upcoming tasks, and recommended next action. There are no notifications.

## Future roadmap

Only after the Tier 1 workflow is stable:

- **v2.0:** workload health, daily briefing, end-of-day review, adaptive reminders, and project health.
- **v3.0:** natural-language commands, project mode, personal productivity insights, predictive risk, and advanced resource recommendations.

KAIROS does not claim universal novelty, optimal personal decisions, predictive risk, or performance gains without supporting evidence.

## Accounts, calendar and charts

- **Accounts.** Sign up and log in from the sidebar. Each account has its own private tasks, plans and focus history. Users and login sessions are kept in the project's own hash table, and passwords are stored as salted PBKDF2 hashes. On your own computer, login is optional and accounts are saved in `backend/kairos_data/`. On the hosted server, `KAIROS_REQUIRE_LOGIN=1` makes login required, and `KAIROS_DATABASE_URL` stores accounts in Postgres, because Render's free disk is wiped whenever the server restarts.
- **Calendar.** Plan → Calendar shows planned study time and deadlines on a month grid. **Export to calendar (.ics)** downloads a file you can import into Google Calendar, Outlook or Apple Calendar.
- **Charts.** Progress shows focus hours for the last 14 days, and planned versus tracked hours for each task.
