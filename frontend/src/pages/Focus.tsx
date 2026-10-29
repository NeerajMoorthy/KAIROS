import { useEffect, useMemo, useState } from "react";
import { Check, CirclePause, CirclePlay, Clock3, FileText, Target } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { api, type FocusSession, type RankedResource, type Task } from "@/lib/api";
import { RankedList } from "@/components/RankedList";

/** The server's elapsed_seconds already includes active time up to the moment
 *  it answered, so only the time since that response is added here. (Adding
 *  the time since started_at counted the active stretch twice after a reload.) */
function elapsed(session: FocusSession, receivedAt: number) {
  const sinceResponse = session.status === "active"
    ? Math.max(0, Math.floor((Date.now() - receivedAt) / 1000))
    : 0;
  return session.elapsed_seconds + sinceResponse;
}

function clock(seconds: number) {
  const h = Math.floor(seconds / 3600).toString().padStart(2, "0");
  const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return h + ":" + m + ":" + s;
}

export function Focus({
  taskId,
  refreshKey,
  onChanged,
}: {
  taskId: string | null;
  refreshKey: number;
  onChanged: () => void;
}) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [sessions, setSessions] = useState<FocusSession[]>([]);
  const [current, setCurrentSession] = useState<FocusSession | null>(null);
  const [receivedAt, setReceivedAt] = useState(0);
  const [selectedTaskId, setSelectedTaskId] = useState(taskId ?? "");
  const [objective, setObjective] = useState("");
  const [progressOverride, setProgressOverride] = useState("");
  const [resources, setResources] = useState<RankedResource[]>([]);
  const [, setTick] = useState(0); // re-renders the clock every second
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const selectedTask = tasks.find((task) => task.id === selectedTaskId) ?? null;
  const activeTaskId = current?.task_id ?? selectedTaskId;
  const focusedTask = tasks.find((task) => task.id === current?.task_id) ?? null;
  const currentElapsed = current ? elapsed(current, receivedAt) : 0;
  const completedSessions = sessions.filter((session) => session.status === "completed");

  function setCurrent(session: FocusSession | null) {
    setCurrentSession(session);
    setReceivedAt(Date.now());
  }

  async function load() {
    try {
      const [taskResult, sessionResult] = await Promise.all([
        api.listTasks("deadline"),
        api.focusSessions(),
      ]);
      setTasks(taskResult.tasks);
      setSessions(sessionResult.sessions);
      setCurrent(sessionResult.current);
      if (taskId) setSelectedTaskId(taskId);
      else if (!selectedTaskId && taskResult.tasks.find((task) => !task.completed)) {
        setSelectedTaskId(taskResult.tasks.find((task) => !task.completed)!.id);
      }
      setError(null);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
  }

  useEffect(() => { void load(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [refreshKey, taskId]);
  useEffect(() => {
    const timer = window.setInterval(() => setTick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!activeTaskId) { setResources([]); return; }
    api.workspace(activeTaskId, 5, false)
      .then((workspace) => setResources(workspace.local_resources))
      .catch(() => setResources([]));
  }, [activeTaskId]);

  const openTasks = useMemo(() => tasks.filter((task) => !task.completed), [tasks]);

  async function start() {
    if (!selectedTaskId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.startFocusSession({ task_id: selectedTaskId, objective });
      setCurrent(result.session);
      setObjective("");
      await load();
      onChanged();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }

  async function act(action: "pause" | "resume" | "complete") {
    if (!current) return;
    setBusy(true);
    setError(null);
    try {
      const progress = progressOverride.trim() === "" ? undefined : Number(progressOverride);
      await api.updateFocusSession(current.id, { action, ...(action === "complete" && progress !== undefined ? { progress } : {}) });
      setProgressOverride("");
      await load();
      onChanged();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.8fr)]">
      <div className="space-y-4">
        <Card>
          <CardHeader className="border-b pb-3">
            <CardTitle className="flex items-center gap-2">
              <Target className="h-4 w-4" /> Focus on one task
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Start a session from your recommended action or choose another task.
            </p>
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            {current ? (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-semibold">{current.task_title}</h2>
                  <Badge variant="secondary">{current.status}</Badge>
                </div>
                <p className="rounded-md bg-muted p-3 text-sm">{current.objective}</p>
                {focusedTask && (
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>Task progress</span>
                      <span>{focusedTask.progress}% · {focusedTask.remaining_hours} h remaining</span>
                    </div>
                    <Progress value={focusedTask.progress} />
                  </div>
                )}
                <p className="font-mono text-5xl font-semibold tabular-nums">{clock(currentElapsed)}</p>
                <div className="flex flex-wrap gap-2">
                  {current.status === "active" ? (
                    <Button variant="outline" onClick={() => void act("pause")} disabled={busy}>
                      <CirclePause className="h-4 w-4" /> Pause
                    </Button>
                  ) : (
                    <Button variant="outline" onClick={() => void act("resume")} disabled={busy}>
                      <CirclePlay className="h-4 w-4" /> Resume
                    </Button>
                  )}
                  <div className="flex items-center gap-2">
                    <Label htmlFor="progress-after" className="text-xs">Progress after session (%)</Label>
                    <Input
                      id="progress-after"
                      type="number"
                      min={0}
                      max={100}
                      step={5}
                      value={progressOverride}
                      onChange={(e) => setProgressOverride(e.target.value)}
                      placeholder="Auto"
                      className="w-24"
                    />
                  </div>
                  <Button onClick={() => void act("complete")} disabled={busy}>
                    <Check className="h-4 w-4" /> Finish session
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  If you leave progress on Auto, KAIROS estimates it from session time and task effort. You can adjust it in Tasks.
                </p>
              </>
            ) : (
              <>
                <div className="space-y-1.5">
                  <Label htmlFor="focus-task">Task</Label>
                  <Select id="focus-task" value={selectedTaskId} onChange={(e) => setSelectedTaskId(e.target.value)}>
                    <option value="">Choose a task</option>
                    {openTasks.map((task) => (
                      <option key={task.id} value={task.id}>{task.title} · {task.remaining_hours} h left</option>
                    ))}
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="objective">Session objective</Label>
                  <Input
                    id="objective"
                    value={objective}
                    onChange={(e) => setObjective(e.target.value)}
                    placeholder={selectedTask?.description || "Write one section, review a source, solve a problem…"}
                  />
                </div>
                <Button onClick={() => void start()} disabled={busy || !selectedTaskId}>
                  <CirclePlay className="h-4 w-4" /> Start focus session
                </Button>
              </>
            )}
            {error && <p className="text-sm text-destructive">{error}</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <FileText className="h-4 w-4" /> Helpful resources
            </CardTitle>
            <p className="text-sm text-muted-foreground">From your selected Knowledge Vault folders.</p>
          </CardHeader>
          <CardContent className="pt-4">
            <RankedList items={resources} />
          </CardContent>
        </Card>
      </div>

      <Card className="h-fit">
        <CardHeader className="border-b pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Clock3 className="h-4 w-4" /> Recent sessions
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          {completedSessions.length ? (
            <ul className="space-y-2">
              {completedSessions.slice(0, 8).map((session) => (
                <li key={session.id} className="rounded-md border p-3">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <span className="min-w-0 flex-1 truncate">{session.task_title}</span>
                    <span className="font-mono text-xs">{clock(session.elapsed_seconds)}</span>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted-foreground">{session.objective}</p>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {new Date(session.completed_at ?? session.created_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              Completed focus sessions will appear here.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
