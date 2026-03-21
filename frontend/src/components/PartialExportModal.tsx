import { useEffect } from "react";
import { createPortal } from "react-dom";

type Props = {
  open: boolean;
  confirmedCount: number;
  total: number;
  onCancel: () => void;
  onConfirm: () => void;
  busy: boolean;
};

/**
 * Classic fixed overlay (no <dialog>): native dialog + ::backdrop are inconsistent across
 * browsers when combined with SPA layout; this pattern always dims and stacks above the app.
 */
export function PartialExportModal({ open, confirmedCount, total, onCancel, onConfirm, busy }: Readonly<Props>) {
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !busy) onCancel();
    }
    globalThis.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      globalThis.removeEventListener("keydown", onKey);
    };
  }, [open, busy, onCancel]);

  if (!open) return null;

  return createPortal(
    <div className="partial-export-overlay">
      <button
        type="button"
        className="partial-export-scrim-btn"
        aria-label="Close dialog"
        onClick={() => {
          if (!busy) onCancel();
        }}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="partial-export-title"
        className="modal-dialog card partial-export-panel"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <h2 id="partial-export-title" className="modal-title">
          Finish early and export?
        </h2>
        <p className="subtle" style={{ marginTop: 0 }}>
          Some practices are still incomplete. You can still download an export package now. Incomplete practices will be
          clearly marked in the PDF and JSON; no scores are invented for practices you have not confirmed.
        </p>
        <ul className="modal-list subtle">
          <li>
            <strong>{confirmedCount}</strong> of <strong>{total}</strong> practices confirmed so far.
          </li>
          <li>
            The ZIP includes <code>report.pdf</code> and <code>results.json</code> with partial-completion metadata.
          </li>
          <li>You can keep working in this session after exporting if you prefer—this does not end the session.</li>
        </ul>
        <div className="modal-actions row">
          <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="btn btn-secondary" onClick={onConfirm} disabled={busy}>
            {busy ? "Preparing ZIP…" : "Export partial package"}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
