import { useCallback, useEffect, useState } from "react";
import type { SessionFull } from "../types";
import { downloadPartialExport, getSession, navigateSession } from "../api";
import { AppHeader } from "./AppHeader";
import { FinalSummary } from "./FinalSummary";
import { PartialExportModal } from "./PartialExportModal";
import { PracticePanel } from "./PracticePanel";
import { ProgressNav } from "./ProgressNav";
import { ThemeToggle } from "./ThemeToggle";

type Props = {
  sessionId: number;
  initial: SessionFull;
  onNewSession: () => void;
};

export function AssessmentApp({ sessionId, initial, onNewSession }: Props) {
  const [data, setData] = useState<SessionFull>(initial);
  const [partialOpen, setPartialOpen] = useState(false);
  const [partialBusy, setPartialBusy] = useState(false);
  const [exportNotice, setExportNotice] = useState<string | null>(null);

  const onRefresh = useCallback((s: SessionFull) => setData(s), []);

  useEffect(() => {
    if (!exportNotice) return;
    const t = window.setTimeout(() => setExportNotice(null), 10000);
    return () => window.clearTimeout(t);
  }, [exportNotice]);

  async function selectNav(index: number) {
    try {
      const s = await navigateSession(sessionId, index);
      setData(s);
    } catch {
      const s = await getSession(sessionId);
      setData(s);
    }
  }

  async function runPartialExport() {
    setPartialBusy(true);
    try {
      const { blob, filename } = await downloadPartialExport(sessionId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      setPartialOpen(false);
      setExportNotice("Partial export downloaded. Incomplete practices are labeled in the PDF and JSON.");
    } catch (e) {
      setExportNotice(e instanceof Error ? e.message : "Partial export failed.");
    } finally {
      setPartialBusy(false);
    }
  }

  const keys = data.ordered_practice_keys;
  const idx = Math.min(Math.max(data.session.current_practice_index, 0), Math.max(keys.length - 1, 0));
  const currentKey = keys[idx];
  const practice = data.config.practices.find((p) => p.key === currentKey);
  const practiceState = practice ? data.practices_state[practice.key] : undefined;

  const subtitle = `Session #${sessionId} · ${data.session.name} · ${data.session.team_name} · v${data.session.assessment_version}`;

  const headerUtilities = (
    <>
      <ThemeToggle />
      <button type="button" className="btn btn-ghost btn-compact" onClick={onNewSession}>
        New session
      </button>
    </>
  );

  const headerActionsInProgress = (
    <>
      <button type="button" className="btn btn-ghost btn-compact" onClick={() => setPartialOpen(true)}>
        Finish early
      </button>
      {headerUtilities}
    </>
  );

  if (data.all_complete) {
    return (
      <>
        <AppHeader subtitle={subtitle}>{headerUtilities}</AppHeader>
        <FinalSummary sessionId={sessionId} data={data} onNewSession={onNewSession} />
      </>
    );
  }

  if (!practice || !practiceState) {
    return (
      <>
        <AppHeader subtitle={subtitle}>{headerActionsInProgress}</AppHeader>
        <p className="subtle">Loading…</p>
      </>
    );
  }

  return (
    <>
      <AppHeader subtitle={subtitle}>{headerActionsInProgress}</AppHeader>
      {exportNotice ? (
        <div className="success-banner" role="status">
          {exportNotice}
        </div>
      ) : null}
      <PartialExportModal
        open={partialOpen}
        confirmedCount={data.completed_count}
        total={data.total_practices}
        onCancel={() => setPartialOpen(false)}
        onConfirm={runPartialExport}
        busy={partialBusy}
      />
      <div className="layout">
        <ProgressNav
          practices={data.config.practices}
          orderedKeys={keys}
          stateByKey={data.practices_state}
          currentIndex={idx}
          onSelect={selectNav}
        />
        <PracticePanel
          sessionId={sessionId}
          data={data}
          practice={practice}
          practiceState={practiceState}
          onRefresh={onRefresh}
          onOpenPartialExport={() => setPartialOpen(true)}
        />
      </div>
    </>
  );
}
