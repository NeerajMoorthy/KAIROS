import type { ElementType, ReactNode } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/** Placeholder blocks shaped like the content that is loading. */
export function LoadingState({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-3", className)} aria-busy="true" aria-label="Loading">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton h-24" />)}
      </div>
      {Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton h-28" />)}
    </div>
  );
}

/** A failed load, with a retry button when the caller can reload. */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Card className="border-destructive/30">
      <CardContent className="flex flex-wrap items-center gap-3 p-4">
        <div className="rounded-lg bg-destructive/10 p-2 text-destructive"><AlertTriangle className="h-4 w-4" /></div>
        <p className="min-w-0 flex-1 text-sm">{message}</p>
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RotateCw className="h-3.5 w-3.5" /> Try again
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

/** A friendly "nothing here yet" panel with an optional call to action. */
export function EmptyState({
  icon: Icon,
  title,
  children,
  action,
  className,
}: {
  icon: ElementType;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-3 px-6 py-10 text-center", className)}>
      <div className="surface rounded-2xl border bg-card p-3 text-primary"><Icon className="h-6 w-6" /></div>
      <div>
        <p className="font-semibold">{title}</p>
        {children && <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{children}</p>}
      </div>
      {action}
    </div>
  );
}
