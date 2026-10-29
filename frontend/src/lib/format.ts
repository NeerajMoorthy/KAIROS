import type { Priority } from "@/lib/api";

export const PRIORITY_STYLES: Record<Priority, string> = {
  LOW: "bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-200 dark:bg-slate-800/70 dark:text-slate-200 dark:ring-slate-700",
  MEDIUM: "bg-sky-50 text-sky-800 ring-1 ring-inset ring-sky-200 dark:bg-sky-950/70 dark:text-sky-200 dark:ring-sky-900",
  HIGH: "bg-amber-50 text-amber-900 ring-1 ring-inset ring-amber-200 dark:bg-amber-950/70 dark:text-amber-200 dark:ring-amber-900",
  CRITICAL: "bg-rose-50 text-rose-900 ring-1 ring-inset ring-rose-200 dark:bg-rose-950/70 dark:text-rose-200 dark:ring-rose-900",
};

export const RISK_STYLES: Record<string, string> = {
  Low: "bg-emerald-50 text-emerald-800 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950/70 dark:text-emerald-200 dark:ring-emerald-900",
  Moderate: "bg-amber-50 text-amber-900 ring-1 ring-inset ring-amber-200 dark:bg-amber-950/70 dark:text-amber-200 dark:ring-amber-900",
  High: "bg-orange-50 text-orange-900 ring-1 ring-inset ring-orange-200 dark:bg-orange-950/70 dark:text-orange-200 dark:ring-orange-900",
  Critical: "bg-rose-50 text-rose-800 ring-1 ring-inset ring-rose-200 dark:bg-rose-950/70 dark:text-rose-200 dark:ring-rose-900",
};

export function parseDate(dateStr: string): Date {
  const clean = dateStr.includes("T") ? dateStr.split("T")[0] : dateStr.split(" ")[0];
  return new Date(clean + "T00:00:00");
}

export function daysLeft(deadline: string): number {
  return Math.round(
    (parseDate(deadline).getTime() - new Date().setHours(0, 0, 0, 0)) / 86400000
  );
}

export function dueLabel(deadline: string): string {
  const d = daysLeft(deadline);
  if (d < 0) return `${-d} day${d === -1 ? "" : "s"} overdue`;
  if (d === 0) return "Due today";
  if (d === 1) return "Due tomorrow";
  if (d <= 7) return `Due in ${d} days`;
  return `Due ${parseDate(deadline).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  })}`;
}

export function dueTone(deadline: string, completed = false): string {
  if (completed) return "text-muted-foreground";
  const d = daysLeft(deadline);
  if (d < 0) return "text-rose-600 dark:text-rose-400";
  if (d === 0) return "text-orange-600 dark:text-orange-400";
  if (d <= 2) return "text-amber-600 dark:text-amber-400";
  return "text-muted-foreground";
}

export function shortDate(iso: string): string {
  return parseDate(iso).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}
