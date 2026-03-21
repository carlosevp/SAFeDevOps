"""Build results.json payloads for full and partial assessment exports."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.assessment_loader import AssessmentDefinition
from app.models import AssessmentSession, PracticeResponse


def _mean(nums: list[float]) -> float | None:
    if not nums:
        return None
    return round(sum(nums) / len(nums), 3)


def _practice_row_status(row: PracticeResponse | None, practice_confirmed: bool) -> str:
    if practice_confirmed:
        return "completed"
    if not row:
        return "not_started"
    if (row.narrative or "").strip():
        return "in_progress"
    try:
        hist = json.loads(row.review_history_json or "[]")
    except json.JSONDecodeError:
        hist = []
    if hist:
        return "in_progress"
    try:
        files = json.loads(row.files_json or "[]")
    except json.JSONDecodeError:
        files = []
    if files:
        return "in_progress"
    return "not_started"


def practice_progress_detail(row: PracticeResponse | None, practice_confirmed: bool) -> str:
    """Nav/export-aligned status: not_started | in_progress | completed."""
    return _practice_row_status(row, practice_confirmed)


def build_results_payload(
    definition: AssessmentDefinition,
    session: AssessmentSession,
    responses: dict[str, PracticeResponse],
    *,
    partial_export: bool = False,
) -> dict[str, Any]:
    keys = [p.key for p in definition.practices]
    total = len(keys)
    confirmed_count = sum(1 for k in keys if responses.get(k) and responses[k].user_confirmed)
    completion_pct = round(100.0 * confirmed_count / total, 2) if total else 0.0

    practice_scores: list[dict[str, Any]] = []
    domain_scores: dict[str, list[float]] = defaultdict(list)
    all_scores: list[float] = []

    domain_confs: dict[str, list[float]] = defaultdict(list)
    domain_completed: dict[str, int] = defaultdict(int)
    domain_incomplete: dict[str, int] = defaultdict(int)

    for pdef in definition.practices:
        row = responses.get(pdef.key)
        practice_confirmed = bool(row and row.user_confirmed)
        row_status = _practice_row_status(row, practice_confirmed)

        score_val: float | None = None
        conf_val: float | None = None
        rationale = None
        evidence_flag = False
        fu_count = 0
        insuff = False
        low_conf = False

        if practice_confirmed and row:
            if row.internal_score:
                try:
                    score_val = float(row.internal_score)
                except ValueError:
                    score_val = None
            if row.sufficiency_confidence:
                try:
                    conf_val = float(row.sufficiency_confidence)
                except ValueError:
                    conf_val = None
            rationale = row.rationale_summary
            try:
                meta = json.loads(row.files_json or "[]")
            except json.JSONDecodeError:
                meta = []
            evidence_flag = len(meta) > 0
            fu_count = int(row.follow_up_rounds_used or 0)
            insuff = bool(row.insufficient_after_cap)
            low_conf = bool(row.low_confidence_flag)
            if score_val is not None:
                domain_scores[pdef.pipeline_area_name].append(score_val)
                all_scores.append(score_val)
            if conf_val is not None:
                domain_confs[pdef.pipeline_area_name].append(conf_val)
            domain_completed[pdef.pipeline_area_name] += 1
        else:
            if row:
                try:
                    meta = json.loads(row.files_json or "[]")
                except json.JSONDecodeError:
                    meta = []
                evidence_flag = len(meta) > 0
                fu_count = int(row.follow_up_rounds_used or 0)
            domain_incomplete[pdef.pipeline_area_name] += 1

        practice_scores.append(
            {
                "practice_key": pdef.key,
                "practice_name": pdef.name,
                "pipeline_area": pdef.pipeline_area_name,
                "pipeline_area_key": pdef.pipeline_area_key,
                "practice_completion_status": "completed" if practice_confirmed else "incomplete",
                "progress_detail": row_status,
                "score": score_val,
                "sufficiency_confidence": conf_val,
                "rationale_summary": rationale,
                "evidence_files_present": evidence_flag,
                "follow_up_rounds_used": fu_count,
                "insufficient_after_cap": insuff if practice_confirmed else False,
                "low_confidence_flag": low_conf if practice_confirmed else False,
            }
        )

    rollup: dict[str, Any] = {}
    all_areas = {p.pipeline_area_name for p in definition.practices}
    for area in sorted(all_areas):
        scored = domain_scores.get(area, [])
        confs = domain_confs.get(area, [])
        rollup[area] = {
            "average_score": _mean(scored) if scored else None,
            "average_confidence": _mean(confs) if confs else None,
            "practices_scored_count": len(scored),
            "practices_completed_confirmed": domain_completed.get(area, 0),
            "practices_incomplete_or_unconfirmed": domain_incomplete.get(area, 0),
            "practice_count": domain_completed.get(area, 0) + domain_incomplete.get(area, 0),
        }

    overall = _mean(all_scores) if all_scores else None
    overall_conf = _mean(
        [p["sufficiency_confidence"] for p in practice_scores if p["sufficiency_confidence"] is not None]
    )

    complete_mode = "complete" if (not partial_export and confirmed_count == total and total > 0) else "partial"
    is_partial = partial_export or confirmed_count < total

    export_summary = (
        f"Full completion export: {confirmed_count}/{total} practices confirmed."
        if not is_partial
        else (
            f"Partial / early completion export: {confirmed_count}/{total} practices confirmed "
            f"({completion_pct}%); incomplete practices have no score and are marked in this file."
        )
    )

    return {
        "identity": {
            "name": session.name,
            "email": session.email,
            "team_name": session.team_name,
        },
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "assessment_version": definition.assessment_version,
        "session_id": session.id,
        "completion_mode": complete_mode,
        "partial_export": bool(is_partial),
        "completion_percentage": completion_pct,
        "practices_confirmed_count": confirmed_count,
        "practices_total": total,
        "export_summary": export_summary,
        "practices": practice_scores,
        "domain_rollups": rollup,
        "overall_score": overall,
        "overall_confidence": overall_conf,
        "overall_partial": bool(is_partial),
    }
