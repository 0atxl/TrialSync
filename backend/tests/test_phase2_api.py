from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete

from trialsync.db.models import User
from trialsync.db.session import get_session_factory

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


async def register(api: AsyncClient, email: str, password: str = "CorrectHorse123") -> Response:
    return await api.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "Demo Researcher", "password": password},
    )


def auth(response: Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def email_prefix() -> AsyncIterator[str]:
    prefix = f"phase2-{uuid.uuid4()}"
    yield prefix
    async with get_session_factory()() as session:
        await session.execute(delete(User).where(User.email.like(f"{prefix}%")))
        await session.commit()


async def test_registration_login_and_duplicate_email(api: AsyncClient, email_prefix: str) -> None:
    email = f"{email_prefix}@example.com"
    created = await register(api, email)
    assert created.status_code == 201
    assert created.json()["user"]["email"] == email

    duplicate = await register(api, email)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"

    login = await api.post(
        "/api/v1/auth/login", json={"email": email, "password": "CorrectHorse123"}
    )
    assert login.status_code == 200

    invalid = await api.post("/api/v1/auth/login", json={"email": email, "password": "incorrect"})
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_authentication_and_cross_user_patient_isolation(
    api: AsyncClient, email_prefix: str
) -> None:
    first = await register(api, f"{email_prefix}-a@example.com")
    second = await register(api, f"{email_prefix}-b@example.com")
    unauthenticated = await api.get("/api/v1/patients")
    assert unauthenticated.status_code == 401

    created = await api.post(
        "/api/v1/patients",
        headers=auth(first),
        json={"external_id": "SYN-001", "display_name": "Synthetic Ada"},
    )
    assert created.status_code == 201
    patient_id = created.json()["id"]

    hidden = await api.get(f"/api/v1/patients/{patient_id}", headers=auth(second))
    assert hidden.status_code == 404

    update = await api.patch(
        f"/api/v1/patients/{patient_id}",
        headers=auth(second),
        json={"display_name": "Not allowed"},
    )
    assert update.status_code == 404
    deleted = await api.delete(f"/api/v1/patients/{patient_id}", headers=auth(second))
    assert deleted.status_code == 404


async def test_patient_fact_numeric_unit_validation(api: AsyncClient, email_prefix: str) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    created = await api.post(
        "/api/v1/patients",
        headers=auth(account),
        json={"external_id": "SYN-LAB", "display_name": "Synthetic Lab Case"},
    )
    patient_id = created.json()["id"]
    invalid = await api.post(
        f"/api/v1/patients/{patient_id}/facts",
        headers=auth(account),
        json={"fact_type": "observation", "concept": "HbA1c", "value_numeric": 7.1},
    )
    assert invalid.status_code == 422

    valid = await api.post(
        f"/api/v1/patients/{patient_id}/facts",
        headers=auth(account),
        json={
            "fact_type": "observation",
            "concept": "HbA1c",
            "value_numeric": 7.1,
            "unit": "%",
            "effective_date": "2026-07-01",
        },
    )
    assert valid.status_code == 201
    assert valid.json()["unit"] == "%"


async def test_generated_record_ids_and_duplicate_patient_confirmation(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)

    first = await api.post(
        "/api/v1/patients",
        headers=headers,
        json={"display_name": "Synthetic Duplicate"},
    )
    assert first.status_code == 201
    assert first.json()["external_id"].startswith("SYN-")

    warning = await api.post(
        "/api/v1/patients",
        headers=headers,
        json={"display_name": "synthetic duplicate"},
    )
    assert warning.status_code == 409
    assert warning.json()["error"]["code"] == "PATIENT_NAME_REVIEW_REQUIRED"
    assert warning.json()["error"]["details"][0]["patient_id"] == first.json()["id"]

    confirmed = await api.post(
        "/api/v1/patients",
        headers=headers,
        json={"display_name": "Synthetic Duplicate", "confirm_duplicate_name": True},
    )
    assert confirmed.status_code == 201
    assert confirmed.json()["external_id"] != first.json()["external_id"]

    trial = await api.post(
        "/api/v1/trials",
        headers=headers,
        json={"title": "Synthetic generated ID study", "condition": "Synthetic condition"},
    )
    assert trial.status_code == 201
    assert trial.json()["registry_id"].startswith("SYN-TRIAL-")


async def test_trial_ownership_and_criterion_ordering(api: AsyncClient, email_prefix: str) -> None:
    first = await register(api, f"{email_prefix}-a@example.com")
    second = await register(api, f"{email_prefix}-b@example.com")
    trial = await api.post(
        "/api/v1/trials",
        headers=auth(first),
        json={
            "registry_id": "SYN-TRIAL-01",
            "title": "Synthetic metabolic study",
            "condition": "Type 2 diabetes",
            "phase": "Phase 2",
        },
    )
    assert trial.status_code == 201
    trial_id = trial.json()["id"]
    assert (await api.get(f"/api/v1/trials/{trial_id}", headers=auth(second))).status_code == 404
    assert (
        await api.patch(
            f"/api/v1/trials/{trial_id}",
            headers=auth(second),
            json={"title": "Not allowed"},
        )
    ).status_code == 404
    assert (await api.delete(f"/api/v1/trials/{trial_id}", headers=auth(second))).status_code == 404

    version = await api.post(
        f"/api/v1/trials/{trial_id}/versions",
        headers=auth(first),
        json={"version": 1, "status": "draft"},
    )
    assert version.status_code == 201
    version_id = version.json()["id"]
    criterion_url = f"/api/v1/trials/{trial_id}/versions/{version_id}/criteria"
    inclusion = await api.post(
        criterion_url,
        headers=auth(first),
        json={"kind": "inclusion", "order": 1, "source_text": "Age 18 years or older"},
    )
    assert inclusion.status_code == 201
    duplicate_order = await api.post(
        criterion_url,
        headers=auth(first),
        json={"kind": "exclusion", "order": 1, "source_text": "Current insulin therapy"},
    )
    assert duplicate_order.status_code == 409

    approved = await api.put(
        f"/api/v1/trials/{trial_id}/versions/{version_id}",
        headers=auth(first),
        json={"version": 1, "status": "approved"},
    )
    assert approved.status_code == 200
    immutable = await api.post(
        criterion_url,
        headers=auth(first),
        json={"kind": "exclusion", "order": 2, "source_text": "Pregnancy"},
    )
    assert immutable.status_code == 409
    assert immutable.json()["error"]["code"] == "APPROVED_VERSION_IMMUTABLE"
