from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import desc, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from trialsync.api.deps import CurrentUser, SessionDep
from trialsync.api.errors import ApplicationError
from trialsync.db.models import (
    Assertion,
    FactType,
    Patient,
    PatientChangeEvent,
    PatientFact,
    PatientUnsupportedDetail,
)
from trialsync.patient_data import (
    BiologicalSex,
    ConditionMedicationValue,
    NumericObservationValue,
    PatientFactCatalogEntry,
    PatientFactCreateRequest,
    PatientFactInputKind,
    PatientFactUpdateRequest,
    PatientFactVoidRequest,
    PregnancyStatusValue,
)
from trialsync.patient_data.catalog import (
    active_catalog_entry_by_fact,
    active_catalog_entry_by_key,
)
from trialsync.schemas import (
    FactRead,
    PatientChangeEventRead,
    PatientCreate,
    PatientRead,
    PatientUpdate,
    UnsupportedDetailCreate,
    UnsupportedDetailRead,
    UnsupportedDetailUpdate,
)

router = APIRouter(prefix="/api/v1/patients", tags=["patients"])


def pregnancy_present_fact(patient: Patient) -> PatientFact | None:
    return next(
        (
            fact
            for fact in patient.facts
            if fact.fact_type is FactType.condition
            and fact.concept == "pregnancy"
            and fact.assertion is Assertion.present
        ),
        None,
    )


def pregnancy_sex_conflict(
    *,
    field: str,
    fact: PatientFact | None = None,
) -> ApplicationError:
    details = [{"fact_id": str(fact.id)}] if fact is not None else None
    return ApplicationError(
        code="PATIENT_PREGNANCY_SEX_CONFLICT",
        message=(
            "Pregnancy cannot be recorded as Pregnant when biological sex "
            "is Male. Reconcile the pregnancy status or biological sex first."
        ),
        status_code=409,
        field=field,
        details=details,
    )


def validate_pregnancy_value_for_patient(
    patient: Patient,
    entry: PatientFactCatalogEntry,
    value: ConditionMedicationValue | PregnancyStatusValue | NumericObservationValue,
    *,
    fact: PatientFact | None = None,
) -> None:
    if (
        entry.input_kind is PatientFactInputKind.pregnancy_status
        and value.assertion is Assertion.present
        and patient.sex == BiologicalSex.male.value
    ):
        raise pregnancy_sex_conflict(field="value.assertion", fact=fact)


def catalog_fact_values(
    entry: PatientFactCatalogEntry,
    value: ConditionMedicationValue | PregnancyStatusValue | NumericObservationValue,
    source_label: str,
) -> dict[str, object]:
    if value.input_kind != entry.input_kind.value:
        raise ApplicationError(
            code="PATIENT_FACT_VALUE_INVALID",
            message=f"{entry.display_label} requires a {entry.input_kind.value} value.",
            status_code=422,
            field="value.input_kind",
        )
    if value.assertion not in entry.allowed_assertions:
        raise ApplicationError(
            code="PATIENT_FACT_VALUE_INVALID",
            message=f"The selected status is not supported for {entry.display_label}.",
            status_code=422,
            field="value.assertion",
        )
    values: dict[str, object] = {
        "fact_type": entry.fact_type,
        "concept": entry.concept,
        "value_numeric": None,
        "value_text": None,
        "unit": None,
        "assertion": value.assertion,
        "effective_date": value.effective_date,
        "source_label": source_label,
    }
    if isinstance(value, NumericObservationValue):
        values["value_numeric"] = value.value_numeric
        values["unit"] = entry.fixed_unit
    return values


def duplicate_fact_error(entry: PatientFactCatalogEntry, fact: PatientFact) -> ApplicationError:
    return ApplicationError(
        code="PATIENT_FACT_DUPLICATE",
        message=f"{entry.display_label} already exists. Edit the existing detail instead.",
        status_code=409,
        field="catalog_key",
        details=[
            {
                "fact_id": str(fact.id),
                "catalog_key": entry.key,
                "display_label": entry.display_label,
            }
        ],
    )


def profile_event_payload(patient: Patient) -> dict[str, object]:
    return {
        "display_name": patient.display_name,
        "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        "sex": patient.sex,
    }


def fact_event_payload(fact: PatientFact) -> dict[str, object]:
    return {
        "id": str(fact.id),
        "fact_type": fact.fact_type.value,
        "concept": fact.concept,
        "value_numeric": str(fact.value_numeric) if fact.value_numeric is not None else None,
        "value_text": fact.value_text,
        "unit": fact.unit,
        "assertion": fact.assertion.value,
        "effective_date": fact.effective_date.isoformat() if fact.effective_date else None,
        "source_label": fact.source_label,
        "voided_at": fact.voided_at.isoformat() if fact.voided_at else None,
        "void_reason": fact.void_reason,
    }


def record_change(
    session: SessionDep,
    *,
    patient_id: uuid.UUID,
    actor_id: uuid.UUID,
    event_type: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    before: dict[str, object] | None = None,
    after: dict[str, object] | None = None,
    reason: str | None = None,
) -> None:
    session.add(
        PatientChangeEvent(
            patient_id=patient_id,
            actor_id=actor_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            before_json=before,
            after_json=after,
        )
    )


async def owned_patient(session: SessionDep, user: CurrentUser, patient_id: uuid.UUID) -> Patient:
    patient = await session.scalar(
        select(Patient)
        .options(
            selectinload(Patient.facts),
            selectinload(Patient.unsupported_details),
            selectinload(Patient.activity),
        )
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
        .options(
            selectinload(Patient.facts),
            selectinload(Patient.unsupported_details),
            selectinload(Patient.activity),
        )
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
        sex=payload.sex.value if payload.sex is not None else None,
    )
    session.add(patient)
    try:
        await session.flush()
        record_change(
            session,
            patient_id=patient.id,
            actor_id=user.id,
            event_type="patient_created",
            entity_type="patient",
            entity_id=patient.id,
            after=profile_event_payload(patient),
        )
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


@router.get("/{patient_id}/activity", response_model=list[PatientChangeEventRead])
async def get_patient_activity(
    patient_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> list[PatientChangeEvent]:
    """Return the bounded immutable change history for one owned patient."""

    await owned_patient(session, user, patient_id)
    result = await session.scalars(
        select(PatientChangeEvent)
        .where(PatientChangeEvent.patient_id == patient_id)
        .order_by(desc(PatientChangeEvent.created_at))
        .limit(100)
    )
    return list(result)


@router.patch("/{patient_id}", response_model=PatientRead)
async def update_patient(
    payload: PatientUpdate, patient_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Patient:
    patient = await owned_patient(session, user, patient_id)
    if patient.updated_at != payload.expected_updated_at:
        raise ApplicationError(
            code="PATIENT_RECORD_STALE",
            message=(
                "This patient profile changed after you opened it. "
                "Reload and review the latest values."
            ),
            status_code=409,
            details=[
                {
                    "expected_updated_at": payload.expected_updated_at.isoformat(),
                    "current_updated_at": patient.updated_at.isoformat(),
                }
            ],
        )
    if (
        "sex" in payload.model_fields_set
        and payload.sex is BiologicalSex.male
        and patient.sex != BiologicalSex.male.value
    ):
        conflicting_fact = pregnancy_present_fact(patient)
        if conflicting_fact is not None:
            raise pregnancy_sex_conflict(field="sex", fact=conflicting_fact)
    values = payload.model_dump(exclude={"expected_updated_at"}, exclude_unset=True)
    if payload.sex is not None:
        values["sex"] = payload.sex.value
    try:
        before = profile_event_payload(patient)
        result = await session.execute(
            update(Patient)
            .where(
                Patient.id == patient_id,
                Patient.owner_id == user.id,
                Patient.updated_at == payload.expected_updated_at,
            )
            .values(**values, updated_at=func.now())
            .returning(Patient.id)
        )
        if result.scalar_one_or_none() is None:
            await session.rollback()
            raise ApplicationError(
                code="PATIENT_RECORD_STALE",
                message=(
                    "This patient profile changed while you were saving. "
                    "Reload and review the latest values."
                ),
                status_code=409,
            )
        after_date_of_birth = values.get("date_of_birth", before["date_of_birth"])
        after = {
            "display_name": values.get("display_name", before["display_name"]),
            "date_of_birth": (
                after_date_of_birth.isoformat()
                if hasattr(after_date_of_birth, "isoformat")
                else after_date_of_birth
            ),
            "sex": values.get("sex", before["sex"]),
        }
        record_change(
            session,
            patient_id=patient_id,
            actor_id=user.id,
            event_type="profile_updated",
            entity_type="patient",
            entity_id=patient_id,
            before=before,
            after=after,
        )
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
    payload: PatientFactCreateRequest,
    patient_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> PatientFact:
    patient = await owned_patient(session, user, patient_id)
    if patient.updated_at != payload.expected_patient_updated_at:
        raise ApplicationError(
            code="PATIENT_RECORD_STALE",
            message=(
                "This patient record changed after you opened it. "
                "Reload before adding a detail."
            ),
            status_code=409,
        )
    entry = await active_catalog_entry_by_key(session, payload.catalog_key)
    if entry is None:
        raise ApplicationError(
            code="PATIENT_FACT_UNSUPPORTED",
            message="Choose a supported clinical detail from the catalog.",
            status_code=422,
            field="catalog_key",
        )
    values = catalog_fact_values(entry, payload.value, payload.source_label)
    validate_pregnancy_value_for_patient(patient, entry, payload.value)
    duplicate_query = select(PatientFact).where(
        PatientFact.patient_id == patient_id,
        PatientFact.fact_type == entry.fact_type,
        PatientFact.concept == entry.concept,
        PatientFact.voided_at.is_(None),
    )
    if entry.input_kind is PatientFactInputKind.numeric:
        duplicate_query = duplicate_query.where(
            PatientFact.effective_date == payload.value.effective_date
        )
    duplicate = await session.scalar(duplicate_query.order_by(PatientFact.created_at.desc()))
    if duplicate is not None:
        raise duplicate_fact_error(entry, duplicate)
    fact = PatientFact(patient_id=patient_id, **values)
    session.add(fact)
    await session.flush()
    record_change(
        session,
        patient_id=patient_id,
        actor_id=user.id,
        event_type="fact_created",
        entity_type="fact",
        entity_id=fact.id,
        after=fact_event_payload(fact),
    )
    await session.commit()
    await session.refresh(fact)
    return fact


@router.patch("/{patient_id}/facts/{fact_id}", response_model=FactRead)
async def update_fact(
    payload: PatientFactUpdateRequest,
    patient_id: uuid.UUID,
    fact_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> PatientFact:
    patient = await owned_patient(session, user, patient_id)
    fact = await session.scalar(
        select(PatientFact).where(
            PatientFact.id == fact_id,
            PatientFact.patient_id == patient_id,
            PatientFact.voided_at.is_(None),
        )
    )
    if fact is None:
        raise ApplicationError(
            code="FACT_NOT_FOUND", message="Patient fact was not found.", status_code=404
        )
    entry = await active_catalog_entry_by_fact(session, fact.fact_type, fact.concept)
    if entry is None:
        raise ApplicationError(
            code="PATIENT_FACT_UNSUPPORTED",
            message="This legacy detail is not available in the controlled catalog.",
            status_code=422,
            field="fact_id",
        )
    if fact.updated_at != payload.expected_fact_updated_at:
        raise ApplicationError(
            code="PATIENT_RECORD_STALE",
            message="This clinical detail changed after you opened it. Reload before saving.",
            status_code=409,
        )
    values = catalog_fact_values(entry, payload.value, payload.source_label)
    validate_pregnancy_value_for_patient(patient, entry, payload.value, fact=fact)
    before = fact_event_payload(fact)
    result = await session.execute(
        update(PatientFact)
        .where(
            PatientFact.id == fact_id,
            PatientFact.patient_id == patient_id,
            PatientFact.updated_at == payload.expected_fact_updated_at,
        )
        .values(**values, updated_at=func.now())
        .returning(PatientFact.id)
    )
    if result.scalar_one_or_none() is None:
        await session.rollback()
        raise ApplicationError(
            code="PATIENT_RECORD_STALE",
            message="This clinical detail changed while you were saving. Reload before retrying.",
            status_code=409,
        )
    await session.flush()
    await session.refresh(fact)
    record_change(
        session,
        patient_id=patient_id,
        actor_id=user.id,
        event_type="fact_updated",
        entity_type="fact",
        entity_id=fact.id,
        before=before,
        after=fact_event_payload(fact),
    )
    await session.commit()
    return fact


@router.delete("/{patient_id}/facts/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fact(
    payload: PatientFactVoidRequest,
    patient_id: uuid.UUID,
    fact_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    await owned_patient(session, user, patient_id)
    fact = await session.scalar(
        select(PatientFact).where(
            PatientFact.id == fact_id,
            PatientFact.patient_id == patient_id,
            PatientFact.voided_at.is_(None),
        )
    )
    if fact is None:
        raise ApplicationError(
            code="PATIENT_FACT_ALREADY_REMOVED",
            message="This clinical detail is already removed or was not found.",
            status_code=404,
        )
    if fact.updated_at != payload.expected_fact_updated_at:
        raise ApplicationError(
            code="PATIENT_RECORD_STALE",
            message="This clinical detail changed after you opened it. Reload before removing.",
            status_code=409,
        )
    before = fact_event_payload(fact)
    fact.voided_at = func.now()
    fact.void_reason = payload.reason
    fact.voided_by_id = user.id
    await session.flush()
    await session.refresh(fact)
    record_change(
        session,
        patient_id=patient_id,
        actor_id=user.id,
        event_type="fact_voided",
        entity_type="fact",
        entity_id=fact.id,
        before=before,
        after=fact_event_payload(fact),
        reason=payload.reason,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{patient_id}/facts/{fact_id}/restore", response_model=FactRead)
async def restore_fact(
    patient_id: uuid.UUID,
    fact_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> PatientFact:
    await owned_patient(session, user, patient_id)
    fact = await session.scalar(
        select(PatientFact).where(
            PatientFact.id == fact_id,
            PatientFact.patient_id == patient_id,
        )
    )
    if fact is None:
        raise ApplicationError(
            code="FACT_NOT_FOUND", message="Patient fact was not found.", status_code=404
        )
    if fact.voided_at is None:
        raise ApplicationError(
            code="PATIENT_FACT_RESTORE_CONFLICT",
            message="This clinical detail is already active.",
            status_code=409,
        )
    entry = await active_catalog_entry_by_fact(session, fact.fact_type, fact.concept)
    if entry is None:
        raise ApplicationError(
            code="PATIENT_FACT_UNSUPPORTED",
            message="This legacy detail is no longer available in the controlled catalog.",
            status_code=422,
            field="fact_id",
        )
    duplicate = await session.scalar(
        select(PatientFact).where(
            PatientFact.patient_id == patient_id,
            PatientFact.fact_type == fact.fact_type,
            PatientFact.concept == fact.concept,
            PatientFact.voided_at.is_(None),
        )
    )
    if duplicate is not None:
        raise ApplicationError(
            code="PATIENT_FACT_RESTORE_CONFLICT",
            message=f"{entry.display_label} is already active. Edit it instead.",
            status_code=409,
            details=[{"fact_id": str(duplicate.id)}],
        )
    before = fact_event_payload(fact)
    fact.voided_at = None
    fact.void_reason = None
    fact.voided_by_id = None
    await session.flush()
    await session.refresh(fact)
    record_change(
        session,
        patient_id=patient_id,
        actor_id=user.id,
        event_type="fact_restored",
        entity_type="fact",
        entity_id=fact.id,
        before=before,
        after=fact_event_payload(fact),
    )
    await session.commit()
    return fact


async def owned_unsupported_detail(
    session: SessionDep,
    user: CurrentUser,
    patient_id: uuid.UUID,
    detail_id: uuid.UUID,
) -> PatientUnsupportedDetail:
    await owned_patient(session, user, patient_id)
    detail = await session.scalar(
        select(PatientUnsupportedDetail).where(
            PatientUnsupportedDetail.id == detail_id,
            PatientUnsupportedDetail.patient_id == patient_id,
        )
    )
    if detail is None:
        raise ApplicationError(
            code="PATIENT_UNSUPPORTED_DETAIL_NOT_FOUND",
            message="Unsupported clinical detail was not found.",
            status_code=404,
        )
    return detail


@router.post(
    "/{patient_id}/unsupported-details",
    response_model=UnsupportedDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_unsupported_detail(
    payload: UnsupportedDetailCreate,
    patient_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> PatientUnsupportedDetail:
    await owned_patient(session, user, patient_id)
    duplicate = await session.scalar(
        select(PatientUnsupportedDetail).where(
            PatientUnsupportedDetail.patient_id == patient_id,
            PatientUnsupportedDetail.category == payload.category,
            func.lower(PatientUnsupportedDetail.label) == payload.label.lower(),
        )
    )
    if duplicate is not None:
        raise ApplicationError(
            code="PATIENT_UNSUPPORTED_DETAIL_DUPLICATE",
            message="This unsupported detail is already recorded for review.",
            status_code=409,
            field="label",
            details=[{"detail_id": str(duplicate.id)}],
        )
    detail = PatientUnsupportedDetail(patient_id=patient_id, **payload.model_dump())
    session.add(detail)
    await session.commit()
    await session.refresh(detail)
    return detail


@router.patch(
    "/{patient_id}/unsupported-details/{detail_id}",
    response_model=UnsupportedDetailRead,
)
async def update_unsupported_detail(
    payload: UnsupportedDetailUpdate,
    patient_id: uuid.UUID,
    detail_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> PatientUnsupportedDetail:
    detail = await owned_unsupported_detail(session, user, patient_id, detail_id)
    if detail.updated_at != payload.expected_updated_at:
        raise ApplicationError(
            code="PATIENT_RECORD_STALE",
            message="This review item changed after you opened it. Reload before saving.",
            status_code=409,
        )
    values = payload.model_dump(exclude={"expected_updated_at"}, exclude_unset=True)
    if values:
        result = await session.execute(
            update(PatientUnsupportedDetail)
            .where(
                PatientUnsupportedDetail.id == detail_id,
                PatientUnsupportedDetail.patient_id == patient_id,
                PatientUnsupportedDetail.updated_at == payload.expected_updated_at,
            )
            .values(**values, updated_at=func.now())
            .returning(PatientUnsupportedDetail.id)
        )
        if result.scalar_one_or_none() is None:
            await session.rollback()
            raise ApplicationError(
                code="PATIENT_RECORD_STALE",
                message="This review item changed while you were saving. Reload before retrying.",
                status_code=409,
            )
        await session.commit()
        await session.refresh(detail)
    return detail


@router.delete(
    "/{patient_id}/unsupported-details/{detail_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_unsupported_detail(
    patient_id: uuid.UUID,
    detail_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    detail = await owned_unsupported_detail(session, user, patient_id, detail_id)
    await session.delete(detail)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
