from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trialsync.config import Settings, get_settings
from trialsync.db.models import User
from trialsync.db.session import (
    _cached_engine,
    _cached_session_factory,
    get_session_factory,
)
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
    _cached_engine.cache_clear()
    _cached_session_factory.cache_clear()

    # The test app created with test settings must still use its isolated database
    test_app = create_app(settings)
    assert test_app.state.engine.url.database == "trialsync_test_20260828"

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
        _cached_engine.cache_clear()
        _cached_session_factory.cache_clear()


async def test_app_and_fixture_cleanup_use_same_session_factory(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    assert app.state.session_factory is session_factory
    assert get_session_factory(app) is session_factory


async def test_get_session_factory_from_settings(settings: Settings) -> None:
    factory = get_session_factory(settings)
    assert factory is not None
