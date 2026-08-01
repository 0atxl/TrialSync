from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError

from trialsync.db.models import Patient, User
from trialsync.db.session import get_session_factory
from trialsync.patient_data import PatientDataErrorCode

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


@pytest.fixture
async def email_prefix() -> AsyncIterator[str]:
    prefix = f"pd0-{uuid.uuid4()}"
    yield prefix
    async with get_session_factory()() as session:
        await session.execute(delete(User).where(User.email.like(f"{prefix}%")))
        await session.commit()


async def register(api: AsyncClient, email: str) -> Response:
    response = await api.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "PD0 Researcher", "password": "CorrectHorse123"},
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
    sex: str | None = None,
    date_of_birth: str | None = "1990-07-15",
) -> dict[str, object]:
    response = await api.post(
        "/api/v1/patients",
        headers=headers,
        json={
            "external_id": f"SYN-PD0-{suffix}",
            "display_name": f"Synthetic PD0 {suffix}",
            "date_of_birth": date_of_birth,
            "sex": sex,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_current_profile_create_and_update_round_trip(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers, suffix="PROFILE", sex="female")

    changed = await api.patch(
        f"/api/v1/patients/{patient['id']}",
        headers=headers,
        json={
            "display_name": "Synthetic PD0 Updated",
            "date_of_birth": "1991-08-16",
            "sex": "male",
            "expected_updated_at": patient["updated_at"],
        },
    )

    assert changed.status_code == 200
    assert changed.json()["display_name"] == "Synthetic PD0 Updated"
    assert changed.json()["date_of_birth"] == "1991-08-16"
    assert changed.json()["sex"] == "male"


@pytest.mark.parametrize("sex", ["male", "female", None])
async def test_pd2_canonical_biological_sex_round_trips(
    api: AsyncClient, email_prefix: str, sex: str | None
) -> None:
    account = await register(api, f"{email_prefix}-{sex or 'none'}@example.com")
    headers = auth(account)
    patient = await create_patient(
        api,
        headers,
        suffix=f"SEX-{sex or 'NONE'}",
        sex=sex,
        date_of_birth=None,
    )

    detail = await api.get(f"/api/v1/patients/{patient['id']}", headers=headers)

    assert detail.status_code == 200
    assert detail.json()["sex"] == sex
    assert detail.json()["date_of_birth"] is None


async def test_pd2_profile_can_explicitly_clear_demographics(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers, suffix="CLEAR", sex="female")

    changed = await api.patch(
        f"/api/v1/patients/{patient['id']}",
        headers=headers,
        json={
            "date_of_birth": None,
            "sex": None,
            "expected_updated_at": patient["updated_at"],
        },
    )

    assert changed.status_code == 200
    assert changed.json()["date_of_birth"] is None
    assert changed.json()["sex"] is None


async def test_pd2_database_rejects_noncanonical_biological_sex(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers, suffix="DB-CONSTRAINT", sex="female")

    async with get_session_factory()() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                update(Patient)
                .where(Patient.id == patient["id"])
                .values(sex="unsupported")
            )
            await session.commit()
        await session.rollback()

    unchanged = await api.get(f"/api/v1/patients/{patient['id']}", headers=headers)
    assert unchanged.status_code == 200
    assert unchanged.json()["sex"] == "female"


async def test_current_fact_create_update_delete_and_ownership(
    api: AsyncClient, email_prefix: str
) -> None:
    first = await register(api, f"{email_prefix}-a@example.com")
    second = await register(api, f"{email_prefix}-b@example.com")
    headers = auth(first)
    patient = await create_patient(api, headers, suffix="FACT")
    fact_url = f"/api/v1/patients/{patient['id']}/facts"
    created = await api.post(
        fact_url,
        headers=headers,
        json={
            "catalog_key": "pregnancy",
            "value": {
                "input_kind": "pregnancy_status",
                "assertion": "absent",
                "effective_date": "2026-07-28",
            },
            "expected_patient_updated_at": patient["updated_at"],
        },
    )
    assert created.status_code == 201
    fact_id = created.json()["id"]

    updated = await api.patch(
        f"{fact_url}/{fact_id}",
        headers=headers,
        json={
            "value": {
                "input_kind": "pregnancy_status",
                "assertion": "present",
                "effective_date": "2026-07-29",
            },
            "expected_fact_updated_at": created.json()["updated_at"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == fact_id
    assert updated.json()["assertion"] == "present"

    hidden = await api.patch(
        f"{fact_url}/{fact_id}",
        headers=auth(second),
        json={
            "value": {
                "input_kind": "pregnancy_status",
                "assertion": "absent",
                "effective_date": "2026-07-29",
            },
            "expected_fact_updated_at": updated.json()["updated_at"],
        },
    )
    assert hidden.status_code == 404

    removed = await api.request(
        "DELETE",
        f"{fact_url}/{fact_id}",
        headers=headers,
        json={
            "reason": "Reconciled against the latest synthetic source.",
            "expected_fact_updated_at": updated.json()["updated_at"],
        },
    )
    assert removed.status_code == 204
    detail = await api.get(f"/api/v1/patients/{patient['id']}", headers=headers)
    assert detail.json()["facts"] == []
    assert any(item["event_type"] == "fact_voided" for item in detail.json()["activity"])
    restored = await api.post(f"{fact_url}/{fact_id}/restore", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["id"] == fact_id
    assert (await api.delete(f"{fact_url}/{fact_id}", headers=headers)).status_code == 422


async def test_fact_void_requires_reason_and_activity_is_owner_scoped(
    api: AsyncClient, email_prefix: str
) -> None:
    first = await register(api, f"{email_prefix}-activity-a@example.com")
    second = await register(api, f"{email_prefix}-activity-b@example.com")
    headers = auth(first)
    patient = await create_patient(api, headers, suffix="ACTIVITY")
    fact_response = await api.post(
        f"/api/v1/patients/{patient['id']}/facts",
        headers=headers,
        json={
            "catalog_key": "hba1c",
            "value": {
                "input_kind": "numeric",
                "value_numeric": 7.4,
                "effective_date": "2026-07-29",
            },
            "expected_patient_updated_at": patient["updated_at"],
        },
    )
    assert fact_response.status_code == 201
    fact = fact_response.json()
    fact_url = f"/api/v1/patients/{patient['id']}/facts/{fact['id']}"

    missing_reason = await api.delete(fact_url, headers=headers)
    assert missing_reason.status_code == 422
    assert missing_reason.json()["error"]["code"] == "PATIENT_FACT_REMOVAL_REASON_REQUIRED"

    hidden_activity = await api.get(
        f"/api/v1/patients/{patient['id']}/activity", headers=auth(second)
    )
    assert hidden_activity.status_code == 404

    removed = await api.request(
        "DELETE",
        fact_url,
        headers=headers,
        json={
            "reason": "The value was entered from the wrong source.",
            "expected_fact_updated_at": fact["updated_at"],
        },
    )
    assert removed.status_code == 204
    activity = await api.get(
        f"/api/v1/patients/{patient['id']}/activity", headers=headers
    )
    assert activity.status_code == 200
    voided = next(item for item in activity.json() if item["event_type"] == "fact_voided")
    assert voided["reason"] == "The value was entered from the wrong source."

    restored_by_other = await api.post(
        f"{fact_url}/restore", headers=auth(second)
    )
    assert restored_by_other.status_code == 404


async def test_fact_edits_do_not_rewrite_saved_screening_evidence(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers, suffix="SNAPSHOT")
    fact = await api.post(
        f"/api/v1/patients/{patient['id']}/facts",
        headers=headers,
        json={
            "catalog_key": "hba1c",
            "value": {
                "input_kind": "numeric",
                "value_numeric": 7.1,
                "effective_date": "2026-07-01",
            },
            "expected_patient_updated_at": patient["updated_at"],
        },
    )
    assert fact.status_code == 201

    trial = await api.post(
        "/api/v1/trials",
        headers=headers,
        json={
            "registry_id": "SYN-PD0-TRIAL",
            "title": "Synthetic PD0 HbA1c study",
            "condition": "Synthetic metabolic condition",
        },
    )
    version = await api.post(
        f"/api/v1/trials/{trial.json()['id']}/versions",
        headers=headers,
        json={"version": 1, "status": "draft"},
    )
    criterion = await api.post(
        f"/api/v1/trials/{trial.json()['id']}/versions/{version.json()['id']}/criteria",
        headers=headers,
        json={
            "kind": "inclusion",
            "order": 1,
            "source_text": "HbA1c between 7.0% and 8.0%",
            "normalized_rule": {
                "op": "between",
                "fact": "observation.hba1c",
                "min": 7.0,
                "max": 8.0,
                "unit": "%",
                "selection": "latest",
            },
        },
    )
    assert criterion.status_code == 201
    approved = await api.put(
        f"/api/v1/trials/{trial.json()['id']}/versions/{version.json()['id']}",
        headers=headers,
        json={"version": 1, "status": "approved"},
    )
    assert approved.status_code == 200

    first = await api.post(
        "/api/v1/screenings",
        headers=headers,
        json={
            "patient_id": patient["id"],
            "trial_version_id": version.json()["id"],
            "screening_date": "2026-07-15",
        },
    )
    assert first.status_code == 201
    assert first.json()["overall_state"] == "potentially_eligible"

    updated = await api.patch(
        f"/api/v1/patients/{patient['id']}/facts/{fact.json()['id']}",
        headers=headers,
        json={
            "value": {
                "input_kind": "numeric",
                "value_numeric": 9.1,
                "effective_date": "2026-07-14",
            },
            "expected_fact_updated_at": fact.json()["updated_at"],
        },
    )
    assert updated.status_code == 200

    historical = await api.get(f"/api/v1/screenings/{first.json()['id']}", headers=headers)
    assert historical.json()["overall_state"] == "potentially_eligible"
    assert historical.json()["evaluations"][0]["evidence"][0]["value"] == "7.100000"

    second = await api.post(
        "/api/v1/screenings",
        headers=headers,
        json={
            "patient_id": patient["id"],
            "trial_version_id": version.json()["id"],
            "screening_date": "2026-07-15",
        },
    )
    assert second.status_code == 201
    assert second.json()["patient_snapshot_id"] != first.json()["patient_snapshot_id"]
    assert second.json()["overall_state"] == "likely_ineligible"
    assert second.json()["evaluations"][0]["evidence"][0]["value"] == "9.100000"


@pytest.mark.parametrize("sex", ["unsupported", "Female", "male or female"])
async def test_contract_rejects_unsupported_biological_sex(
    api: AsyncClient, email_prefix: str, sex: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    response = await api.post(
        "/api/v1/patients",
        headers=auth(account),
        json={"display_name": "Synthetic Invalid Sex", "sex": sex},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == PatientDataErrorCode.sex_invalid


async def test_contract_rejects_future_date_of_birth(api: AsyncClient, email_prefix: str) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    response = await api.post(
        "/api/v1/patients",
        headers=auth(account),
        json={"display_name": "Synthetic Future DOB", "date_of_birth": "2099-01-01"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == PatientDataErrorCode.date_of_birth_in_future


async def test_pd2_rejects_future_date_of_birth_during_profile_update(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers, suffix="FUTURE-UPDATE")

    response = await api.patch(
        f"/api/v1/patients/{patient['id']}",
        headers=headers,
        json={
            "date_of_birth": "2099-01-01",
            "expected_updated_at": patient["updated_at"],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == PatientDataErrorCode.date_of_birth_in_future


async def test_contract_rejects_pregnancy_present_for_male_patient(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers, suffix="CONFLICT", sex="male")
    response = await api.post(
        f"/api/v1/patients/{patient['id']}/facts",
        headers=headers,
        json={
            "catalog_key": "pregnancy",
            "value": {
                "input_kind": "pregnancy_status",
                "assertion": "present",
                "effective_date": "2026-07-29",
            },
            "expected_patient_updated_at": patient["updated_at"],
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == PatientDataErrorCode.pregnancy_sex_conflict


async def test_contract_rejects_duplicate_current_status_fact(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers, suffix="DUPLICATE")
    payload = {
        "catalog_key": "type2_diabetes",
        "value": {"input_kind": "status", "assertion": "present"},
        "expected_patient_updated_at": patient["updated_at"],
    }
    first = await api.post(f"/api/v1/patients/{patient['id']}/facts", headers=headers, json=payload)
    second = await api.post(
        f"/api/v1/patients/{patient['id']}/facts", headers=headers, json=payload
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == PatientDataErrorCode.fact_duplicate


async def test_contract_rejects_stale_profile_update(api: AsyncClient, email_prefix: str) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers, suffix="STALE")
    stale_revision = patient["updated_at"]
    first = await api.patch(
        f"/api/v1/patients/{patient['id']}",
        headers=headers,
        json={
            "display_name": "Synthetic First Update",
            "expected_updated_at": stale_revision,
        },
    )
    assert first.status_code == 200
    stale = await api.patch(
        f"/api/v1/patients/{patient['id']}",
        headers=headers,
        json={
            "display_name": "Synthetic Stale Update",
            "expected_updated_at": stale_revision,
        },
    )

    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == PatientDataErrorCode.record_stale
