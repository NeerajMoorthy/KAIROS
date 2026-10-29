import { Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tilt } from "@/components/Tilt";
import { PriorityBadge, RiskBadge } from "@/components/badges";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { dueLabel, dueTone } from "@/lib/format";
import { cn } from "@/lib/utils";

/** The task KAIROS recommends working on now, with a one-click focus session. */
export function NextAction({
  refreshKey,
  onStartFocus,
  onOpenWorkspace,
}: {
  refreshKey: number;
  onStartFocus: (id: string) => void;
  onOpenWorkspace: (id: string) => void;
}) {
  const { data } = useApi(api.dashboard, [refreshKey]);
  const action = data?.recommended_action;
  if (!action) return null;

  return (
    <Tilt max={2} className="surface-raised border border-primary/25 bg-card">
      <div className="relative overflow-hidden rounded-xl p-5 [transform-style:preserve-3d]">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary to-[hsl(var(--glow-2))]" aria-hidden />
        <div className="flex flex-col gap-4 md:flex-row md:items-center">
          <div className="min-w-0 flex-1 space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-primary">Recommended next action</p>
            <h3 className="text-xl font-bold tracking-tight">{action.task.title}</h3>
            <div className="flex flex-wrap items-center gap-2">
              <PriorityBadge priority={action.task.priority} />
              <RiskBadge level={action.risk.level} />
              <span className={cn("text-sm font-medium", dueTone(action.task.deadline))}>{dueLabel(action.task.deadline)}</span>
              <span className="text-xs text-muted-foreground">
                · {action.task.remaining_hours} h left · {action.recommended_session_minutes} min session suggested
              </span>
            </div>
            <Progress value={action.task.progress} className="max-w-md" />
            <p className="text-xs text-muted-foreground">Why this task: {action.reasons.join(" · ")}</p>
          </div>
          <div className="depth-1 flex shrink-0 flex-wrap gap-2">
            <Button size="sm" onClick={() => onStartFocus(action.task.id)}><Play className="h-3.5 w-3.5" /> Start focus session</Button>
            <Button size="sm" variant="outline" onClick={() => onOpenWorkspace(action.task.id)}>View task details</Button>
          </div>
        </div>
      </div>
    </Tilt>
  );
}
