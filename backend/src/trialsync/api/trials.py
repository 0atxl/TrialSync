from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from trialsync.api.deps import CurrentUser, SessionDep
from trialsync.api.errors import ApplicationError
from trialsync.db.models import Criterion, Trial, TrialVersion, VersionStatus
from trialsync.schemas import (
    CriterionCreate,
    CriterionRead,
    TrialCreate,
    TrialRead,
    TrialUpdate,
    VersionCreate,
    VersionRead,
)

router = APIRouter(prefix="/api/v1/trials", tags=["trials"])


def trial_options():
    return selectinload(Trial.versions).selectinload(TrialVersion.criteria)


async def owned_trial(session: SessionDep, user: CurrentUser, trial_id: uuid.UUID) -> Trial:
    trial = await session.scalar(
        select(Trial)
        .options(trial_options())
        .where(Trial.id == trial_id, Trial.owner_id == user.id)
    )
    if trial is None:
        raise ApplicationError(
            code="TRIAL_NOT_FOUND", message="Trial was not found.", status_code=404
        )
    return trial


async def owned_version(
    session: SessionDep, user: CurrentUser, trial_id: uuid.UUID, version_id: uuid.UUID
) -> TrialVersion:
    await owned_trial(session, user, trial_id)
    version = await session.scalar(
        select(TrialVersion)
        .options(selectinload(TrialVersion.criteria))
        .where(TrialVersion.id == version_id, TrialVersion.trial_id == trial_id)
    )
    if version is None:
        raise ApplicationError(
            code="TRIAL_VERSION_NOT_FOUND", message="Trial version was not found.", status_code=404
        )
    return version


def require_draft(version: TrialVersion) -> None:
    if version.status is not VersionStatus.draft:
        raise ApplicationError(
            code="APPROVED_VERSION_IMMUTABLE",
            message="Approved trial versions cannot be changed.",
            status_code=409,
        )


@router.get("", response_model=list[TrialRead])
async def list_trials(session: SessionDep, user: CurrentUser) -> list[Trial]:
    result = await session.scalars(
        select(Trial)
        .options(trial_options())
        .where(Trial.owner_id == user.id)
        .order_by(Trial.updated_at.desc())
        .limit(100)
    )
    return list(result.unique())


@router.post("", response_model=TrialRead, status_code=status.HTTP_201_CREATED)
async def create_trial(payload: TrialCreate, session: SessionDep, user: CurrentUser) -> Trial:
    trial = Trial(
        owner_id=user.id,
        registry_id=payload.registry_id or f"SYN-TRIAL-{uuid.uuid4().hex[:10].upper()}",
        title=payload.title,
        condition=payload.condition,
        phase=payload.phase,
    )
    session.add(trial)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="TRIAL_REGISTRY_ID_EXISTS",
            message="This registry ID is already in use.",
            status_code=409,
            field="registry_id",
        ) from exception
    return await owned_trial(session, user, trial.id)


@router.get("/{trial_id}", response_model=TrialRead)
async def get_trial(trial_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Trial:
    return await owned_trial(session, user, trial_id)


@router.patch("/{trial_id}", response_model=TrialRead)
async def update_trial(
    payload: TrialUpdate, trial_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Trial:
    trial = await owned_trial(session, user, trial_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(trial, key, value)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="TRIAL_REGISTRY_ID_EXISTS",
            message="This registry ID is already in use.",
            status_code=409,
            field="registry_id",
        ) from exception
    return await owned_trial(session, user, trial.id)


@router.delete("/{trial_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trial(trial_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    trial = await owned_trial(session, user, trial_id)
    await session.delete(trial)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="TRIAL_HAS_SCREENING_HISTORY",
            message="Trials used by saved screenings cannot be deleted.",
            status_code=409,
        ) from exception
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{trial_id}/versions", response_model=VersionRead, status_code=status.HTTP_201_CREATED
)
async def create_version(
    payload: VersionCreate, trial_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> TrialVersion:
    await owned_trial(session, user, trial_id)
    version = TrialVersion(trial_id=trial_id, **payload.model_dump())
    session.add(version)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="TRIAL_VERSION_EXISTS",
            message="This trial version already exists.",
            status_code=409,
            field="version",
        ) from exception
    return await owned_version(session, user, trial_id, version.id)


@router.put("/{trial_id}/versions/{version_id}", response_model=VersionRead)
async def update_version(
    payload: VersionCreate,
    trial_id: uuid.UUID,
    version_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> TrialVersion:
    version = await owned_version(session, user, trial_id, version_id)
    require_draft(version)
    for key, value in payload.model_dump().items():
        setattr(version, key, value)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="TRIAL_VERSION_EXISTS",
            message="This trial version already exists.",
            status_code=409,
            field="version",
        ) from exception
    return await owned_version(session, user, trial_id, version_id)


@router.delete("/{trial_id}/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_version(
    trial_id: uuid.UUID,
    version_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    version = await owned_version(session, user, trial_id, version_id)
    require_draft(version)
    await session.delete(version)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{trial_id}/versions/{version_id}/criteria",
    response_model=CriterionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_criterion(
    payload: CriterionCreate,
    trial_id: uuid.UUID,
    version_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Criterion:
    version = await owned_version(session, user, trial_id, version_id)
    require_draft(version)
    criterion = Criterion(trial_version_id=version_id, **payload.model_dump())
    session.add(criterion)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="CRITERION_ORDER_EXISTS",
            message="Criterion order must be unique within a version.",
            status_code=409,
            field="order",
        ) from exception
    await session.refresh(criterion)
    return criterion


@router.put(
    "/{trial_id}/versions/{version_id}/criteria/{criterion_id}", response_model=CriterionRead
)
async def update_criterion(
    payload: CriterionCreate,
    trial_id: uuid.UUID,
    version_id: uuid.UUID,
    criterion_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Criterion:
    version = await owned_version(session, user, trial_id, version_id)
    require_draft(version)
    criterion = await session.scalar(
        select(Criterion).where(
            Criterion.id == criterion_id, Criterion.trial_version_id == version_id
        )
    )
    if criterion is None:
        raise ApplicationError(
            code="CRITERION_NOT_FOUND", message="Criterion was not found.", status_code=404
        )
    for key, value in payload.model_dump().items():
        setattr(criterion, key, value)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="CRITERION_ORDER_EXISTS",
            message="Criterion order must be unique within a version.",
            status_code=409,
            field="order",
        ) from exception
    await session.refresh(criterion)
    return criterion


@router.delete(
    "/{trial_id}/versions/{version_id}/criteria/{criterion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_criterion(
    trial_id: uuid.UUID,
    version_id: uuid.UUID,
    criterion_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    version = await owned_version(session, user, trial_id, version_id)
    require_draft(version)
    criterion = await session.scalar(
        select(Criterion).where(
            Criterion.id == criterion_id, Criterion.trial_version_id == version_id
        )
    )
    if criterion is None:
        raise ApplicationError(
            code="CRITERION_NOT_FOUND", message="Criterion was not found.", status_code=404
        )
    await session.delete(criterion)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
