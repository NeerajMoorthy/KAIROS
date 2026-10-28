import { useEffect, useState } from "react";
import { AlertTriangle, Clock3, ListTodo, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress as ProgressBar } from "@/components/ui/progress";
import { Metric } from "@/components/Metric";
import { api, type ProgressSummary } from "@/lib/api";
import { RISK_STYLES } from "@/lib/format";
import { cn } from "@/lib/utils";

export function ProgressPage({
  refreshKey,
  onOpenTask,
}: {
  refreshKey: number;
  onOpenTask: (id: string) => void;
}) {
  const [data, setData] = useState<ProgressSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.progressOverview()
      .then((result) => { setData(result); setError(null); })
      .catch((e) => setError(String(e instanceof Error ? e.message : e)));
  }, [refreshKey]);

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!data) return <p className="text-sm text-muted-foreground">Loading progress…</p>;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={TrendingUp} label="Overall progress" value={`${data.overall_progress}%`} />
        <Metric icon={ListTodo} label="Tasks complete" value={`${data.completed_tasks} / ${data.completed_tasks + data.remaining_tasks}`} />
        <Metric icon={Clock3} label="Planned effort" value={`${data.planned_hours} h`} hint={`${data.actual_hours} h tracked`} />
        <Metric icon={AlertTriangle} label="Work remaining" value={`${data.remaining_hours} h`} />
      </div>

      <Card>
        <CardHeader className="border-b pb-3">
          <CardTitle>Task progress</CardTitle>
          <p className="text-sm text-muted-foreground">
            Progress is weighted by each task’s estimated effort. Planned and actual hours come from task estimates and focus sessions.
          </p>
        </CardHeader>
        <CardContent className="pt-4">
          {data.tasks.length ? (
            <ul className="space-y-3">
              {data.tasks.map((task) => (
                <li
                  key={task.id}
                  className="cursor-pointer rounded-lg border p-3 transition-colors hover:bg-muted/40"
                  onClick={() => onOpenTask(task.id)}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">{task.title}</span>
                    <span className="text-xs text-muted-foreground">{task.remaining_hours} h left</span>
                    {task.risk && <Badge variant="secondary" className={cn("capitalize", RISK_STYLES[task.risk.level])}>{task.risk.level} risk</Badge>}
                    <span className="w-10 text-right font-mono text-xs">{task.progress}%</span>
                  </div>
                  <ProgressBar className="mt-2" value={task.progress} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">Create a task to start tracking progress.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
