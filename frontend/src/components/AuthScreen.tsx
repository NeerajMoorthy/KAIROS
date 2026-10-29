import { useState, type FormEvent } from "react";
import { LogIn, UserPlus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LogoCube } from "@/components/LogoCube";
import { Tilt } from "@/components/Tilt";
import { api } from "@/lib/api";

/** Log in or create an account. `onCancel` is offered only when login is optional. */
export function AuthScreen({
  onSignedIn,
  onCancel,
  notice,
}: {
  onSignedIn: (token: string, username: string) => void;
  onCancel?: () => void;
  notice?: string | null;
}) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = mode === "login" ? await api.logIn(username, password) : await api.signUp(username, password);
      onSignedIn(result.token, result.username);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-background/60 p-4 backdrop-blur-sm">
      <div className="app-backdrop" aria-hidden />
      <Tilt max={3} className="glass surface-raised w-full max-w-sm rounded-2xl border">
        <form onSubmit={submit} className="relative space-y-4 p-6 [transform-style:preserve-3d]">
          {onCancel && (
            <button type="button" onClick={onCancel} className="absolute right-3 top-3 rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Close">
              <X className="h-4 w-4" />
            </button>
          )}
          <div className="depth-1 flex flex-col items-center gap-2 text-center">
            <LogoCube className="h-12 w-12 scale-125" />
            <h1 className="text-xl font-bold tracking-tight">
              {mode === "login" ? "Welcome back to KAIROS" : "Create your KAIROS account"}
            </h1>
            <p className="text-sm text-muted-foreground">
              {mode === "login" ? "Log in to see your own tasks and plans." : "Your tasks, plans and progress stay private to you."}
            </p>
          </div>

          {notice && <p className="rounded-lg bg-muted px-3 py-2 text-center text-xs text-muted-foreground">{notice}</p>}

          <Tabs value={mode} onValueChange={(value) => { setMode(value as "login" | "signup"); setError(null); }}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="login">Log in</TabsTrigger>
              <TabsTrigger value="signup">Sign up</TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="space-y-1.5">
            <Label htmlFor="auth-username">Username</Label>
            <Input id="auth-username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="auth-password">Password</Label>
            <Input
              id="auth-password"
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={mode === "signup" ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            {mode === "signup" && <p className="text-[11px] text-muted-foreground">At least 8 characters.</p>}
          </div>

          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

          <Button type="submit" className="w-full" disabled={busy}>
            {mode === "login" ? <LogIn className="h-4 w-4" /> : <UserPlus className="h-4 w-4" />}
            {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
          </Button>
        </form>
      </Tilt>
    </div>
  );
}
