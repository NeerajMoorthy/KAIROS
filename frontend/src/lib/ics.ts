import type { Task, TimelineDay } from "@/lib/api";

/** "2026-10-29" (or an ISO timestamp) -> "20261029" */
function icsDate(iso: string): string {
  return iso.slice(0, 10).replace(/-/g, "");
}

function nextDay(iso: string): string {
  const d = new Date(iso.slice(0, 10) + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

/** Escape text for an iCalendar property value (RFC 5545 §3.3.11). */
function escapeText(text: string): string {
  return text.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
}

/** Lines longer than 75 characters continue on the next line after a space. */
function fold(line: string): string {
  const parts: string[] = [];
  for (let i = 0; i < line.length; i += 74) parts.push(line.slice(i, i + 74));
  return parts.join("\r\n ");
}

function allDayEvent(uid: string, day: string, summary: string, description: string, stamp: string): string[] {
  return [
    "BEGIN:VEVENT",
    `UID:${uid}@kairos`,
    `DTSTAMP:${stamp}`,
    `DTSTART;VALUE=DATE:${icsDate(day)}`,
    `DTEND;VALUE=DATE:${icsDate(nextDay(day))}`,
    `SUMMARY:${escapeText(summary)}`,
    `DESCRIPTION:${escapeText(description)}`,
    "TRANSP:TRANSPARENT",
    "END:VEVENT",
  ];
}

/**
 * Build an .ics file with one all-day event per planned study block and one
 * per open task deadline. Google Calendar, Outlook and Apple Calendar all
 * import it.
 */
export function buildIcs(timeline: TimelineDay[], tasks: Task[]): string {
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//KAIROS//Study plan//EN", "CALSCALE:GREGORIAN", "X-WR-CALNAME:KAIROS study plan"];
  for (const day of timeline) {
    day.blocks.forEach((block, index) => {
      lines.push(...allDayEvent(
        `plan-${day.date}-${block.task_id}-${index}`,
        day.date,
        `Study: ${block.title} (${block.hours} h)`,
        `KAIROS planned ${block.hours} h of work on "${block.title}" for this day.`,
        stamp,
      ));
    });
  }
  for (const task of tasks) {
    if (task.completed) continue;
    lines.push(...allDayEvent(
      `due-${task.id}`,
      task.deadline,
      `Due: ${task.title}`,
      `${task.title} is due. About ${task.remaining_hours} h of work remained when this was exported.`,
      stamp,
    ));
  }
  lines.push("END:VCALENDAR");
  return lines.map(fold).join("\r\n") + "\r\n";
}

export function downloadIcs(content: string, filename = "kairos-plan.ics") {
  const url = URL.createObjectURL(new Blob([content], { type: "text/calendar;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
