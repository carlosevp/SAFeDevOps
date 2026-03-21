import { FormEvent, useState } from "react";
import { gateLogin } from "../api";
import { ThemeToggle } from "./ThemeToggle";

type Props = { onSuccess: () => void };

export function GateScreen({ onSuccess }: Props) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await gateLogin(password);
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header" style={{ marginBottom: "1.5rem" }}>
        <div className="app-header-inner">
          <div className="app-title-block">
            <h1 className="app-title">SAFe DevOps assessment</h1>
            <p className="app-subtitle">This deployment requires a password.</p>
          </div>
          <ThemeToggle />
        </div>
      </header>
      <div className="card identity-card" style={{ maxWidth: "420px", margin: "0 auto" }}>
        <form onSubmit={onSubmit} autoComplete="current-password">
          <div className="field">
            <label htmlFor="gate-pw">Access password</label>
            <input
              id="gate-pw"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={busy}
              autoFocus
            />
          </div>
          {error ? <div className="error-text">{error}</div> : null}
          <div className="row" style={{ marginTop: "1rem" }}>
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? "Checking…" : "Continue"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
