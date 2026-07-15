import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from trialsync.api.errors import ApplicationError
from trialsync.api.health import get_readiness_probe

pytestmark = pytest.mark.anyio


class PassingProbe:
    async def check(self) -> None:
        return None


class FailingProbe:
    async def check(self) -> None:
        raise ApplicationError(
            code="SERVICE_NOT_READY",
            message="The database is unavailable or has not been migrated.",
            status_code=503,
        )


async def passing_probe() -> PassingProbe:
    return PassingProbe()


async def failing_probe() -> FailingProbe:
    return FailingProbe()


async def request(app: FastAPI, path: str) -> Response:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        return await client.get(path)


async def test_liveness_does_not_require_database(app: FastAPI) -> None:
    response = await request(app, "/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Trace-ID"]


async def test_readiness_passes_when_dependencies_are_ready(app: FastAPI) -> None:
    app.dependency_overrides[get_readiness_probe] = passing_probe

    response = await request(app, "/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_readiness_has_structured_failure(app: FastAPI) -> None:
    app.dependency_overrides[get_readiness_probe] = failing_probe

    response = await request(app, "/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_NOT_READY"
    assert response.json()["error"]["trace_id"] == response.headers["X-Trace-ID"]


async def test_not_found_has_structured_failure(app: FastAPI) -> None:
    response = await request(app, "/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert response.json()["error"]["trace_id"] == response.headers["X-Trace-ID"]
