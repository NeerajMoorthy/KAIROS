import { useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, BookOpen, CalendarClock, Clock3, Play, Plus, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Metric } from "@/components/Metric";
import { Tilt } from "@/components/Tilt";
import { PriorityBadge, RiskBadge } from "@/components/badges";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { useApi } from "@/hooks/useApi";
import { api, type RankedResource } from "@/lib/api";
import { dueLabel, dueTone } from "@/lib/format";
import { cn } from "@/lib/utils";

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

/** Overall progress shown inside a slowly orbiting 3D sphere. */
function ProgressOrb({ value }: { value: number }) {
  return (
    <div className="orb-scene relative h-36 w-36 shrink-0 sm:h-40 sm:w-40" role="img" aria-label={`${value}% overall progress`}>
      <div className="orb-ring" />
      <div className="orb-ring" />
      <div className="orb-ring" />
      <div className="orb-sphere flex items-center justify-center">
        <span className="text-xl font-bold text-white drop-shadow">{value}%</span>
      </div>
    </div>
  );
}

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
  const { data, error, reload } = useApi(api.dashboard, [refreshKey]);
  const [helpfulResources, setHelpfulResources] = useState<RankedResource[]>([]);
  const actionTaskId = data?.recommended_action?.task?.id;

  useEffect(() => {
    if (!actionTaskId) return;
    let current = true;
    api.workspace(actionTaskId, 3, false)
      .then((workspace) => { if (current) setHelpfulResources(workspace.local_resources.slice(0, 3)); })
      .catch(() => { if (current) setHelpfulResources([]); });
    return () => { current = false; };
  }, [actionTaskId, refreshKey]);

  if (error && !data) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <LoadingState />;

  const action = data.recommended_action;
  const risks = data.deadline_risks ?? [];
  const resources = actionTaskId ? helpfulResources : [];

  if (data.open_tasks === 0 && data.completed_tasks === 0) {
    return (
      <Card className="mx-auto max-w-2xl">
        <EmptyState
          icon={CalendarClock}
          title="Start with one task"
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <Button onClick={onNewTask}><Plus className="h-4 w-4" /> Add a task</Button>
              <Button variant="outline" onClick={() => onGoto("knowledge")}><BookOpen className="h-4 w-4" /> Add resources</Button>
            </div>
          }
        >
          Add a deadline and a time estimate, then connect a folder of notes or project files when you’re ready.
        </EmptyState>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      {/* hero */}
      <Card className="surface-raised relative overflow-hidden">
        <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-primary/15 blur-3xl" aria-hidden />
        <CardContent className="flex flex-col items-center gap-6 p-6 sm:flex-row sm:p-8">
          <div className="min-w-0 flex-1 text-center sm:text-left">
            <p className="text-sm font-medium text-muted-foreground">{greeting()}</p>
            <h2 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">
              {data.open_tasks === 0
                ? <>Everything is <span className="text-gradient">done</span>.</>
                : <><span className="text-gradient">{data.open_tasks} open task{data.open_tasks === 1 ? "" : "s"}</span>, {data.remaining_hours} h to go</>}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {data.due_today > 0 && `${data.due_today} due today · `}
              {data.due_this_week} due this week · {data.completed_tasks} completed
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2 sm:justify-start">
              <Button size="sm" onClick={onNewTask}><Plus className="h-4 w-4" /> New task</Button>
              <Button size="sm" variant="outline" onClick={() => onGoto("plan")}>Plan my week <ArrowRight className="h-3.5 w-3.5" /></Button>
            </div>
          </div>
          <ProgressOrb value={data.overall_progress} />
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={CalendarClock} label="Open tasks" value={data.open_tasks} hint={`${data.remaining_hours} h of work remain`} />
        <Metric icon={AlertTriangle} tone={data.high_risk_count ? "warning" : "primary"} label="At risk" value={data.high_risk_count} hint={data.high_risk_count ? "Needs attention before the deadline" : "No high deadline risks"} />
        <Metric icon={TrendingUp} label="Overall progress" value={`${data.overall_progress}%`} hint={`${data.actual_hours} h tracked in focus`} />
        <Metric icon={Clock3} label="Available each day" value={`${data.available_hours_per_day} h`} hint="Change this in Settings" />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-5">
          <Tilt max={3} className="surface-raised border border-primary/25 bg-card">
            <div className="relative overflow-hidden rounded-xl p-5 [transform-style:preserve-3d]">
              <div className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary to-[hsl(var(--glow-2))]" aria-hidden />
              <p className="text-xs font-semibold uppercase tracking-wider text-primary">Recommended next action</p>
              <h3 className="mt-1 text-xl font-bold tracking-tight">{action ? action.task.title : "No task needs a session right now"}</h3>
              {action ? (
                <div className="mt-3 space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <PriorityBadge priority={action.task.priority} />
                    <RiskBadge level={action.risk.level} />
                    <span className={cn("text-sm font-medium", dueTone(action.task.deadline))}>{dueLabel(action.task.deadline)}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    {[
                      ["Remaining", `${action.task.remaining_hours} h`],
                      ["Available today", `${action.available_hours_now} h`],
                      ["Session", `${action.recommended_session_minutes} min`],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-lg bg-muted/70 px-2 py-2">
                        <p className="text-sm font-semibold">{value}</p>
                        <p className="text-[11px] text-muted-foreground">{label}</p>
                      </div>
                    ))}
                  </div>
                  <Progress value={action.task.progress} />
                  <p className="text-xs text-muted-foreground">Why this task: {action.reasons.join(" · ")}</p>
                  <div className="depth-1 flex flex-wrap gap-2">
                    <Button size="sm" onClick={() => onStartFocus(action.task.id)}><Play className="h-3.5 w-3.5" /> Start focus session</Button>
                    <Button size="sm" variant="outline" onClick={() => onOpenWorkspace(action.task.id)}>View task details</Button>
                    <Button size="sm" variant="ghost" onClick={() => onGoto("plan")}>Open plan</Button>
                  </div>
                </div>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">Set your daily availability in Settings to receive a recommendation.</p>
              )}
            </div>
          </Tilt>

          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0 border-b">
              <CardTitle>Coming up</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => onGoto("tasks")}>All tasks <ArrowRight className="h-3.5 w-3.5" /></Button>
            </CardHeader>
            <CardContent className="p-0">
              <ul className="divide-y">
                {data.upcoming.map((task) => (
                  <li key={task.id}>
                    <button className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-accent/50" onClick={() => onOpenWorkspace(task.id)}>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{task.title}</p>
                        <p className="truncate text-xs text-muted-foreground">{task.category || task.topic}</p>
                      </div>
                      <PriorityBadge priority={task.priority} className="hidden sm:inline-flex" />
                      <span className={cn("w-24 text-right text-xs", dueTone(task.deadline))}>{dueLabel(task.deadline)}</span>
                    </button>
                  </li>
                ))}
                {data.upcoming.length === 0 && <li className="px-4 py-6 text-center text-sm text-muted-foreground">All caught up.</li>}
              </ul>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-5">
          <Card>
            <CardHeader className="border-b pb-3">
              <CardTitle>Deadline risk</CardTitle>
              <p className="text-sm text-muted-foreground">Remaining work compared with your available hours before each due date.</p>
            </CardHeader>
            <CardContent className="space-y-2 pt-4">
              {risks.slice(0, 4).map((risk) => (
                <button key={risk.task_id} className="lift w-full rounded-lg border bg-card p-3 text-left" onClick={() => onOpenWorkspace(risk.task_id)}>
                  <div className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">{risk.title}</span>
                    <RiskBadge level={risk.level} />
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
                <div><p className="text-2xl font-bold">{data.resources_indexed}</p><p className="text-xs text-muted-foreground">files in your selected folders</p></div>
                <Button variant="outline" size="sm" onClick={() => onGoto("knowledge")}>Search resources</Button>
              </div>
              {resources.length ? (
                <div className="border-t pt-3">
                  <p className="mb-2 text-xs font-medium">Helpful for your recommended task</p>
                  <ul className="space-y-2">
                    {resources.map((match) => (
                      <li key={match.resource.id} className="rounded-lg border bg-muted/30 p-2.5">
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
