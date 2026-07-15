from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from trialsync.api.deps import CurrentUser, SessionDep
from trialsync.api.errors import ApplicationError
from trialsync.db.models import Patient, PatientFact
from trialsync.schemas import FactCreate, FactRead, PatientCreate, PatientRead, PatientUpdate

router = APIRouter(prefix="/api/v1/patients", tags=["patients"])


async def owned_patient(session: SessionDep, user: CurrentUser, patient_id: uuid.UUID) -> Patient:
    patient = await session.scalar(
        select(Patient)
        .options(selectinload(Patient.facts))
        .where(Patient.id == patient_id, Patient.owner_id == user.id)
    )
    if patient is None:
        raise ApplicationError(
            code="PATIENT_NOT_FOUND", message="Patient was not found.", status_code=404
        )
    return patient


@router.get("", response_model=list[PatientRead])
async def list_patients(session: SessionDep, user: CurrentUser) -> list[Patient]:
    result = await session.scalars(
        select(Patient)
        .options(selectinload(Patient.facts))
        .where(Patient.owner_id == user.id)
        .order_by(Patient.updated_at.desc())
        .limit(100)
    )
    return list(result.unique())


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
async def create_patient(payload: PatientCreate, session: SessionDep, user: CurrentUser) -> Patient:
    duplicate = await session.scalar(
        select(Patient).where(
            Patient.owner_id == user.id,
            func.lower(Patient.display_name) == payload.display_name.strip().lower(),
        )
    )
    if duplicate is not None and not payload.confirm_duplicate_name:
        raise ApplicationError(
            code="PATIENT_NAME_REVIEW_REQUIRED",
            message=(
                "A patient with this name already exists. Review it or continue creating "
                "a distinct synthetic record."
            ),
            status_code=409,
            field="display_name",
            details=[{"patient_id": str(duplicate.id), "display_name": duplicate.display_name}],
        )
    patient = Patient(
        owner_id=user.id,
        external_id=payload.external_id or f"SYN-{uuid.uuid4().hex[:10].upper()}",
        display_name=payload.display_name,
        date_of_birth=payload.date_of_birth,
        sex=payload.sex,
    )
    session.add(patient)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="PATIENT_EXTERNAL_ID_EXISTS",
            message="This synthetic patient ID is already in use.",
            status_code=409,
            field="external_id",
        ) from exception
    return await owned_patient(session, user, patient.id)


@router.get("/{patient_id}", response_model=PatientRead)
async def get_patient(patient_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Patient:
    return await owned_patient(session, user, patient_id)


@router.patch("/{patient_id}", response_model=PatientRead)
async def update_patient(
    payload: PatientUpdate, patient_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Patient:
    patient = await owned_patient(session, user, patient_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, key, value)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="PATIENT_EXTERNAL_ID_EXISTS",
            message="This synthetic patient ID is already in use.",
            status_code=409,
            field="external_id",
        ) from exception
    return await owned_patient(session, user, patient.id)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(patient_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    patient = await owned_patient(session, user, patient_id)
    await session.delete(patient)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{patient_id}/facts", response_model=FactRead, status_code=status.HTTP_201_CREATED)
async def create_fact(
    payload: FactCreate, patient_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> PatientFact:
    await owned_patient(session, user, patient_id)
    fact = PatientFact(patient_id=patient_id, **payload.model_dump())
    session.add(fact)
    await session.commit()
    await session.refresh(fact)
    return fact


@router.patch("/{patient_id}/facts/{fact_id}", response_model=FactRead)
async def update_fact(
    payload: FactCreate,
    patient_id: uuid.UUID,
    fact_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> PatientFact:
    await owned_patient(session, user, patient_id)
    fact = await session.scalar(
        select(PatientFact).where(PatientFact.id == fact_id, PatientFact.patient_id == patient_id)
    )
    if fact is None:
        raise ApplicationError(
            code="FACT_NOT_FOUND", message="Patient fact was not found.", status_code=404
        )
    for key, value in payload.model_dump().items():
        setattr(fact, key, value)
    await session.commit()
    await session.refresh(fact)
    return fact


@router.delete("/{patient_id}/facts/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fact(
    patient_id: uuid.UUID, fact_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Response:
    await owned_patient(session, user, patient_id)
    fact = await session.scalar(
        select(PatientFact).where(PatientFact.id == fact_id, PatientFact.patient_id == patient_id)
    )
    if fact is None:
        raise ApplicationError(
            code="FACT_NOT_FOUND", message="Patient fact was not found.", status_code=404
        )
    await session.delete(fact)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
