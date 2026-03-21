from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.assessment_loader import AssessmentDefinition, PracticeDefinition, get_effective_thresholds
from app.database import get_db
from app.deps import get_assessment_definition
from app.models import AssessmentSession, PracticeResponse
from app.narrative_merge import append_followup_text_to_narrative, merge_transcript_followups_into_narrative
from app.export_payload import build_results_payload, practice_progress_detail
from app.review_persist import apply_review_to_row
from app.schemas_api import (
    AssessmentConfigOut,
    ConfirmPracticeIn,
    FileMetaOut,
    FollowUpAnswerIn,
    PartialExportIn,
    PracticeStateOut,
    ReviewResultOut,
    SavePracticeIn,
    SessionCreateIn,
    SessionFullOut,
    SessionOut,
)
from app.services.export_builder import build_pdf_report, load_responses_map, write_export_zip
from app.services.openai_review import openai_review_service
from app.settings import settings

router = APIRouter(
    prefix="/api",
    tags=["assessment"],
    responses={
        400: {"description": "Bad request"},
        404: {"description": "Not found"},
        503: {"description": "Service unavailable"},
    },
)

DbSession = Annotated[Session, Depends(get_db)]
AssessmentDep = Annotated[AssessmentDefinition, Depends(get_assessment_definition)]
UploadFileDep = Annotated[UploadFile, File(...)]


def require_assessment_session(session_id: int, db: DbSession) -> AssessmentSession:
    """Load session from path or 404; keeps HTTPException on a Depends target (not a bare helper)."""
    row = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return row


SessionPathDep = Annotated[AssessmentSession, Depends(require_assessment_session)]

UNKNOWN_PRACTICE_DETAIL = "Unknown practice"

# OpenAPI: document HTTPException status codes per operation (Sonar / FastAPI convention).
HTTP_400 = {400: {"description": "Bad request"}}
HTTP_404 = {404: {"description": "Not found"}}
HTTP_503 = {503: {"description": "Service unavailable"}}
HTTP_400_404 = {**HTTP_400, **HTTP_404}
HTTP_400_404_503 = {**HTTP_400, **HTTP_404, **HTTP_503}

NEUTRAL_CONFIRM = "You can continue to the next practice when ready."
NEUTRAL_CAP = "You have reached the follow-up limit. You may still continue."

ALLOWED_UPLOAD_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def _safe_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    return base[:180] if base else "file"


def _get_or_create_practice(db: Session, session: AssessmentSession, key: str) -> PracticeResponse:
    row = (
        db.query(PracticeResponse)
        .filter(PracticeResponse.session_id == session.id, PracticeResponse.practice_key == key)
        .first()
    )
    if row:
        return row
    row = PracticeResponse(session_id=session.id, practice_key=key)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _ordered_keys(definition) -> list[str]:
    return [p.key for p in definition.practices]


def _practice_at_index(definition, index: int) -> PracticeDefinition | None:
    keys = _ordered_keys(definition)
    if index < 0 or index >= len(keys):
        return None
    return definition.practice_by_key(keys[index])


def _file_paths_for_practice(row: PracticeResponse) -> list[Path]:
    try:
        meta = json.loads(row.files_json or "[]")
    except json.JSONDecodeError:
        return []
    base = settings.upload_dir / str(row.session_id) / row.practice_key
    out: list[Path] = []
    for item in meta:
        rel = item.get("stored_name")
        if not rel:
            continue
        p = base / rel
        if p.is_file():
            out.append(p)
    return out


def _last_review(history: list[dict]) -> dict | None:
    if not history:
        return None
    return history[-1]


def _show_evaluation_feedback() -> bool:
    return bool(settings.safedevops_debug_mode)


def _redact_practice_state(state: PracticeStateOut) -> PracticeStateOut:
    if _show_evaluation_feedback():
        return state
    return state.model_copy(
        update={
            "sufficiency_plain": None,
            "last_rationale_short": None,
            "confirmation_message": NEUTRAL_CONFIRM if state.allow_confirm else None,
            "cap_warning": NEUTRAL_CAP if state.cap_warning else None,
        }
    )


def _redact_review_out(out: ReviewResultOut) -> ReviewResultOut:
    if _show_evaluation_feedback() or not out.ok:
        return out
    return out.model_copy(
        update={
            "sufficiency_plain": None,
            "rationale_short": None,
            "confirmation_message": NEUTRAL_CONFIRM if out.allow_confirm else None,
            "cap_warning": NEUTRAL_CAP if out.cap_warning else None,
        }
    )


def _build_practice_state_out(row: PracticeResponse | None, pdef: PracticeDefinition) -> PracticeStateOut:
    if not row:
        return PracticeStateOut(
            practice_key=pdef.key,
            narrative="",
            files=[],
            follow_up_transcript=[],
            follow_up_rounds_used=0,
            user_confirmed=False,
            progress_detail=practice_progress_detail(None, False),
        )
    try:
        files = json.loads(row.files_json or "[]")
    except json.JSONDecodeError:
        files = []
    try:
        transcript = json.loads(row.follow_up_transcript_json or "[]")
    except json.JSONDecodeError:
        transcript = []
    try:
        history = json.loads(row.review_history_json or "[]")
    except json.JSONDecodeError:
        history = []

    last = _last_review(history)
    review_status = None
    sufficiency_plain = None
    follow_ups: list[str] = []
    confirmation_message = None
    cap_warning = None
    rationale_short = None
    allow_confirm_flag = False
    if last:
        review_status = "sufficient" if last.get("is_sufficient") else "needs_detail"
        if last.get("force_complete"):
            review_status = "forced_complete"
        allow_confirm_flag = bool(last.get("allow_confirm"))
        sufficiency_plain = last.get("sufficiency_plain")
        follow_ups = list(last.get("follow_up_questions") or [])
        confirmation_message = last.get("confirmation_message")
        cap_warning = last.get("cap_warning")
        rationale_short = last.get("rationale_short")

    file_out = [
        FileMetaOut(
            id=str(f.get("id")),
            filename=str(f.get("filename", "")),
            content_type=str(f.get("content_type", "")),
            size_bytes=int(f.get("size_bytes", 0)),
        )
        for f in files
    ]

    return PracticeStateOut(
        practice_key=pdef.key,
        narrative=row.narrative or "",
        files=file_out,
        follow_up_transcript=transcript,
        follow_up_rounds_used=row.follow_up_rounds_used,
        user_confirmed=bool(row.user_confirmed),
        progress_detail=practice_progress_detail(row, bool(row.user_confirmed)),
        allow_confirm=allow_confirm_flag,
        review_status=review_status,
        sufficiency_plain=sufficiency_plain,
        follow_up_questions=follow_ups,
        confirmation_message=confirmation_message,
        cap_warning=cap_warning,
        last_rationale_short=rationale_short,
    )


def _session_full(db: Session, session: AssessmentSession, definition) -> SessionFullOut:
    keys = _ordered_keys(definition)
    rmap = load_responses_map(db, session.id)
    merged_any = False
    for row in rmap.values():
        if merge_transcript_followups_into_narrative(row):
            merged_any = True
    if merged_any:
        db.commit()
        rmap = load_responses_map(db, session.id)
    states = {
        k: _redact_practice_state(_build_practice_state_out(rmap.get(k), definition.practice_by_key(k)))
        for k in keys
    }
    completed = sum(1 for k in keys if rmap.get(k) and rmap[k].user_confirmed)
    all_complete = completed == len(keys) and len(keys) > 0

    cfg_practices: list[dict] = []
    for p in definition.practices:
        cfg_practices.append(
            {
                "key": p.key,
                "pipeline_area_key": p.pipeline_area_key,
                "pipeline_area_name": p.pipeline_area_name,
                "name": p.name,
                "what_it_evaluates": p.what_it_evaluates,
                "enterprise_examples": p.enterprise_examples,
                "user_prompt": p.user_prompt,
                "evidence_encouragement": p.evidence_encouragement,
            }
        )

    return SessionFullOut(
        session=SessionOut.model_validate(session),
        config=AssessmentConfigOut(
            assessment_version=definition.assessment_version,
            defaults=dict(definition.defaults),
            practices=cfg_practices,
            show_evaluation_feedback=_show_evaluation_feedback(),
        ),
        practices_state=states,
        ordered_practice_keys=keys,
        completed_count=completed,
        total_practices=len(keys),
        all_complete=all_complete,
    )


@router.post("/sessions", response_model=SessionFullOut)
def create_session(body: SessionCreateIn, db: DbSession, definition: AssessmentDep):
    s = AssessmentSession(
        name=body.name.strip(),
        email=str(body.email).strip(),
        team_name=body.team_name.strip(),
        assessment_version=definition.assessment_version,
        current_practice_index=0,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _session_full(db, s, definition)


@router.get("/sessions/{session_id}", response_model=SessionFullOut, responses=HTTP_404)
def get_session(session: SessionPathDep, db: DbSession, definition: AssessmentDep):
    return _session_full(db, session, definition)


@router.put(
    "/sessions/{session_id}/practice/{practice_key}/draft",
    response_model=SessionFullOut,
    responses=HTTP_404,
)
def save_draft(
    practice_key: str,
    body: SavePracticeIn,
    session: SessionPathDep,
    db: DbSession,
    definition: AssessmentDep,
):
    s = session
    pdef = definition.practice_by_key(practice_key)
    if not pdef:
        raise HTTPException(status_code=404, detail=UNKNOWN_PRACTICE_DETAIL)
    row = _get_or_create_practice(db, s, practice_key)
    row.narrative = body.narrative or ""
    db.commit()
    return _session_full(db, s, definition)


@router.post(
    "/sessions/{session_id}/practice/{practice_key}/files",
    response_model=SessionFullOut,
    responses=HTTP_400_404,
)
async def upload_file(
    practice_key: str,
    session: SessionPathDep,
    db: DbSession,
    definition: AssessmentDep,
    file: UploadFileDep,
):
    s = session
    pdef = definition.practice_by_key(practice_key)
    if not pdef:
        raise HTTPException(status_code=404, detail=UNKNOWN_PRACTICE_DETAIL)

    row = _get_or_create_practice(db, s, practice_key)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXT:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large")

    uid = str(uuid.uuid4())
    stored = f"{uid}_{_safe_filename(file.filename or 'upload')}"
    dest_dir = settings.upload_dir / str(s.id) / practice_key
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / stored
    dest_path.write_bytes(data)

    try:
        meta = json.loads(row.files_json or "[]")
    except json.JSONDecodeError:
        meta = []
    meta.append(
        {
            "id": uid,
            "filename": file.filename or stored,
            "stored_name": stored,
            "content_type": file.content_type or "application/octet-stream",
            "size_bytes": len(data),
        }
    )
    row.files_json = json.dumps(meta)
    db.commit()
    return _session_full(db, s, definition)


@router.delete(
    "/sessions/{session_id}/practice/{practice_key}/files/{file_id}",
    response_model=SessionFullOut,
    responses=HTTP_404,
)
def delete_file(
    practice_key: str,
    file_id: str,
    session: SessionPathDep,
    db: DbSession,
    definition: AssessmentDep,
):
    s = session
    row = _get_or_create_practice(db, s, practice_key)
    try:
        meta = json.loads(row.files_json or "[]")
    except json.JSONDecodeError:
        meta = []
    new_meta: list[dict] = []
    for item in meta:
        if str(item.get("id")) == file_id:
            dest_dir = settings.upload_dir / str(s.id) / practice_key
            p = dest_dir / str(item.get("stored_name", ""))
            if p.is_file():
                p.unlink()
            continue
        new_meta.append(item)
    row.files_json = json.dumps(new_meta)
    db.commit()
    return _session_full(db, s, definition)


def _persist_review_result(
    row: PracticeResponse,
    parsed,
    definition,
    pdef: PracticeDefinition,
    *,
    at_cap: bool,
) -> ReviewResultOut:
    ctx = apply_review_to_row(row, parsed, definition, pdef, at_cap=at_cap)
    entry = ctx["entry"]
    suff_plain = ctx["suff_plain"]
    follow_ups = ctx["follow_ups"]
    cap = ctx["cap"]
    return _redact_review_out(
        ReviewResultOut(
            ok=True,
            is_sufficient=bool(entry.get("is_sufficient")),
            allow_confirm=bool(entry.get("allow_confirm")),
            sufficiency_plain=suff_plain,
            follow_up_questions=list(entry.get("follow_up_questions") or follow_ups),
            confirmation_message=entry.get("confirmation_message"),
            cap_warning=entry.get("cap_warning"),
            follow_up_rounds_used=row.follow_up_rounds_used,
            follow_up_cap=cap,
            rationale_short=entry.get("rationale_short"),
        )
    )


@router.post(
    "/sessions/{session_id}/practice/{practice_key}/review",
    response_model=ReviewResultOut,
    responses=HTTP_400_404_503,
)
def run_review(
    practice_key: str,
    session: SessionPathDep,
    db: DbSession,
    definition: AssessmentDep,
):
    s = session
    pdef = definition.practice_by_key(practice_key)
    if not pdef:
        raise HTTPException(status_code=404, detail=UNKNOWN_PRACTICE_DETAIL)
    row = _get_or_create_practice(db, s, practice_key)
    if not (row.narrative or "").strip():
        raise HTTPException(status_code=400, detail="Add a response before reviewing.")

    _, cap = get_effective_thresholds(definition, pdef)
    at_cap = row.follow_up_rounds_used >= cap

    paths = _file_paths_for_practice(row)
    try:
        transcript = json.loads(row.follow_up_transcript_json or "[]")
    except json.JSONDecodeError:
        transcript = []

    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OpenAI is not configured (missing OPENAI_API_KEY).")

    try:
        parsed = openai_review_service.review_practice(
            definition,
            pdef,
            row.narrative or "",
            transcript,
            row.follow_up_rounds_used,
            paths,
        )
    except RuntimeError as e:
        return ReviewResultOut(ok=False, error=str(e))
    except Exception:
        logger.exception(
            "run_review_unexpected session_id=%s practice_key=%s",
            s.id,
            practice_key,
        )
        return ReviewResultOut(
            ok=False,
            error="Review failed unexpectedly (see server logs). Check OPENAI_API_KEY, OPENAI_MODEL, and network; then try again.",
        )

    try:
        out = _persist_review_result(row, parsed, definition, pdef, at_cap=at_cap)
        db.commit()
        return out
    except Exception:
        db.rollback()
        logger.exception(
            "run_review_persist_failed session_id=%s practice_key=%s",
            s.id,
            practice_key,
        )
        return ReviewResultOut(ok=False, error="Could not save review results. Try again.")


@router.post(
    "/sessions/{session_id}/practice/{practice_key}/followup",
    response_model=ReviewResultOut,
    responses=HTTP_400_404_503,
)
def submit_followup(
    practice_key: str,
    body: FollowUpAnswerIn,
    session: SessionPathDep,
    db: DbSession,
    definition: AssessmentDep,
):
    s = session
    pdef = definition.practice_by_key(practice_key)
    if not pdef:
        raise HTTPException(status_code=404, detail=UNKNOWN_PRACTICE_DETAIL)
    row = _get_or_create_practice(db, s, practice_key)

    _, cap = get_effective_thresholds(definition, pdef)
    if row.follow_up_rounds_used >= cap:
        raise HTTPException(status_code=400, detail="Follow-up cap reached for this practice.")

    text = "\n\n".join([a.strip() for a in body.answers if a and a.strip()])
    if not text.strip():
        raise HTTPException(status_code=400, detail="Follow-up answers are empty.")

    try:
        transcript = json.loads(row.follow_up_transcript_json or "[]")
    except json.JSONDecodeError:
        transcript = []

    rnd = row.follow_up_rounds_used + 1
    transcript.append({"kind": "user_followup_response", "round": rnd, "text": text})
    row.follow_up_transcript_json = json.dumps(transcript, ensure_ascii=False)
    row.follow_up_rounds_used = rnd
    row.narrative = append_followup_text_to_narrative(row.narrative, text)
    db.commit()

    at_cap = row.follow_up_rounds_used >= cap
    paths = _file_paths_for_practice(row)

    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OpenAI is not configured (missing OPENAI_API_KEY).")

    try:
        parsed = openai_review_service.review_practice(
            definition,
            pdef,
            row.narrative or "",
            transcript,
            row.follow_up_rounds_used,
            paths,
        )
    except RuntimeError as e:
        return ReviewResultOut(ok=False, error=str(e))
    except Exception:
        logger.exception(
            "submit_followup_review_unexpected session_id=%s practice_key=%s",
            s.id,
            practice_key,
        )
        return ReviewResultOut(
            ok=False,
            error="Follow-up review failed unexpectedly (see server logs). Check OPENAI_API_KEY, OPENAI_MODEL, and network; then try again.",
        )

    try:
        out = _persist_review_result(row, parsed, definition, pdef, at_cap=at_cap)
        db.commit()
        return out
    except Exception:
        db.rollback()
        logger.exception(
            "submit_followup_persist_failed session_id=%s practice_key=%s",
            s.id,
            practice_key,
        )
        return ReviewResultOut(ok=False, error="Could not save follow-up review. Try again.")


@router.post(
    "/sessions/{session_id}/practice/{practice_key}/confirm",
    response_model=SessionFullOut,
    responses=HTTP_400_404,
)
def confirm_practice(
    practice_key: str,
    body: ConfirmPracticeIn,
    session: SessionPathDep,
    db: DbSession,
    definition: AssessmentDep,
):
    s = session
    pdef = definition.practice_by_key(practice_key)
    if not pdef:
        raise HTTPException(status_code=404, detail=UNKNOWN_PRACTICE_DETAIL)
    row = _get_or_create_practice(db, s, practice_key)

    try:
        hist = json.loads(row.review_history_json or "[]")
    except json.JSONDecodeError:
        hist = []
    last = _last_review(hist)
    if not last:
        raise HTTPException(status_code=400, detail="Run a review before confirming.")
    if not last.get("allow_confirm"):
        raise HTTPException(status_code=400, detail="Resolve follow-ups or reach the follow-up cap before confirming.")
    if row.internal_score is None:
        raise HTTPException(status_code=400, detail="No score available yet; run review again.")
    if not body.acknowledge_consolidated_response:
        raise HTTPException(
            status_code=400,
            detail="Confirm the checkbox: your full response (including follow-ups) is what you want assessed.",
        )

    if body.final_narrative is not None:
        row.narrative = body.final_narrative

    row.user_confirmed = True
    keys = _ordered_keys(definition)
    rmap = load_responses_map(db, s.id)
    next_idx = None
    for j, k in enumerate(keys):
        r = rmap.get(k)
        if not r or not r.user_confirmed:
            next_idx = j
            break
    if next_idx is None:
        next_idx = max(len(keys) - 1, 0)
    s.current_practice_index = next_idx

    db.commit()
    return _session_full(db, s, definition)


@router.post(
    "/sessions/{session_id}/navigate/{index}",
    response_model=SessionFullOut,
    responses=HTTP_400_404,
)
def navigate(index: int, session: SessionPathDep, db: DbSession, definition: AssessmentDep):
    s = session
    keys = _ordered_keys(definition)
    if index < 0 or index >= len(keys):
        raise HTTPException(status_code=400, detail="Invalid index")
    s.current_practice_index = index
    db.commit()
    return _session_full(db, s, definition)


@router.get("/sessions/{session_id}/summary-json", responses=HTTP_400_404)
def summary_json(
    session: SessionPathDep,
    db: DbSession,
    definition: AssessmentDep,
    allow_incomplete: bool = False,
):
    s = session
    keys = _ordered_keys(definition)
    rmap = load_responses_map(db, s.id)
    if not allow_incomplete:
        for k in keys:
            r = rmap.get(k)
            if not r or not r.user_confirmed:
                raise HTTPException(status_code=400, detail="Assessment not complete yet.")
        return build_results_payload(definition, s, rmap, partial_export=False)
    confirmed = sum(1 for k in keys if rmap.get(k) and rmap[k].user_confirmed)
    partial_flag = bool(keys) and confirmed < len(keys)
    return build_results_payload(definition, s, rmap, partial_export=partial_flag)


def _commit_export_zip(
    db: Session,
    session: AssessmentSession,
    definition,
    rmap: dict[str, PracticeResponse],
    *,
    partial_export: bool,
) -> FileResponse:
    results = build_results_payload(definition, session, rmap, partial_export=partial_export)
    session.export_payload_json = json.dumps(results, ensure_ascii=False)
    pdf_bytes = build_pdf_report(definition, session, rmap, results)
    zip_path = write_export_zip(session.id, pdf_bytes, results)
    db.commit()
    return FileResponse(
        path=str(zip_path),
        filename=zip_path.name,
        media_type="application/zip",
    )


@router.post("/sessions/{session_id}/export", responses=HTTP_400_404)
def export_zip(session: SessionPathDep, db: DbSession, definition: AssessmentDep):
    s = session
    keys = _ordered_keys(definition)
    rmap = load_responses_map(db, s.id)
    for k in keys:
        r = rmap.get(k)
        if not r or not r.user_confirmed:
            raise HTTPException(status_code=400, detail="Complete and confirm all practices before export.")
    return _commit_export_zip(db, s, definition, rmap, partial_export=False)


@router.post("/sessions/{session_id}/export-partial", responses=HTTP_400_404)
def export_partial_zip(
    body: PartialExportIn,
    session: SessionPathDep,
    db: DbSession,
    definition: AssessmentDep,
):
    if not body.confirm_partial:
        raise HTTPException(
            status_code=400,
            detail="Confirm partial export: set confirm_partial to true in the request body.",
        )
    s = session
    keys = _ordered_keys(definition)
    rmap = load_responses_map(db, s.id)
    confirmed = sum(1 for k in keys if rmap.get(k) and rmap[k].user_confirmed)
    total = len(keys)
    partial_flag = total == 0 or confirmed < total
    return _commit_export_zip(db, s, definition, rmap, partial_export=partial_flag)


@router.get("/health")
def health():
    return {"ok": True}
