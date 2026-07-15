from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete, func, select

import trialsync.api.screenings as screening_api
from trialsync.db.models import PatientSnapshot, Screening, ScreeningBatch, User
from trialsync.db.session import get_session_factory

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

    changed = await api.patch(
        f"/api/v1/patients/{patient_id}", headers=headers, json={"date_of_birth": "2015-07-15"}
    )
    assert changed.status_code == 200
    historical = await api.get(f"/api/v1/screenings/{saved['id']}", headers=headers)
    assert historical.status_code == 200
    assert historical.json()["overall_state"] == "potentially_eligible"
    assert historical.json()["patient_snapshot_id"] == saved["patient_snapshot_id"]

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
            "sex": "Female",
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
    assert "/api/v1/screening-batches" in paths
    assert "/api/v1/screening-batches/{batch_id}" in paths
