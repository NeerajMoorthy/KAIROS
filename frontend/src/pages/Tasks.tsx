import { useEffect, useMemo, useState } from "react";
import { CalendarDays, Flag, Pencil, Plus, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, type Task } from "@/lib/api";
import { PRIORITY_STYLES, dueLabel, dueTone } from "@/lib/format";
import { cn } from "@/lib/utils";

export function Tasks({
  refreshKey,
  onChanged,
  onOpenWorkspace,
  onNewTask,
  onEditTask,
}: {
  refreshKey: number;
  onChanged: () => void;
  onOpenWorkspace: (id: string) => void;
  onNewTask: () => void;
  onEditTask: (task: Task) => void;
}) {
  const [view, setView] = useState<"deadline" | "priority">("deadline");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState("view");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const r = await api.listTasks(view);
      setTasks(r.tasks);
      setError(null);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, refreshKey]);

  async function toggle(task: Task) {
    try {
      await api.updateTask(task.id, { completed: !task.completed });
      await load();
      onChanged();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
  }

  async function remove(id: string) {
    if (!window.confirm("Delete this task?")) return;
    try {
      await api.deleteTask(id);
      await load();
      onChanged();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
  }

  const visible = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    const filtered = tasks.filter((task) => {
      const text = [task.title, task.topic, task.category, task.project, task.description]
        .filter(Boolean).join(" ").toLocaleLowerCase();
      return (!needle || text.includes(needle)) &&
        (statusFilter === "all" || task.status === statusFilter);
    });
    // "view" keeps the server's order for the selected tab (deadline order,
    // or the urgency heap for "By priority"). Sorting by deadline here by
    // default used to make the "By priority" tab look identical to "By deadline".
    if (sortBy === "view") return filtered;
    const priority = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
    return filtered.sort((a, b) => {
      if (sortBy === "title") return a.title.localeCompare(b.title);
      if (sortBy === "priority") return priority.indexOf(b.priority) - priority.indexOf(a.priority);
      if (sortBy === "progress") return b.progress - a.progress;
      return a.deadline.localeCompare(b.deadline);
    });
  }, [tasks, query, statusFilter, sortBy]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Tabs value={view} onValueChange={(value) => setView(value as "deadline" | "priority")}>
          <TabsList>
            <TabsTrigger value="deadline" className="gap-1.5">
              <CalendarDays className="h-3.5 w-3.5" /> By deadline
            </TabsTrigger>
            <TabsTrigger value="priority" className="gap-1.5">
              <Flag className="h-3.5 w-3.5" /> By priority
            </TabsTrigger>
          </TabsList>
        </Tabs>
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search tasks…"
          className="h-9 w-full max-w-xs"
        />
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="h-9 w-40">
          <option value="all">All statuses</option>
          <option value="todo">To do</option>
          <option value="in_progress">In progress</option>
          <option value="completed">Completed</option>
        </Select>
        <Select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="h-9 w-44">
          <option value="view">Sort: {view === "priority" ? "urgency" : "deadline"} (tab order)</option>
          <option value="deadline">Sort: deadline</option>
          <option value="priority">Sort: priority</option>
          <option value="title">Sort: title</option>
          <option value="progress">Sort: progress</option>
        </Select>
        <Button className="ml-auto" onClick={onNewTask}>
          <Plus className="h-4 w-4" /> New task
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {visible.map((task) => (
          <Card
            key={task.id}
            className={cn("group cursor-pointer transition-shadow hover:shadow-md", task.completed && "opacity-65")}
            onClick={() => onOpenWorkspace(task.id)}
          >
            <CardHeader className="pb-2">
              <div className="flex items-start gap-2">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 shrink-0 accent-primary"
                  checked={task.completed}
                  onClick={(e) => e.stopPropagation()}
                  onChange={() => void toggle(task)}
                  aria-label="Mark complete"
                />
                <div className="min-w-0 flex-1">
                  <CardTitle className={cn("text-base", task.completed && "line-through")}>
                    {task.title}
                  </CardTitle>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">
                    {[task.category || task.topic, task.project].filter(Boolean).join(" · ")}
                  </p>
                </div>
                <button
                  className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                  onClick={(e) => { e.stopPropagation(); onEditTask(task); }}
                  aria-label="Edit task"
                  title="Edit task"
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                  onClick={(e) => { e.stopPropagation(); void remove(task.id); }}
                  aria-label="Delete task"
                  title="Delete task"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary" className={PRIORITY_STYLES[task.priority]}>
                  {task.priority}
                </Badge>
                <Badge variant="outline" className="text-[10px]">
                  {task.status.replace("_", " ")}
                </Badge>
                <span className={cn("text-xs font-medium", dueTone(task.deadline, task.completed))}>
                  {dueLabel(task.deadline)}
                </span>
                <span className="ml-auto text-xs text-muted-foreground">
                  {task.remaining_hours} h left
                </span>
              </div>
              <div>
                <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                  <span>Progress</span><span>{task.progress}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary/70" style={{ width: `${task.progress}%` }} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {visible.length === 0 && (
        <Card>
          <CardContent className="p-10 text-center text-sm text-muted-foreground">
            {tasks.length === 0 ? "No tasks yet — create your first one." : "Nothing matches those filters."}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
