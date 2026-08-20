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

    def predict(self, snapshot: Any) -> RiskPredictionOutput:
        assert tuple(snapshot.values) == FEATURE_NAMES
        return RiskPredictionOutput(
            probability=0.64,
            contributions=(
                RiskContribution(
                    feature="missed_visit_rate",
                    value=snapshot.values["missed_visit_rate"],
                    shap_value=0.18,
                    direction="higher",
                ),
            ),
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


async def _event(
    api: AsyncClient,
    headers: dict[str, str],
    enrollment_id: str,
    route: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    response = await api.post(
        f"/api/v1/research/enrollments/{enrollment_id}/{route}",
        headers=headers,
        json={"source_label": "Day-30 follow-up", **payload},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_platform_events_build_prediction_without_training_row_lookup(
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

    empty_follow_up = await api.post(
        f"/api/v1/research/enrollments/{enrollment_id}/follow-up-snapshots",
        headers=headers,
        json={
            "dose_record_complete": True,
            "visit_record_complete": True,
            "measurement_record_complete": True,
            "adverse_event_record_complete": True,
        },
    )
    assert empty_follow_up.status_code == 201, empty_follow_up.text
    assert empty_follow_up.json()["status"] == "incomplete"
    assert "missed_dose_rate" in empty_follow_up.json()["missing_features"]
    assert "missed_visit_rate" in empty_follow_up.json()["missing_features"]
    assert empty_follow_up.json()["features"][-2]["value"] == 0

    dose = await _event(
        api,
        headers,
        enrollment_id,
        "dose-events",
        {
            "medication_concept": "study_treatment",
            "scheduled_date": "2026-09-10",
            "scheduled_count": 10,
            "administered_count": 9,
            "status": "partially_administered",
        },
    )
    await _event(
        api,
        headers,
        enrollment_id,
        "dose-events",
        {
            "medication_concept": "study_treatment",
            "scheduled_date": "2026-09-10",
            "scheduled_count": 10,
            "administered_count": 8,
            "status": "partially_administered",
            "supersedes_event_id": dose["id"],
            "correction_reason": "Reconciled against the reviewed dose log",
        },
    )
    event_history = await api.get(
        f"/api/v1/research/enrollments/{enrollment_id}/events", headers=headers
    )
    assert event_history.status_code == 200, event_history.text
    assert [item["is_superseded"] for item in event_history.json()["dose_events"]] == [
        True,
        False,
    ]
    await _event(
        api,
        headers,
        enrollment_id,
        "visit-events",
        {
            "visit_type": "follow_up",
            "scheduled_date": "2026-08-30",
            "completed_date": "2026-08-30",
            "status": "completed",
        },
    )
    await _event(
        api,
        headers,
        enrollment_id,
        "visit-events",
        {
            "visit_type": "follow_up",
            "scheduled_date": "2026-09-09",
            "status": "missed",
        },
    )
    for observed_date, value in (("2026-08-20", 0.3), ("2026-09-19", 0.4)):
        await _event(
            api,
            headers,
            enrollment_id,
            "measurements",
            {
                "concept": "functional_severity",
                "value_numeric": value,
                "unit": "score",
                "observed": True,
                "observed_date": observed_date,
            },
        )
    for day in range(8):
        await _event(
            api,
            headers,
            enrollment_id,
            "measurements",
            {
                "concept": f"follow_up_measure_{day}",
                "value_numeric": 1.0 if day < 7 else None,
                "unit": "score",
                "observed": day < 7,
                "observed_date": f"2026-09-{day + 1:02d}",
            },
        )

    follow_up = await api.post(
        f"/api/v1/research/enrollments/{enrollment_id}/follow-up-snapshots",
        headers=headers,
        json={
            "dose_record_complete": True,
            "visit_record_complete": True,
            "measurement_record_complete": True,
            "adverse_event_record_complete": True,
        },
    )
    assert follow_up.status_code == 201, follow_up.text
    assert follow_up.json()["status"] == "ready"
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
    assert predicted.json()["probability"] == 0.64
    assert predicted.json()["model"]["candidate_id"] == "xgboost-05"
    assert predicted.json()["horizon_day"] == 90
    unchanged = await api.get(f"/api/v1/screenings/{screening_id}", headers=headers)
    assert unchanged.json()["overall_state"] == initial_state

    overview = await api.get(
        f"/api/v1/research/trial-overview/{screening['trial_version_id']}", headers=headers
    )
    assert overview.status_code == 200, overview.text
    assert overview.json()["retention"]["linked_predictions"] == 1
