import { useEffect, useMemo, useState } from "react";
import { CalendarDays, Flag, ListTodo, Plus, SearchX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { TaskCard } from "@/components/TaskCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, type Task } from "@/lib/api";

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
  const [loaded, setLoaded] = useState(false);

  async function load() {
    try {
      const r = await api.listTasks(view);
      setTasks(r.tasks);
      setError(null);
      setLoaded(true);
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
          type="search"
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
          <option value="view">Sort: tab order</option>
          <option value="deadline">Sort: deadline</option>
          <option value="priority">Sort: priority</option>
          <option value="title">Sort: title</option>
          <option value="progress">Sort: progress</option>
        </Select>
        <Button className="ml-auto" onClick={onNewTask}>
          <Plus className="h-4 w-4" /> New task
        </Button>
      </div>

      {error && <ErrorState message={error} onRetry={() => void load()} />}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {visible.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            onOpen={() => onOpenWorkspace(task.id)}
            onToggle={() => void toggle(task)}
            onEdit={() => onEditTask(task)}
            onDelete={() => void remove(task.id)}
          />
        ))}
      </div>

      {!loaded && !error && <LoadingState rows={0} />}

      {loaded && visible.length === 0 && (
        <Card>
          {tasks.length === 0 ? (
            <EmptyState icon={ListTodo} title="No tasks yet" action={<Button onClick={onNewTask}><Plus className="h-4 w-4" /> Create your first task</Button>}>
              Add what you need to do, when it is due, and roughly how long it takes.
            </EmptyState>
          ) : (
            <EmptyState icon={SearchX} title="Nothing matches those filters">Try a different search or status.</EmptyState>
          )}
        </Card>
      )}
    </div>
  );
}
