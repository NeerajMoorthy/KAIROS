import type { ElementType } from "react";
import { Card, CardContent } from "@/components/ui/card";

/** A small summary tile: label, big value, optional icon and hint. */
export function Metric({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon?: ElementType;
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-start gap-3 p-4">
        {Icon && <div className="rounded-lg bg-muted p-2"><Icon className="h-4 w-4" /></div>}
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold">{value}</p>
          {hint && <p className="truncate text-[11px] text-muted-foreground">{hint}</p>}
        </div>
      </CardContent>
    </Card>
  );
}
