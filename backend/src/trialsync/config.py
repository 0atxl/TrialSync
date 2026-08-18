from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        env_prefix="TRIALSYNC_",
        extra="ignore",
    )

    app_name: str = "TrialSync API"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    auth_secret: SecretStr = Field(default=SecretStr(""))
    access_token_minutes: int = Field(default=480, ge=5, le=1440)
    cors_origins: list[str] = Field(default_factory=list)
    screening_batch_max_patients: int = Field(default=50, ge=1, le=100)
    screening_batch_max_trials: int = Field(default=10, ge=1, le=50)
    screening_batch_max_pairs: int = Field(default=500, ge=1, le=1000)
    groq_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-20b", min_length=1, max_length=120)
    extraction_provider: Literal["auto", "rule_based", "groq", "disabled"] = "groq"
    screening_chat_provider: Literal["auto", "canonical", "groq", "disabled"] = "auto"
    provider_timeout_seconds: float = Field(default=12.0, ge=1.0, le=30.0)
    provider_max_retries: int = Field(default=1, ge=0, le=2)
    provider_max_input_chars: int = Field(default=100_000, ge=1_000, le=200_000)
    screening_chat_message_max_chars: int = Field(default=1_000, ge=100, le=4_000)
    screening_chat_max_messages: int = Field(default=10, ge=2, le=20, multiple_of=2)
    screening_chat_max_answer_chars: int = Field(default=2_000, ge=200, le=4_000)
    terminology_suggestions_enabled: bool = True
    terminology_timeout_seconds: float = Field(default=5.0, ge=1.0, le=10.0)
    terminology_max_results: int = Field(default=5, ge=1, le=10)
    loinc_username: SecretStr = Field(default=SecretStr(""))
    loinc_password: SecretStr = Field(default=SecretStr(""))
    research_cohort_artifact_root: Path = Path("artifacts/r6")
    research_cohort_active_run: str | None = Field(
        default=None,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        url = value.get_secret_value()
        if not url.startswith(("postgresql+psycopg://", "postgresql://")):
            raise ValueError("DATABASE_URL must use PostgreSQL with the psycopg driver")
        return value

    def require_auth_secret(self) -> str:
        secret = self.auth_secret.get_secret_value()
        if len(secret) < 32:
            raise ValueError("TRIALSYNC_AUTH_SECRET must contain at least 32 characters")
        return secret


@lru_cache
def get_settings() -> Settings:
    return Settings()
