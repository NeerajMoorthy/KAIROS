import { useEffect, useState } from "react";
import { Check, Clock3, HardDrive, RotateCcw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type SnapshotStatus } from "@/lib/api";

export function SettingsPage({ refreshKey, onChanged }: { refreshKey: number; onChanged: () => void }) {
  const [hours, setHours] = useState(3);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demoMessage, setDemoMessage] = useState<string | null>(null);
  const [storage, setStorage] = useState<SnapshotStatus | null>(null);

  useEffect(() => {
    api.settings().then((settings) => setHours(settings.available_hours_per_day)).catch((e) => setError(String(e instanceof Error ? e.message : e)));
    api.snapshotStatus().then(setStorage).catch(() => setStorage(null));
  }, [refreshKey, saved, demoMessage]);

  async function save() {
    setBusy(true);
    setSaved(false);
    setError(null);
    try {
      const settings = await api.updateSettings({ available_hours_per_day: hours });
      setHours(settings.available_hours_per_day);
      setSaved(true);
      onChanged();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }

  async function loadExample() {
    setBusy(true);
    setError(null);
    setDemoMessage(null);
    try {
      const result = await api.seed();
      setDemoMessage(result.count
        ? `Added ${result.count} example tasks and local project resources.`
        : "Example tasks are already present; no duplicates were added.");
      onChanged();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }

  async function resetWorkspace() {
    if (!window.confirm("Clear all tasks, resources, and focus-session history from this workspace?")) return;
    setBusy(true);
    setError(null);
    setDemoMessage(null);
    try {
      await api.reset();
      setDemoMessage("Workspace data cleared.");
      onChanged();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="max-w-2xl">
      <CardHeader className="border-b pb-3">
        <CardTitle className="flex items-center gap-2"><Clock3 className="h-4 w-4" /> Daily availability</CardTitle>
        <p className="text-sm text-muted-foreground">KAIROS uses this estimate to explain deadline risk and recommend a realistic focus session.</p>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        <div className="max-w-xs space-y-1.5">
          <Label htmlFor="availability">Hours available per day</Label>
          <Input id="availability" type="number" min={0} max={16} step={0.5} value={hours} onChange={(e) => setHours(Number(e.target.value))} />
          <p className="text-xs text-muted-foreground">Set 0 when you have no work time available. This is a planning estimate, not a calendar connection.</p>
        </div>
        <Button onClick={() => void save()} disabled={busy || hours < 0 || hours > 16}>
          <Check className="h-4 w-4" /> {busy ? "Saving…" : "Save availability"}
        </Button>
        {saved && <p className="text-sm text-emerald-700 dark:text-emerald-300">Availability saved.</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>

      <CardContent className="space-y-1.5 border-t pt-4" data-testid="storage-status">
        <p className="flex items-center gap-2 font-medium"><HardDrive className="h-4 w-4" /> Saving</p>
        {storage === null ? (
          <p className="text-sm text-muted-foreground">Save status is unavailable.</p>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              {storage.account
                ? `Every change is saved automatically to your account (${storage.account}).`
                : storage.autosave.enabled
                ? "Every change is saved automatically to this computer."
                : "Automatic saving is off (KAIROS_AUTOSAVE=0). Changes are saved when the server stops."}
            </p>
            <p className="break-all font-mono text-[11px] text-muted-foreground">{storage.path}</p>
            {storage.autosave.last_error ? (
              <p className="text-sm text-destructive">Last automatic save failed: {storage.autosave.last_error}</p>
            ) : storage.saved_at ? (
              <p className="text-xs text-muted-foreground">
                Last saved {new Date(storage.saved_at).toLocaleString()}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">Nothing has been saved yet.</p>
            )}
          </>
        )}
      </CardContent>

      <CardContent className="space-y-3 border-t pt-4">
        <div>
          <p className="font-medium">Example workspace</p>
          <p className="mt-1 text-sm text-muted-foreground">Load generic project tasks and sample files to walk through KAIROS.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void loadExample()} disabled={busy}><Sparkles className="h-4 w-4" /> Load example data</Button>
          <Button variant="ghost" onClick={() => void resetWorkspace()} disabled={busy}><RotateCcw className="h-4 w-4" /> Clear workspace</Button>
        </div>
        {demoMessage && <p className="text-sm text-muted-foreground">{demoMessage}</p>}
      </CardContent>
    </Card>
  );
}
