"""Persist OpenAI review outcomes into PracticeResponse (reduces complexity in the router)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.assessment_loader import AssessmentDefinition, PracticeDefinition, get_effective_thresholds
from app.models import PracticeResponse
from app.services.openai_review import AIReviewResult, confidence_plain


def _utc_timestamp_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def evidence_notes_json_for_row(parsed: AIReviewResult) -> str:
    try:
        return json.dumps(list(parsed.evidence_notes or []), ensure_ascii=False)
    except (TypeError, ValueError):
        return "[]"


def apply_review_to_row(
    row: PracticeResponse,
    parsed: AIReviewResult,
    definition: AssessmentDefinition,
    pdef: PracticeDefinition,
    *,
    at_cap: bool,
) -> dict[str, Any]:
    """Mutate row from parsed AI result; append review history. Returns keys for ReviewResultOut."""
    low_thr = float(definition.defaults.get("low_confidence_flag_threshold", 0.55))
    _, cap = get_effective_thresholds(definition, pdef)
    suff_plain = confidence_plain(parsed.confidence)
    follow_ups = list(parsed.follow_up_questions or [])

    if parsed.is_sufficient and parsed.internal_score is not None:
        row.internal_score = f"{float(parsed.internal_score):.3f}"
        row.sufficiency_confidence = f"{float(parsed.confidence):.4f}"
        row.rationale_summary = parsed.score_rationale_summary or parsed.rationale
        row.insufficient_after_cap = False
        row.low_confidence_flag = float(parsed.confidence) < low_thr
        row.evidence_notes_json = evidence_notes_json_for_row(parsed)
        confirmation = (
            "Your response looks sufficient to score. Confirm below when you are ready to move on "
            "(your numeric score stays hidden until export)."
        )
        entry = {
            "at": _utc_timestamp_z(),
            "is_sufficient": True,
            "force_complete": False,
            "allow_confirm": True,
            "sufficiency_plain": suff_plain,
            "follow_up_questions": [],
            "rationale_short": (parsed.rationale or "")[:800],
            "confirmation_message": confirmation,
            "cap_warning": None,
        }
    elif parsed.force_complete or (at_cap and not parsed.is_sufficient):
        score = parsed.provisional_internal_score or parsed.internal_score or 2.5
        row.internal_score = f"{float(score):.3f}"
        row.sufficiency_confidence = f"{float(parsed.confidence):.4f}"
        row.rationale_summary = parsed.provisional_score_rationale_summary or parsed.rationale
        row.insufficient_after_cap = True
        row.low_confidence_flag = True
        row.evidence_notes_json = evidence_notes_json_for_row(parsed)
        confirmation = (
            "The follow-up limit was reached. You can still continue; the export will flag this practice as "
            "lower-confidence or capped."
        )
        entry = {
            "at": _utc_timestamp_z(),
            "is_sufficient": False,
            "force_complete": True,
            "allow_confirm": True,
            "sufficiency_plain": suff_plain,
            "follow_up_questions": [],
            "rationale_short": (parsed.rationale or "")[:800],
            "confirmation_message": confirmation,
            "cap_warning": confirmation,
        }
    else:
        row.internal_score = None
        row.rationale_summary = None
        row.insufficient_after_cap = False
        row.low_confidence_flag = False
        row.evidence_notes_json = evidence_notes_json_for_row(parsed)
        if follow_ups:
            try:
                transcript = json.loads(row.follow_up_transcript_json or "[]")
            except json.JSONDecodeError:
                transcript = []
            transcript.append(
                {
                    "kind": "ai_followups",
                    "round": row.follow_up_rounds_used + 1,
                    "questions": follow_ups,
                }
            )
            row.follow_up_transcript_json = json.dumps(transcript, ensure_ascii=False)
        entry = {
            "at": _utc_timestamp_z(),
            "is_sufficient": False,
            "force_complete": False,
            "allow_confirm": False,
            "sufficiency_plain": suff_plain,
            "follow_up_questions": follow_ups,
            "rationale_short": (parsed.rationale or "")[:800],
            "confirmation_message": None,
            "cap_warning": None,
        }

    try:
        hist = json.loads(row.review_history_json or "[]")
    except json.JSONDecodeError:
        hist = []
    hist.append(entry)
    row.review_history_json = json.dumps(hist, ensure_ascii=False)

    return {
        "entry": entry,
        "suff_plain": suff_plain,
        "follow_ups": follow_ups,
        "cap": cap,
    }
