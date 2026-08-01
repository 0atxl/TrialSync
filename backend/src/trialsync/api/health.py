from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from trialsync.api.errors import ApplicationError, ErrorResponse
from trialsync.db.session import get_db_session

EXPECTED_SCHEMA_REVISION = "20260730_0011"

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str


@dataclass(frozen=True)
class ReadinessProbe:
    session: AsyncSession

    async def check(self) -> None:
        try:
            await self.session.execute(text("SELECT 1"))
            revision_result = await self.session.execute(
                text("SELECT version_num FROM alembic_version")
            )
            revision = revision_result.scalar_one_or_none()
        except SQLAlchemyError as exception:
            raise ApplicationError(
                code="SERVICE_NOT_READY",
                message="The database is unavailable or has not been migrated.",
                status_code=503,
            ) from exception

        if revision != EXPECTED_SCHEMA_REVISION:
            raise ApplicationError(
                code="DATABASE_MIGRATION_REQUIRED",
                message="The database schema is not at the required revision.",
                status_code=503,
            )


async def get_readiness_probe(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReadinessProbe:
    return ReadinessProbe(session=session)


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={503: {"model": ErrorResponse}},
)
async def ready(
    probe: Annotated[ReadinessProbe, Depends(get_readiness_probe)],
) -> HealthResponse:
    await probe.check()
    return HealthResponse(status="ready")
