from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete

from trialsync.db.models import Assertion, FactType, PatientFact, User
from trialsync.db.session import get_session_factory
from trialsync.patient_data import PatientDataErrorCode, PatientDataWarningCode

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.fixture
async def email_prefix() -> AsyncIterator[str]:
    prefix = f"pd4-{uuid.uuid4()}"
    yield prefix
    async with get_session_factory()() as session:
        await session.execute(delete(User).where(User.email.like(f"{prefix}%")))
        await session.commit()


async def register(api: AsyncClient, email: str) -> Response:
    response = await api.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "display_name": "PD4 Researcher",
            "password": "CorrectHorse123",
        },
    )
    assert response.status_code == 201
    return response


def auth(response: Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def create_patient(
    api: AsyncClient,
    headers: dict[str, str],
    *,
    suffix: str,
    sex: str | None,
) -> dict[str, object]:
    response = await api.post(
        "/api/v1/patients",
        headers=headers,
        json={
            "external_id": f"SYN-PD4-{suffix}",
            "display_name": f"Synthetic PD4 {suffix}",
            "date_of_birth": "1990-01-15",
            "sex": sex,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def add_pregnancy(
    api: AsyncClient,
    headers: dict[str, str],
    patient: dict[str, object],
    assertion: str,
) -> Response:
    return await api.post(
        f"/api/v1/patients/{patient['id']}/facts",
        headers=headers,
        json={
            "catalog_key": "pregnancy",
            "value": {
                "input_kind": "pregnancy_status",
                "assertion": assertion,
                "effective_date": "2026-07-29",
            },
            "expected_patient_updated_at": patient["updated_at"],
        },
    )


@pytest.mark.parametrize("assertion", ["present", "absent", "unknown"])
async def test_female_patient_accepts_each_explicit_pregnancy_status(
    api: AsyncClient,
    email_prefix: str,
    assertion: str,
) -> None:
    account = await register(api, f"{email_prefix}-{assertion}@example.com")
    headers = auth(account)
    patient = await create_patient(
        api,
        headers,
        suffix=f"FEMALE-{assertion}",
        sex="female",
    )

    response = await add_pregnancy(api, headers, patient, assertion)

    assert response.status_code == 201
    assert response.json()["assertion"] == assertion


@pytest.mark.parametrize("assertion", ["absent", "unknown"])
async def test_male_patient_accepts_explicit_non_present_pregnancy_status(
    api: AsyncClient,
    email_prefix: str,
    assertion: str,
) -> None:
    account = await register(api, f"{email_prefix}-{assertion}@example.com")
    headers = auth(account)
    patient = await create_patient(
        api,
        headers,
        suffix=f"MALE-{assertion}",
        sex="male",
    )

    response = await add_pregnancy(api, headers, patient, assertion)

    assert response.status_code == 201
    assert response.json()["assertion"] == assertion


async def test_missing_sex_allows_pregnancy_present_with_stable_review_warning(
    api: AsyncClient,
    email_prefix: str,
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers, suffix="MISSING-SEX", sex=None)

    fact = await add_pregnancy(api, headers, patient, "present")
    detail = await api.get(f"/api/v1/patients/{patient['id']}", headers=headers)

    assert fact.status_code == 201
    assert detail.status_code == 200
    assert detail.json()["consistency_issues"] == [
        {
            "code": PatientDataWarningCode.sex_not_recorded_for_pregnancy,
            "severity": "warning",
            "message": (
                "Pregnancy is recorded as Pregnant, but biological sex is not recorded."
            ),
            "field": "sex",
            "fact_id": fact.json()["id"],
        }
    ]


async def test_direct_fact_update_cannot_store_male_pregnancy_conflict(
    api: AsyncClient,
    email_prefix: str,
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers, suffix="EDIT-BLOCK", sex="male")
    fact = await add_pregnancy(api, headers, patient, "absent")
    assert fact.status_code == 201

    blocked = await api.patch(
        f"/api/v1/patients/{patient['id']}/facts/{fact.json()['id']}",
        headers=headers,
        json={
            "value": {
                "input_kind": "pregnancy_status",
                "assertion": "present",
                "effective_date": "2026-07-30",
            },
            "expected_fact_updated_at": fact.json()["updated_at"],
        },
    )
    unchanged = await api.get(f"/api/v1/patients/{patient['id']}", headers=headers)

    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == PatientDataErrorCode.pregnancy_sex_conflict
    assert blocked.json()["error"]["field"] == "value.assertion"
    assert blocked.json()["error"]["details"] == [{"fact_id": fact.json()["id"]}]
    assert unchanged.json()["facts"][0]["assertion"] == "absent"
    assert unchanged.json()["facts"][0]["effective_date"] == "2026-07-29"


async def test_changing_sex_to_male_is_blocked_with_conflicting_fact_identifier(
    api: AsyncClient,
    email_prefix: str,
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers, suffix="SEX-BLOCK", sex="female")
    fact = await add_pregnancy(api, headers, patient, "present")
    assert fact.status_code == 201

    blocked = await api.patch(
        f"/api/v1/patients/{patient['id']}",
        headers=headers,
        json={
            "sex": "male",
            "expected_updated_at": patient["updated_at"],
        },
    )
    unchanged = await api.get(f"/api/v1/patients/{patient['id']}", headers=headers)

    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == PatientDataErrorCode.pregnancy_sex_conflict
    assert blocked.json()["error"]["field"] == "sex"
    assert blocked.json()["error"]["details"] == [{"fact_id": fact.json()["id"]}]
    assert unchanged.json()["sex"] == "female"
    assert unchanged.json()["facts"][0]["assertion"] == "present"


async def test_sex_change_to_male_succeeds_after_pregnancy_is_reconciled(
    api: AsyncClient,
    email_prefix: str,
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers, suffix="RECONCILED", sex="female")
    fact = await add_pregnancy(api, headers, patient, "absent")
    assert fact.status_code == 201

    changed = await api.patch(
        f"/api/v1/patients/{patient['id']}",
        headers=headers,
        json={
            "sex": "male",
            "expected_updated_at": patient["updated_at"],
        },
    )

    assert changed.status_code == 200
    assert changed.json()["sex"] == "male"
    assert changed.json()["facts"][0]["assertion"] == "absent"
    assert changed.json()["consistency_issues"] == []


async def test_legacy_conflict_is_visible_and_can_be_reconciled_without_inference(
    api: AsyncClient,
    email_prefix: str,
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers, suffix="LEGACY", sex="male")
    fact_id = uuid.uuid4()
    async with get_session_factory()() as session:
        session.add(
            PatientFact(
                id=fact_id,
                patient_id=uuid.UUID(str(patient["id"])),
                fact_type=FactType.condition,
                concept="pregnancy",
                assertion=Assertion.present,
                effective_date=date(2026, 7, 29),
                source_label="Synthetic legacy fixture",
            )
        )
        await session.commit()

    legacy = await api.get(f"/api/v1/patients/{patient['id']}", headers=headers)
    issue = legacy.json()["consistency_issues"][0]
    reconciled = await api.patch(
        f"/api/v1/patients/{patient['id']}/facts/{fact_id}",
        headers=headers,
        json={
            "value": {
                "input_kind": "pregnancy_status",
                "assertion": "unknown",
                "effective_date": "2026-07-29",
            },
            "expected_fact_updated_at": legacy.json()["facts"][0]["updated_at"],
        },
    )
    current = await api.get(f"/api/v1/patients/{patient['id']}", headers=headers)

    assert issue["code"] == PatientDataErrorCode.pregnancy_sex_conflict
    assert issue["severity"] == "conflict"
    assert issue["fact_id"] == str(fact_id)
    assert reconciled.status_code == 200
    assert reconciled.json()["assertion"] == "unknown"
    assert current.json()["consistency_issues"] == []
    assert current.json()["facts"][0]["assertion"] == "unknown"


async def test_male_sex_does_not_infer_or_create_pregnancy_absence(
    api: AsyncClient,
    email_prefix: str,
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers, suffix="NO-INFERENCE", sex="male")

    detail = await api.get(f"/api/v1/patients/{patient['id']}", headers=headers)

    assert detail.status_code == 200
    assert detail.json()["facts"] == []
    assert detail.json()["consistency_issues"] == []
