import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Folder,
  FolderPlus,
  Globe,
  RefreshCw,
  Search,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RankedList } from "@/components/RankedList";
import { api, type IndexOutcome, type LibraryFolder, type RankedResource } from "@/lib/api";

function plural(n: number, word: string, many = `${word}s`) {
  return `${n} ${n === 1 ? word : many}`;
}

/** One sentence describing what an index or rescan changed. */
export function describeOutcome(o: IndexOutcome, where: string): string {
  const changes = [
    o.indexed > 0 ? `added ${o.indexed}` : "",
    o.updated > 0 ? `updated ${o.updated}` : "",
    o.removed > 0 ? `removed ${o.removed} that ${o.removed === 1 ? "is" : "are"} no longer on disk or in scope` : "",
  ].filter(Boolean);
  const head = changes.length
    ? `${where}: ${changes.join(", ")}.`
    : `${where}: nothing changed; ${plural(o.skipped, "file")} already current.`;
  return o.truncated
    ? `${head} The scan stopped at the 2,000-file limit, so files beyond it were not checked.`
    : head;
}

function folderName(path: string) {
  const parts = path.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] ?? path;
}

function shortTime(iso: string) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function FolderRow({
  folder,
  busy,
  onRescan,
  onRemove,
}: {
  folder: LibraryFolder;
  busy: boolean;
  onRescan: () => void;
  onRemove: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  return (
    <li className="rounded-lg border p-2.5" data-testid="library-folder">
      <div className="flex items-start gap-2">
        <Folder className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium" title={folder.path}>{folderName(folder.path)}</p>
          <p className="truncate font-mono text-[11px] text-muted-foreground" title={folder.path}>{folder.path}</p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            {plural(folder.resource_count, "file")} · {folder.recursive ? "includes subfolders" : "top level only"}
            {folder.tags.length > 0 && ` · ${folder.tags.join(", ")}`}
          </p>
          <p className="text-[11px] text-muted-foreground">Last scanned {shortTime(folder.last_indexed_at)}</p>
          {!folder.exists && (
            <p className="mt-1 flex items-center gap-1 text-[11px] text-amber-700 dark:text-amber-300">
              <AlertTriangle className="h-3 w-3" /> Folder not found on disk
            </p>
          )}
        </div>
      </div>
      {confirming ? (
        <div className="mt-2 rounded-md bg-muted p-2">
          <p className="text-[11px] text-muted-foreground">
            Remove this folder from your library? Files on disk are not changed.
          </p>
          <div className="mt-1.5 flex gap-1.5">
            <Button size="sm" variant="destructive" disabled={busy} onClick={() => { setConfirming(false); onRemove(); }}>
              Remove
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>Cancel</Button>
          </div>
        </div>
      ) : (
        <div className="mt-2 flex gap-1.5">
          <Button size="sm" variant="outline" disabled={busy || !folder.exists} onClick={onRescan}>
            <RefreshCw className="h-3.5 w-3.5" /> Rescan
          </Button>
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => setConfirming(true)}>
            <Trash2 className="h-3.5 w-3.5" /> Remove
          </Button>
        </div>
      )}
    </li>
  );
}

export function Resources({ onChanged }: { onChanged: () => void }) {
  const [folder, setFolder] = useState("");
  const [tags, setTags] = useState("");
  const [indexMsg, setIndexMsg] = useState<string | null>(null);
  const [indexing, setIndexing] = useState(false);

  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [results, setResults] = useState<RankedResource[]>([]);
  const [summary, setSummary] = useState<{ local: number; web: number } | null>(null);
  const [includeWeb, setIncludeWeb] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [libraryCount, setLibraryCount] = useState(0);
  const [folders, setFolders] = useState<LibraryFolder[]>([]);
  const [unmanaged, setUnmanaged] = useState(0);
  const [libraryError, setLibraryError] = useState<string | null>(null);

  const loadLibrary = useCallback(() => {
    api.listResources().then((r) => setLibraryCount(r.count)).catch(() => {});
    api
      .libraryFolders()
      .then((r) => {
        setFolders(r.folders);
        setUnmanaged(r.unmanaged_count);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadLibrary();
  }, [loadLibrary]);

  async function libraryAction(action: () => Promise<string>) {
    setLibraryError(null);
    setIndexMsg(null);
    setIndexing(true);
    try {
      setIndexMsg(await action());
      setResults([]);
      setSummary(null);
      loadLibrary();
      onChanged();
    } catch (err: any) {
      setLibraryError(String(err.message ?? err));
      loadLibrary();
    } finally {
      setIndexing(false);
    }
  }

  const rescanOne = (path: string) =>
    libraryAction(async () => describeOutcome(await api.rescanFolder(path), folderName(path)));

  const rescanAll = () =>
    libraryAction(async () => {
      const r = await api.rescanAllFolders();
      const failed = r.results.filter((x) => !x.ok);
      const base = describeOutcome(
        { indexed: r.indexed, updated: r.updated, removed: r.removed, skipped: r.skipped, text_indexed: 0, truncated: false },
        `Rescanned ${plural(r.results.length - failed.length, "folder")}`,
      );
      return failed.length
        ? `${base} ${plural(failed.length, "folder")} could not be scanned: ${failed.map((x) => folderName(x.path)).join(", ")}.`
        : base;
    });

  const removeOne = (path: string) =>
    libraryAction(async () => {
      const r = await api.removeFolder(path);
      return `Removed ${folderName(path)} from your library (${plural(r.removed, "entry", "entries")}). Files on disk were not changed.`;
    });

  useEffect(() => {
    const term = query.trim().split(/\s+/).pop() ?? "";
    if (term.length < 2) {
      const t = setTimeout(() => setSuggestions([]), 0);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => {
      api
        .autocomplete(term)
        .then((r) => setSuggestions(r.suggestions.filter((s) => s !== term)))
        .catch(() => setSuggestions([]));
    }, 180);
    return () => clearTimeout(t);
  }, [query]);

  async function indexFolder(e: React.FormEvent) {
    e.preventDefault();
    await libraryAction(async () => {
      const r = await api.indexFolder(
        folder,
        tags.split(",").map((t) => t.trim()).filter(Boolean)
      );
      setFolder("");
      setTags("");
      return `${describeOutcome(r, folderName(r.path))} Your library is searchable on ${r.library_keywords} keywords.`;
    });
  }

  async function runSearch(q = query) {
    if (!q.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.search(q, 8, includeWeb);
      setResults(r.results);
      setSummary({ local: r.local_matches, web: r.web_matches });
    } catch (err: any) {
      setError(String(err.message ?? err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_22rem]">
      <div className="space-y-4">
        <Card>
          <CardHeader className="border-b pb-3">
            <CardTitle className="flex items-center gap-2">
              <Search className="h-4 w-4" /> Find your resources
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              Search folders you explicitly add. Public web suggestions are optional.
            </p>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="flex flex-wrap gap-2">
              <Input
                className="min-w-[15rem] flex-1"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runSearch()}
                placeholder="project report, citations, topic…"
              />
              <Button onClick={() => runSearch()} disabled={busy}>
                {busy ? "Searching…" : "Search"}
              </Button>
              <Button
                variant={includeWeb ? "secondary" : "outline"}
                onClick={() => setIncludeWeb((v) => !v)}
                title="If enabled, your search terms are sent to Wikipedia for public suggestions."
              >
                <Globe className="h-4 w-4" />
                Public web {includeWeb ? "on" : "off"}
              </Button>
            </div>

            {suggestions.length > 0 && (
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-muted-foreground">Suggestions:</span>
                {suggestions.map((s) => (
                  <button
                    key={s}
                    className="rounded-full border px-2.5 py-0.5 text-xs transition-colors hover:bg-accent"
                    onClick={() => {
                      const parts = query.trim().split(/\s+/);
                      parts[parts.length - 1] = s;
                      const next = parts.join(" ");
                      setQuery(next);
                      runSearch(next);
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}

            {error && <p className="mt-3 text-sm text-destructive">{error}</p>}

            {summary && (
              <p className="mt-3 text-xs text-muted-foreground">
                {summary.local} file{summary.local === 1 ? "" : "s"} from your library
                {summary.web > 0 && ` and ${summary.web} from the web`}, ranked by explainable match points.
              </p>
            )}

            <div className="mt-3">
              <RankedList items={results} />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader className="border-b pb-3">
            <CardTitle className="flex items-center gap-2">
              <FolderPlus className="h-4 w-4" /> Your library
            </CardTitle>
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground" data-testid="library-summary">
                {plural(libraryCount, "item")} indexed · {plural(folders.length, "folder")}
              </p>
              {folders.length > 0 && (
                <Button size="sm" variant="outline" disabled={indexing} onClick={() => void rescanAll()}>
                  <RefreshCw className="h-3.5 w-3.5" /> Rescan all
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            {folders.length > 0 && (
              <ul className="space-y-2">
                {folders.map((f) => (
                  <FolderRow
                    key={f.path}
                    folder={f}
                    busy={indexing}
                    onRescan={() => void rescanOne(f.path)}
                    onRemove={() => void removeOne(f.path)}
                  />
                ))}
              </ul>
            )}
            {unmanaged > 0 && (
              <p className="rounded-md border border-dashed p-2 text-[11px] text-muted-foreground">
                {plural(unmanaged, "file")} came from folders indexed before folder tracking. Index those folders again to manage them here.
              </p>
            )}
            <form onSubmit={indexFolder} className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="folder">Folder path you choose</Label>
                <Input
                  id="folder"
                  value={folder}
                  onChange={(e) => setFolder(e.target.value)}
                  placeholder={"C:\\Users\\you\\Documents\\Project Files"}
                  required
                />
                <p className="text-[11px] text-muted-foreground">
                  Only this chosen folder is indexed. KAIROS stores file paths and metadata; files remain where they are.
                </p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="tags">Tags (optional)</Label>
                <Input
                  id="tags"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="project, reading, notes"
                />
              </div>
              <Button type="submit" className="w-full" disabled={indexing}>
                {indexing ? "Working…" : "Add folder"}
              </Button>
            </form>
            {indexMsg && (
              <p className="rounded-md bg-muted p-2 text-xs text-muted-foreground" role="status">
                {indexMsg}
              </p>
            )}
            {libraryError && <p className="text-xs text-destructive" role="alert">{libraryError}</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
