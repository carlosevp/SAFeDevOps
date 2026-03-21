import { useEffect, useRef } from "react";

type Props = {
  open: boolean;
  confirmedCount: number;
  total: number;
  onCancel: () => void;
  onConfirm: () => void;
  busy: boolean;
};

export function PartialExportModal({ open, confirmedCount, total, onCancel, onConfirm, busy }: Readonly<Props>) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open) {
      if (!el.open) el.showModal();
    } else {
      el.close();
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !busy) onCancel();
    }
    globalThis.addEventListener("keydown", onKey);
    return () => globalThis.removeEventListener("keydown", onKey);
  }, [open, busy, onCancel]);

  return (
    <dialog
      ref={dialogRef}
      className="partial-export-dialog"
      aria-labelledby="partial-export-title"
      onCancel={(e) => {
        if (busy) e.preventDefault();
        else onCancel();
      }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy) onCancel();
      }}
    >
      <div className="modal-dialog card" onMouseDown={(e) => e.stopPropagation()}>
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
    </dialog>
  );
}
