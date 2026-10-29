import { useEffect, useState } from "react";
import { ArrowLeft, FileText, Play, Save } from "lucide-react";
import { PriorityBadge, RiskBadge } from "@/components/badges";
import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { RankedList } from "@/components/RankedList";
import { api, type DeadlineRisk, type RankedResource, type Task } from "@/lib/api";
import { dueLabel, dueTone } from "@/lib/format";
import { cn } from "@/lib/utils";

export function Workspace({
  taskId,
  onBack,
  onChanged,
  onStartFocus,
}: {
  taskId: string | null;
  onBack: () => void;
  onChanged: () => void;
  onStartFocus: (taskId: string) => void;
}) {
  const [task, setTask] = useState<Task | null>(null);
  const [risk, setRisk] = useState<DeadlineRisk | null>(null);
  const [resources, setResources] = useState<RankedResource[]>([]);
  const [progress, setProgress] = useState(0);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!taskId) return;
    setLoading(true);
    setError(null);
    try {
      // The workspace endpoint builds the resource query the same way for
      // every page (Dashboard, Focus, here), so results stay consistent.
      const [workspace, risksResponse] = await Promise.all([
        api.workspace(taskId, 6, false),
        api.deadlineRisks(),
      ]);
      setTask(workspace.task);
      setProgress(workspace.task.progress);
      setRisk(risksResponse.risks.find((item) => item.task_id === taskId) ?? null);
      setResources(workspace.local_resources);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [taskId]);

  if (!taskId) {
    return <Card><CardContent className="p-10 text-center text-sm text-muted-foreground">Choose a task to see its details.</CardContent></Card>;
  }

  async function saveProgress() {
    if (!taskId) return;
    setSaving(true);
    setError(null);
    try {
      await api.updateTask(taskId, { progress });
      await load();
      onChanged();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" onClick={onBack}><ArrowLeft className="h-4 w-4" /> Back to tasks</Button>
      {error && <ErrorState message={error} onRetry={() => void load()} />}
      {loading && !task ? <LoadingState rows={1} /> : task && (
        <>
          <Card>
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="min-w-0 flex-1 text-xl">{task.title}</CardTitle>
                <PriorityBadge priority={task.priority} />
                {risk && <RiskBadge level={risk.level} />}
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                <span className={cn("font-medium", dueTone(task.deadline, task.completed))}>{dueLabel(task.deadline)}</span>
                <span className="text-muted-foreground">{task.remaining_hours} h remaining of {task.estimated_hours} h</span>
                <span className="text-muted-foreground">{task.category || task.topic}</span>
                {task.project && <span className="text-muted-foreground">{task.project}</span>}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {task.description && <p className="text-sm text-muted-foreground">{task.description}</p>}
              <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="task-progress">Progress</Label>
                    <span className="font-mono text-sm">{progress}%</span>
                  </div>
                  <Input id="task-progress" type="range" min={0} max={100} step={5} value={progress} onChange={(e) => setProgress(Number(e.target.value))} />
                  <Progress value={progress} />
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => void saveProgress()} disabled={saving || progress === task.progress}>
                    <Save className="h-4 w-4" /> {saving ? "Saving…" : "Save progress"}
                  </Button>
                  <Button onClick={() => onStartFocus(task.id)} disabled={task.completed}>
                    <Play className="h-4 w-4" /> Start focus
                  </Button>
                </div>
              </div>
              {risk && <p className="rounded-md bg-muted p-3 text-sm">{risk.explanation}</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b pb-3">
              <CardTitle className="flex items-center gap-2 text-base"><FileText className="h-4 w-4" /> Relevant resources</CardTitle>
              <p className="text-sm text-muted-foreground">Matches from the folders you added to Knowledge. Web search is off here.</p>
            </CardHeader>
            <CardContent className="pt-4">
              <RankedList items={resources} />
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
