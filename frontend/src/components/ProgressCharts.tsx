import { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FocusSession, Task } from "@/lib/api";

const DAYS = 14;

function isoDay(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function hoursLabel(hours: number): string {
  if (hours === 0) return "0 h";
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  return `${Math.round(hours * 10) / 10} h`;
}

/** Hours of focus recorded on each of the last 14 days (one series, so no legend). */
export function FocusTimeChart({ sessions }: { sessions: FocusSession[] }) {
  const [hover, setHover] = useState<number | null>(null);

  const days = useMemo(() => {
    const totals = new Map<string, number>();
    for (const session of sessions) {
      const when = session.completed_at ?? session.paused_at ?? session.started_at ?? session.created_at;
      if (!when || session.elapsed_seconds <= 0) continue;
      const key = isoDay(new Date(when));
      totals.set(key, (totals.get(key) ?? 0) + session.elapsed_seconds / 3600);
    }
    const today = new Date();
    return Array.from({ length: DAYS }, (_, i) => {
      const date = new Date(today);
      date.setDate(today.getDate() - (DAYS - 1 - i));
      return { date, hours: totals.get(isoDay(date)) ?? 0 };
    });
  }, [sessions]);

  const max = Math.max(1, ...days.map((d) => d.hours));
  const total = days.reduce((sum, d) => sum + d.hours, 0);
  const active = days.filter((d) => d.hours > 0).length;

  return (
    <Card>
      <CardHeader className="border-b pb-3">
        <CardTitle>Focus time, last 14 days</CardTitle>
        <p className="text-sm text-muted-foreground">
          {hoursLabel(total)} recorded on {active} of {DAYS} days.
        </p>
      </CardHeader>
      <CardContent className="pt-5">
        {total === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">Finish a focus session to see your study time here.</p>
        ) : (
          <div className="relative">
            <div className="flex h-44 items-end gap-1 border-b border-border/80 sm:gap-1.5" role="img" aria-label={`Focus hours per day for the last ${DAYS} days`}>
              {days.map((day, index) => (
                <div
                  key={index}
                  className="group relative flex h-full flex-1 cursor-default items-end justify-center"
                  onMouseEnter={() => setHover(index)}
                  onMouseLeave={() => setHover(null)}
                >
                  <div
                    className="w-full max-w-7 rounded-t bg-primary transition-opacity group-hover:opacity-80"
                    style={{ height: day.hours ? `${Math.max(3, (day.hours / max) * 100)}%` : 0 }}
                  />
                  {hover === index && (
                    <div className="pointer-events-none absolute bottom-full z-10 mb-1 whitespace-nowrap rounded-md border bg-popover px-2 py-1 text-xs shadow-lg">
                      <span className="font-medium">{day.date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</span>
                      <span className="text-muted-foreground"> · {hoursLabel(day.hours)}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="mt-1.5 flex gap-1 text-center text-[10px] text-muted-foreground sm:gap-1.5">
              {days.map((day, index) => (
                <span key={index} className="flex-1">
                  {index % 2 === (DAYS - 1) % 2 ? day.date.getDate() : ""}
                </span>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** Planned (estimated) hours as a track, with tracked hours filled in on top. */
export function PlannedVsActualChart({ tasks }: { tasks: Task[] }) {
  const rows = tasks.filter((task) => task.estimated_hours > 0).slice(0, 8);
  const max = Math.max(1, ...rows.map((t) => Math.max(t.estimated_hours, t.actual_hours)));

  return (
    <Card>
      <CardHeader className="border-b pb-3">
        <CardTitle>Planned vs tracked hours</CardTitle>
        <div className="flex flex-wrap gap-4 pt-1 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-muted ring-1 ring-inset ring-border" /> Planned (estimate)</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-primary" /> Tracked in focus</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-4">
        {rows.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">Add a task with an estimate to compare.</p>}
        {rows.map((task) => {
          const over = task.actual_hours > task.estimated_hours;
          return (
            <div key={task.id} title={`${task.title}: ${hoursLabel(task.actual_hours)} tracked of ${hoursLabel(task.estimated_hours)} planned`}>
              <div className="mb-1 flex items-baseline gap-2 text-xs">
                <span className="min-w-0 flex-1 truncate font-medium">{task.title}</span>
                <span className="font-mono text-muted-foreground">
                  {hoursLabel(task.actual_hours)} / {hoursLabel(task.estimated_hours)}
                </span>
                {over && <span className="text-[10px] font-medium text-amber-700 dark:text-amber-300">over estimate</span>}
              </div>
              <div className="relative h-2.5 rounded-full">
                <div className="absolute inset-y-0 left-0 rounded-full bg-muted ring-1 ring-inset ring-border" style={{ width: `${(task.estimated_hours / max) * 100}%` }} />
                <div
                  className="absolute inset-y-0 left-0 rounded-full bg-primary ring-2 ring-card"
                  style={{ width: `${(task.actual_hours / max) * 100}%`, minWidth: task.actual_hours > 0 ? 4 : 0 }}
                />
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
