import pytest
from fastapi import FastAPI

from trialsync.config import Settings
from trialsync.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        DATABASE_URL="postgresql+psycopg://test:test@localhost:5432/test",
        environment="test",
        auth_secret="test-secret-that-is-at-least-32-characters-long",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
