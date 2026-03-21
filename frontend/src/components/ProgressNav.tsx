import { useMemo } from "react";
import type { PracticeConfig, PracticeState } from "../types";

type Props = {
  readonly practices: PracticeConfig[];
  readonly orderedKeys: string[];
  readonly stateByKey: Record<string, PracticeState>;
  readonly currentIndex: number;
  readonly onSelect: (index: number) => void;
};

function needsFollowUp(st: PracticeState | undefined, done: boolean): boolean {
  if (!st || done) return false;
  if (st.follow_up_questions?.length) return true;
  return st.review_status === "needs_detail" && !st.allow_confirm;
}

function statusIcon(current: boolean, done: boolean, needsFu: boolean, inProgress: boolean): string {
  if (done) return "✓";
  if (needsFu) return "!";
  if (current) return "●";
  if (inProgress) return "◐";
  return "○";
}

function stepSubtitle(done: boolean, needsFu: boolean, inProg: boolean): string {
  if (done) return "Completed";
  if (needsFu) return "Needs follow-up";
  if (inProg) return "In progress";
  return "Not started";
}

export function ProgressNav({ practices, orderedKeys, stateByKey, currentIndex, onSelect }: Readonly<Props>) {
  const confirmed = orderedKeys.filter((k) => stateByKey[k]?.user_confirmed).length;
  const total = orderedKeys.length;
  const pct = total ? Math.round((100 * confirmed) / total) : 0;

  const domainRows = useMemo(() => {
    const m = new Map<string, { total: number; done: number }>();
    for (const key of orderedKeys) {
      const cfg = practices.find((p) => p.key === key);
      if (!cfg) continue;
      const cur = m.get(cfg.pipeline_area_name) || { total: 0, done: 0 };
      cur.total += 1;
      if (stateByKey[key]?.user_confirmed) cur.done += 1;
      m.set(cfg.pipeline_area_name, cur);
    }
    return Array.from(m.entries());
  }, [orderedKeys, practices, stateByKey]);

  let lastArea = "";
  return (
    <nav className="card card-tight progress-rail" aria-label="Assessment progress">
      <h2 className="section-label" style={{ marginBottom: "0.35rem" }}>
        Progress
      </h2>
      <p className="progress-summary">
        <strong>
          {confirmed} / {total}
        </strong>{" "}
        practices confirmed ({pct}%). Use the list to jump between practices.
      </p>
      {domainRows.length ? (
        <ul className="progress-domains" aria-label="Progress by pipeline area">
          {domainRows.map(([name, { done, total: t }]) => (
            <li key={name}>
              {name}: {done}/{t}
            </li>
          ))}
        </ul>
      ) : null}
      <ul className="progress-list">
        {orderedKeys.map((key, idx) => {
          const cfg = practices.find((p) => p.key === key);
          if (!cfg) return null;
          const st = stateByKey[key];
          const done = !!st?.user_confirmed;
          const current = idx === currentIndex;
          const nf = needsFollowUp(st, done);
          const inProg = !done && st?.progress_detail === "in_progress" && !nf;
          const icon = statusIcon(current, done, nf, inProg);
          const areaHeader = cfg.pipeline_area_name !== lastArea;
          if (areaHeader) lastArea = cfg.pipeline_area_name;
          const itemClass = [
            "progress-item",
            current ? "current" : "",
            done ? "done" : "",
            nf ? "needs-followup" : "",
            inProg ? "in-progress" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <li key={key}>
              {areaHeader ? <div className="area-label">{cfg.pipeline_area_name}</div> : null}
              <button
                type="button"
                className={itemClass}
                onClick={() => onSelect(idx)}
                aria-current={current ? "step" : undefined}
              >
                <span className="progress-icon" aria-hidden>
                  {icon}
                </span>
                <span className="practice-title-wrap">
                  <span className="practice-title">{cfg.name}</span>
                  <span className="practice-title-meta">{stepSubtitle(done, nf, inProg)}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
