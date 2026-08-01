from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from io import BytesIO

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from pypdf import PdfReader
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

import trialsync.api.screenings as screening_api
from trialsync.db.models import PatientSnapshot, Screening, ScreeningBatch, User
from trialsync.db.session import get_session_factory
from trialsync.reports import (
    ScreeningReportCounts,
    ScreeningReportCriterion,
    ScreeningReportDocument,
    ScreeningReportEvidence,
    ScreeningReportMissingInformation,
    ScreeningReportPatientSnapshot,
    ScreeningReportTrial,
    assemble_screening_report,
    render_screening_report_pdf,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


@pytest.fixture
async def email_prefix() -> AsyncIterator[str]:
    prefix = f"phase4-{uuid.uuid4()}"
    yield prefix
    async with get_session_factory()() as session:
        await session.execute(delete(User).where(User.email.like(f"{prefix}%")))
        await session.commit()


async def register(api: AsyncClient, email: str) -> Response:
    return await api.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "Demo Researcher", "password": "CorrectHorse123"},
    )


def auth(response: Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def patient(api: AsyncClient, headers: dict[str, str], number: int) -> str:
    response = await api.post(
        "/api/v1/patients",
        headers=headers,
        json={
            "external_id": f"SYN-{number}",
            "display_name": f"Synthetic {number}",
            "date_of_birth": "1990-07-15",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def approved_trial(api: AsyncClient, headers: dict[str, str], number: int = 1) -> str:
    _, version_id = await approved_trial_record(api, headers, number)
    return version_id


async def approved_trial_record(
    api: AsyncClient, headers: dict[str, str], number: int = 1
) -> tuple[str, str]:
    trial = await api.post(
        "/api/v1/trials",
        headers=headers,
        json={
            "registry_id": f"SYN-TRIAL-{number}",
            "title": "Synthetic age study",
            "condition": "Synthetic condition",
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
            "source_text": "Age 18 to 75 years at screening",
            "normalized_rule": {
                "op": "between",
                "fact": "demographic.age",
                "min": 18,
                "max": 75,
                "unit": "year",
            },
        },
    )
    assert criterion.status_code == 201
    approved = await api.put(
        f"/api/v1/trials/{trial_id}/versions/{version_id}",
        headers=headers,
        json={"version": 1, "status": "approved"},
    )
    assert approved.status_code == 200
    return trial_id, version_id


async def approved_sex_trial(api: AsyncClient, headers: dict[str, str]) -> str:
    trial = await api.post(
        "/api/v1/trials",
        headers=headers,
        json={
            "registry_id": "SYN-TRIAL-SEX",
            "title": "Synthetic demographic study",
            "condition": "Synthetic condition",
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
            "source_text": "Female participants",
            "normalized_rule": {
                "op": "concept_is",
                "fact_type": "demographic",
                "concept": "female",
            },
        },
    )
    assert criterion.status_code == 201
    approved = await api.put(
        f"/api/v1/trials/{trial_id}/versions/{version_id}",
        headers=headers,
        json={"version": 1, "status": "approved"},
    )
    assert approved.status_code == 200
    return version_id


async def screen(
    api: AsyncClient,
    headers: dict[str, str],
    patient_id: str,
    version_id: str,
    screening_date: str = "2026-07-15",
) -> dict[str, object]:
    response = await api.post(
        "/api/v1/screenings",
        headers=headers,
        json={
            "patient_id": patient_id,
            "trial_version_id": version_id,
            "screening_date": screening_date,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_screening_persists_evidence_and_is_immutable_after_edits(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient_id = await patient(api, headers, 1)
    trial_id, version_id = await approved_trial_record(api, headers)

    saved = await screen(api, headers, patient_id, version_id)
    assert saved["overall_state"] == "potentially_eligible"
    assert saved["screening_date"] == "2026-07-15"
    assert saved["counts"] == {"pass_count": 1, "fail_count": 0, "unknown_count": 0}
    assert saved["evaluations"][0]["evidence"][0]["fact_id"] == "date_of_birth"
    assert saved["patient_snapshot"] == {
        "id": saved["patient_snapshot_id"],
        "external_id": "SYN-1",
        "display_name": "Synthetic 1",
        "date_of_birth": "1990-07-15",
        "sex": None,
        "facts": [],
    }
    assert saved["trial_version"] == {
        "registry_id": "SYN-TRIAL-1",
        "title": "Synthetic age study",
        "version": 1,
    }
    assert saved["evaluations"][0]["criterion_source_text"] == "Age 18 to 75 years at screening"

    current_patient = await api.get(f"/api/v1/patients/{patient_id}", headers=headers)
    changed = await api.patch(
        f"/api/v1/patients/{patient_id}",
        headers=headers,
        json={
            "date_of_birth": "2015-07-15",
            "expected_updated_at": current_patient.json()["updated_at"],
        },
    )
    assert changed.status_code == 200
    historical = await api.get(f"/api/v1/screenings/{saved['id']}", headers=headers)
    assert historical.status_code == 200
    assert historical.json()["overall_state"] == "potentially_eligible"
    assert historical.json()["patient_snapshot_id"] == saved["patient_snapshot_id"]
    assert historical.json()["patient_snapshot"]["display_name"] == "Synthetic 1"

    renamed_trial = await api.patch(
        f"/api/v1/trials/{trial_id}", headers=headers, json={"title": "Renamed current trial"}
    )
    assert renamed_trial.status_code == 200
    historical_after_trial_edit = await api.get(
        f"/api/v1/screenings/{saved['id']}", headers=headers
    )
    assert historical_after_trial_edit.json()["trial_version"]["title"] == "Synthetic age study"

    deleted_patient = await api.delete(f"/api/v1/patients/{patient_id}", headers=headers)
    assert deleted_patient.status_code == 204
    assert (await api.get(f"/api/v1/patients/{patient_id}", headers=headers)).status_code == 404
    blocked_trial_delete = await api.delete(f"/api/v1/trials/{trial_id}", headers=headers)
    assert blocked_trial_delete.status_code == 409
    assert blocked_trial_delete.json()["error"]["code"] == "TRIAL_HAS_SCREENING_HISTORY"
    assert (await api.get(f"/api/v1/screenings/{saved['id']}", headers=headers)).status_code == 200


async def test_screening_is_deterministic_for_explicit_date(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient_id = await patient(api, headers, 1)
    version_id = await approved_trial(api, headers)

    first = await screen(api, headers, patient_id, version_id)
    second = await screen(api, headers, patient_id, version_id)

    assert first["patient_snapshot_id"] == second["patient_snapshot_id"]
    assert first["overall_state"] == second["overall_state"]
    assert first["counts"] == second["counts"]
    first_evaluation = {key: value for key, value in first["evaluations"][0].items() if key != "id"}
    second_evaluation = {
        key: value for key, value in second["evaluations"][0].items() if key != "id"
    }
    assert first_evaluation == second_evaluation


async def test_patient_profile_sex_is_snapshotted_as_demographic_evidence(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    created = await api.post(
        "/api/v1/patients",
        headers=headers,
        json={
            "external_id": "SYN-SEX",
            "display_name": "Synthetic demographic case",
            "sex": "female",
        },
    )
    version_id = await approved_sex_trial(api, headers)

    saved = await screen(api, headers, created.json()["id"], version_id)

    assert saved["overall_state"] == "potentially_eligible"
    assert saved["evaluations"][0]["evidence"][0]["fact_id"] == "demographic.sex"


async def test_unknown_round_trips_and_user_ownership_applies(
    api: AsyncClient, email_prefix: str
) -> None:
    first = await register(api, f"{email_prefix}-a@example.com")
    second = await register(api, f"{email_prefix}-b@example.com")
    headers = auth(first)
    patient_id = await patient(api, headers, 1)
    trial_id = await approved_trial(api, headers)
    saved = await screen(api, headers, patient_id, trial_id)
    assert saved["evaluations"][0]["result"] == "pass"
    hidden = await api.get(f"/api/v1/screenings/{saved['id']}", headers=auth(second))
    assert hidden.status_code == 404

    no_dob = await api.post(
        "/api/v1/patients",
        headers=headers,
        json={"external_id": "SYN-UNKNOWN", "display_name": "Unknown age"},
    )
    unknown = await screen(api, headers, no_dob.json()["id"], trial_id)
    assert unknown["overall_state"] == "needs_review"
    detail = await api.get(f"/api/v1/screenings/{unknown['id']}", headers=headers)
    evaluation = detail.json()["evaluations"][0]
    assert evaluation["result"] == "unknown"
    assert evaluation["missing_information"][0]["fact"] == "date_of_birth"


async def test_batch_deduplicates_pairs_and_matches_single_result(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    version_ids = [await approved_trial(api, headers, number) for number in (1, 2)]
    patient_ids = [await patient(api, headers, number) for number in (1, 2, 3)]
    singles: dict[tuple[str, str], dict[str, object]] = {}
    snapshots: list[str] = []
    for patient_id in patient_ids:
        for version_id in version_ids:
            saved = await screen(api, headers, patient_id, version_id)
            snapshot_id = str(saved["patient_snapshot_id"])
            singles[(snapshot_id, version_id)] = saved
            if snapshot_id not in snapshots:
                snapshots.append(snapshot_id)
    batch = await api.post(
        "/api/v1/screening-batches",
        headers=headers,
        json={
            "patient_snapshot_ids": [*snapshots, snapshots[0]],
            "trial_version_ids": [*version_ids, version_ids[0]],
            "screening_date": "2026-07-15",
        },
    )
    assert batch.status_code == 201, batch.text
    body = batch.json()
    assert body["pair_count"] == 6
    assert len(body["screenings"]) == 6
    assert body["state_counts"] == {
        "potentially_eligible": 6,
        "likely_ineligible": 0,
        "needs_review": 0,
    }
    assert body["unknown_criterion_count"] == 0
    assert {item["overall_state"] for item in body["screenings"]} == {"potentially_eligible"}
    for item in body["screenings"]:
        individual = singles[(item["patient_snapshot_id"], item["trial_version_id"])]
        stored = await api.get(f"/api/v1/screenings/{item['screening_id']}", headers=headers)
        assert stored.status_code == 200
        assert stored.json()["overall_state"] == individual["overall_state"]
        assert stored.json()["counts"] == individual["counts"]
        assert [
            {key: value for key, value in evaluation.items() if key != "id"}
            for evaluation in stored.json()["evaluations"]
        ] == [
            {key: value for key, value in evaluation.items() if key != "id"}
            for evaluation in individual["evaluations"]
        ]
    detail = await api.get(f"/api/v1/screening-batches/{body['id']}", headers=headers)
    assert detail.status_code == 200
    assert len(detail.json()["screenings"]) == 6


async def test_batch_accepts_unscreened_patients_and_creates_snapshots(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    version_id = await approved_trial(api, headers)
    patient_ids = [await patient(api, headers, number) for number in (1, 2)]

    assert (await api.get("/api/v1/screenings", headers=headers)).json() == []
    batch = await api.post(
        "/api/v1/screening-batches",
        headers=headers,
        json={
            "patient_ids": [*patient_ids, patient_ids[0]],
            "trial_version_ids": [version_id],
            "screening_date": "2026-07-15",
        },
    )

    assert batch.status_code == 201, batch.text
    assert batch.json()["pair_count"] == 2
    assert len(batch.json()["screenings"]) == 2
    assert {item["patient_snapshot"]["display_name"] for item in batch.json()["screenings"]} == {
        "Synthetic 1",
        "Synthetic 2",
    }


async def test_single_unexpected_failure_rolls_back_snapshot_and_screening(
    api: AsyncClient, email_prefix: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    patient_id = await patient(api, headers, 1)
    version_id = await approved_trial(api, headers)

    async def fail(*args: object, **kwargs: object) -> Screening:
        raise RuntimeError("synthetic single-screening failure")

    monkeypatch.setattr(screening_api, "run_and_store", fail)
    async with AsyncClient(
        transport=ASGITransport(app=api._transport.app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as failing_client:
        failed = await failing_client.post(
            "/api/v1/screenings",
            headers=headers,
            json={"patient_id": patient_id, "trial_version_id": version_id},
        )
    assert failed.status_code == 500
    async with get_session_factory()() as session:
        owner_id = uuid.UUID(account.json()["user"]["id"])
        assert await session.scalar(
            select(func.count()).select_from(Screening).where(Screening.owner_id == owner_id)
        ) == 0
        assert await session.scalar(
            select(func.count())
            .select_from(PatientSnapshot)
            .where(PatientSnapshot.owner_id == owner_id)
        ) == 0


async def test_batch_rejects_other_user_snapshot_before_writing(
    api: AsyncClient, email_prefix: str
) -> None:
    first = await register(api, f"{email_prefix}-a@example.com")
    second = await register(api, f"{email_prefix}-b@example.com")
    first_headers, second_headers = auth(first), auth(second)
    version_id = await approved_trial(api, first_headers)
    patient_id = await patient(api, first_headers, 1)
    snapshot_id = (await screen(api, first_headers, patient_id, version_id))["patient_snapshot_id"]
    rejected = await api.post(
        "/api/v1/screening-batches",
        headers=second_headers,
        json={"patient_snapshot_ids": [snapshot_id], "trial_version_ids": [version_id]},
    )
    assert rejected.status_code == 404
    second_user_id = uuid.UUID(second.json()["user"]["id"])
    first_user_id = uuid.UUID(first.json()["user"]["id"])
    async with get_session_factory()() as session:
        assert await session.scalar(
            select(func.count())
            .select_from(ScreeningBatch)
            .where(ScreeningBatch.owner_id == second_user_id)
        ) == 0
        assert await session.scalar(
            select(func.count())
            .select_from(Screening)
            .where(Screening.owner_id == first_user_id)
        ) == 1


async def test_twenty_by_one_batch_and_unexpected_failure_roll_back(
    api: AsyncClient, email_prefix: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    version_id = await approved_trial(api, headers)
    snapshot_ids = []
    for number in range(1, 21):
        patient_id = await patient(api, headers, number)
        saved = await screen(api, headers, patient_id, version_id)
        snapshot_ids.append(saved["patient_snapshot_id"])

    batch = await api.post(
        "/api/v1/screening-batches",
        headers=headers,
        json={"patient_snapshot_ids": snapshot_ids, "trial_version_ids": [version_id]},
    )
    assert batch.status_code == 201
    assert batch.json()["pair_count"] == 20
    assert len(batch.json()["screenings"]) == 20

    original = screening_api.run_and_store
    calls = 0

    async def fail_after_one(*args: object, **kwargs: object) -> Screening:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic persistence failure")
        return await original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(screening_api, "run_and_store", fail_after_one)
    async with AsyncClient(
        transport=ASGITransport(app=api._transport.app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as failing_client:
        failed = await failing_client.post(
            "/api/v1/screening-batches",
            headers=headers,
            json={"patient_snapshot_ids": snapshot_ids[:2], "trial_version_ids": [version_id]},
        )
    assert failed.status_code == 500
    async with get_session_factory()() as session:
        owner_id = uuid.UUID(account.json()["user"]["id"])
        batch_count = await session.scalar(
            select(func.count())
            .select_from(ScreeningBatch)
            .where(ScreeningBatch.owner_id == owner_id)
        )
        assert batch_count == 1


async def test_batch_rejects_empty_over_limit_and_nonexistent_inputs(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}@example.com")
    headers = auth(account)
    empty = await api.post(
        "/api/v1/screening-batches",
        headers=headers,
        json={"patient_snapshot_ids": [], "trial_version_ids": []},
    )
    assert empty.status_code == 422

    version_id = await approved_trial(api, headers)
    missing = await api.post(
        "/api/v1/screening-batches",
        headers=headers,
        json={"patient_snapshot_ids": [str(uuid.uuid4())], "trial_version_ids": [version_id]},
    )
    assert missing.status_code == 404

    deduplicated = await api.post(
        "/api/v1/screening-batches",
        headers=headers,
        json={"patient_snapshot_ids": [str(uuid.uuid4())] * 51, "trial_version_ids": [version_id]},
    )
    assert deduplicated.status_code == 404

    absolute_limit = await api.post(
        "/api/v1/screening-batches",
        headers=headers,
        json={
            "patient_snapshot_ids": [str(uuid.uuid4())] * 501,
            "trial_version_ids": [version_id],
        },
    )
    assert absolute_limit.status_code == 422

    over_limit = await api.post(
        "/api/v1/screening-batches",
        headers=headers,
        json={
            "patient_snapshot_ids": [str(uuid.uuid4()) for _ in range(51)],
            "trial_version_ids": [version_id],
        },
    )
    assert over_limit.status_code == 422


async def test_screening_routes_are_in_openapi(app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/openapi.json")
    paths = response.json()["paths"]
    assert "/api/v1/screenings" in paths
    assert "/api/v1/screenings/{screening_id}" in paths
    assert "/api/v1/screenings/{screening_id}/report.pdf" in paths
    assert "/api/v1/screening-batches" in paths
    assert "/api/v1/screening-batches/{batch_id}" in paths


async def test_canonical_screening_report_is_owner_scoped_and_contains_stored_evidence(
    api: AsyncClient, email_prefix: str
) -> None:
    first = await register(api, f"{email_prefix}-report-a@example.com")
    second = await register(api, f"{email_prefix}-report-b@example.com")
    headers = auth(first)
    patient_id = await patient(api, headers, 1)
    version_id = await approved_trial(api, headers)
    saved = await screen(api, headers, patient_id, version_id)

    report = await api.get(f"/api/v1/screenings/{saved['id']}/report.pdf", headers=headers)

    assert report.status_code == 200, report.text
    assert report.headers["content-type"] == "application/pdf"
    assert report.headers["content-disposition"] == (
        f'attachment; filename="trialsync-screening-{saved["id"]}.pdf"'
    )
    assert report.content.startswith(b"%PDF-")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(report.content)).pages)
    assert "Canonical screening report" in text
    assert "Synthetic 1" in text
    assert "Age 18 to 75 years at screening" in text
    assert "EVALUATED_TRUE" in text
    assert str(saved["patient_snapshot_id"]) in text
    assert str(saved["trial_version_id"]) in text

    unauthenticated = await api.get(f"/api/v1/screenings/{saved['id']}/report.pdf")
    assert unauthenticated.status_code == 401

    hidden = await api.get(
        f"/api/v1/screenings/{saved['id']}/report.pdf", headers=auth(second)
    )
    assert hidden.status_code == 404


def test_report_renderer_wraps_unicode_and_long_criteria_across_pages() -> None:
    generated_at = datetime(2026, 7, 15, 12, 30, tzinfo=UTC)
    long_source = "UNKNOWN-CRITERION-UNIQUE: " + (
        "Participants must have an observation ≥ 7.0 mL/min/1.73m² and a reviewed source label. "
        * 80
    )
    report = ScreeningReportDocument(
        schema_version="r1-report-v1",
        template_version="r1-pdf-template-v1",
        generated_at=generated_at,
        screening_id="00000000-0000-0000-0000-000000000001",
        created_at=generated_at,
        screening_date="2026-07-15",
        overall_state="needs_review",
        patient_snapshot=ScreeningReportPatientSnapshot(
            id="00000000-0000-0000-0000-000000000002",
            external_id="SYN-LONG",
            display_name="Synthetic Unicode Ada",
            date_of_birth=None,
            sex=None,
            snapshot_version="pd0-snapshot-v1",
            content_hash="a" * 64,
            as_of_date="2026-07-15",
        ),
        trial=ScreeningReportTrial(
            id="00000000-0000-0000-0000-000000000003",
            registry_id="SYN-LONG-TRIAL",
            title="A long synthetic protocol",
            version=1,
        ),
        engine_version="0.1.0",
        dsl_version="1.0",
        terminology_version="catalog-v1",
        unit_version="units-v1",
        counts=ScreeningReportCounts(pass_count=1, fail_count=1, unknown_count=1),
        criteria=[
            ScreeningReportCriterion(
                id="00000000-0000-0000-0000-000000000004",
                criterion_id="00000000-0000-0000-0000-000000000005",
                order=1,
                kind="inclusion",
                source_text=long_source,
                result="unknown",
                truth="unknown",
                reason_code="MISSING_FACT",
                canonical_explanation="The required evidence is not recorded.",
                missing_information=[
                    ScreeningReportMissingInformation(
                        fact="observation.egfr",
                        reason="MISSING_FACT",
                        detail="Add the measured value and effective date.",
                    )
                ],
                evidence=[
                    ScreeningReportEvidence(
                        fact_id="fact-1",
                        value="≥ 7.0",
                        unit="mL/min/1.73m²",
                        effective_date="2026-07-01",
                        source_label="Synthetic laboratory import",
                    )
                ],
                rejected_evidence=[
                    ScreeningReportEvidence(
                        fact_id="stale-fact-1",
                        value="6.1",
                        unit="mL/min/1.73m²",
                        effective_date="2020-01-01",
                        source_label="STALE-SOURCE-LABEL " * 25,
                    )
                ],
            ),
            ScreeningReportCriterion(
                id="00000000-0000-0000-0000-000000000006",
                criterion_id="00000000-0000-0000-0000-000000000007",
                order=2,
                kind="inclusion",
                source_text="PASS-CRITERION-UNIQUE",
                result="pass",
                truth="true",
                reason_code="EVALUATED_TRUE",
                canonical_explanation="The recorded evidence proves this inclusion criterion.",
            ),
            ScreeningReportCriterion(
                id="00000000-0000-0000-0000-000000000008",
                criterion_id="00000000-0000-0000-0000-000000000009",
                order=3,
                kind="exclusion",
                source_text="FAIL-CRITERION-UNIQUE",
                result="fail",
                truth="true",
                reason_code="EVALUATED_TRUE",
                canonical_explanation="The recorded evidence proves this exclusion criterion.",
            )
        ],
    )

    first = render_screening_report_pdf(report)
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(first)).pages)

    assert first.startswith(b"%PDF-")
    assert len(PdfReader(BytesIO(first)).pages) > 1
    assert "mL/min/1.73m" in text
    assert "observation.egfr" in text
    assert "MISSING_FACT" in text
    assert "Add the measured value and effective date." in text
    assert "STALE-SOURCE-LABEL" in text
    assert text.count("UNKNOWN-CRITERION-UNIQUE") == 1
    assert text.count("PASS-CRITERION-UNIQUE") == 1
    assert text.count("FAIL-CRITERION-UNIQUE") == 1


async def test_report_assembly_is_deterministic_for_a_stored_screening(
    api: AsyncClient, email_prefix: str
) -> None:
    account = await register(api, f"{email_prefix}-report-determinism@example.com")
    headers = auth(account)
    patient_id = await patient(api, headers, 1)
    version_id = await approved_trial(api, headers)
    saved = await screen(api, headers, patient_id, version_id)

    async with get_session_factory()() as session:
        stored = await session.scalar(
            select(Screening)
            .options(
                selectinload(Screening.patient_snapshot),
                selectinload(Screening.evaluations),
            )
            .where(Screening.id == saved["id"])
        )
        assert stored is not None
        generated_at = datetime(2026, 7, 15, 12, 30, tzinfo=UTC)
        assert assemble_screening_report(stored, generated_at=generated_at) == (
            assemble_screening_report(stored, generated_at=generated_at)
        )
