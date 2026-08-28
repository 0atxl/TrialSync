from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from trialsync.config import Settings, get_settings


@lru_cache
def _cached_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(settings.database_url.get_secret_value(), pool_pre_ping=True)


@lru_cache
def _cached_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=_cached_engine(), autoflush=False, expire_on_commit=False)


def get_engine(target: Any | None = None) -> AsyncEngine:
    if target is not None and hasattr(target, "state") and hasattr(target.state, "engine"):
        engine: AsyncEngine = target.state.engine
        return engine
    if isinstance(target, Settings):
        return create_async_engine(target.database_url.get_secret_value(), pool_pre_ping=True)
    return _cached_engine()


def get_session_factory(
    target: Any | None = None,
) -> async_sessionmaker[AsyncSession]:
    if target is not None and hasattr(target, "state") and hasattr(target.state, "session_factory"):
        factory: async_sessionmaker[AsyncSession] = target.state.session_factory
        return factory
    if isinstance(target, Settings):
        return async_sessionmaker(bind=get_engine(target), autoflush=False, expire_on_commit=False)
    return _cached_session_factory()


async def get_db_session(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    session_factory: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "session_factory", None
    )
    if session_factory is None:
        session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
