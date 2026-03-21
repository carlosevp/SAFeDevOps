import { useEffect, useState } from "react";
import type { SessionFull } from "../types";
import { downloadExport } from "../api";
import { apiUrl } from "../apiBase";

type SummaryJson = {
  identity: { name: string; email: string; team_name: string };
  timestamp_utc: string;
  assessment_version: string;
  completion_mode?: string;
  partial_export?: boolean;
  completion_percentage?: number;
  export_summary?: string;
  practices_confirmed_count?: number;
  practices_total?: number;
  overall_score: number | null;
  overall_confidence: number | null;
  overall_partial?: boolean;
  domain_rollups: Record<
    string,
    {
      average_score: number | null;
      average_confidence?: number | null;
      practice_count?: number;
      practices_scored_count?: number;
      practices_completed_confirmed?: number;
      practices_incomplete_or_unconfirmed?: number;
    }
  >;
  practices: Array<{
    practice_name: string;
    pipeline_area: string;
    practice_completion_status?: string;
    score: number | null;
    sufficiency_confidence?: number | null;
    rationale_summary?: string | null;
    insufficient_after_cap?: boolean;
    low_confidence_flag?: boolean;
  }>;
};

type Props = {
  sessionId: number;
  data: SessionFull;
  onNewSession: () => void;
};

export function FinalSummary({ sessionId, data, onNewSession }: Props) {
  const [summary, setSummary] = useState<SummaryJson | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(apiUrl(`/api/sessions/${sessionId}/summary-json`));
        if (!res.ok) {
          const t = await res.text();
          throw new Error(t || res.statusText);
        }
        const j = (await res.json()) as SummaryJson;
        if (!cancelled) setSummary(j);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not load summary");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId, data.all_complete]);

  async function onExport() {
    setExporting(true);
    setError(null);
    try {
      const { blob, filename } = await downloadExport(sessionId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="card">
      <h1 style={{ marginBottom: "0.35rem" }}>Final summary</h1>
      <p className="subtle">
        All practices are confirmed. Here is your quantitative summary (hidden until this stage). Download a ZIP with{" "}
        <code>report.pdf</code> and <code>results.json</code> for your records.
      </p>

      {error ? <div className="error-text">{error}</div> : null}

      {summary ? (
        <>
          {summary.export_summary ? (
            <p className="notice ok" style={{ marginTop: "1rem", marginBottom: 0 }}>
              {summary.export_summary}
            </p>
          ) : null}

          <div className="notice ok" style={{ marginTop: "1rem" }}>
            <strong>{summary.identity.name}</strong> · {summary.identity.email}
            <div>{summary.identity.team_name}</div>
            <div className="subtle" style={{ marginTop: "0.35rem" }}>
              Completed at {summary.timestamp_utc} · Version {summary.assessment_version}
            </div>
          </div>

          <h2>Overall</h2>
          <p>
            Overall average score: <strong>{summary.overall_score ?? "n/a"}</strong> (1.0–5.0 scale, confirmed
            practices only)
            {summary.overall_confidence != null && (
              <span className="subtle"> · confidence {summary.overall_confidence.toFixed(2)}</span>
            )}
          </p>

          <h2>By pipeline area</h2>
          <ul>
            {Object.entries(summary.domain_rollups).map(([area, r]) => (
              <li key={area}>
                <strong>{area}</strong>: average {r.average_score ?? "n/a"}
                {r.practices_incomplete_or_unconfirmed != null && r.practices_incomplete_or_unconfirmed > 0 ? (
                  <span className="subtle"> ({r.practices_incomplete_or_unconfirmed} incomplete in domain)</span>
                ) : null}
                {r.practice_count != null ? (
                  <span className="subtle"> · {r.practice_count} practices</span>
                ) : r.practices_scored_count != null ? (
                  <span className="subtle"> · {r.practices_scored_count} scored</span>
                ) : null}
                {r.average_confidence != null && (
                  <span className="subtle"> (confidence {r.average_confidence.toFixed(2)})</span>
                )}
              </li>
            ))}
          </ul>

          <h2>Practice scores</h2>
          <ul>
            {summary.practices.map((p) => (
              <li key={p.practice_name + p.pipeline_area}>
                <strong>{p.practice_name}</strong> ({p.pipeline_area}
                {p.practice_completion_status ? ` · ${p.practice_completion_status}` : ""}): {p.score ?? "n/a"}
                {p.insufficient_after_cap ? " — capped follow-ups" : ""}
                {p.low_confidence_flag ? " — low confidence" : ""}
              </li>
            ))}
          </ul>
        </>
      ) : (
        !error && <p className="subtle">Loading summary…</p>
      )}

      <div className="row" style={{ marginTop: "1.35rem", gap: "0.65rem" }}>
        <button type="button" className="btn btn-primary" onClick={() => void onExport()} disabled={exporting}>
          {exporting ? "Preparing ZIP…" : "Download export ZIP"}
        </button>
        <button type="button" className="btn btn-ghost btn-compact" onClick={onNewSession}>
          Start a new session
        </button>
      </div>
    </div>
  );
}
