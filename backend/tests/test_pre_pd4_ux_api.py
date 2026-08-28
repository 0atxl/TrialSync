from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trialsync.db.models import User

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.fixture
async def account_prefix(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[str]:
    prefix = f"pre-pd4-{uuid.uuid4()}"
    yield prefix
    async with session_factory() as session:
        await session.execute(delete(User).where(User.email.like(f"{prefix}%")))
        await session.commit()


async def register(api: AsyncClient, email: str) -> Response:
    return await api.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "display_name": "Synthetic UX reviewer",
            "password": "CorrectHorse123",
        },
    )


def auth(response: Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_unsupported_patient_detail_is_separate_from_screening_facts(
    api: AsyncClient,
    account_prefix: str,
) -> None:
    owner = await register(api, f"{account_prefix}-owner@example.com")
    other = await register(api, f"{account_prefix}-other@example.com")
    patient = await api.post(
        "/api/v1/patients",
        headers=auth(owner),
        json={"display_name": "Synthetic unsupported-detail case"},
    )
    patient_id = patient.json()["id"]

    created = await api.post(
        f"/api/v1/patients/{patient_id}/unsupported-details",
        headers=auth(owner),
        json={
            "category": "medication",
            "label": "  Synthetic   study medication  ",
            "context": "Reported for later catalog review",
        },
    )

    assert created.status_code == 201
    assert created.json()["label"] == "Synthetic study medication"
    detail_id = created.json()["id"]
    current = await api.get(f"/api/v1/patients/{patient_id}", headers=auth(owner))
    assert current.json()["facts"] == []
    assert current.json()["unsupported_details"][0]["id"] == detail_id
    assert (
        await api.post(
            f"/api/v1/patients/{patient_id}/unsupported-details",
            headers=auth(owner),
            json={"category": "medication", "label": "synthetic study medication"},
        )
    ).status_code == 409
    assert (
        await api.delete(
            f"/api/v1/patients/{patient_id}/unsupported-details/{detail_id}",
            headers=auth(other),
        )
    ).status_code == 404
    assert (
        await api.delete(
            f"/api/v1/patients/{patient_id}/unsupported-details/{detail_id}",
            headers=auth(owner),
        )
    ).status_code == 204


async def test_guided_trial_authoring_derives_rules_order_units_and_revisions(
    api: AsyncClient,
    account_prefix: str,
) -> None:
    account = await register(api, f"{account_prefix}@example.com")
    headers = auth(account)
    trial = await api.post(
        "/api/v1/trials",
        headers=headers,
        json={"title": "Synthetic guided protocol", "condition": "Synthetic condition"},
    )
    trial_id = trial.json()["id"]

    draft = await api.post(f"/api/v1/trials/{trial_id}/versions/draft", headers=headers)
    assert draft.status_code == 201
    assert draft.json()["version"] == 1
    version_id = draft.json()["id"]
    duplicate_draft = await api.post(
        f"/api/v1/trials/{trial_id}/versions/draft",
        headers=headers,
    )
    assert duplicate_draft.status_code == 409
    assert duplicate_draft.json()["error"]["code"] == "TRIAL_DRAFT_EXISTS"

    age = await api.post(
        f"/api/v1/trials/{trial_id}/versions/{version_id}/guided-criteria",
        headers=headers,
        json={
            "kind": "inclusion",
            "subject_key": "age",
            "operator": "between",
            "minimum": 18,
            "maximum": 75,
        },
    )
    assert age.status_code == 201
    assert age.json()["order"] == 1
    assert age.json()["source_text"] == "Age between 18 and 75 years"
    assert age.json()["normalized_rule"] == {
        "op": "between",
        "fact": "demographic.age",
        "min": 18,
        "max": 75,
        "unit": "year",
    }

    hba1c = await api.post(
        f"/api/v1/trials/{trial_id}/versions/{version_id}/guided-criteria",
        headers=headers,
        json={
            "kind": "inclusion",
            "subject_key": "hba1c",
            "operator": "lte",
            "value": 8,
        },
    )
    assert hba1c.status_code == 201
    assert hba1c.json()["order"] == 2
    assert hba1c.json()["normalized_rule"]["unit"] == "%"
    assert hba1c.json()["normalized_rule"]["selection"] == "latest"

    client_unit = await api.post(
        f"/api/v1/trials/{trial_id}/versions/{version_id}/guided-criteria",
        headers=headers,
        json={
            "kind": "inclusion",
            "subject_key": "hba1c",
            "operator": "lte",
            "value": 8,
            "unit": "mg/dL",
        },
    )
    assert client_unit.status_code == 422

    unsupported = await api.post(
        f"/api/v1/trials/{trial_id}/versions/{version_id}/unsupported-criteria",
        headers=headers,
        json={
            "kind": "exclusion",
            "category": "other",
            "source_text": "Prior synthetic procedure within 30 days",
        },
    )
    assert unsupported.status_code == 201
    assert unsupported.json()["order"] == 3
    assert unsupported.json()["normalized_rule"] is None

    blocked = await api.put(
        f"/api/v1/trials/{trial_id}/versions/{version_id}",
        headers=headers,
        json={"version": 1, "status": "approved"},
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "TRIAL_VERSION_REVIEW_INCOMPLETE"

    assert (
        await api.delete(
            f"/api/v1/trials/{trial_id}/versions/{version_id}/criteria/{unsupported.json()['id']}",
            headers=headers,
        )
    ).status_code == 204
    approved = await api.put(
        f"/api/v1/trials/{trial_id}/versions/{version_id}",
        headers=headers,
        json={"version": 1, "status": "approved"},
    )
    assert approved.status_code == 200

    revision = await api.post(
        f"/api/v1/trials/{trial_id}/versions/draft",
        headers=headers,
    )
    assert revision.status_code == 201
    assert revision.json()["version"] == 2
    assert [item["source_text"] for item in revision.json()["criteria"]] == [
        "Age between 18 and 75 years",
        "HbA1c at most 8 %",
    ]


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        (
            {
                "kind": "inclusion",
                "subject_key": "age",
                "operator": "between",
                "minimum": 80,
                "maximum": 18,
            },
            "minimum",
        ),
        (
            {
                "kind": "exclusion",
                "subject_key": "metformin",
                "operator": "between",
                "minimum": 1,
                "maximum": 2,
            },
            "operator",
        ),
    ],
)
async def test_guided_trial_criterion_validation_is_stable(
    api: AsyncClient,
    account_prefix: str,
    payload: dict[str, object],
    field: str,
) -> None:
    account = await register(api, f"{account_prefix}-{field}@example.com")
    headers = auth(account)
    trial = await api.post(
        "/api/v1/trials",
        headers=headers,
        json={"title": f"Synthetic invalid {field}", "condition": "Synthetic"},
    )
    trial_id = trial.json()["id"]
    version = await api.post(f"/api/v1/trials/{trial_id}/versions/draft", headers=headers)

    response = await api.post(
        f"/api/v1/trials/{trial_id}/versions/{version.json()['id']}/guided-criteria",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TRIAL_CRITERION_VALUE_INVALID"
    assert response.json()["error"]["field"] == field


async def test_generic_trial_rule_validation_rejects_typos_and_unknown_facts(
    api: AsyncClient,
    account_prefix: str,
) -> None:
    account = await register(api, f"{account_prefix}-rule-validation@example.com")
    headers = auth(account)
    trial = await api.post(
        "/api/v1/trials",
        headers=headers,
        json={"title": "Synthetic rule validation", "condition": "Synthetic"},
    )
    trial_id = trial.json()["id"]
    version = await api.post(f"/api/v1/trials/{trial_id}/versions/draft", headers=headers)
    criteria_url = f"/api/v1/trials/{trial_id}/versions/{version.json()['id']}/criteria"

    misspelled_operator = await api.post(
        criteria_url,
        headers=headers,
        json={
            "kind": "inclusion",
            "order": 1,
            "source_text": "Type 2 diabetes",
            "normalized_rule": {"op": "presnet", "fact": "condition.type2_diabetes"},
        },
    )
    assert misspelled_operator.status_code == 422
    assert misspelled_operator.json()["error"]["code"] == "TRIAL_RULE_INVALID"
    assert '"presnet"' in misspelled_operator.json()["error"]["message"]
    assert misspelled_operator.json()["error"]["details"][0]["path"] == "$.op"

    unknown_fact = await api.post(
        criteria_url,
        headers=headers,
        json={
            "kind": "inclusion",
            "order": 1,
            "source_text": "Diabetes",
            "normalized_rule": {"op": "present", "fact": "condition.diabtes"},
        },
    )
    assert unknown_fact.status_code == 422
    assert unknown_fact.json()["error"]["details"][0]["code"] == "RULE_FACT_UNKNOWN"


async def test_direct_approved_version_creation_requires_reviewed_draft(
    api: AsyncClient,
    account_prefix: str,
) -> None:
    account = await register(api, f"{account_prefix}-direct-approved@example.com")
    headers = auth(account)
    trial = await api.post(
        "/api/v1/trials",
        headers=headers,
        json={"title": "Synthetic direct approval", "condition": "Synthetic"},
    )

    response = await api.post(
        f"/api/v1/trials/{trial.json()['id']}/versions",
        headers=headers,
        json={"version": 1, "status": "approved"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TRIAL_VERSION_REVIEW_INCOMPLETE"
    assert response.json()["error"]["field"] == "status"
