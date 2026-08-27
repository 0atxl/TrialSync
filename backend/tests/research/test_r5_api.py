from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete

from trialsync.db.models import User
from trialsync.db.session import get_session_factory
from trialsync.research.risk.artifacts import (
    RiskContribution,
    RiskModelDescriptor,
    RiskPredictionOutput,
)
from trialsync.research.risk.features import FEATURE_NAMES

pytestmark = pytest.mark.anyio


class StubArtifacts:
    def descriptor(self) -> RiskModelDescriptor:
        return RiskModelDescriptor(
            model_id="dropout-xgboost-05-v1",
            name="dropout-xgboost",
            version="1",
            alias="r5_runtime",
            candidate_id="xgboost-05",
            threshold=0.21347740292549133,
            horizon_day=90,
            dataset_version="r3-dataset-contract-v1",
            dataset_checksum="746a6f63a02c0948205b53767801a775b16fe35d08aafccc522e3fd975e35982",
            feature_schema_version="r4-day30-features-v1",
            feature_schema_checksum=(
                "6d0fe2185247cda50f69fc7954bf958c1c61c5cb4ef160cd34b445170236ca83"
            ),
            band_policy_version="r5-risk-bands-v1",
            artifact_checksum=("ab2377e9a6a81fa39d77805f0f2fe3bfc09b2c957fcd934b62b7a205051b5de7"),
            metrics={"test_auroc": 0.6807348560079444},
        )

    def predict(self, snapshot: Any, *, top_k: int = 5) -> RiskPredictionOutput:
        assert tuple(snapshot.values) == FEATURE_NAMES
        probability = 0.4 + float(snapshot.values["missed_dose_rate"]) * 0.2
        return RiskPredictionOutput(
            probability=probability,
            contributions=(
                RiskContribution(
                    feature="missed_visit_rate",
                    value=snapshot.values["missed_visit_rate"],
                    shap_value=0.18,
                    direction="higher",
                ),
            )[:top_k],
        )


@pytest.fixture
async def api(app: FastAPI) -> AsyncIterator[AsyncClient]:
    app.state.research_risk = StubArtifacts()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


@pytest.fixture
async def email_prefix() -> AsyncIterator[str]:
    prefix = f"r5-{uuid.uuid4()}"
    yield prefix
    async with get_session_factory()() as session:
        await session.execute(delete(User).where(User.email.like(f"{prefix}%")))
        await session.commit()


async def _register(api: AsyncClient, email: str) -> Response:
    return await api.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "Research user", "password": "CorrectHorse123"},
    )


def _auth(response: Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _saved_screening(api: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    patient = await api.post(
        "/api/v1/patients",
        headers=headers,
        json={
            "external_id": f"R5-{uuid.uuid4()}",
            "display_name": "Research participant",
            "date_of_birth": "1980-01-01",
            "sex": "female",
        },
    )
    assert patient.status_code == 201, patient.text
    trial = await api.post(
        "/api/v1/trials",
        headers=headers,
        json={
            "registry_id": f"R5-TRIAL-{uuid.uuid4()}",
            "title": "Respiratory retention study",
            "condition": "Asthma",
        },
    )
    assert trial.status_code == 201, trial.text
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
            "source_text": "Adults are eligible",
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
    screening = await api.post(
        "/api/v1/screenings",
        headers=headers,
        json={
            "patient_id": patient.json()["id"],
            "trial_version_id": version_id,
            "screening_date": "2026-08-20",
        },
    )
    assert screening.status_code == 201, screening.text
    return screening.json()


async def test_day30_summary_builds_prediction_and_exact_scenarios(
    api: AsyncClient, email_prefix: str
) -> None:
    first = await _register(api, f"{email_prefix}-a@example.com")
    second = await _register(api, f"{email_prefix}-b@example.com")
    headers = _auth(first)
    screening = await _saved_screening(api, headers)
    screening_id = screening["id"]
    initial_state = screening["overall_state"]

    hidden = await api.get(
        f"/api/v1/research/risk/screenings/{screening_id}/context", headers=_auth(second)
    )
    assert hidden.status_code == 404
    unlinked = await api.get(
        f"/api/v1/research/risk/screenings/{screening_id}/context", headers=headers
    )
    assert unlinked.status_code == 200
    assert unlinked.json()["status"] == "unlinked"
    initial_worklist = await api.get("/api/v1/research/risk/worklist", headers=headers)
    assert initial_worklist.status_code == 200, initial_worklist.text
    assert initial_worklist.json()[0]["workflow_status"] == "not_started"
    assert initial_worklist.json()[0]["estimate"] is None

    enrollment = await api.post(
        f"/api/v1/research/screenings/{screening_id}/enrollment",
        headers=headers,
        json={
            "enrollment_date": "2026-08-20",
            "baseline": {
                "site_region": {"value": "west", "source": "Enrollment form"},
                "treatment_arm": {"value": "active", "source": "Enrollment form"},
                "baseline_functional_severity": {
                    "value": 0.3,
                    "source": "Enrollment form",
                },
                "patient_reported_burden": {"value": 0.2, "source": "Enrollment form"},
                "baseline_treatment_burden": {"value": 2, "source": "Enrollment form"},
                "travel_access_burden": {"value": 2, "source": "Enrollment form"},
                "support_availability": {"value": 1, "source": "Enrollment form"},
            },
        },
    )
    assert enrollment.status_code == 201, enrollment.text
    enrollment_id = enrollment.json()["id"]
    assert enrollment.json()["missing_baseline_features"] == []

    summary = {
        "scheduled_doses": 10,
        "missed_doses": 2,
        "scheduled_visits": 2,
        "missed_visits": 1,
        "delayed_visits": 0,
        "total_visit_delay_days": 0,
        "expected_assessments": 10,
        "completed_assessments": 9,
        "latest_functional_severity": 0.4,
        "latest_assessment_day": 30,
        "adverse_event_count": 0,
        "adverse_event_burden": 0,
    }
    follow_up = await api.post(
        f"/api/v1/research/enrollments/{enrollment_id}/day30-summary",
        headers=headers,
        json=summary,
    )
    assert follow_up.status_code == 201, follow_up.text
    assert follow_up.json()["status"] == "ready"
    assert follow_up.json()["input_summary"] == summary
    features = {item["name"]: item["value"] for item in follow_up.json()["features"]}
    assert features["missed_dose_rate"] == pytest.approx(0.2)
    assert features["missed_visit_rate"] == pytest.approx(0.5)
    assert features["measurement_missingness_rate"] == pytest.approx(0.1)
    assert features["adverse_event_count"] == 0

    predicted = await api.post(
        "/api/v1/research/risk/predictions",
        headers=headers,
        json={"follow_up_snapshot_id": follow_up.json()["id"]},
    )
    assert predicted.status_code == 201, predicted.text
    assert predicted.json()["probability"] == pytest.approx(0.44)
    assert predicted.json()["model"]["candidate_id"] == "xgboost-05"
    assert predicted.json()["horizon_day"] == 90
    predicted_worklist = await api.get("/api/v1/research/risk/worklist", headers=headers)
    assert predicted_worklist.status_code == 200, predicted_worklist.text
    assert predicted_worklist.json()[0]["workflow_status"] == "predicted"
    assert predicted_worklist.json()[0]["next_action"] == "view_prediction"
    assert predicted_worklist.json()[0]["estimate"]["probability"] == pytest.approx(0.44)
    unchanged = await api.get(f"/api/v1/screenings/{screening_id}", headers=headers)
    assert unchanged.json()["overall_state"] == initial_state

    overview = await api.get(
        f"/api/v1/research/trial-overview/{screening['trial_version_id']}", headers=headers
    )
    assert overview.status_code == 200, overview.text
    assert overview.json()["retention"]["linked_predictions"] == 1

    scenarios = await api.post(
        "/api/v1/research/risk/scenarios",
        headers=headers,
        json={"follow_up_snapshot_id": follow_up.json()["id"]},
    )
    assert scenarios.status_code == 200, scenarios.text
    assert [point["missed_doses"] for point in scenarios.json()["points"]] == [2, 3, 4]
    assert [point["scheduled_doses"] for point in scenarios.json()["points"]] == [10, 11, 12]
    assert [point["probability"] for point in scenarios.json()["points"]] == pytest.approx(
        [0.44, 0.4 + (3 / 11) * 0.2, 0.4 + (4 / 12) * 0.2]
    )


async def test_day30_summary_rejects_implicit_or_impossible_counts(
    api: AsyncClient, email_prefix: str
) -> None:
    registered = await _register(api, f"{email_prefix}-validation@example.com")
    headers = _auth(registered)
    screening = await _saved_screening(api, headers)
    enrollment = await api.post(
        f"/api/v1/research/screenings/{screening['id']}/enrollment",
        headers=headers,
        json={
            "enrollment_date": "2026-08-20",
            "baseline": {
                "site_region": {"value": "west", "source": "Enrollment form"},
                "treatment_arm": {"value": "active", "source": "Enrollment form"},
                "baseline_functional_severity": {"value": 0.3, "source": "Enrollment form"},
                "patient_reported_burden": {"value": 0.2, "source": "Enrollment form"},
                "baseline_treatment_burden": {"value": 2, "source": "Enrollment form"},
                "travel_access_burden": {"value": 2, "source": "Enrollment form"},
                "support_availability": {"value": 1, "source": "Enrollment form"},
            },
        },
    )
    enrollment_id = enrollment.json()["id"]
    missing = await api.post(
        f"/api/v1/research/enrollments/{enrollment_id}/day30-summary",
        headers=headers,
        json={"scheduled_doses": 8, "missed_doses": 8},
    )
    assert missing.status_code == 422
    impossible = await api.post(
        f"/api/v1/research/enrollments/{enrollment_id}/day30-summary",
        headers=headers,
        json={
            "scheduled_doses": 8,
            "missed_doses": 9,
            "scheduled_visits": 1,
            "missed_visits": 0,
            "delayed_visits": 0,
            "total_visit_delay_days": 0,
            "expected_assessments": 1,
            "completed_assessments": 1,
            "latest_functional_severity": 0.4,
            "latest_assessment_day": 30,
            "adverse_event_count": 0,
            "adverse_event_burden": 0,
        },
    )
    assert impossible.status_code == 422
