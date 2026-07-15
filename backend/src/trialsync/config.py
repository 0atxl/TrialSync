from __future__ import annotations

from functools import lru_cache
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
    return Settings()  # type: ignore[call-arg]
