"""Merge follow-up answers into the main narrative for one consolidated self-assessment text."""

from __future__ import annotations

import json

from app.models import PracticeResponse

FOLLOWUP_BLOCK_SEPARATOR = "\n\n--- Additional detail (follow-up) ---\n\n"


def append_followup_text_to_narrative(narrative: str, followup_text: str) -> str:
    t = followup_text.strip()
    if not t:
        return narrative or ""
    base = (narrative or "").rstrip()
    addition = FOLLOWUP_BLOCK_SEPARATOR + t
    if addition in base:
        return base
    return base + addition


def merge_transcript_followups_into_narrative(row: PracticeResponse) -> bool:
    """Idempotent: append any transcript follow-up texts not already present in narrative."""
    try:
        tr = json.loads(row.follow_up_transcript_json or "[]")
    except json.JSONDecodeError:
        return False
    base = row.narrative or ""
    changed = False
    for item in tr:
        if item.get("kind") != "user_followup_response":
            continue
        t = (item.get("text") or "").strip()
        if not t:
            continue
        addition = FOLLOWUP_BLOCK_SEPARATOR + t
        if addition in base:
            continue
        base = base.rstrip() + addition
        changed = True
    if changed:
        row.narrative = base
    return changed


def transcript_for_ai_prompt(transcript: list[dict]) -> list[dict]:
    """Omit user_followup_response entries; those are merged into narrative for the model."""
    return [x for x in transcript if x.get("kind") != "user_followup_response"]
