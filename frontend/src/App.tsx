import { useEffect, useState } from "react";
import { createSession, getGateStatus } from "./api";
import { apiUrl } from "./apiBase";
import type { SessionFull } from "./types";
import { AppHeader } from "./components/AppHeader";
import { AssessmentApp } from "./components/AssessmentApp";
import { GateScreen } from "./components/GateScreen";
import { IdentityStep } from "./components/IdentityStep";
import { ThemeToggle } from "./components/ThemeToggle";

const STORAGE_KEY = "safedevops_pilot_session_id";

type GatePhase = "loading" | "login" | "through";

export default function App() {
  const [gatePhase, setGatePhase] = useState<GatePhase>("loading");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [initial, setInitial] = useState<SessionFull | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const st = await getGateStatus();
        if (cancelled) return;
        if (st.gate_enabled && !st.authenticated) setGatePhase("login");
        else setGatePhase("through");
      } catch {
        if (!cancelled) setGatePhase("through");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (gatePhase !== "through") return;
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const id = Number(raw);
    if (!Number.isFinite(id)) return;
    (async () => {
      try {
        const res = await fetch(apiUrl(`/api/sessions/${id}`), { credentials: "include" });
        if (!res.ok) throw new Error("Session not found");
        const s = (await res.json()) as SessionFull;
        setSessionId(id);
        setInitial(s);
      } catch {
        sessionStorage.removeItem(STORAGE_KEY);
      }
    })();
  }, [gatePhase]);

  async function onStart(body: {
    name: string;
    email: string;
    team_name: string;
    ai_review_consent: boolean;
    data_restrictions_ack: boolean;
  }) {
    const s = await createSession(body);
    sessionStorage.setItem(STORAGE_KEY, String(s.session.id));
    setSessionId(s.session.id);
    setInitial(s);
  }

  function resetSession() {
    sessionStorage.removeItem(STORAGE_KEY);
    setSessionId(null);
    setInitial(null);
  }

  if (gatePhase === "loading") {
    return (
      <div className="app-shell">
        <p className="subtle">Loading…</p>
      </div>
    );
  }

  if (gatePhase === "login") {
    return <GateScreen onSuccess={() => setGatePhase("through")} />;
  }

  if (sessionId != null && initial) {
    return (
      <div className="app-shell">
        <AssessmentApp sessionId={sessionId} initial={initial} onNewSession={resetSession} />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <AppHeader subtitle="Pilot: guided self-assessment with optional AI review and evidence.">
        <ThemeToggle />
      </AppHeader>
      <IdentityStep onStart={onStart} />
    </div>
  );
}
