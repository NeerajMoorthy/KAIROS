import { Badge } from "@/components/ui/badge";
import type { DeadlineRisk, Priority, Task } from "@/lib/api";
import { PRIORITY_STYLES, RISK_STYLES } from "@/lib/format";
import { cn } from "@/lib/utils";

export function PriorityBadge({ priority, className }: { priority: Priority; className?: string }) {
  return (
    <Badge variant="secondary" className={cn(PRIORITY_STYLES[priority], className)}>
      {priority.charAt(0) + priority.slice(1).toLowerCase()}
    </Badge>
  );
}

export function RiskBadge({ level, className }: { level: DeadlineRisk["level"]; className?: string }) {
  return (
    <Badge variant="secondary" className={cn(RISK_STYLES[level], className)}>
      {level} risk
    </Badge>
  );
}

const STATUS_LABELS: Record<Task["status"], string> = {
  todo: "To do",
  in_progress: "In progress",
  completed: "Done",
};

export function StatusBadge({ status }: { status: Task["status"] }) {
  return <Badge variant="outline" className="text-[10px]">{STATUS_LABELS[status]}</Badge>;
}
