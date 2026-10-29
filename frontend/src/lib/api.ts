/** REST client for the KAIROS backend. */

export type Priority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface ScoreBreakdown {
  priority_component: number;
  deadline_component: number;
  workload_component: number;
  overdue_penalty: number;
  days_to_deadline: number;
  formula: string;
}

export interface Task {
  id: string;
  title: string;
  topic: string;
  category?: string | null;
  project?: string | null;
  description?: string;
  deadline: string;
  priority: Priority;
  estimated_hours: number;
  notes: string;
  progress: number;
  status: "todo" | "in_progress" | "completed";
  actual_hours: number;
  remaining_hours: number;
  urgency_score: number;
  score_breakdown: ScoreBreakdown;
  created_at: string;
  updated_at: string;
  completed: boolean;
}

export interface DeadlineRisk {
  task_id: string;
  title: string;
  level: "Low" | "Moderate" | "High" | "Critical";
  days_to_deadline: number;
  remaining_hours: number;
  available_hours_before_deadline: number;
  workload_ratio: number | null;
  explanation: string;
}

export interface FocusSession {
  id: string;
  task_id: string;
  task_title: string;
  objective: string;
  status: "active" | "paused" | "completed";
  created_at: string;
  started_at: string | null;
  paused_at: string | null;
  completed_at: string | null;
  elapsed_seconds: number;
}

export interface ProgressSummary {
  overall_progress: number;
  completed_tasks: number;
  remaining_tasks: number;
  planned_hours: number;
  actual_hours: number;
  remaining_hours: number;
  tasks: (Task & { risk: DeadlineRisk | null })[];
}

export interface Resource {
  id: string;
  title: string;
  source: "local" | "web";
  kind: string;
  location: string;
  tags: string[];
  keywords: string[];
  /** Terms extracted from the file's own text, not its name. */
  content_keywords: string[];
  size_bytes: number | null;
  modified: string | null;
  snippet: string;
}

/** A folder the user added to the library, with the options used to scan it. */
export interface LibraryFolder {
  path: string;
  tags: string[];
  recursive: boolean;
  read_contents: boolean;
  added_at: string;
  last_indexed_at: string;
  last_result?: IndexOutcome;
  /** library files this folder's scan covers */
  resource_count: number;
  /** false when the folder was moved or deleted on disk */
  exists: boolean;
}

export interface IndexOutcome {
  indexed: number;
  updated: number;
  /** entries dropped because the file was deleted or is no longer reached */
  removed: number;
  skipped: number;
  text_indexed: number;
  /** the scan stopped at the per-request file limit */
  truncated: boolean;
}

export interface SnapshotStatus {
  path: string;
  /** set when the workspace belongs to a logged-in account */
  account?: string;
  exists: boolean;
  readable?: boolean;
  saved_at?: string;
  tasks?: number;
  resources?: number;
  autosave: {
    enabled: boolean;
    last_saved_at: string | null;
    last_error: string | null;
    saves: number;
  };
}

export interface RankedResource {
  resource: Resource;
  score: number;
  reasons: string[];
}

export interface ConceptRow {
  concept: string;
  mastery: number;
  status: "weak" | "developing" | "strong" | "unassessed";
  assessed: boolean;
  effective: number;
}

export interface Progress {
  task_id: string;
  task_title: string;
  topic: string;
  concepts: ConceptRow[];
  overall_mastery: number;
  assessed_count: number;
  weak_areas: string[];
  weak_threshold: number;
}

export interface PlanBlock {
  concept: string;
  mastery: number;
  status: string;
  hours: number;
  weight: number;
  reason: string;
}

export interface StudyPlan {
  task_id: string;
  task_title: string;
  topic: string;
  total_hours: number;
  allocated_hours: number;
  overall_mastery: number;
  weak_areas: string[];
  blocks: PlanBlock[];
  explanation: string;
}

export interface TimelineBlock {
  task_id: string;
  title: string;
  topic?: string;
  hours: number;
  deadline?: string;
  kind: "task" | "revision";
  overdue?: boolean;
  concept?: string;
}

export interface TimelineDay {
  date: string;
  hours: number;
  blocks: TimelineBlock[];
}

export interface Reminder {
  task_id: string;
  title: string;
  topic: string;
  deadline: string;
  days_to_deadline: number;
  level: "info" | "soon" | "urgent" | "overdue";
  remaining_hours: number;
  mastery: number;
  weak_area: string | null;
  message: string;
  urgency: number;
}

/** Backend address; empty means same origin (the Vite dev proxy). */
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "";
const BASE = API_BASE;

const TOKEN_KEY = "kairos-token";
/** Fired when the server rejects the saved login, so the app can show the login screen. */
export const AUTH_EXPIRED_EVENT = "kairos:auth-expired";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: the login lasts for this visit only */
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) {
        // FastAPI validation errors: [{ loc: [...], msg: "..." }, ...]
        detail = body.detail
          .map((item: { loc?: unknown[]; msg?: string }) =>
            [item.loc?.[item.loc.length - 1], item.msg].filter(Boolean).join(": "))
          .join("; ");
      } else if (body.detail !== undefined) detail = JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

const post = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () =>
    request<{ status: string; name: string; tagline: string; urgency_formula: string; login_required?: boolean }>("/api/health"),

  // accounts ----------------------------------------------------------
  signUp: (username: string, password: string) =>
    post<{ token: string; username: string }>("/api/auth/signup", { username, password }),
  logIn: (username: string, password: string) =>
    post<{ token: string; username: string }>("/api/auth/login", { username, password }),
  logOut: () => post<{ status: string }>("/api/auth/logout", {}),
  me: () => request<{ username: string | null; login_required: boolean }>("/api/auth/me"),


  dashboard: () =>
    request<{
      today: string;
      open_tasks: number;
      completed_tasks: number;
      overdue: number;
      due_today: number;
      due_this_week: number;
      total_hours: number;
      week_hours: number;
      next_task: Task | null;
      upcoming: Task[];
      reminders: Reminder[];
      resources_indexed: number;
      keywords_indexed: number;
      recommended_action: {
        task: Task;
        risk: DeadlineRisk;
        available_hours_now: number;
        recommended_session_minutes: number;
        reasons: string[];
        label: string;
      } | null;
      deadline_risks: DeadlineRisk[];
      high_risk_count: number;
      overall_progress: number;
      actual_hours: number;
      remaining_hours: number;
      available_hours_per_day: number;
    }>("/api/dashboard"),

  progressOverview: () => request<ProgressSummary>("/api/progress"),
  deadlineRisks: () => request<{ risks: DeadlineRisk[] }>("/api/deadline-risk"),
  settings: () => request<{ available_hours_per_day: number }>("/api/settings"),
  updateSettings: (body: { available_hours_per_day: number }) =>
    request<{ available_hours_per_day: number }>("/api/settings", {
      method: "PATCH", body: JSON.stringify(body),
    }),
  focusSessions: () =>
    request<{ current: FocusSession | null; sessions: FocusSession[] }>("/api/focus/sessions"),
  startFocusSession: (body: { task_id: string; objective?: string }) =>
    post<{ session: FocusSession }>("/api/focus/sessions", body),
  updateFocusSession: (
    id: string,
    body: { action: "pause" | "resume" | "complete"; progress?: number },
  ) =>
    request<{ session: FocusSession; task: Task | null }>(`/api/focus/sessions/${id}`, {
      method: "PATCH", body: JSON.stringify(body),
    }),

  // tasks -------------------------------------------------------------
  createTask: (body: {
    title: string;
    topic?: string;
    category?: string | null;
    project?: string | null;
    description?: string;
    deadline: string;
    priority: Priority;
    estimated_hours: number;
    notes?: string;
  }) => post<{ task: Task; concepts: string[] }>("/api/tasks", body),

  listTasks: (view: "deadline" | "priority") =>
    request<{ view: string; tasks: Task[] }>(`/api/tasks?view=${view}`),

  getTask: (id: string) => request<{ task: Task }>(`/api/tasks/${id}`),

  updateTask: (
    id: string,
    body: Partial<Pick<Task, "completed" | "title" | "topic" | "category" | "project" | "description" | "notes" | "deadline" | "priority" | "estimated_hours" | "progress" | "status" | "actual_hours">>,
  ) =>
    request<{ task: Task }>(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify(body) }),

  deleteTask: (id: string) =>
    request<{ deleted: string }>(`/api/tasks/${id}`, { method: "DELETE" }),

  // resources ---------------------------------------------------------
  indexFolder: (path: string, tags: string[], readContents = true) =>
    post<IndexOutcome & {
      path: string;
      /** distinct searchable keywords across the whole library */
      library_keywords: number;
    }>("/api/resources/index", {
      path,
      tags,
      recursive: true,
      read_contents: readContents,
    }),

  libraryFolders: () =>
    request<{ folders: LibraryFolder[]; unmanaged_count: number }>("/api/resources/folders"),

  rescanFolder: (path: string) =>
    post<IndexOutcome & { path: string }>("/api/resources/folders/rescan", { path }),

  rescanAllFolders: () =>
    post<{
      results: ((IndexOutcome & { ok: true; path: string }) | { ok: false; path: string; error: string })[];
      indexed: number;
      updated: number;
      removed: number;
      skipped: number;
    }>("/api/resources/folders/rescan", {}),

  removeFolder: (path: string) =>
    request<{ path: string; removed: number }>(
      `/api/resources/folders?path=${encodeURIComponent(path)}`,
      { method: "DELETE" },
    ),

  snapshotStatus: () => request<SnapshotStatus>("/api/snapshot/status"),

  autocomplete: (prefix: string) =>
    request<{ suggestions: string[] }>(
      `/api/resources/autocomplete?prefix=${encodeURIComponent(prefix)}&limit=8`
    ),

  search: (q: string, topK: number, web: boolean) =>
    request<{
      query: string;
      autocomplete: string[];
      local_matches: number;
      web_matches: number;
      results: RankedResource[];
    }>(`/api/resources/search?q=${encodeURIComponent(q)}&top_k=${topK}&web=${web}`),

  listResources: () =>
    request<{ resources: Resource[]; count: number }>("/api/resources"),

  // workspace ---------------------------------------------------------
  workspace: (taskId: string, topK: number, web: boolean) =>
    request<{
      task: Task;
      query: string;
      resources: RankedResource[];
      local_resources: RankedResource[];
      web_resources: RankedResource[];
      progress: Progress;
      study_plan: StudyPlan;
    }>(`/api/workspace/${taskId}?top_k=${topK}&web=${web}`),

  // scheduling --------------------------------------------------------
  adaptivePlan: (body: { capacity_hours: number; daily_hours: number; horizon_days?: number }) =>
    post<{
      timeline: TimelineDay[];
      scheduled_hours: number;
      capacity_hours: number;
      daily_hours: number;
      horizon_days: number;
      task_count: number;
      selected: { id: string; title: string; hours: number }[];
      deferred: {
        id: string;
        title: string;
        deadline: string;
        priority: Priority;
        hours: number;
        scheduled_hours: number;
        reason: string;
        risk: DeadlineRisk | null;
      }[];
    }>("/api/plan", body),

  seed: () => post<{ count: number }>("/api/demo/seed", {}),
  reset: () => post<{ status: string }>("/api/demo/reset", {}),
};
