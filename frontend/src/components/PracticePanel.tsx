import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type { PracticeConfig, PracticeState, ReviewResult, SessionFull } from "../types";
import {
  confirmPractice,
  deleteFile,
  getSession,
  runReview,
  saveDraft,
  submitFollowup,
  uploadFile,
} from "../api";
import { fileExt, formatBytes, saveStatusMessage } from "./practicePanelUtils";

type Props = {
  readonly sessionId: number;
  readonly data: SessionFull;
  readonly practice: PracticeConfig;
  readonly practiceState: PracticeState;
  readonly onRefresh: (s: SessionFull) => void;
  readonly onOpenPartialExport: () => void;
};

export function PracticePanel({
  sessionId,
  data,
  practice,
  practiceState,
  onRefresh,
  onOpenPartialExport,
}: Readonly<Props>) {
  const [narrative, setNarrative] = useState(practiceState.narrative);
  const [saving, setSaving] = useState(false);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [followupText, setFollowupText] = useState("");
  const [localReview, setLocalReview] = useState<ReviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ackConsolidated, setAckConsolidated] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showEval = data.config.show_evaluation_feedback === true;
  const canConfirm =
    !practiceState.user_confirmed && (localReview?.allow_confirm || practiceState.allow_confirm);

  const lastAiRound = [...(practiceState.follow_up_transcript || [])]
    .reverse()
    .find((t) => t.kind === "ai_followups");
  const followUpRoundLabel = lastAiRound?.round ?? (practiceState.follow_up_questions.length ? 1 : null);

  useEffect(() => {
    setNarrative(practiceState.narrative);
    setLocalReview(null);
    setFollowupText("");
    setError(null);
    setAckConsolidated(false);
    setLastSavedAt(null);
  }, [practice.key, practiceState.narrative]);

  useEffect(() => {
    if (!canConfirm) return;
    setAckConsolidated(false);
  }, [narrative, canConfirm]);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      if (narrative === practiceState.narrative) return;
      setSaving(true);
      try {
        const s = await saveDraft(sessionId, practice.key, narrative);
        onRefresh(s);
        setLastSavedAt(Date.now());
      } catch {
        /* autosave best-effort */
      } finally {
        setSaving(false);
      }
    }, 600);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [narrative, practice.key, practiceState.narrative, sessionId, onRefresh]);

  const dirty = narrative !== practiceState.narrative;
  const saveStatus = saveStatusMessage(
    practiceState.user_confirmed,
    saving,
    dirty,
    lastSavedAt
  );

  const MAX_MB = 15;

  const runUploadFiles = useCallback(
    async (files: File[]) => {
      setError(null);
      for (const f of files) {
        if (f.size > MAX_MB * 1024 * 1024) {
          setError(`File "${f.name}" exceeds ${MAX_MB} MB.`);
          return;
        }
        const ext = f.name.split(".").pop()?.toLowerCase();
        if (!ext || !["png", "jpg", "jpeg", "webp", "gif", "pdf"].includes(ext)) {
          setError(`File "${f.name}" has unsupported type. Use PNG, JPG, WebP, GIF, or PDF.`);
          return;
        }
        try {
          const s = await uploadFile(sessionId, practice.key, f);
          onRefresh(s);
        } catch (e) {
          setError(e instanceof Error ? e.message : "Upload failed");
          return;
        }
      }
    },
    [onRefresh, practice.key, sessionId]
  );

  async function onUpload(files: FileList | null) {
    if (!files?.length) return;
    await runUploadFiles(Array.from(files));
  }

  async function onDeleteFile(id: string) {
    setError(null);
    try {
      const s = await deleteFile(sessionId, practice.key, id);
      onRefresh(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  async function onReview() {
    setError(null);
    setReviewBusy(true);
    setLocalReview(null);
    try {
      await saveDraft(sessionId, practice.key, narrative);
      const r = await runReview(sessionId, practice.key);
      if (r.ok) {
        setLocalReview(null);
        setError(null);
      } else {
        setLocalReview(r);
        setError(r.error || "Review failed");
      }
      const refreshed = await getSession(sessionId);
      onRefresh(refreshed);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed");
    } finally {
      setReviewBusy(false);
    }
  }

  async function onFollowup() {
    setError(null);
    setReviewBusy(true);
    try {
      const answers = followupText.split(/\n---\n/).map((x) => x.trim()).filter(Boolean);
      const payload = answers.length ? answers : [followupText.trim()];
      const r = await submitFollowup(sessionId, practice.key, payload);
      setFollowupText("");
      if (!r.ok) {
        setLocalReview(r);
        setError(r.error || "Follow-up failed");
      } else {
        setLocalReview(null);
        setError(null);
      }
      const refreshed = await getSession(sessionId);
      onRefresh(refreshed);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Follow-up failed");
    } finally {
      setReviewBusy(false);
    }
  }

  async function onConfirm() {
    setError(null);
    if (!narrative.trim()) {
      setError("Your response cannot be empty.");
      return;
    }
    if (!ackConsolidated) {
      setError("Confirm the checkbox that this full response is what you want assessed.");
      return;
    }
    try {
      await saveDraft(sessionId, practice.key, narrative);
      const s = await confirmPractice(sessionId, practice.key, {
        acknowledge_consolidated_response: true,
        final_narrative: narrative,
      });
      onRefresh(s);
      setLocalReview(null);
      setAckConsolidated(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not confirm");
    }
  }

  const displayQuestions =
    localReview?.follow_up_questions?.length ? localReview.follow_up_questions : practiceState.follow_up_questions;
  const displaySufficiency = localReview?.sufficiency_plain || practiceState.sufficiency_plain;
  const displayConfirm = localReview?.confirmation_message || practiceState.confirmation_message;
  const displayCap = localReview?.cap_warning || practiceState.cap_warning;
  const displayRationale = localReview?.rationale_short || practiceState.last_rationale_short;
  const cap = Number(data.config.defaults?.follow_up_cap ?? localReview?.follow_up_cap ?? 3) || 3;
  const atCap = practiceState.follow_up_rounds_used >= cap;

  const sufficiencyOk = Boolean(displayConfirm && !displayQuestions.length);

  let followupSection: ReactNode = null;
  if (!practiceState.user_confirmed && displayQuestions.length > 0) {
    followupSection = (
      <section className="section-block panel-followup" aria-labelledby="followup-heading">
        <div className="panel-followup-round" id="followup-heading">
          Follow-up {followUpRoundLabel != null ? `(round ${followUpRoundLabel} of ${cap})` : ""}
        </div>
        <p style={{ margin: "0 0 0.35rem", fontWeight: 600 }}>The reviewer needs a bit more detail</p>
        <p className="subtle" style={{ marginTop: 0 }}>
          Answer the prompts below. Your main response stays above; new detail will be woven into your narrative when
          you submit.
        </p>
        <div className="response-vs-followup">
          <div>
            <div className="section-label" style={{ marginBottom: "0.35rem" }}>
              Your current response (reference)
            </div>
            <div className="original-response-panel">{narrative.trim() || "(empty)"}</div>
          </div>
          <div>
            <div className="section-label" style={{ marginBottom: "0.35rem" }}>
              What to add next
            </div>
            <ol className="followup-questions">
              {displayQuestions.map((q, i) => (
                <li key={`${practice.key}-followup-${i}`}>{q}</li>
              ))}
            </ol>
          </div>
        </div>
        <label className="sr-only" htmlFor={`followup-${practice.key}`}>
          Follow-up answers
        </label>
        <textarea
          id={`followup-${practice.key}`}
          className="narrative"
          style={{ minHeight: 140 }}
          value={followupText}
          onChange={(e) => setFollowupText(e.target.value)}
          disabled={atCap || reviewBusy}
          placeholder="Add detail for each question above. Separate answers with a blank line, or a line containing only ---"
        />
        <div className="row" style={{ marginTop: "0.5rem" }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void onFollowup()}
            disabled={reviewBusy || atCap || !followupText.trim()}
          >
            {reviewBusy ? "Sending…" : "Submit follow-up answers"}
          </button>
          {atCap ? <span className="subtle">Follow-up cap reached — use Confirm if available.</span> : null}
        </div>
      </section>
    );
  }

  const showSufficiencyReview =
    !practiceState.user_confirmed &&
    showEval &&
    Boolean(displaySufficiency || displayConfirm || displayRationale);

  let sufficiencyReviewPanel: ReactNode = null;
  if (showSufficiencyReview) {
    sufficiencyReviewPanel = (
      <div
        className={sufficiencyOk ? "notice ok" : "notice"}
        style={{ marginTop: "1rem" }}
        role="status"
        aria-live="polite"
      >
        <strong>{sufficiencyOk ? "Sufficiency review: ready" : "Sufficiency review: more detail"}</strong>
        {sufficiencyOk ? (
          <div style={{ marginTop: "0.35rem", whiteSpace: "pre-wrap" }}>{displayConfirm}</div>
        ) : (
          <>
            {displaySufficiency ? (
              <div className="subtle" style={{ marginTop: "0.35rem" }}>
                {displaySufficiency}
              </div>
            ) : null}
            {displayRationale ? (
              <div className="subtle" style={{ marginTop: "0.35rem", whiteSpace: "pre-wrap" }}>
                {displayRationale}
              </div>
            ) : null}
          </>
        )}
      </div>
    );
  }

  return (
    <div className="card">
      <div className="focus-practice-header">
        <div>
          <span className="pill">{practice.pipeline_area_name}</span>
          <h2 className="practice-name">{practice.name}</h2>
        </div>
        {practiceState.user_confirmed ? <span className="pill pill-success">Confirmed</span> : null}
      </div>

      <section className="section-block" aria-labelledby="eval-heading">
        <h2 id="eval-heading">
          <span className="section-label">Evaluates</span>
        </h2>
        <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{practice.what_it_evaluates}</p>
      </section>

      <section className="section-block" aria-labelledby="examples-heading">
        <h2 id="examples-heading">
          <span className="section-label">Examples</span>
        </h2>
        <details className="guidance-details">
          <summary>Enterprise context examples (optional)</summary>
          <div className="guidance-body subtle">
            {practice.enterprise_examples.length ? (
              <ul>
                {practice.enterprise_examples.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            ) : (
              <p style={{ margin: 0 }}>No examples configured for this practice.</p>
            )}
          </div>
        </details>
      </section>

      <section className="section-block" aria-labelledby="response-heading">
        <h2 id="response-heading">
          <span className="section-label">Your response</span>
        </h2>
        <p className="subtle" style={{ whiteSpace: "pre-wrap", marginTop: 0 }}>
          {practice.user_prompt}
        </p>
        {practiceState.follow_up_rounds_used > 0 ? (
          <p className="subtle" style={{ marginBottom: "0.5rem" }}>
            Your initial answer and follow-up details are merged in the box below. Edit freely before confirming this
            practice.
          </p>
        ) : (
          <p className="subtle" style={{ marginBottom: "0.5rem" }}>
            Write in your own words. Longer answers are fine — aim for enough detail for a fair review.
          </p>
        )}

        <label className="sr-only" htmlFor={`narrative-${practice.key}`}>
          Narrative response for {practice.name}
        </label>
        <textarea
          id={`narrative-${practice.key}`}
          className="narrative"
          value={narrative}
          onChange={(e) => setNarrative(e.target.value)}
          disabled={practiceState.user_confirmed}
          placeholder="Describe how your team handles this practice today: tooling, habits, handoffs, pain points, and what would improve…"
          aria-describedby={`narrative-hint-${practice.key}`}
        />
        <div className="narrative-meta" id={`narrative-hint-${practice.key}`}>
          <span className={!dirty && !saving && !practiceState.user_confirmed ? "saved-ok" : undefined}>
            {saveStatus}
            {lastSavedAt && !dirty && !saving && !practiceState.user_confirmed
              ? ` · ${new Date(lastSavedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
              : null}
          </span>
          <span>{narrative.length.toLocaleString()} characters</span>
        </div>
      </section>

      <section className="section-block" aria-labelledby="evidence-heading">
        <h2 id="evidence-heading">
          <span className="section-label">Evidence</span> <span className="subtle" style={{ fontWeight: 400 }}>(optional)</span>
        </h2>
        <p className="subtle" style={{ whiteSpace: "pre-wrap", marginTop: 0 }}>
          {practice.evidence_encouragement}
        </p>
        <p className="subtle dropzone-hint">
          Screenshots or PDFs help the reviewer ground feedback in real artifacts. Files stay with this session for
          export; remove anything sensitive before uploading.
        </p>
        <section
          className={`dropzone${dragOver ? " dropzone-active" : ""}`}
          aria-label="Upload or drop evidence files"
          onDragOver={(e) => {
            e.preventDefault();
            if (!practiceState.user_confirmed) setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            if (practiceState.user_confirmed) return;
            void onUpload(e.dataTransfer.files);
          }}
        >
          <label className="dropzone-label">
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif,application/pdf"
              multiple
              disabled={practiceState.user_confirmed}
              onChange={(e) => {
                void onUpload(e.target.files);
                e.target.value = "";
              }}
            />
            <strong>Upload</strong> or drag files here · PNG, JPG, WebP, GIF, PDF · max {MAX_MB} MB each
          </label>
          <ul className="file-list">
            {practiceState.files.length === 0 ? (
              <li className="subtle" style={{ border: "none" }}>
                No files attached yet.
              </li>
            ) : null}
            {practiceState.files.map((f) => (
              <li key={f.id}>
                <span style={{ display: "flex", alignItems: "center", gap: "0.5rem", minWidth: 0 }}>
                  <span className="file-badge" title={f.content_type}>
                    {fileExt(f.filename)}
                  </span>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{f.filename}</span>
                  <span className="subtle" style={{ flexShrink: 0 }}>
                    {formatBytes(f.size_bytes)}
                  </span>
                </span>
                {practiceState.user_confirmed ? null : (
                  <button type="button" className="btn btn-ghost btn-compact" onClick={() => onDeleteFile(f.id)}>
                    Remove
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      </section>

      {error ? (
        <div className="error-text" style={{ marginTop: "0.75rem" }} role="alert">
          {error}
        </div>
      ) : null}

      {followupSection}

      {sufficiencyReviewPanel}

      {!showEval && displayConfirm && !practiceState.user_confirmed ? (
        <div className="notice ok" style={{ marginTop: "1rem" }} role="status" aria-live="polite">
          <strong>Review complete</strong>
          <div style={{ marginTop: "0.35rem" }}>{displayConfirm}</div>
        </div>
      ) : null}

      {displayCap ? (
        <div className="notice warn" style={{ marginTop: "0.75rem" }}>
          <strong>{showEval ? "Heads up" : "Note"}</strong>
          <div style={{ whiteSpace: "pre-wrap" }}>{displayCap}</div>
        </div>
      ) : null}

      {canConfirm ? (
        <div className="final-check-panel">
          <h2 style={{ marginTop: 0, fontSize: "1.05rem" }}>Confirm this practice</h2>
          <p className="subtle">
            The text area above is the full record for this practice. Edit if needed, then confirm. Numeric scores stay
            hidden until the final summary or export.
          </p>
          <label
            style={{ display: "flex", gap: "0.5rem", alignItems: "flex-start", cursor: "pointer", marginTop: "0.75rem" }}
          >
            <input type="checkbox" checked={ackConsolidated} onChange={(e) => setAckConsolidated(e.target.checked)} />
            <span>I confirm the full response above is what I want used for this practice.</span>
          </label>
          <div className="row" style={{ marginTop: "1rem" }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void onConfirm()}
              disabled={!ackConsolidated || !narrative.trim()}
            >
              Confirm &amp; continue
            </button>
          </div>
        </div>
      ) : null}

      {practiceState.user_confirmed ? null : (
        <section className="practice-action-bar" aria-label="Practice actions">
          <div className="practice-action-primary">
            <button type="button" className="btn btn-primary" onClick={() => void onReview()} disabled={reviewBusy}>
              {reviewBusy ? "Reviewing…" : "Review this response"}
            </button>
            <span className="subtle">
              Follow-ups used: {practiceState.follow_up_rounds_used} / {cap}
            </span>
          </div>
          <span className="action-divider" aria-hidden />
          <button type="button" className="btn-text" onClick={onOpenPartialExport}>
            Finish early / export partial
          </button>
          <span className="subtle" style={{ fontSize: "0.82rem", maxWidth: "28ch" }}>
            Next practice: use the progress list when this one is confirmed.
          </span>
        </section>
      )}
    </div>
  );
}
