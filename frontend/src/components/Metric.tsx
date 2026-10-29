import type { ElementType } from "react";
import { Tilt } from "@/components/Tilt";
import { cn } from "@/lib/utils";

/** A small summary tile: label, big value, optional icon and hint. */
export function Metric({
  icon: Icon,
  label,
  value,
  hint,
  tone = "primary",
}: {
  icon?: ElementType;
  label: string;
  value: string | number;
  hint?: string;
  tone?: "primary" | "warning";
}) {
  return (
    <Tilt className="surface border border-border/70 bg-card">
      <div className="flex items-start gap-3 p-4 [transform-style:preserve-3d]">
        {Icon && (
          <div
            className={cn(
              "depth-1 rounded-xl p-2.5 text-white shadow-lg",
              tone === "warning"
                ? "bg-gradient-to-br from-amber-400 to-orange-500 shadow-orange-500/30"
                : "bg-gradient-to-br from-primary to-[hsl(var(--glow-2))] shadow-primary/30",
            )}
          >
            <Icon className="h-4 w-4" />
          </div>
        )}
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold tracking-tight">{value}</p>
          {hint && <p className="truncate text-[11px] text-muted-foreground">{hint}</p>}
        </div>
      </div>
    </Tilt>
  );
}
