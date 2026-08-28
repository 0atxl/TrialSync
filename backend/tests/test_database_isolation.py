from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.conftest import resolve_test_database_url

from trialsync.config import Settings, get_settings
from trialsync.db.models import User
from trialsync.db.session import get_db_session, get_engine, get_session_factory
from trialsync.main import create_app

pytestmark = pytest.mark.anyio


async def test_conflicting_process_database_url_does_not_affect_isolated_app(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Point the process environment to an invalid / unreachable database host
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://unreachable-dev-user:wrong-password@127.0.0.99:9999/unreachable_dev_db",
    )
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    # The test app created with test settings and dependency override must use its isolated database
    test_app = create_app(settings)

    async def _test_get_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    test_app.dependency_overrides[get_db_session] = _test_get_db_session

    email = f"isolation-{uuid.uuid4()}@example.com"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": email,
                    "display_name": "Isolation User",
                    "password": "CorrectHorse123",
                },
            )
            assert response.status_code == 201

            health_response = await client.get("/health/ready")
            assert health_response.status_code == 200
            assert health_response.json() == {"status": "ready"}

        # Verify the record exists in the test database via the test session factory
        async with session_factory() as session:
            user = await session.scalar(select(User).where(User.email == email))
            assert user is not None
            assert user.display_name == "Isolation User"
    finally:
        async with session_factory() as session:
            existing = await session.scalar(select(User).where(User.email == email))
            if existing is not None:
                await session.delete(existing)
                await session.commit()
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()


async def test_api_requests_and_cleanup_use_same_session_factory(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    email = f"shared-factory-{uuid.uuid4()}@example.com"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": email,
                    "display_name": "Shared Factory User",
                    "password": "CorrectHorse123",
                },
            )
            assert response.status_code == 201

        async with session_factory() as session:
            user = await session.scalar(select(User).where(User.email == email))
            assert user is not None
            assert user.display_name == "Shared Factory User"
    finally:
        async with session_factory() as session:
            existing = await session.scalar(select(User).where(User.email == email))
            if existing is not None:
                await session.delete(existing)
                await session.commit()


def test_missing_test_database_url_fails_with_instruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("TRIALSYNC_TEST_DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="explicit TEST_DATABASE_URL environment variable"):
        resolve_test_database_url()


def test_test_database_url_cannot_match_development_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev_url = "postgresql+psycopg://trialsync:replace-with-local-password@localhost:5432/trialsync"
    monkeypatch.setenv("TEST_DATABASE_URL", dev_url)
    monkeypatch.setenv("TRIALSYNC_ENVIRONMENT", "development")

    with pytest.raises(RuntimeError, match=r"matches the development DATABASE_URL in \.env"):
        resolve_test_database_url()


async def test_engine_disposal_lifecycle(test_database_url: str) -> None:
    test_engine = create_async_engine(test_database_url, pool_pre_ping=True)
    async with test_engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1

    await test_engine.dispose()
