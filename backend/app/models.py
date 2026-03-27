from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    team_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ai_review_consent: Mapped[bool] = mapped_column(default=False, nullable=False)
    assessment_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)
    current_practice_index: Mapped[int] = mapped_column(Integer, default=0)
    export_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    practices: Mapped[list["PracticeResponse"]] = relationship(
        "PracticeResponse",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="PracticeResponse.id",
    )


class PracticeResponse(Base):
    __tablename__ = "practice_responses"
    __table_args__ = (UniqueConstraint("session_id", "practice_key", name="uq_session_practice"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("assessment_sessions.id"), nullable=False)
    practice_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    narrative: Mapped[str] = mapped_column(Text, default="")
    follow_up_transcript_json: Mapped[str] = mapped_column(Text, default="[]")
    files_json: Mapped[str] = mapped_column(Text, default="[]")
    review_history_json: Mapped[str] = mapped_column(Text, default="[]")
    follow_up_rounds_used: Mapped[int] = mapped_column(Integer, default=0)
    user_confirmed: Mapped[bool] = mapped_column(default=False)
    internal_score: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sufficiency_confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rationale_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    insufficient_after_cap: Mapped[bool] = mapped_column(default=False)
    low_confidence_flag: Mapped[bool] = mapped_column(default=False)
    evidence_notes_json: Mapped[str] = mapped_column(Text, default="[]")

    session: Mapped["AssessmentSession"] = relationship("AssessmentSession", back_populates="practices")
