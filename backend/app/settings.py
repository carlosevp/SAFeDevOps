from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_timeout_seconds: float = 120.0

    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    upload_dir: Path = Path(__file__).resolve().parent.parent / "uploads"
    database_url: str = "sqlite:///./safedevops_pilot.db"

    assessment_yaml: str = "assessment.yaml"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # When true, API returns AI rationale and sufficiency-style messaging to the UI.
    # Omitted or false = gentler UX (follow-ups only, neutral confirmations). Set true in .env for pilot debugging.
    safedevops_debug_mode: bool = False

    # Non-empty = require shared password (signed HttpOnly cookie) for /api, /assets, /docs, and SPA public files.
    safedevops_access_password: str = ""

    @field_validator("safedevops_access_password", mode="before")
    @classmethod
    def strip_access_password(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
