from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from trialsync.api.deps import CurrentUser, SessionDep
from trialsync.api.errors import ApplicationError
from trialsync.db.models import Screening, ScreeningBatch
from trialsync.schemas import (
    BatchCreate,
    BatchPairRead,
    BatchStateCounts,
    CriterionEvaluationRead,
    ScreeningBatchRead,
    ScreeningCounts,
    ScreeningCreate,
    ScreeningRead,
)
from trialsync.screening.service import (
    owned_approved_version,
    owned_patient,
    owned_snapshot,
    run_and_store,
    snapshot_for_patient,
)

router = APIRouter(tags=["screenings"])


def _counts(screening: Screening) -> ScreeningCounts:
    results = [item.result.value for item in screening.evaluations]
    return ScreeningCounts(
        pass_count=results.count("pass"),
        fail_count=results.count("fail"),
        unknown_count=results.count("unknown"),
    )


def _screening_read(screening: Screening) -> ScreeningRead:
    return ScreeningRead(
        id=screening.id,
        batch_id=screening.batch_id,
        patient_snapshot_id=screening.patient_snapshot_id,
        trial_version_id=screening.trial_version_id,
        overall_state=screening.overall_state.value,
        screening_date=screening.screening_date,
        engine_version=screening.engine_version,
        dsl_version=screening.dsl_version,
        terminology_version=screening.terminology_version,
        unit_version=screening.unit_version,
        created_at=screening.created_at,
        counts=_counts(screening),
        evaluations=[
            CriterionEvaluationRead(
                id=item.id,
                criterion_id=item.criterion_id,
                criterion_order=item.criterion_order,
                criterion_kind=item.criterion_kind,
                result=item.result.value,
                truth=item.truth,
                reason_code=item.reason_code,
                canonical_explanation=item.canonical_explanation,
                evidence=item.evidence_json,
                rejected_evidence=item.rejected_evidence_json,
                missing_information=item.missing_information_json,
            )
            for item in screening.evaluations
        ],
    )


def _batch_read(batch: ScreeningBatch) -> ScreeningBatchRead:
    states = [item.overall_state.value for item in batch.screenings]
    unknown_criterion_count = sum(_counts(item).unknown_count for item in batch.screenings)
    return ScreeningBatchRead(
        id=batch.id,
        label=batch.label,
        pair_count=batch.pair_count,
        created_at=batch.created_at,
        state_counts=BatchStateCounts(
            potentially_eligible=states.count("potentially_eligible"),
            likely_ineligible=states.count("likely_ineligible"),
            needs_review=states.count("needs_review"),
        ),
        unknown_criterion_count=unknown_criterion_count,
        screenings=[
            BatchPairRead(
                patient_snapshot_id=item.patient_snapshot_id,
                trial_version_id=item.trial_version_id,
                screening_id=item.id,
                overall_state=item.overall_state.value,
                counts=_counts(item),
            )
            for item in batch.screenings
        ],
    )


async def _owned_screening(
    session: SessionDep, owner_id: uuid.UUID, screening_id: uuid.UUID
) -> Screening:
    screening = await session.scalar(
        select(Screening)
        .options(selectinload(Screening.evaluations))
        .where(Screening.id == screening_id, Screening.owner_id == owner_id)
    )
    if screening is None:
        raise ApplicationError(
            code="SCREENING_NOT_FOUND", message="Screening was not found.", status_code=404
        )
    return screening


async def _owned_batch(
    session: SessionDep, owner_id: uuid.UUID, batch_id: uuid.UUID
) -> ScreeningBatch:
    batch = await session.scalar(
        select(ScreeningBatch)
        .options(
            selectinload(ScreeningBatch.screenings).selectinload(Screening.evaluations),
        )
        .where(ScreeningBatch.id == batch_id, ScreeningBatch.owner_id == owner_id)
    )
    if batch is None:
        raise ApplicationError(
            code="SCREENING_BATCH_NOT_FOUND",
            message="Screening batch was not found.",
            status_code=404,
        )
    return batch


@router.post(
    "/api/v1/screenings",
    response_model=ScreeningRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_screening(
    payload: ScreeningCreate, session: SessionDep, user: CurrentUser
) -> ScreeningRead:
    try:
        patient = await owned_patient(session, user.id, payload.patient_id)
        version = await owned_approved_version(session, user.id, payload.trial_version_id)
        snapshot = await snapshot_for_patient(session, patient)
        screening = await run_and_store(
            session,
            owner_id=user.id,
            snapshot=snapshot,
            version=version,
            screening_date=payload.screening_date or date.today(),
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return _screening_read(await _owned_screening(session, user.id, screening.id))


@router.get("/api/v1/screenings", response_model=list[ScreeningRead])
async def list_screenings(session: SessionDep, user: CurrentUser) -> list[ScreeningRead]:
    results = await session.scalars(
        select(Screening)
        .options(selectinload(Screening.evaluations))
        .where(Screening.owner_id == user.id)
        .order_by(Screening.created_at.desc())
        .limit(100)
    )
    return [_screening_read(item) for item in results.unique()]


@router.get("/api/v1/screenings/{screening_id}", response_model=ScreeningRead)
async def get_screening(
    screening_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> ScreeningRead:
    return _screening_read(await _owned_screening(session, user.id, screening_id))


@router.post(
    "/api/v1/screening-batches",
    response_model=ScreeningBatchRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_batch(
    payload: BatchCreate, request: Request, session: SessionDep, user: CurrentUser
) -> ScreeningBatchRead:
    snapshot_ids = list(dict.fromkeys(payload.patient_snapshot_ids))
    version_ids = list(dict.fromkeys(payload.trial_version_ids))
    max_patients = request.app.state.settings.screening_batch_max_patients
    max_trials = request.app.state.settings.screening_batch_max_trials
    max_pairs = request.app.state.settings.screening_batch_max_pairs
    if len(snapshot_ids) > max_patients or len(version_ids) > max_trials:
        raise ApplicationError(
            code="BATCH_LIMIT_EXCEEDED",
            message="Batch selection exceeds configured limits.",
            status_code=422,
        )
    pair_count = len(snapshot_ids) * len(version_ids)
    if pair_count > max_pairs:
        raise ApplicationError(
            code="BATCH_LIMIT_EXCEEDED",
            message="Batch pair count exceeds configured limit.",
            status_code=422,
        )
    try:
        snapshots = [await owned_snapshot(session, user.id, item) for item in snapshot_ids]
        versions = [await owned_approved_version(session, user.id, item) for item in version_ids]
        batch = ScreeningBatch(owner_id=user.id, label=payload.label, pair_count=pair_count)
        session.add(batch)
        await session.flush()
        screening_date = payload.screening_date or date.today()
        for snapshot in snapshots:
            for version in versions:
                await run_and_store(
                    session,
                    owner_id=user.id,
                    snapshot=snapshot,
                    version=version,
                    screening_date=screening_date,
                    batch=batch,
                )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return _batch_read(await _owned_batch(session, user.id, batch.id))


@router.get("/api/v1/screening-batches", response_model=list[ScreeningBatchRead])
async def list_batches(session: SessionDep, user: CurrentUser) -> list[ScreeningBatchRead]:
    results = await session.scalars(
        select(ScreeningBatch)
        .options(
            selectinload(ScreeningBatch.screenings).selectinload(Screening.evaluations),
        )
        .where(ScreeningBatch.owner_id == user.id)
        .order_by(ScreeningBatch.created_at.desc())
        .limit(100)
    )
    return [_batch_read(item) for item in results.unique()]


@router.get("/api/v1/screening-batches/{batch_id}", response_model=ScreeningBatchRead)
async def get_batch(
    batch_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> ScreeningBatchRead:
    return _batch_read(await _owned_batch(session, user.id, batch_id))
