import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type Priority, type Task } from "@/lib/api";

const PRIORITIES: Priority[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

function inDays(n: number) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

export function TaskDialog({
  open,
  onOpenChange,
  onCreated,
  initialTask,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated: (taskId: string) => void;
  initialTask?: Task | null;
}) {
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [project, setProject] = useState("");
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState(inDays(3));
  const [priority, setPriority] = useState<Priority>("MEDIUM");
  const [hours, setHours] = useState(3);
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setTitle(initialTask?.title ?? "");
    setCategory(initialTask?.category ?? initialTask?.topic ?? "");
    setProject(initialTask?.project ?? "");
    setDescription(initialTask?.description ?? initialTask?.notes ?? "");
    setDeadline(initialTask?.deadline.slice(0, 10) ?? inDays(3));
    setPriority(initialTask?.priority ?? "MEDIUM");
    setHours(initialTask?.estimated_hours ?? 3);
    setProgress(initialTask?.progress ?? 0);
    setError(null);
  }, [open, initialTask]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (initialTask) {
        await api.updateTask(initialTask.id, {
          title,
          topic: category || "General",
          category: category || null,
          project: project || null,
          description,
          deadline,
          priority,
          estimated_hours: Number(hours),
          progress: Number(progress),
        });
        onCreated(initialTask.id);
      } else {
        const { task } = await api.createTask({
          title,
          topic: category || "General",
          category: category || null,
          project: project || null,
          description,
          deadline,
          priority,
          estimated_hours: Number(hours),
        });
        onCreated(task.id);
      }
      onOpenChange(false);
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{initialTask ? "Edit task" : "New task"}</DialogTitle>
          <DialogDescription>
            Keep the details that help you plan and find your material.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="grid gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="title">Task</Label>
            <Input
              id="title"
              autoFocus
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Project Report"
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="category">Category or topic</Label>
              <Input
                id="category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="Research, presentation, exam prep…"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="project">Project (optional)</Label>
              <Input
                id="project"
                value={project}
                onChange={(e) => setProject(e.target.value)}
                placeholder="Course or project name"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="description">Description (optional)</Label>
            <Input
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does finished look like?"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="deadline">Deadline</Label>
              <Input
                id="deadline"
                type="date"
                required
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
              />
              <div className="flex gap-1">
                {[
                  ["Today", 0],
                  ["Tomorrow", 1],
                  ["Next week", 7],
                ].map(([label, n]) => (
                  <button
                    key={label as string}
                    type="button"
                    onClick={() => setDeadline(inDays(n as number))}
                    className="rounded border px-1.5 py-0.5 text-[11px] text-muted-foreground hover:bg-accent"
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="hours">Estimated effort (hours)</Label>
              <Input
                id="hours"
                type="number"
                min={0.25}
                max={1000}
                step={0.25}
                value={hours}
                onChange={(e) => setHours(Number(e.target.value))}
                required
              />
              {initialTask && (
                <>
                  <Label htmlFor="progress">Progress (%)</Label>
                  <Input
                    id="progress"
                    type="number"
                    min={0}
                    max={100}
                    step={5}
                    value={progress}
                    onChange={(e) => setProgress(Number(e.target.value))}
                  />
                </>
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Priority</Label>
            <div className="flex flex-wrap gap-2">
              {PRIORITIES.map((p) => (
                <Button
                  key={p}
                  type="button"
                  size="sm"
                  variant={priority === p ? "default" : "outline"}
                  onClick={() => setPriority(p)}
                >
                  {p.charAt(0) + p.slice(1).toLowerCase()}
                </Button>
              ))}
            </div>
          </div>

          {error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy || hours <= 0}>
              {busy ? "Saving…" : initialTask ? "Save changes" : "Create task"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
