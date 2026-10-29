import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Task, TimelineDay } from "@/lib/api";
import { cn } from "@/lib/utils";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function isoDay(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Month grid: planned study blocks and task deadlines on the days they fall. */
export function PlanCalendar({ timeline, tasks }: { timeline: TimelineDay[]; tasks: Task[] }) {
  const today = isoDay(new Date());
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const planByDay = useMemo(() => new Map(timeline.map((day) => [day.date, day])), [timeline]);
  const dueByDay = useMemo(() => {
    const map = new Map<string, Task[]>();
    for (const task of tasks) {
      if (task.completed) continue;
      const key = task.deadline.slice(0, 10);
      map.set(key, [...(map.get(key) ?? []), task]);
    }
    return map;
  }, [tasks]);

  // Six rows of seven days, starting on the Monday on or before the 1st.
  const cells = useMemo(() => {
    const start = new Date(month);
    start.setDate(1 - ((start.getDay() + 6) % 7));
    return Array.from({ length: 42 }, (_, i) => {
      const date = new Date(start);
      date.setDate(start.getDate() + i);
      return date;
    });
  }, [month]);

  const shift = (delta: number) => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + delta, 1));

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="flex-1 text-base font-semibold">
          {month.toLocaleDateString(undefined, { month: "long", year: "numeric" })}
        </h3>
        <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => shift(-1)} aria-label="Previous month">
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="sm" className="h-8" onClick={() => { const n = new Date(); setMonth(new Date(n.getFullYear(), n.getMonth(), 1)); }}>
          Today
        </Button>
        <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => shift(1)} aria-label="Next month">
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      <div className="grid grid-cols-7 overflow-hidden rounded-xl border bg-border/60 [gap:1px]">
        {WEEKDAYS.map((day) => (
          <div key={day} className="bg-muted/60 px-2 py-1.5 text-center text-[11px] font-medium text-muted-foreground">{day}</div>
        ))}
        {cells.map((date) => {
          const key = isoDay(date);
          const plan = planByDay.get(key);
          const due = dueByDay.get(key) ?? [];
          const inMonth = date.getMonth() === month.getMonth();
          return (
            <div
              key={key}
              className={cn(
                "min-h-[4.5rem] space-y-1 bg-card p-1 sm:min-h-[6.5rem] sm:p-1.5",
                !inMonth && "bg-muted/30 text-muted-foreground/60",
              )}
            >
              <div className="flex items-center justify-between">
                <span
                  className={cn(
                    "flex h-6 w-6 items-center justify-center rounded-full text-xs",
                    key === today && "bg-primary font-semibold text-primary-foreground shadow-md shadow-primary/30",
                  )}
                >
                  {date.getDate()}
                </span>
                {plan && <span className="hidden font-mono text-[10px] text-muted-foreground sm:inline">{plan.hours} h</span>}
              </div>
              {plan?.blocks.map((block, index) => (
                <div
                  key={block.task_id + index}
                  title={`${block.title} · ${block.hours} h planned`}
                  className="truncate rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary ring-1 ring-inset ring-primary/20 sm:text-[11px]"
                >
                  <span className="hidden sm:inline">{block.title} · </span>{block.hours} h
                </div>
              ))}
              {due.map((task) => (
                <div
                  key={task.id}
                  title={`${task.title} is due`}
                  className="truncate rounded-md bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-900 ring-1 ring-inset ring-amber-200 dark:bg-amber-950/70 dark:text-amber-200 dark:ring-amber-900 sm:text-[11px]"
                >
                  Due<span className="hidden sm:inline">: {task.title}</span>
                </div>
              ))}
            </div>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-primary/30 ring-1 ring-primary/40" /> Planned study time</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-amber-200 ring-1 ring-amber-300" /> Deadline</span>
      </div>
    </div>
  );
}
