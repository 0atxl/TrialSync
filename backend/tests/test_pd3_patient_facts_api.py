from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete

from trialsync.db.models import User
from trialsync.db.session import get_session_factory
from trialsync.patient_data import INITIAL_CATALOG_CONCEPTS

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


@pytest.fixture
async def email_prefix() -> AsyncIterator[str]:
    prefix = f"pd3-{uuid.uuid4()}"
    yield prefix
    async with get_session_factory()() as session:
        await session.execute(delete(User).where(User.email.like(f"{prefix}%")))
        await session.commit()


async def register(api: AsyncClient, email: str) -> Response:
    response = await api.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "display_name": "PD3 Researcher",
            "password": "CorrectHorse123",
        },
    )
    assert response.status_code == 201
    return response


def auth(response: Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def create_patient(api: AsyncClient, headers: dict[str, str]) -> dict[str, object]:
    response = await api.post(
        "/api/v1/patients",
        headers=headers,
        json={"display_name": "Synthetic PD3 Catalog Patient"},
    )
    assert response.status_code == 201
    return response.json()


async def test_catalog_is_complete_stable_and_authenticated(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    response = await api.get("/api/v1/patient-fact-catalog", headers=auth(account))

    assert response.status_code == 200
    assert response.json()["version"] == "pd0-contract-v1"
    entries = response.json()["entries"]
    concepts = {(entry["fact_type"], entry["concept"]) for entry in entries}
    expected_concepts = {
        (fact_type.value, concept) for fact_type, concept in INITIAL_CATALOG_CONCEPTS
    }
    assert expected_concepts <= concepts
    assert len(entries) == len({entry["key"] for entry in entries})
    assert len(entries) >= len(expected_concepts) == 25
    assert next(entry for entry in entries if entry["key"] == "hba1c") == {
        "key": "hba1c",
        "fact_type": "observation",
        "concept": "hba1c",
        "display_label": "HbA1c",
        "group": "observations",
        "input_kind": "numeric",
        "allowed_assertions": ["present", "unknown"],
        "fixed_unit": "%",
        "allowed_units": [],
        "effective_date_required": True,
        "screening_supported": True,
        "help_text": "Record the measured HbA1c result.",
        "display_order": 10,
    }
    assert (await api.get("/api/v1/patient-fact-catalog")).status_code == 401


async def test_catalog_backed_create_and_edit_round_trip(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers)
    created = await api.post(
        f"/api/v1/patients/{patient['id']}/facts",
        headers=headers,
        json={
            "catalog_key": "type2_diabetes",
            "value": {
                "input_kind": "status",
                "assertion": "present",
                "effective_date": "2026-07-01",
            },
            "expected_patient_updated_at": patient["updated_at"],
        },
    )

    assert created.status_code == 201
    assert created.json()["fact_type"] == "condition"
    assert created.json()["concept"] == "type2_diabetes"
    assert created.json()["unit"] is None
    changed = await api.patch(
        f"/api/v1/patients/{patient['id']}/facts/{created.json()['id']}",
        headers=headers,
        json={
            "value": {
                "input_kind": "status",
                "assertion": "absent",
                "effective_date": "2026-07-02",
            },
            "expected_fact_updated_at": created.json()["updated_at"],
        },
    )

    assert changed.status_code == 200
    assert changed.json()["concept"] == "type2_diabetes"
    assert changed.json()["assertion"] == "absent"
    assert changed.json()["effective_date"] == "2026-07-02"


async def test_unknown_numeric_observation_does_not_invent_a_value(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers)
    response = await api.post(
        f"/api/v1/patients/{patient['id']}/facts",
        headers=headers,
        json={
            "catalog_key": "hba1c",
            "value": {
                "input_kind": "numeric",
                "assertion": "unknown",
                "effective_date": "2026-07-03",
            },
            "expected_patient_updated_at": patient["updated_at"],
        },
    )

    assert response.status_code == 201
    assert response.json()["assertion"] == "unknown"
    assert response.json()["value_numeric"] is None
    assert response.json()["value_text"] is None
    assert response.json()["unit"] == "%"


async def test_duplicate_status_directs_the_client_to_existing_detail(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers)
    payload = {
        "catalog_key": "metformin",
        "value": {"input_kind": "status", "assertion": "present"},
        "expected_patient_updated_at": patient["updated_at"],
    }
    first = await api.post(
        f"/api/v1/patients/{patient['id']}/facts", headers=headers, json=payload
    )
    duplicate = await api.post(
        f"/api/v1/patients/{patient['id']}/facts", headers=headers, json=payload
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PATIENT_FACT_DUPLICATE"
    assert duplicate.json()["error"]["details"] == [
        {
            "fact_id": first.json()["id"],
            "catalog_key": "metformin",
            "display_label": "Metformin",
        }
    ]


async def test_observations_allow_new_dates_but_reject_the_same_date(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers)

    async def add(effective_date: str, value: float) -> Response:
        return await api.post(
            f"/api/v1/patients/{patient['id']}/facts",
            headers=headers,
            json={
                "catalog_key": "creatinine",
                "value": {
                    "input_kind": "numeric",
                    "value_numeric": value,
                    "effective_date": effective_date,
                },
                "expected_patient_updated_at": patient["updated_at"],
            },
        )

    assert (await add("2026-07-01", 1.0)).status_code == 201
    assert (await add("2026-07-02", 1.1)).status_code == 201
    duplicate = await add("2026-07-02", 1.2)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PATIENT_FACT_DUPLICATE"


async def test_unsupported_wrong_shape_and_stale_edits_use_stable_errors(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient = await create_patient(api, headers)
    unsupported = await api.post(
        f"/api/v1/patients/{patient['id']}/facts",
        headers=headers,
        json={
            "catalog_key": "custom_condition",
            "value": {"input_kind": "status", "assertion": "present"},
            "expected_patient_updated_at": patient["updated_at"],
        },
    )
    wrong_shape = await api.post(
        f"/api/v1/patients/{patient['id']}/facts",
        headers=headers,
        json={
            "catalog_key": "hba1c",
            "value": {"input_kind": "status", "assertion": "present"},
            "expected_patient_updated_at": patient["updated_at"],
        },
    )
    created = await api.post(
        f"/api/v1/patients/{patient['id']}/facts",
        headers=headers,
        json={
            "catalog_key": "asthma",
            "value": {"input_kind": "status", "assertion": "present"},
            "expected_patient_updated_at": patient["updated_at"],
        },
    )
    changed = await api.patch(
        f"/api/v1/patients/{patient['id']}/facts/{created.json()['id']}",
        headers=headers,
        json={
            "value": {"input_kind": "status", "assertion": "absent"},
            "expected_fact_updated_at": created.json()["updated_at"],
        },
    )
    stale = await api.patch(
        f"/api/v1/patients/{patient['id']}/facts/{created.json()['id']}",
        headers=headers,
        json={
            "value": {"input_kind": "status", "assertion": "unknown"},
            "expected_fact_updated_at": created.json()["updated_at"],
        },
    )

    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "PATIENT_FACT_UNSUPPORTED"
    assert wrong_shape.status_code == 422
    assert wrong_shape.json()["error"]["code"] == "PATIENT_FACT_VALUE_INVALID"
    assert changed.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "PATIENT_RECORD_STALE"
