from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from dotenv import dotenv_values
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from trialsync.config import Settings
from trialsync.db.session import get_db_session
from trialsync.main import create_app


def resolve_test_database_url() -> str:
    test_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("TRIALSYNC_TEST_DATABASE_URL")
    if not test_url or not test_url.strip():
        raise RuntimeError(
            "Database-backed tests require an explicit TEST_DATABASE_URL environment variable "
            "(e.g. TEST_DATABASE_URL=postgresql+psycopg://.../trialsync_test). "
            "Automatic fallback to the development database is prohibited to prevent data loss."
        )
    test_url = test_url.strip()

    # Safety check: prevent running tests against the development database
    env_vals = dotenv_values(".env")
    dev_url = env_vals.get("DATABASE_URL")
    env_name = os.environ.get("TRIALSYNC_ENVIRONMENT") or env_vals.get("TRIALSYNC_ENVIRONMENT")
    if dev_url and env_name != "test":
        dev_url_clean = dev_url.strip()
        if test_url == dev_url_clean:
            raise RuntimeError(
                f"TEST_DATABASE_URL ({test_url}) matches the development DATABASE_URL in .env. "
                "Database-backed tests must run against an isolated test database to "
                "protect development data."
            )

    return test_url


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return resolve_test_database_url()


@pytest.fixture
def settings(test_database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        DATABASE_URL=test_database_url,
        environment="test",
        auth_secret="test-secret-that-is-at-least-32-characters-long",
        cors_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    )


@pytest.fixture
async def engine(test_database_url: str) -> AsyncIterator[AsyncEngine]:
    test_engine = create_async_engine(test_database_url, pool_pre_ping=True)
    try:
        yield test_engine
    finally:
        await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def app(settings: Settings, session_factory: async_sessionmaker[AsyncSession]) -> FastAPI:
    application = create_app(settings)

    async def _test_get_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    application.dependency_overrides[get_db_session] = _test_get_db_session
    return application


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
