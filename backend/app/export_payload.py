"""Build results.json payloads for full and partial assessment exports."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.assessment_loader import AssessmentDefinition, PracticeDefinition
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


def _parse_float_field(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _files_meta_count(row: PracticeResponse) -> tuple[list[Any], bool]:
    try:
        meta = json.loads(row.files_json or "[]")
    except json.JSONDecodeError:
        meta = []
    return meta, len(meta) > 0


def _metrics_confirmed(row: PracticeResponse) -> dict[str, Any]:
    score_val = _parse_float_field(row.internal_score)
    conf_val = _parse_float_field(row.sufficiency_confidence)
    _, evidence_flag = _files_meta_count(row)
    fu_count = int(row.follow_up_rounds_used or 0)
    return {
        "score_val": score_val,
        "conf_val": conf_val,
        "rationale": row.rationale_summary,
        "evidence_flag": evidence_flag,
        "fu_count": fu_count,
        "insuff": bool(row.insufficient_after_cap),
        "low_conf": bool(row.low_confidence_flag),
    }


def _metrics_incomplete(row: PracticeResponse) -> dict[str, Any]:
    _, evidence_flag = _files_meta_count(row)
    fu_count = int(row.follow_up_rounds_used or 0)
    return {
        "score_val": None,
        "conf_val": None,
        "rationale": None,
        "evidence_flag": evidence_flag,
        "fu_count": fu_count,
        "insuff": False,
        "low_conf": False,
    }


def _one_practice_score_entry(
    pdef: PracticeDefinition,
    row: PracticeResponse | None,
    practice_confirmed: bool,
    row_status: str,
) -> dict[str, Any]:
    if practice_confirmed and row:
        m = _metrics_confirmed(row)
    elif row:
        m = _metrics_incomplete(row)
    else:
        m = {
            "score_val": None,
            "conf_val": None,
            "rationale": None,
            "evidence_flag": False,
            "fu_count": 0,
            "insuff": False,
            "low_conf": False,
        }

    return {
        "practice_key": pdef.key,
        "practice_name": pdef.name,
        "pipeline_area": pdef.pipeline_area_name,
        "pipeline_area_key": pdef.pipeline_area_key,
        "practice_completion_status": "completed" if practice_confirmed else "incomplete",
        "progress_detail": row_status,
        "score": m["score_val"],
        "sufficiency_confidence": m["conf_val"],
        "rationale_summary": m["rationale"],
        "evidence_files_present": m["evidence_flag"],
        "follow_up_rounds_used": m["fu_count"],
        "insufficient_after_cap": m["insuff"] if practice_confirmed else False,
        "low_confidence_flag": m["low_conf"] if practice_confirmed else False,
    }


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
        practice_scores.append(_one_practice_score_entry(pdef, row, practice_confirmed, row_status))

        area = pdef.pipeline_area_name
        if practice_confirmed and row:
            m = _metrics_confirmed(row)
            if m["score_val"] is not None:
                domain_scores[area].append(m["score_val"])
                all_scores.append(m["score_val"])
            if m["conf_val"] is not None:
                domain_confs[area].append(m["conf_val"])
            domain_completed[area] += 1
        else:
            domain_incomplete[area] += 1

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
            "ai_review_consent": bool(session.ai_review_consent),
            "data_restrictions_ack": bool(session.data_restrictions_ack),
            "ai_consent_version": session.ai_consent_version,
            "ai_consented_at": session.ai_consented_at.isoformat(),
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
