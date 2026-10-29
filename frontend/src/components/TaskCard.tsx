import { Pencil, Trash2 } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { Tilt } from "@/components/Tilt";
import { PriorityBadge, StatusBadge } from "@/components/badges";
import type { Task } from "@/lib/api";
import { dueLabel, dueTone } from "@/lib/format";
import { cn } from "@/lib/utils";

/** One task as a tilting card: complete toggle, edit, delete, progress. */
export function TaskCard({
  task,
  onOpen,
  onToggle,
  onEdit,
  onDelete,
}: {
  task: Task;
  onOpen: () => void;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <Tilt max={4} className={cn("surface lift cursor-pointer border border-border/70 bg-card", task.completed && "opacity-65")}>
      <div className="space-y-3 p-4 [transform-style:preserve-3d]" onClick={onOpen}>
        <div className="flex items-start gap-2">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 shrink-0 cursor-pointer accent-primary"
            checked={task.completed}
            onClick={(e) => e.stopPropagation()}
            onChange={onToggle}
            aria-label="Mark complete"
          />
          <div className="min-w-0 flex-1">
            <h3 className={cn("font-semibold leading-snug", task.completed && "line-through")}>{task.title}</h3>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              {[task.category || task.topic, task.project].filter(Boolean).join(" · ")}
            </p>
          </div>
          <button
            className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            onClick={(e) => { e.stopPropagation(); onEdit(); }}
            aria-label="Edit task"
            title="Edit task"
          >
            <Pencil className="h-4 w-4" />
          </button>
          <button
            className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            aria-label="Delete task"
            title="Delete task"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PriorityBadge priority={task.priority} />
          <StatusBadge status={task.status} />
          <span className={cn("text-xs font-medium", dueTone(task.deadline, task.completed))}>{dueLabel(task.deadline)}</span>
          <span className="ml-auto text-xs text-muted-foreground">{task.remaining_hours} h left</span>
        </div>
        <div className="depth-1">
          <div className="mb-1 flex justify-between text-xs text-muted-foreground">
            <span>Progress</span><span className="font-medium text-foreground">{task.progress}%</span>
          </div>
          <Progress value={task.progress} className="h-1.5" />
        </div>
      </div>
    </Tilt>
  );
}
