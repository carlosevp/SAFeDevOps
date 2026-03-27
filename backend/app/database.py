from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.settings import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_schema_compat()


def _ensure_schema_compat() -> None:
    inspector = inspect(engine)
    if "assessment_sessions" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("assessment_sessions")}
    with engine.begin() as conn:
        if "ai_review_consent" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE assessment_sessions "
                    "ADD COLUMN ai_review_consent BOOLEAN NOT NULL DEFAULT false"
                )
            )
        if "data_restrictions_ack" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE assessment_sessions "
                    "ADD COLUMN data_restrictions_ack BOOLEAN NOT NULL DEFAULT false"
                )
            )
        if "ai_consent_version" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE assessment_sessions "
                    "ADD COLUMN ai_consent_version VARCHAR(64) NOT NULL DEFAULT '2026-03-privacy-guard-v1'"
                )
            )
        if "ai_consented_at" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE assessment_sessions "
                    "ADD COLUMN ai_consented_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
                )
            )
