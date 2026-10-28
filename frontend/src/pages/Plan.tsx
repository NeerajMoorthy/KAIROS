import { useEffect, useState } from "react";
import { CalendarRange, Check, Clock3 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Metric } from "@/components/Metric";
import { api, type TimelineDay } from "@/lib/api";
import { shortDate } from "@/lib/format";

type PlanData = Awaited<ReturnType<typeof api.adaptivePlan>>;

export function Plan({ refreshKey }: { refreshKey: number }) {
  const [capacity, setCapacity] = useState(21);
  const [daily, setDaily] = useState(3);
  const [schedule, setSchedule] = useState<PlanData | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.adaptivePlan({
        capacity_hours: capacity,
        daily_hours: daily,
      });
      setSchedule(result);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
      setSchedule(null);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    api.settings().then((settings) => {
      setDaily(settings.available_hours_per_day);
      setCapacity(settings.available_hours_per_day * 7);
      setReady(true);
    }).catch(() => setReady(true));
  }, []);

  useEffect(() => {
    if (ready) void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey, ready]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="border-b pb-3">
          <CardTitle className="flex items-center gap-2"><CalendarRange className="h-4 w-4" /> Plan the week</CardTitle>
          <p className="text-sm text-muted-foreground">
            KAIROS fits remaining task effort into your available hours and orders work by deadline.
          </p>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
            <div className="space-y-1.5">
              <Label htmlFor="capacity">Hours available this week</Label>
              <Input id="capacity" type="number" min={0} max={500} step={0.5} value={capacity} onChange={(e) => setCapacity(Number(e.target.value))} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="daily-hours">Hours available per day</Label>
              <Input id="daily-hours" type="number" min={0} max={16} step={0.5} value={daily} onChange={(e) => setDaily(Number(e.target.value))} />
            </div>
            <Button onClick={() => void run()} disabled={busy || capacity < 0 || daily < 0}>
              {busy ? "Building plan…" : "Build plan"}
            </Button>
          </div>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
          <p className="mt-3 text-xs text-muted-foreground">
            The plan includes at most {capacity} total hours and {daily} hours in a day. Change these values when your availability changes.
          </p>
        </CardContent>
      </Card>

      {schedule && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Metric label="Scheduled" value={`${schedule.scheduled_hours} h`} />
            <Metric label="Tasks in plan" value={schedule.selected.length} />
            <Metric label="Deferred" value={schedule.deferred.length} />
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <Card>
              <CardHeader className="border-b pb-3">
                <CardTitle className="flex items-center gap-2 text-base"><CalendarRange className="h-4 w-4" /> Day-by-day plan</CardTitle>
                <p className="text-sm text-muted-foreground">Each day stays within your stated availability.</p>
              </CardHeader>
              <CardContent className="space-y-3 pt-4">
                {schedule.timeline.map((day: TimelineDay) => (
                  <Day key={day.date} day={day} />
                ))}
                {schedule.timeline.length === 0 && (
                  <p className="py-6 text-center text-sm text-muted-foreground">
                    {daily === 0 || capacity === 0 ? "No hours are available. Update your availability to schedule work." : schedule.deferred.length ? "No work fits within the available hours." : "No open work needs to be scheduled."}
                  </p>
                )}
              </CardContent>
            </Card>

            <Card className="h-fit">
              <CardHeader className="border-b pb-3">
                <CardTitle className="text-base">Not scheduled yet</CardTitle>
                <p className="text-sm text-muted-foreground">These tasks need more time than is available in this plan.</p>
              </CardHeader>
              <CardContent className="pt-4">
                {schedule.deferred.length ? (
                  <ul className="space-y-2">
                    {schedule.deferred.map((task) => (
                      <li key={task.id} className="flex items-center gap-2 rounded-md border p-3">
                        <span className="min-w-0 flex-1 truncate text-sm font-medium">{task.title}</span>
                        {task.risk && <Badge variant="secondary">{task.risk.level} risk</Badge>}
                        <Badge variant="outline">{task.hours} h left</Badge>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="py-4 text-center text-sm text-muted-foreground">All open work fits in the plan.</p>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function Day({ day }: { day: TimelineDay }) {
  return (
    <div className="rounded-lg border">
      <div className="flex items-center justify-between border-b bg-muted/40 px-3 py-2">
        <span className="text-sm font-medium">{shortDate(day.date)}</span>
        <span className="font-mono text-xs text-muted-foreground">{day.hours} h</span>
      </div>
      <ul className="space-y-2 p-3">
        {day.blocks.map((block, index) => (
          <li key={block.task_id + index} className="flex items-center gap-3 rounded-md bg-background">
            <Check className="h-4 w-4 text-primary" />
            <span className="min-w-0 flex-1 truncate text-sm">{block.title}</span>
            {block.overdue && <Badge variant="secondary" className="text-[10px]">Past deadline</Badge>}
            <span className="flex items-center gap-1 font-mono text-xs text-muted-foreground">
              <Clock3 className="h-3 w-3" /> {block.hours} h
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
