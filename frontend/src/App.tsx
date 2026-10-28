import { useCallback, useEffect, useState } from "react";
import {
  BookMarked,
  CalendarRange,
  Clock3,
  LayoutDashboard,
  ListTodo,
  Menu,
  Moon,
  Plus,
  Settings,
  Sun,
  TrendingUp,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { TaskDialog } from "@/components/TaskDialog";
import { Dashboard } from "@/pages/Dashboard";
import { Focus } from "@/pages/Focus";
import { Plan } from "@/pages/Plan";
import { ProgressPage } from "@/pages/ProgressPage";
import { Resources } from "@/pages/Resources";
import { SettingsPage } from "@/pages/SettingsPage";
import { Tasks } from "@/pages/Tasks";
import { Workspace } from "@/pages/Workspace";
import { API_BASE, api, type Task } from "@/lib/api";
import { cn } from "@/lib/utils";

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

export default function App() {
  const [page, setPage] = useState("dashboard");
  const [workspaceTask, setWorkspaceTask] = useState<string | null>(null);
  const [focusTask, setFocusTask] = useState<string | null>(null);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [online, setOnline] = useState<boolean | null>(null);
  const [dark, setDark] = useState(false);
  const [navOpen, setNavOpen] = useState(false);

  // Check on load and whenever data changes; while offline, retry every 10 s
  // so the banner clears once the backend starts (it used to stay forever).
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
  }, [dark]);

  const bump = useCallback(() => setRefreshKey((key) => key + 1), []);

  function openWorkspace(id: string) {
    setWorkspaceTask(id);
    setPage("workspace");
    setNavOpen(false);
  }

  function openFocus(id: string) {
    setFocusTask(id);
    setPage("focus");
    setNavOpen(false);
  }

  function goto(nextPage: string) {
    setPage(nextPage);
    setNavOpen(false);
  }

  function newTask() {
    setEditingTask(null);
    setDialogOpen(true);
  }

  function editTask(task: Task) {
    setEditingTask(task);
    setDialogOpen(true);
  }

  const meta = TITLES[page] ?? TITLES.dashboard;

  return (
    <div className="flex min-h-screen bg-muted/20">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-60 shrink-0 flex-col border-r bg-background p-3 transition-transform lg:static lg:translate-x-0",
          navOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="px-2 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <span className="text-sm font-bold">K</span>
            </div>
            <div>
              <h1 className="text-base font-semibold leading-none tracking-tight">KAIROS</h1>
              <p className="mt-0.5 text-[10px] leading-tight text-muted-foreground">
                Work with the time you have
              </p>
            </div>
          </div>
        </div>

        <Separator className="my-2" />
        <Button className="mb-3 justify-start gap-2" onClick={newTask}>
          <Plus className="h-4 w-4" /> New task
        </Button>

        <nav className="space-y-0.5" aria-label="Main navigation">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = page === item.id || (page === "workspace" && item.id === "tasks");
            return (
              <button
                key={item.id}
                onClick={() => goto(item.id)}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="mt-auto space-y-2 px-1">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2"
            onClick={() => setDark((value) => !value)}
          >
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            {dark ? "Light appearance" : "Dark appearance"}
          </Button>
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            Backend
            <Badge variant={online ? "secondary" : "destructive"} className="text-[10px]">
              {online === null ? "checking" : online ? "connected" : "offline"}
            </Badge>
          </div>
        </div>
      </aside>

      {navOpen && (
        <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setNavOpen(false)} />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b bg-background/90 px-4 py-3 backdrop-blur">
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setNavOpen(true)}>
            <Menu className="h-4 w-4" />
          </Button>
          <div className="min-w-0">
            <h2 className="truncate text-lg font-semibold leading-tight">{meta.title}</h2>
            <p className="truncate text-xs text-muted-foreground">{meta.subtitle}</p>
          </div>
        </header>

        <main className="min-w-0 flex-1 p-4">
          {online === false && (
            <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm">
              {API_BASE.startsWith("https://") ? (
                <>Can’t reach the backend at <code className="font-mono text-xs">{API_BASE}</code>. A free server can take up to a minute to wake up; this page retries automatically.</>
              ) : (
                <>Can’t reach the backend. Start it with <code className="font-mono text-xs">uvicorn app.main:app --reload --port 8000</code> in the <code className="font-mono text-xs">backend</code> folder.</>
              )}
            </div>
          )}

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
        </main>
      </div>

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
