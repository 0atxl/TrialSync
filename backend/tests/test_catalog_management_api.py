from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, update

from trialsync.db.models import ClinicalConcept, User
from trialsync.db.session import get_session_factory
from trialsync.schemas import TerminologySuggestionRead
from trialsync.terminology.suggestions import TerminologySuggestionResult

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


async def register(api: AsyncClient, email: str) -> dict[str, str]:
    response = await api.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "display_name": "Catalog Coordinator",
            "password": "CorrectHorse123",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_catalog_management_is_admin_only_and_retirement_is_safe(
    api: AsyncClient,
) -> None:
    suffix = uuid.uuid4().hex
    email = f"catalog-{suffix}@example.com"
    headers = await register(api, email)

    denied = await api.get("/api/v1/clinical-concepts", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "CATALOG_ADMIN_REQUIRED"

    async with get_session_factory()() as session:
        await session.execute(
            update(User).where(User.email == email).values(is_catalog_admin=True)
        )
        await session.commit()

    concept_id: str | None = None
    try:
        created = await api.post(
            "/api/v1/clinical-concepts",
            headers=headers,
            json={
                "display_label": "C-reactive protein",
                "fact_type": "observation",
                "fixed_unit": "mg/L",
                "screening_supported": True,
            },
        )
        assert created.status_code == 201, created.text
        concept = created.json()
        concept_id = concept["id"]
        assert concept["key"] == "c_reactive_protein"
        assert concept["input_kind"] == "numeric"
        assert concept["fixed_unit"] == "mg/L"

        catalog = await api.get("/api/v1/patient-fact-catalog", headers=headers)
        assert catalog.status_code == 200
        assert any(item["key"] == "c_reactive_protein" for item in catalog.json()["entries"])

        patient = await api.post(
            "/api/v1/patients",
            headers=headers,
            json={
                "external_id": f"SYN-CATALOG-{suffix[:8]}",
                "display_name": "Synthetic Catalog Patient",
            },
        )
        assert patient.status_code == 201, patient.text
        fact = await api.post(
            f"/api/v1/patients/{patient.json()['id']}/facts",
            headers=headers,
            json={
                "catalog_key": "c_reactive_protein",
                "value": {
                    "input_kind": "numeric",
                    "assertion": "present",
                    "value_numeric": 4.2,
                    "effective_date": "2026-07-30",
                },
                "expected_patient_updated_at": patient.json()["updated_at"],
            },
        )
        assert fact.status_code == 201, fact.text
        assert fact.json()["unit"] == "mg/L"

        retired = await api.post(
            f"/api/v1/clinical-concepts/{concept_id}/retire",
            headers=headers,
        )
        assert retired.status_code == 200
        assert retired.json()["active"] is False

        active_catalog = await api.get("/api/v1/patient-fact-catalog", headers=headers)
        assert all(item["key"] != "c_reactive_protein" for item in active_catalog.json()["entries"])
        detail = await api.get(f"/api/v1/patients/{patient.json()['id']}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["facts"][0]["concept"] == "c_reactive_protein"
    finally:
        async with get_session_factory()() as session:
            if concept_id is not None:
                await session.execute(
                    delete(ClinicalConcept).where(ClinicalConcept.id == concept_id)
                )
            await session.execute(delete(User).where(User.email == email))
            await session.commit()


async def test_catalog_admin_can_review_a_suggestion_before_saving_it(
    api: AsyncClient,
    app: FastAPI,
) -> None:
    suffix = uuid.uuid4().hex
    email = f"catalog-suggestion-{suffix}@example.com"
    headers = await register(api, email)
    async with get_session_factory()() as session:
        await session.execute(
            update(User).where(User.email == email).values(is_catalog_admin=True)
        )
        await session.commit()

    class FakeSuggestions:
        async def suggest(self, *, query: str, **_: object) -> TerminologySuggestionResult:
            assert query == "metformin"
            return TerminologySuggestionResult(
                suggestions=[
                    TerminologySuggestionRead(
                        source="rxnorm",
                        code="6809",
                        display_label="metformin",
                        detail="RXNORM",
                    )
                ],
                unavailable_sources=[],
            )

    app.state.terminology_suggestions = FakeSuggestions()
    concept_id: str | None = None
    try:
        suggested = await api.get(
            "/api/v1/clinical-concepts/suggestions?query=metformin&fact_type=medication",
            headers=headers,
        )
        assert suggested.status_code == 200, suggested.text
        assert suggested.json()["suggestions"][0]["code"] == "6809"

        created = await api.post(
            "/api/v1/clinical-concepts",
            headers=headers,
            json={
                "display_label": "Metformin custom label",
                "fact_type": "medication",
                "terminology_system": "rxnorm",
                "terminology_code": "6809",
            },
        )
        assert created.status_code == 201, created.text
        concept_id = created.json()["id"]
        assert created.json()["terminology_system"] == "rxnorm"
        assert created.json()["terminology_code"] == "6809"
    finally:
        async with get_session_factory()() as session:
            if concept_id is not None:
                await session.execute(
                    delete(ClinicalConcept).where(ClinicalConcept.id == concept_id)
                )
            await session.execute(delete(User).where(User.email == email))
            await session.commit()
