from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete, select, update

from trialsync.db.models import (
    ResearchEnrollmentBaselineRevision,
    ResearchFollowUpSnapshot,
    ResearchPrediction,
    User,
)
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
            model_id="dropout-xgboost-06-v1",
            name="dropout-xgboost",
            version="2",
            alias="r5_runtime",
            candidate_id="xgboost-06",
            threshold=0.445,
            horizon_day=90,
            dataset_version="r3-dataset-contract-v2",
            dataset_checksum="a2eb65e5a0396553366808dbc1bcd93f86dfe5f282bac0c522e762c3d961ba3d",
            feature_schema_version="r4-day30-features-v2",
            feature_schema_checksum=(
                "b047a68c86a006179856824f8c1e92373759f08abb99c994c55084f3834d63d6"
            ),
            band_policy_version="r5-risk-bands-v1",
            artifact_checksum=("81cd6cd0836f3d6735ecc4173c88da6bf7c6f1fadda8fc827e2056e92ad9cb15"),
            metrics={"test_auroc": 0.8873525073746312},
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


async def _saved_screening(
    api: AsyncClient,
    headers: dict[str, str],
    *,
    condition: str = "Asthma",
) -> dict[str, Any]:
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
            "title": f"{condition} retention study",
            "condition": condition,
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
        "longest_missed_dose_streak": 1,
        "scheduled_visits": 2,
        "missed_visits": 1,
        "longest_missed_visit_streak": 1,
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
    assert predicted.json()["model"]["candidate_id"] == "xgboost-06"
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
    complete = {
        "scheduled_doses": 8,
        "missed_doses": 2,
        "longest_missed_dose_streak": 1,
        "scheduled_visits": 2,
        "missed_visits": 1,
        "longest_missed_visit_streak": 1,
        "delayed_visits": 0,
        "total_visit_delay_days": 0,
        "expected_assessments": 1,
        "completed_assessments": 1,
        "latest_functional_severity": 0.4,
        "latest_assessment_day": 30,
        "adverse_event_count": 0,
        "adverse_event_burden": 0,
    }
    missing_streak = dict(complete)
    del missing_streak["longest_missed_dose_streak"]
    missing_streak_response = await api.post(
        f"/api/v1/research/enrollments/{enrollment_id}/day30-summary",
        headers=headers,
        json=missing_streak,
    )
    assert missing_streak_response.status_code == 422
    inconsistent_streak = await api.post(
        f"/api/v1/research/enrollments/{enrollment_id}/day30-summary",
        headers=headers,
        json={**complete, "longest_missed_visit_streak": 2},
    )
    assert inconsistent_streak.status_code == 422
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
            "longest_missed_dose_streak": 1,
            "scheduled_visits": 1,
            "missed_visits": 0,
            "longest_missed_visit_streak": 0,
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


async def test_enrollment_correction_is_append_only_and_requires_a_new_prediction(
    api: AsyncClient, email_prefix: str
) -> None:
    registered = await _register(api, f"{email_prefix}-correction@example.com")
    headers = _auth(registered)
    screening = await _saved_screening(api, headers)
    screening_id = screening["id"]
    baseline = {
        "site_region": {"value": "west", "source": "Enrollment form"},
        "treatment_arm": {"value": "active", "source": "Enrollment form"},
        "baseline_functional_severity": {"value": 0.3, "source": "Enrollment form"},
        "patient_reported_burden": {"value": 0.2, "source": "Enrollment form"},
        "baseline_treatment_burden": {"value": 2, "source": "Enrollment form"},
        "travel_access_burden": {"value": 2, "source": "Enrollment form"},
        "support_availability": {"value": 1, "source": "Enrollment form"},
    }
    missing_put = await api.put(
        f"/api/v1/research/screenings/{screening_id}/enrollment",
        headers=headers,
        json={"enrollment_date": "2026-08-20", "baseline": baseline},
    )
    assert missing_put.status_code == 404

    created = await api.post(
        f"/api/v1/research/screenings/{screening_id}/enrollment",
        headers=headers,
        json={"enrollment_date": "2026-08-20", "baseline": baseline},
    )
    assert created.status_code == 201, created.text
    assert created.json()["feature_contract_version"] == "r4-day30-features-v2"
    duplicate = await api.post(
        f"/api/v1/research/screenings/{screening_id}/enrollment",
        headers=headers,
        json={"enrollment_date": "2026-08-20", "baseline": baseline},
    )
    assert duplicate.status_code == 409
    enrollment_id = created.json()["id"]

    summary = {
        "scheduled_doses": 10,
        "missed_doses": 2,
        "longest_missed_dose_streak": 1,
        "scheduled_visits": 2,
        "missed_visits": 1,
        "longest_missed_visit_streak": 1,
        "delayed_visits": 0,
        "total_visit_delay_days": 0,
        "expected_assessments": 10,
        "completed_assessments": 9,
        "latest_functional_severity": 0.4,
        "latest_assessment_day": 30,
        "adverse_event_count": 0,
        "adverse_event_burden": 0,
    }
    first_follow_up = await api.post(
        f"/api/v1/research/enrollments/{enrollment_id}/day30-summary",
        headers=headers,
        json=summary,
    )
    assert first_follow_up.status_code == 201, first_follow_up.text
    first_prediction = await api.post(
        "/api/v1/research/risk/predictions",
        headers=headers,
        json={"follow_up_snapshot_id": first_follow_up.json()["id"]},
    )
    assert first_prediction.status_code == 201, first_prediction.text
    legacy_summary = dict(summary)
    legacy_summary.pop("longest_missed_dose_streak")
    legacy_summary.pop("longest_missed_visit_streak")
    async with get_session_factory()() as session:
        await session.execute(
            update(ResearchFollowUpSnapshot)
            .where(ResearchFollowUpSnapshot.id == uuid.UUID(first_follow_up.json()["id"]))
            .values(input_summary_json=legacy_summary)
        )
        await session.commit()
    eligibility_before = await api.get(f"/api/v1/screenings/{screening_id}", headers=headers)

    corrected_baseline = {
        **baseline,
        "baseline_functional_severity": {"value": 0.35, "source": "Corrected source"},
    }
    corrected = await api.put(
        f"/api/v1/research/screenings/{screening_id}/enrollment",
        headers=headers,
        json={"enrollment_date": "2026-08-21", "baseline": corrected_baseline},
    )
    assert corrected.status_code == 200, corrected.text
    baseline_by_name = {item["name"]: item for item in corrected.json()["baseline"]}
    assert baseline_by_name["baseline_functional_severity"]["value"] == pytest.approx(0.35)

    follow_ups = await api.get(
        f"/api/v1/research/enrollments/{enrollment_id}/follow-up-snapshots",
        headers=headers,
    )
    assert follow_ups.status_code == 200
    assert len(follow_ups.json()) == 2
    stored_first = next(
        item for item in follow_ups.json() if item["id"] == first_follow_up.json()["id"]
    )
    assert stored_first["feature_snapshot_hash"] == first_follow_up.json()["feature_snapshot_hash"]
    latest = follow_ups.json()[0]
    assert latest["id"] != first_follow_up.json()["id"]
    assert latest["feature_snapshot_hash"] != first_follow_up.json()["feature_snapshot_hash"]
    assert latest["feature_schema_version"] == "r4-day30-features-v2"
    assert latest["input_summary"]["longest_missed_dose_streak"] == 1
    assert latest["input_summary"]["longest_missed_visit_streak"] == 1

    worklist = await api.get("/api/v1/research/risk/worklist", headers=headers)
    assert worklist.json()[0]["workflow_status"] == "ready"
    assert worklist.json()[0]["estimate"] is None
    main_overview = await api.get("/api/v1/overview", headers=headers)
    assert main_overview.status_code == 200, main_overview.text
    assert main_overview.json()["dropout"]["counts"] == {
        "not_started": 0,
        "information_needed": 0,
        "ready": 1,
        "predicted": 0,
    }
    trial_overview = await api.get(
        f"/api/v1/research/trial-overview/{screening['trial_version_id']}", headers=headers
    )
    assert trial_overview.status_code == 200, trial_overview.text
    assert trial_overview.json()["retention"]["linked_predictions"] == 0
    assert trial_overview.json()["retention"]["unlinked_eligible"] == 1
    assert trial_overview.json()["retention"]["risk_bands"] == {
        "lower": 0,
        "near_threshold": 0,
        "higher": 0,
    }
    second_prediction = await api.post(
        "/api/v1/research/risk/predictions",
        headers=headers,
        json={"follow_up_snapshot_id": latest["id"]},
    )
    assert second_prediction.status_code == 201, second_prediction.text
    assert second_prediction.json()["id"] != first_prediction.json()["id"]

    old_prediction = await api.get(
        f"/api/v1/research/risk/predictions/{first_prediction.json()['id']}", headers=headers
    )
    assert (
        old_prediction.json()["feature_snapshot_hash"]
        == first_prediction.json()["feature_snapshot_hash"]
    )
    assert old_prediction.json()["follow_up_snapshot_id"] == first_follow_up.json()["id"]

    eligibility_after = await api.get(f"/api/v1/screenings/{screening_id}", headers=headers)
    assert eligibility_after.json()["overall_state"] == eligibility_before.json()["overall_state"]
    assert eligibility_after.json()["counts"] == eligibility_before.json()["counts"]
    assert eligibility_after.json()["evaluations"] == eligibility_before.json()["evaluations"]

    async with get_session_factory()() as session:
        revisions = list(
            await session.scalars(
                select(ResearchEnrollmentBaselineRevision)
                .where(
                    ResearchEnrollmentBaselineRevision.research_enrollment_id
                    == uuid.UUID(enrollment_id)
                )
                .order_by(ResearchEnrollmentBaselineRevision.created_at)
            )
        )
        assert len(revisions) == 2
        assert revisions[0].baseline_values_json["baseline_functional_severity"] == 0.3
        assert revisions[1].supersedes_revision_id == revisions[0].id
        predictions = list(
            await session.scalars(
                select(ResearchPrediction).where(
                    ResearchPrediction.research_enrollment_id == uuid.UUID(enrollment_id)
                )
            )
        )
        for prediction in predictions:
            snapshot = await session.get(ResearchFollowUpSnapshot, prediction.follow_up_snapshot_id)
            assert snapshot is not None
            assert prediction.feature_snapshot_hash == snapshot.feature_snapshot_hash


async def test_streaks_are_explicit_and_unsupported_conditions_do_not_change_eligibility(
    api: AsyncClient, email_prefix: str
) -> None:
    registered = await _register(api, f"{email_prefix}-unsupported@example.com")
    headers = _auth(registered)
    unsupported = await _saved_screening(api, headers, condition="Migraine")
    before = await api.get(f"/api/v1/screenings/{unsupported['id']}", headers=headers)
    capabilities = await api.get(
        f"/api/v1/research/screenings/{unsupported['id']}/capabilities", headers=headers
    )
    assert capabilities.status_code == 200
    assert capabilities.json()["dropout_prediction"]["status"] == "unsupported_model_input"
    context = await api.get(
        f"/api/v1/research/risk/screenings/{unsupported['id']}/context", headers=headers
    )
    assert context.json()["status"] == "unsupported_model_input"
    rejected = await api.post(
        f"/api/v1/research/screenings/{unsupported['id']}/enrollment",
        headers=headers,
        json={"enrollment_date": "2026-08-20", "baseline": {}},
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "RESEARCH_MODEL_INPUT_UNSUPPORTED"
    after = await api.get(f"/api/v1/screenings/{unsupported['id']}", headers=headers)
    assert after.json()["overall_state"] == before.json()["overall_state"]
    assert after.json()["evaluations"] == before.json()["evaluations"]
