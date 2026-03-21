from __future__ import annotations

import base64
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any

from openai import APIError, APITimeoutError, OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.assessment_loader import AssessmentDefinition, PracticeDefinition, get_effective_thresholds
from app.narrative_merge import transcript_for_ai_prompt
from app.settings import settings

logger = logging.getLogger(__name__)


class AIReviewResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    is_sufficient: bool
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""
    follow_up_questions: list[str] = Field(default_factory=list)
    evidence_notes: list[str] = Field(default_factory=list)
    internal_score: float | None = Field(default=None, ge=1.0, le=5.0)
    score_rationale_summary: str | None = None
    force_complete: bool = False
    provisional_internal_score: float | None = Field(default=None, ge=1.0, le=5.0)
    provisional_score_rationale_summary: str | None = None

    @field_validator("follow_up_questions", mode="before")
    @classmethod
    def _strip_questions(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v.strip()] if v.strip() else []
        return [str(x).strip() for x in v if str(x).strip()]


def confidence_plain(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.55:
        return "medium"
    return "low"


def _read_pdf_excerpt(path: Path, max_chars: int = 14000) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages[:12]:
            t = page.extract_text() or ""
            if t.strip():
                parts.append(t.strip())
        text = "\n\n".join(parts)
        if len(text) > max_chars:
            return text[:max_chars] + "\n\n[truncated]"
        return text or ""
    except Exception as e:  # noqa: BLE001
        logger.warning("pdf_extract_failed path=%s err=%s", path.name, type(e).__name__)
        return ""


def _image_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    if mime in ("image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"):
        return "image/jpeg" if mime == "image/jpg" else mime
    ext = path.suffix.lower()
    if ext == ".png":
        return "image/png"
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    if ext == ".gif":
        return "image/gif"
    return "application/octet-stream"


def build_multimodal_user_parts(
    text_block: str,
    file_paths: list[Path],
) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [{"type": "text", "text": text_block}]
    for p in file_paths:
        if not p.is_file():
            continue
        suffix = p.suffix.lower()
        if suffix == ".pdf":
            excerpt = _read_pdf_excerpt(p)
            label = f"[Attached PDF: {p.name}]\n"
            if excerpt.strip():
                parts.append({"type": "text", "text": label + "Extracted text (may be incomplete):\n" + excerpt})
            else:
                parts.append(
                    {
                        "type": "text",
                        "text": label
                        + "No extractable text was found; use the narrative and filename only.",
                    }
                )
            continue
        mime = _image_mime(p)
        if not mime.startswith("image/"):
            parts.append({"type": "text", "text": f"[Skipped unsupported file type: {p.name}]"})
            continue
        data = base64.standard_b64encode(p.read_bytes()).decode("ascii")
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{data}"},
            }
        )
    return parts


class OpenAIReviewService:
    """Abstracted OpenAI review: text-only or multimodal (images + PDF text excerpts)."""

    def __init__(self) -> None:
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        if self._client is None:
            self._client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
        return self._client

    def review_practice(
        self,
        definition: AssessmentDefinition,
        practice: PracticeDefinition,
        narrative: str,
        follow_up_transcript: list[dict[str, Any]],
        follow_up_rounds_used: int,
        evidence_file_paths: list[Path],
    ) -> AIReviewResult:
        conf_thr, cap = get_effective_thresholds(definition, practice)
        rubric_summary = definition.rubric_summary_text(practice.ai_review.rubric_ref)
        for_prompt = transcript_for_ai_prompt(follow_up_transcript)
        transcript_text = json.dumps(for_prompt, ensure_ascii=False, indent=2)

        tmpl = definition.review_prompts.get("sufficiency_user_template", "")
        user_text = tmpl.format(
            pipeline_area=practice.pipeline_area_name,
            practice_name=practice.name,
            practice_key=practice.key,
            what_it_evaluates=practice.what_it_evaluates,
            user_prompt=practice.user_prompt,
            narrative=narrative or "(empty)",
            follow_up_transcript=transcript_text if transcript_text != "[]" else "(none)",
            rubric_summary=rubric_summary,
            sufficiency_confidence_threshold=conf_thr,
            follow_up_rounds_used=follow_up_rounds_used,
            follow_up_cap=cap,
        )

        system = definition.review_prompts.get("sufficiency_system", "You are a careful reviewer.")

        schema_hint = (
            "Return JSON with keys: "
            "is_sufficient (boolean), confidence (number 0-1), rationale (string), "
            "follow_up_questions (array of strings), evidence_notes (array of strings), "
            "internal_score (number or null), score_rationale_summary (string or null), "
            "force_complete (boolean), provisional_internal_score (number or null), "
            "provisional_score_rationale_summary (string or null). "
            "Use evidence_notes for extracted_evidence-style bullets."
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system + "\n\n" + schema_hint},
        ]

        parts = build_multimodal_user_parts(user_text, evidence_file_paths)
        if len(parts) == 1:
            messages.append({"role": "user", "content": user_text})
        else:
            messages.append({"role": "user", "content": parts})

        client = self._get_client()
        try:
            resp = client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except APITimeoutError as e:
            logger.warning("openai_timeout model=%s", settings.openai_model)
            raise RuntimeError("OpenAI request timed out. Try again with fewer files or shorter text.") from e
        except APIError as e:
            logger.warning("openai_api_error type=%s", type(e).__name__)
            raise RuntimeError("OpenAI API error during review.") from e

        raw = (resp.choices[0].message.content or "").strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning("openai_json_parse_failed")
            raise RuntimeError("Could not parse AI response as JSON.") from e

        if "extracted_evidence_notes" in data and "evidence_notes" not in data:
            data["evidence_notes"] = data.pop("extracted_evidence_notes")

        try:
            parsed = AIReviewResult.model_validate(data)
        except ValidationError as e:
            logger.warning("openai_schema_validate_failed")
            raise RuntimeError("AI response failed validation.") from e

        if parsed.is_sufficient and parsed.confidence < conf_thr:
            parsed.is_sufficient = False
            parsed.rationale = (
                parsed.rationale
                + " (Confidence was below the sufficiency threshold; more detail is needed.)"
            ).strip()

        at_cap = follow_up_rounds_used >= cap
        if at_cap and not parsed.is_sufficient:
            parsed.force_complete = True
            if parsed.provisional_internal_score is None and parsed.internal_score is not None:
                parsed.provisional_internal_score = parsed.internal_score
            if parsed.provisional_score_rationale_summary is None and parsed.score_rationale_summary:
                parsed.provisional_score_rationale_summary = parsed.score_rationale_summary
            parsed.follow_up_questions = []
        elif not parsed.is_sufficient and not at_cap:
            if not parsed.follow_up_questions:
                fallback = definition.defaults.get("follow_up_fallback_question")
                parsed.follow_up_questions = [
                    str(fallback).strip()
                    if fallback
                    else "Please add more specific detail so the assessment can be scored confidently."
                ]

        return parsed


openai_review_service = OpenAIReviewService()
