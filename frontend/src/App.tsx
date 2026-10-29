import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import {
  BookMarked,
  CalendarRange,
  Clock3,
  LayoutDashboard,
  ListTodo,
  LogIn,
  LogOut,
  Menu,
  Moon,
  Plus,
  Settings,
  Sun,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { AuthScreen } from "@/components/AuthScreen";
import { LogoCube } from "@/components/LogoCube";
import { TaskDialog } from "@/components/TaskDialog";
import { LoadingState } from "@/components/states";
import { API_BASE, AUTH_EXPIRED_EVENT, api, getToken, setToken, type Task } from "@/lib/api";
import { cn } from "@/lib/utils";

// Each page is its own chunk, so the first visit downloads only the dashboard.
const Dashboard = lazy(() => import("@/pages/Dashboard").then((m) => ({ default: m.Dashboard })));
const Tasks = lazy(() => import("@/pages/Tasks").then((m) => ({ default: m.Tasks })));
const Workspace = lazy(() => import("@/pages/Workspace").then((m) => ({ default: m.Workspace })));
const Resources = lazy(() => import("@/pages/Resources").then((m) => ({ default: m.Resources })));
const Plan = lazy(() => import("@/pages/Plan").then((m) => ({ default: m.Plan })));
const Focus = lazy(() => import("@/pages/Focus").then((m) => ({ default: m.Focus })));
const ProgressPage = lazy(() => import("@/pages/ProgressPage").then((m) => ({ default: m.ProgressPage })));
const SettingsPage = lazy(() => import("@/pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));

const NAV = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "tasks", label: "Tasks", icon: ListTodo },
  { id: "knowledge", label: "Knowledge", icon: BookMarked },
  { id: "plan", label: "Plan", icon: CalendarRange },
  { id: "focus", label: "Focus", icon: Clock3 },
  { id: "progress", label: "Progress", icon: TrendingUp },
  { id: "settings", label: "Settings", icon: Settings },
];

const TITLES: Record<string, { title: string; subtitle: string }> = {
  dashboard: { title: "Dashboard", subtitle: "Your work, next action, and deadlines" },
  tasks: { title: "Tasks", subtitle: "Keep work, effort, and deadlines up to date" },
  knowledge: { title: "Knowledge Vault", subtitle: "Search the files and folders you choose" },
  plan: { title: "Plan", subtitle: "Fit remaining work into the time you have" },
  focus: { title: "Focus", subtitle: "Work on one task and record the time" },
  progress: { title: "Progress", subtitle: "Track completed work and remaining effort" },
  settings: { title: "Settings", subtitle: "Availability, saving, and example data" },
  workspace: { title: "Task details", subtitle: "Progress, deadline risk, and useful resources" },
};

const THEME_KEY = "kairos-theme";

function initialDark(): boolean {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved) return saved === "dark";
  } catch {
    /* storage can be unavailable (private mode); fall back to the system */
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

export default function App() {
  const [page, setPage] = useState("dashboard");
  const [workspaceTask, setWorkspaceTask] = useState<string | null>(null);
  const [focusTask, setFocusTask] = useState<string | null>(null);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [online, setOnline] = useState<boolean | null>(null);
  const [dark, setDark] = useState(initialDark);
  const [navOpen, setNavOpen] = useState(false);
  const [user, setUser] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [loginRequired, setLoginRequired] = useState(false);
  const [showAuth, setShowAuth] = useState(false);
  const [authNotice, setAuthNotice] = useState<string | null>(null);

  // Who is logged in (if anyone), and whether this server requires it.
  useEffect(() => {
    api.me()
      .then((result) => {
        if (getToken() && !result.username) setToken(null);
        setUser(result.username);
        setLoginRequired(result.login_required);
      })
      .catch(() => {})
      .finally(() => setAuthChecked(true));
  }, []);

  useEffect(() => {
    function expired() {
      if (!getToken()) return;
      setToken(null);
      setUser(null);
      setAuthNotice("Your login has expired. Please log in again.");
      setShowAuth(true);
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, expired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, expired);
  }, []);

  // Check on load and whenever data changes; while offline, retry every 10 s
  // so the banner clears once the backend starts.
  useEffect(() => {
    api.health().then(() => setOnline(true)).catch(() => setOnline(false));
  }, [refreshKey]);

  useEffect(() => {
    if (online !== false) return;
    const timer = window.setInterval(() => {
      api.health().then(() => { setOnline(true); setRefreshKey((key) => key + 1); }).catch(() => {});
    }, 10_000);
    return () => window.clearInterval(timer);
  }, [online]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem(THEME_KEY, dark ? "dark" : "light");
    } catch {
      /* not saved; the toggle still works for this visit */
    }
  }, [dark]);

  const bump = useCallback(() => setRefreshKey((key) => key + 1), []);

  function goto(nextPage: string) {
    setPage(nextPage);
    setNavOpen(false);
    window.scrollTo({ top: 0 });
  }

  function openWorkspace(id: string) {
    setWorkspaceTask(id);
    goto("workspace");
  }

  function openFocus(id: string) {
    setFocusTask(id);
    goto("focus");
  }

  function newTask() {
    setEditingTask(null);
    setDialogOpen(true);
  }

  function editTask(task: Task) {
    setEditingTask(task);
    setDialogOpen(true);
  }

  function signedIn(token: string, username: string) {
    setToken(token);
    setUser(username);
    setShowAuth(false);
    setAuthNotice(null);
    goto("dashboard");
    bump();
  }

  function logOut() {
    api.logOut().catch(() => {}).finally(() => {
      setToken(null);
      setUser(null);
      goto("dashboard");
      bump();
    });
  }

  if (!authChecked) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <div className="app-backdrop" aria-hidden />
        <LoadingState />
      </div>
    );
  }

  if (loginRequired && !user) {
    return <AuthScreen onSignedIn={signedIn} notice={authNotice} />;
  }

  const meta = TITLES[page] ?? TITLES.dashboard;
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });

  return (
    <div className="flex min-h-screen">
      <div className="app-backdrop" aria-hidden />

      <aside
        className={cn(
          "glass fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col border-r p-3 transition-transform duration-300 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0",
          navOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex items-center gap-2 px-2 py-3">
          <LogoCube />
          <div>
            <h1 className="text-base font-bold leading-none tracking-tight">KAIROS</h1>
            <p className="mt-1 text-[10px] leading-tight text-muted-foreground">Work with the time you have</p>
          </div>
        </div>

        <Button className="my-3 justify-start gap-2" onClick={newTask}>
          <Plus className="h-4 w-4" /> New task
        </Button>

        <nav className="space-y-1" aria-label="Main navigation">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = page === item.id || (page === "workspace" && item.id === "tasks");
            return (
              <button
                key={item.id}
                onClick={() => goto(item.id)}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all",
                  active
                    ? "surface bg-card text-foreground"
                    : "text-muted-foreground hover:translate-x-0.5 hover:bg-card/60 hover:text-foreground"
                )}
              >
                <span
                  className={cn(
                    "rounded-md p-1 transition-colors",
                    active ? "bg-primary text-primary-foreground shadow-md shadow-primary/30" : "group-hover:text-primary"
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                </span>
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="mt-auto space-y-3 px-1">
          {user ? (
            <div className="surface flex items-center gap-2 rounded-lg border bg-card px-2 py-2">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-[hsl(var(--glow-2))] text-xs font-bold uppercase text-white">
                {user.charAt(0)}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm font-medium" data-testid="account-name">{user}</span>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={logOut} aria-label="Log out" title="Log out">
                <LogOut className="h-3.5 w-3.5" />
              </Button>
            </div>
          ) : (
            <Button variant="outline" size="sm" className="w-full justify-start gap-2" onClick={() => { setAuthNotice(null); setShowAuth(true); }}>
              <LogIn className="h-4 w-4" /> Log in or sign up
            </Button>
          )}
          <Button variant="ghost" size="sm" className="w-full justify-start gap-2" onClick={() => setDark((value) => !value)}>
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            {dark ? "Light appearance" : "Dark appearance"}
          </Button>
          <div className="flex items-center gap-2 px-2 text-[11px] text-muted-foreground">
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                online === null ? "bg-slate-400" : online ? "bg-emerald-500 shadow-[0_0_8px] shadow-emerald-500" : "bg-rose-500"
              )}
            />
            Backend {online === null ? "checking…" : online ? "connected" : "offline"}
          </div>
        </div>
      </aside>

      {navOpen && (
        <div className="fixed inset-0 z-30 bg-black/40 backdrop-blur-[2px] lg:hidden" onClick={() => setNavOpen(false)} />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="glass sticky top-0 z-20 flex items-center gap-3 border-b px-4 py-3 sm:px-6">
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setNavOpen(true)} aria-label="Open menu">
            <Menu className="h-4 w-4" />
          </Button>
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-lg font-bold leading-tight tracking-tight">{meta.title}</h2>
            <p className="truncate text-xs text-muted-foreground">{meta.subtitle}</p>
          </div>
          <span className="hidden rounded-full border bg-card/70 px-3 py-1 text-xs text-muted-foreground sm:inline">{today}</span>
        </header>

        <main className="mx-auto w-full min-w-0 max-w-[1400px] flex-1 p-4 sm:p-6">
          {online === false && (
            <div className="mb-4 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm">
              {API_BASE.startsWith("https://") ? (
                <>Can’t reach the backend at <code className="font-mono text-xs">{API_BASE}</code>. A free server can take up to a minute to wake up; this page retries automatically.</>
              ) : (
                <>Can’t reach the backend. Start it with <code className="font-mono text-xs">uvicorn app.main:app --reload --port 8000</code> in the <code className="font-mono text-xs">backend</code> folder.</>
              )}
            </div>
          )}

          <Suspense fallback={<LoadingState />}>
            <div key={page} className="animate-in fade-in-0 slide-in-from-bottom-1 duration-300">
              {page === "dashboard" && (
                <Dashboard refreshKey={refreshKey} onOpenWorkspace={openWorkspace} onNewTask={newTask} onGoto={goto} onStartFocus={openFocus} />
              )}
              {page === "tasks" && (
                <Tasks refreshKey={refreshKey} onChanged={bump} onOpenWorkspace={openWorkspace} onNewTask={newTask} onEditTask={editTask} />
              )}
              {page === "workspace" && (
                <Workspace taskId={workspaceTask} onBack={() => goto("tasks")} onChanged={bump} onStartFocus={openFocus} />
              )}
              {page === "knowledge" && <Resources onChanged={bump} />}
              {page === "plan" && <Plan refreshKey={refreshKey} />}
              {page === "focus" && <Focus taskId={focusTask} refreshKey={refreshKey} onChanged={bump} />}
              {page === "progress" && <ProgressPage refreshKey={refreshKey} onOpenTask={openWorkspace} />}
              {page === "settings" && <SettingsPage refreshKey={refreshKey} onChanged={bump} />}
            </div>
          </Suspense>
        </main>
      </div>

      {showAuth && <AuthScreen onSignedIn={signedIn} onCancel={() => setShowAuth(false)} notice={authNotice} />}

      <TaskDialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) setEditingTask(null);
        }}
        initialTask={editingTask}
        onCreated={(id) => {
          bump();
          if (!editingTask) openWorkspace(id);
          setEditingTask(null);
        }}
      />
    </div>
  );
}
