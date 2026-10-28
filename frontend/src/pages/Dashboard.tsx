import { useEffect, useState } from "react";
import { AlertTriangle, BookOpen, CalendarClock, Clock3, Plus, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { api, type DeadlineRisk, type RankedResource, type Task } from "@/lib/api";
import { Metric } from "@/components/Metric";
import { PRIORITY_STYLES, RISK_STYLES, dueLabel, dueTone } from "@/lib/format";
import { cn } from "@/lib/utils";

type DashboardData = Awaited<ReturnType<typeof api.dashboard>>;

export function Dashboard({
  refreshKey,
  onOpenWorkspace,
  onNewTask,
  onGoto,
  onStartFocus,
}: {
  refreshKey: number;
  onOpenWorkspace: (id: string) => void;
  onNewTask: () => void;
  onGoto: (page: string) => void;
  onStartFocus: (id: string) => void;
}) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [helpfulResources, setHelpfulResources] = useState<RankedResource[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.dashboard()
      .then((result) => { setData(result); setError(null); })
      .catch((e) => setError(String(e instanceof Error ? e.message : e)));
  }, [refreshKey]);

  useEffect(() => {
    const taskId = data?.recommended_action?.task?.id;
    if (!taskId) {
      setHelpfulResources([]);
      return;
    }
    let current = true;
    api.workspace(taskId, 3, false)
      .then((workspace) => {
        if (current) setHelpfulResources(workspace.local_resources.slice(0, 3));
      })
      .catch(() => {
        if (current) setHelpfulResources([]);
      });
    return () => { current = false; };
  }, [data?.recommended_action?.task?.id, refreshKey]);

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!data) return <p className="text-sm text-muted-foreground">Loading your day…</p>;

  const action = data.recommended_action;
  const risks: DeadlineRisk[] = data.deadline_risks ?? [];
  const hasTasks = data.open_tasks > 0 || data.completed_tasks > 0;

  if (!hasTasks) {
    return (
      <Card className="mx-auto max-w-2xl">
        <CardContent className="flex flex-col items-center gap-4 p-10 text-center">
          <div className="rounded-full bg-muted p-4"><CalendarClock className="h-6 w-6" /></div>
          <div>
            <h2 className="text-lg font-semibold">Start with one task</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Add a deadline and a time estimate, then connect a folder of notes or project files when you’re ready.
            </p>
          </div>
          <div className="flex gap-2">
            <Button onClick={onNewTask}><Plus className="h-4 w-4" /> Add a task</Button>
            <Button variant="outline" onClick={() => onGoto("knowledge")}><BookOpen className="h-4 w-4" /> Add resources</Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={CalendarClock} label="Open tasks" value={data.open_tasks} hint={`${data.remaining_hours} h of work remain`} />
        <Metric icon={AlertTriangle} label="At risk" value={data.high_risk_count} hint={data.high_risk_count ? "Needs attention before the deadline" : "No high deadline risks"} />
        <Metric icon={TrendingUp} label="Overall progress" value={`${data.overall_progress}%`} />
        <Metric icon={Clock3} label="Available each day" value={`${data.available_hours_per_day} h`} hint="Change this in Settings" />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-5">
          <Card className="border-primary/25 bg-primary/[0.025]">
            <CardHeader className="pb-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Recommended next action</p>
              {action ? <CardTitle className="text-xl">{action.task.title}</CardTitle> : <CardTitle className="text-xl">No task needs a session right now</CardTitle>}
            </CardHeader>
            <CardContent className="space-y-3">
              {action ? (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary" className={PRIORITY_STYLES[action.task.priority]}>{action.task.priority}</Badge>
                    <Badge variant="secondary" className={cn("capitalize", RISK_STYLES[action.risk.level])}>{action.risk.level} risk</Badge>
                    <span className={cn("text-sm font-medium", dueTone(action.task.deadline))}>{dueLabel(action.task.deadline)}</span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {action.task.remaining_hours} h remain · You have {action.available_hours_now} h available today · Recommended session: {action.recommended_session_minutes} min
                  </p>
                  <Progress value={action.task.progress} />
                  <p className="text-xs text-muted-foreground">Why this task: {action.reasons.join(" · ")}</p>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" onClick={() => onStartFocus(action.task.id)}>Start focus session</Button>
                    <Button size="sm" variant="outline" onClick={() => onOpenWorkspace(action.task.id)}>View task details</Button>
                    <Button size="sm" variant="ghost" onClick={() => onGoto("plan")}>Open plan</Button>
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Set your daily availability in Settings to receive a recommendation.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0 border-b">
              <CardTitle>Coming up</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => onGoto("tasks")}>All tasks</Button>
            </CardHeader>
            <CardContent className="p-0">
              <ul className="divide-y">
                {data.upcoming.map((task: Task) => (
                  <li key={task.id} className="flex cursor-pointer items-center gap-3 px-4 py-3 hover:bg-muted/50" onClick={() => onOpenWorkspace(task.id)}>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{task.title}</p>
                      <p className="truncate text-xs text-muted-foreground">{task.category || task.topic}</p>
                    </div>
                    <Badge variant="secondary" className={PRIORITY_STYLES[task.priority]}>{task.priority}</Badge>
                    <span className={cn("w-28 text-right text-xs", dueTone(task.deadline))}>{dueLabel(task.deadline)}</span>
                  </li>
                ))}
                {data.upcoming.length === 0 && <li className="px-4 py-6 text-center text-sm text-muted-foreground">All caught up.</li>}
              </ul>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader className="border-b pb-3">
              <CardTitle>Deadline risk</CardTitle>
              <p className="text-sm text-muted-foreground">Compares remaining work with your available hours before each due date.</p>
            </CardHeader>
            <CardContent className="space-y-2 pt-4">
              {risks.slice(0, 4).map((risk) => (
                <button key={risk.task_id} className="w-full rounded-md border p-3 text-left transition-colors hover:bg-muted/50" onClick={() => onOpenWorkspace(risk.task_id)}>
                  <div className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">{risk.title}</span>
                    <Badge variant="secondary" className={cn("capitalize", RISK_STYLES[risk.level])}>{risk.level}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{risk.explanation}</p>
                </button>
              ))}
              {risks.length === 0 && <p className="py-4 text-center text-sm text-muted-foreground">No open deadlines.</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b pb-3"><CardTitle>Knowledge Vault</CardTitle></CardHeader>
            <CardContent className="space-y-3 pt-4">
              <div className="flex items-center justify-between gap-3">
                <div><p className="text-2xl font-semibold">{data.resources_indexed}</p><p className="text-xs text-muted-foreground">files in your selected folders</p></div>
                <Button variant="outline" size="sm" onClick={() => onGoto("knowledge")}>Search resources</Button>
              </div>
              {helpfulResources.length ? (
                <div className="border-t pt-3">
                  <p className="mb-2 text-xs font-medium">Helpful for your recommended task</p>
                  <ul className="space-y-2">
                    {helpfulResources.map((match) => (
                      <li key={match.resource.id} className="rounded-md border p-2">
                        <p className="truncate text-sm font-medium">{match.resource.title}</p>
                        <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{match.resource.snippet}</p>
                        <p className="mt-1 text-[11px] text-muted-foreground">Why it matched: {match.reasons.slice(0, 2).join(" · ")}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="border-t pt-3 text-xs text-muted-foreground">Index a folder in Knowledge to see files related to your next task.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
