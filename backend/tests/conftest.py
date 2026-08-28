from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from trialsync.config import Settings
from trialsync.main import create_app


def resolve_test_database_url() -> str:
    env_test_url = (
        os.environ.get("TEST_DATABASE_URL")
        or os.environ.get("TRIALSYNC_TEST_DATABASE_URL")
    )
    if env_test_url and env_test_url.strip():
        return env_test_url.strip()

    from dotenv import dotenv_values

    vals = dotenv_values(".env")
    base_url = (
        vals.get("DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or "postgresql+psycopg://trialsync:replace-with-local-password@localhost:5432/trialsync"
    )
    if "/" in base_url:
        prefix, db_name = base_url.rsplit("/", 1)
        if "?" in db_name:
            _, query = db_name.split("?", 1)
            return f"{prefix}/trialsync_test_20260828?{query}"
        return f"{prefix}/trialsync_test_20260828"
    return "postgresql+psycopg://trialsync:replace-with-local-password@localhost:5432/trialsync_test_20260828"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        DATABASE_URL=resolve_test_database_url(),
        environment="test",
        auth_secret="test-secret-that-is-at-least-32-characters-long",
        cors_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def session_factory(app: FastAPI) -> async_sessionmaker[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = app.state.session_factory
    return factory


@pytest.fixture
def engine(app: FastAPI) -> AsyncEngine:
    eng: AsyncEngine = app.state.engine
    return eng


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
