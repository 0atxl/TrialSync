from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete

from trialsync.db.models import User
from trialsync.db.session import get_session_factory
from trialsync.research.risk.artifacts import RiskArtifactError

pytestmark = pytest.mark.anyio


class UnavailableResearchArtifacts:
    def descriptor(self) -> None:
        raise RiskArtifactError("Unavailable for overview degradation test.")


@pytest.fixture
async def api(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


@pytest.fixture
async def email_prefix() -> AsyncIterator[str]:
    prefix = f"r5a-overview-{uuid.uuid4()}"
    yield prefix
    async with get_session_factory()() as session:
        await session.execute(delete(User).where(User.email.like(f"{prefix}%")))
        await session.commit()


async def _register(api: AsyncClient, email: str) -> Response:
    return await api.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "Overview user", "password": "CorrectHorse123"},
    )


def _auth(response: Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _approved_trial(api: AsyncClient, headers: dict[str, str]) -> str:
    trial = await api.post(
        "/api/v1/trials",
        headers=headers,
        json={
            "registry_id": f"OVERVIEW-{uuid.uuid4()}",
            "title": "Overview respiratory study with a deliberately readable title",
            "condition": "Asthma",
        },
    )
    trial_id = trial.json()["id"]
    version = await api.post(
        f"/api/v1/trials/{trial_id}/versions",
        headers=headers,
        json={"version": 1, "status": "draft"},
    )
    version_id = version.json()["id"]
    criterion = await api.post(
        f"/api/v1/trials/{trial_id}/versions/{version_id}/criteria",
        headers=headers,
        json={
            "kind": "inclusion",
            "order": 1,
            "source_text": "Adults aged 18 years or older",
            "normalized_rule": {
                "op": "gte",
                "fact": "demographic.age",
                "value": 18,
                "unit": "year",
            },
        },
    )
    assert criterion.status_code == 201, criterion.text
    approved = await api.put(
        f"/api/v1/trials/{trial_id}/versions/{version_id}",
        headers=headers,
        json={"version": 1, "status": "approved"},
    )
    assert approved.status_code == 200, approved.text
    return version_id


async def _screening(
    api: AsyncClient,
    headers: dict[str, str],
    version_id: str,
    *,
    name: str,
    date_of_birth: str | None,
) -> dict[str, object]:
    patient = await api.post(
        "/api/v1/patients",
        headers=headers,
        json={
            "external_id": f"OVERVIEW-{uuid.uuid4()}",
            "display_name": name,
            "date_of_birth": date_of_birth,
        },
    )
    assert patient.status_code == 201, patient.text
    response = await api.post(
        "/api/v1/screenings",
        headers=headers,
        json={
            "patient_id": patient.json()["id"],
            "trial_version_id": version_id,
            "screening_date": date.today().isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_overview_is_complete_owner_scoped_and_research_degraded_safe(
    app: FastAPI, api: AsyncClient, email_prefix: str
) -> None:
    app.state.research_risk = UnavailableResearchArtifacts()
    account = await _register(api, f"{email_prefix}-owner@example.com")
    other = await _register(api, f"{email_prefix}-other@example.com")
    headers = _auth(account)
    version_id = await _approved_trial(api, headers)
    eligible = await _screening(
        api,
        headers,
        version_id,
        name="A patient name that remains readable when the row is narrow",
        date_of_birth="1985-01-01",
    )
    review = await _screening(
        api,
        headers,
        version_id,
        name="Patient awaiting age information",
        date_of_birth=None,
    )

    response = await api.get("/api/v1/overview", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["eligibility"] == {
        "total": 2,
        "potentially_eligible": 1,
        "likely_ineligible": 0,
        "needs_review": 1,
    }
    assert len(body["activity"]) == 56
    assert body["activity"][-1] == {"date": date.today().isoformat(), "count": 2}
    assert body["dropout"]["status"] == "degraded"
    assert body["dropout"]["eligible_total"] == 1
    assert body["dropout"]["counts"] == {
        "not_started": 1,
        "information_needed": 0,
        "ready": 0,
        "predicted": 0,
    }
    assert [item["kind"] for item in body["attention"]] == [
        "eligibility_review",
        "dropout_not_started",
    ]
    assert {item["screening_id"] for item in body["recent_screenings"]} == {
        eligible["id"],
        review["id"],
    }

    hidden = await api.get("/api/v1/overview", headers=_auth(other))
    assert hidden.status_code == 200
    assert hidden.json()["eligibility"]["total"] == 0
    assert hidden.json()["recent_screenings"] == []
    assert (await api.get("/api/v1/overview")).status_code == 401


async def test_overview_route_is_documented(app: FastAPI) -> None:
    assert "/api/v1/overview" in app.openapi()["paths"]
