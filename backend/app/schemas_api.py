from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class IdentityIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    team_name: str = Field(min_length=1, max_length=255)
    ai_review_consent: bool = Field(
        ...,
        description="User consent for AI-assisted review of assessment responses.",
    )


class SessionCreateIn(IdentityIn):
    pass


class SessionOut(BaseModel):
    id: int
    name: str
    email: str
    team_name: str
    ai_review_consent: bool
    assessment_version: str
    current_practice_index: int
    created_at: datetime

    class Config:
        from_attributes = True


class FileMetaOut(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int


class PracticeStateOut(BaseModel):
    practice_key: str
    narrative: str
    files: list[FileMetaOut]
    follow_up_transcript: list[dict[str, Any]]
    follow_up_rounds_used: int
    user_confirmed: bool
    progress_detail: str = Field(
        default="not_started",
        description="not_started | in_progress | completed (nav / export alignment)",
    )
    allow_confirm: bool = False
    review_status: str | None = None
    sufficiency_plain: str | None = None
    follow_up_questions: list[str] = Field(default_factory=list)
    confirmation_message: str | None = None
    cap_warning: str | None = None
    last_rationale_short: str | None = None


class AssessmentConfigOut(BaseModel):
    assessment_version: str
    defaults: dict[str, Any] = Field(default_factory=dict)
    practices: list[dict[str, Any]]
    show_evaluation_feedback: bool = True


class SessionFullOut(BaseModel):
    session: SessionOut
    config: AssessmentConfigOut
    practices_state: dict[str, PracticeStateOut]
    ordered_practice_keys: list[str]
    completed_count: int
    total_practices: int
    all_complete: bool


class SavePracticeIn(BaseModel):
    narrative: str = ""


class FollowUpAnswerIn(BaseModel):
    answers: list[str] = Field(default_factory=list)


class ReviewResultOut(BaseModel):
    ok: bool
    error: str | None = None
    is_sufficient: bool | None = None
    allow_confirm: bool = False
    sufficiency_plain: str | None = None
    follow_up_questions: list[str] = Field(default_factory=list)
    confirmation_message: str | None = None
    cap_warning: str | None = None
    follow_up_rounds_used: int = 0
    follow_up_cap: int = 3
    rationale_short: str | None = None


class ConfirmPracticeIn(BaseModel):
    acknowledge_consolidated_response: bool = False
    final_narrative: str | None = None


class PartialExportIn(BaseModel):
    confirm_partial: bool = False
