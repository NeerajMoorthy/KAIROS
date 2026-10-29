import { ExternalLink, FileText, Globe } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { RankedResource } from "@/lib/api";
import { cn } from "@/lib/utils";

function hostname(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url; // a malformed link must not crash the whole list
  }
}

export function RankedList({ items }: { items: RankedResource[] }) {
  if (items.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        No matching material yet.
      </p>
    );
  }
  return (
    <ul className="space-y-2">
      {items.map((r, i) => {
        const web = r.resource.source === "web";
        return (
          <li key={r.resource.id} className="rounded-lg border p-3 transition-colors hover:bg-muted/40">
            <div className="flex items-start gap-3">
              <div className={cn("mt-0.5 rounded-md p-1.5", web ? "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300" : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300")}>
                {web ? <Globe className="h-3.5 w-3.5" /> : <FileText className="h-3.5 w-3.5" />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="text-xs text-muted-foreground">#{i + 1}</span>
                  <span className="font-medium">{r.resource.title}</span>
                  <Badge variant="outline" className="text-[10px]">
                    {r.resource.kind}
                  </Badge>
                  <Badge variant="outline" className="ml-auto text-[10px]" title="Explainable match score, not a probability">
                    {r.score} match points
                  </Badge>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">{r.resource.snippet}</p>
                {web ? (
                  <a
                    href={r.resource.location}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="mt-1 inline-flex items-center gap-1 text-xs text-sky-700 underline underline-offset-2 dark:text-sky-400"
                  >
                    {hostname(r.resource.location)}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                ) : (
                  <p className="mt-1 truncate font-mono text-[11px] text-muted-foreground">
                    {r.resource.location}
                  </p>
                )}
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Why it matched: {r.reasons.slice(0, 3).join(" · ")}
                </p>
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

