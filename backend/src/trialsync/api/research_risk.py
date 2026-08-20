from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from trialsync.api.deps import CurrentUser, SessionDep
from trialsync.api.errors import ApplicationError
from trialsync.db.models import (
    Document,
    OverallState,
    ResearchAdverseEvent,
    ResearchDoseEvent,
    ResearchEnrollment,
    ResearchFollowUpSnapshot,
    ResearchMeasurement,
    ResearchModelVersion,
    ResearchPrediction,
    ResearchVisitEvent,
    Screening,
)
from trialsync.research.artifacts import CohortArtifactService
from trialsync.research.risk import RiskArtifactError, RiskArtifactService, SourcedFeatureValue
from trialsync.research.risk.service import (
    USER_BASELINE_FEATURES,
    active_model,
    build_follow_up_snapshot,
    create_enrollment,
    create_prediction,
    enrollment_for_screening,
    enrollment_payload,
    follow_up_payload,
    owned_enrollment,
    owned_screening,
    prediction_payload,
    validate_descriptor,
)

router = APIRouter(prefix="/api/v1/research", tags=["research risk"])


class SourcedInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | int | float
    source: str = Field(min_length=1, max_length=120)


class EnrollmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enrollment_date: date
    baseline: dict[str, SourcedInput] = Field(default_factory=dict, max_length=7)


class EventSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_label: str = Field(min_length=1, max_length=120)
    source_document_id: uuid.UUID | None = None
    supersedes_event_id: uuid.UUID | None = None
    correction_reason: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def correction_has_reason(self) -> EventSource:
        if self.supersedes_event_id is not None and self.correction_reason is None:
            raise ValueError("correction_reason is required when superseding an event")
        if self.supersedes_event_id is None and self.correction_reason is not None:
            raise ValueError("correction_reason requires supersedes_event_id")
        return self


class DoseEventCreate(EventSource):
    medication_concept: str = Field(min_length=1, max_length=160)
    scheduled_date: date
    scheduled_count: int = Field(ge=1, le=1000)
    administered_count: int = Field(ge=0, le=1000)
    dose_amount: Decimal | None = Field(default=None, gt=0)
    dose_unit: str | None = Field(default=None, min_length=1, max_length=40)
    route: str | None = Field(default=None, min_length=1, max_length=40)
    status: Literal["scheduled", "administered", "partially_administered", "missed", "held"]
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_counts(self) -> DoseEventCreate:
        if self.administered_count > self.scheduled_count:
            raise ValueError("administered_count cannot exceed scheduled_count")
        expected = (
            "administered"
            if self.administered_count == self.scheduled_count
            else "missed"
            if self.administered_count == 0
            else "partially_administered"
        )
        if self.status not in {expected, "held", "scheduled"}:
            raise ValueError("dose status does not match scheduled/administered counts")
        if self.status == "held" and self.administered_count != 0:
            raise ValueError("a held dose cannot have an administered count")
        if (self.dose_amount is None) != (self.dose_unit is None):
            raise ValueError("dose_amount and dose_unit must be supplied together")
        return self


class VisitEventCreate(EventSource):
    visit_type: str = Field(min_length=1, max_length=120)
    scheduled_date: date
    completed_date: date | None = None
    status: Literal["scheduled", "completed", "delayed", "missed"]
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_dates(self) -> VisitEventCreate:
        if self.status in {"completed", "delayed"} and self.completed_date is None:
            raise ValueError("completed_date is required for a completed or delayed visit")
        if self.status in {"scheduled", "missed"} and self.completed_date is not None:
            raise ValueError("completed_date is not valid for a scheduled or missed visit")
        if self.completed_date is not None and self.completed_date < self.scheduled_date:
            raise ValueError("completed_date cannot precede scheduled_date")
        delay = (self.completed_date - self.scheduled_date).days if self.completed_date else None
        if self.status == "completed" and delay != 0:
            raise ValueError("a visit completed after its scheduled date must be delayed")
        if self.status == "delayed" and (delay is None or delay == 0):
            raise ValueError("a delayed visit must occur after its scheduled date")
        return self


class MeasurementCreate(EventSource):
    concept: str = Field(min_length=1, max_length=160)
    value_numeric: Decimal | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    observed: bool = True
    observed_date: date
    method: str | None = Field(default=None, min_length=1, max_length=120)
    reference_range: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_observation(self) -> MeasurementCreate:
        if self.observed and (self.value_numeric is None or self.unit is None):
            raise ValueError("observed measurements require a numeric value and unit")
        if not self.observed and self.value_numeric is not None:
            raise ValueError("an unobserved measurement cannot have a value")
        if self.concept == "functional_severity" and self.observed and self.unit != "score":
            raise ValueError("functional_severity measurements use the score unit")
        return self


class AdverseEventCreate(EventSource):
    event_concept: str = Field(min_length=1, max_length=160)
    onset_date: date
    severity_grade: int = Field(ge=1, le=4)
    resolved_date: date | None = None
    serious: bool = False
    relatedness: Literal["unrelated", "unlikely", "possible", "probable", "definite", "unknown"]
    action_taken: str | None = Field(default=None, min_length=1, max_length=120)
    outcome: Literal["ongoing", "resolved", "resolved_with_sequelae", "unknown"]

    @model_validator(mode="after")
    def validate_resolution(self) -> AdverseEventCreate:
        if self.resolved_date is not None and self.resolved_date < self.onset_date:
            raise ValueError("resolved_date cannot precede onset_date")
        if self.outcome.startswith("resolved") and self.resolved_date is None:
            raise ValueError("resolved outcomes require resolved_date")
        return self


class FollowUpSnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dose_record_complete: bool = False
    visit_record_complete: bool = False
    measurement_record_complete: bool = False
    adverse_event_record_complete: bool = False


class PredictionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    follow_up_snapshot_id: uuid.UUID


def _artifacts(request: Request) -> RiskArtifactService:
    return cast(RiskArtifactService, request.app.state.research_risk)


def _cohorts(request: Request) -> CohortArtifactService:
    return cast(CohortArtifactService, request.app.state.research_cohorts)


def _model_payload(model: ResearchModelVersion, artifacts: RiskArtifactService) -> dict[str, Any]:
    artifact_status: Literal["ready", "degraded"] = "ready"
    artifact_message: str | None = None
    try:
        descriptor = artifacts.descriptor()
        validate_descriptor(model, descriptor)
    except (RiskArtifactError, ApplicationError) as exc:
        artifact_status = "degraded"
        artifact_message = str(exc)
    return {
        "id": model.id,
        "name": model.model_name,
        "version": model.version,
        "alias": model.alias,
        "candidate_id": model.candidate_id,
        "training_dataset_version": model.training_dataset_version,
        "feature_schema_version": model.feature_schema_version,
        "threshold": float(model.threshold),
        "horizon_day": model.horizon_day,
        "validation_status": model.validation_status,
        "metrics": model.metrics_json,
        "band_policy_version": model.band_policy_version,
        "artifact_status": artifact_status,
        "artifact_message": artifact_message,
        "created_at": model.created_at,
    }


@router.get("/risk/models")
async def list_risk_models(
    request: Request, session: SessionDep, _user: CurrentUser
) -> list[dict[str, Any]]:
    models = await session.scalars(
        select(ResearchModelVersion).order_by(ResearchModelVersion.created_at.desc())
    )
    return [_model_payload(model, _artifacts(request)) for model in models]


@router.get("/risk/models/{model_version}")
async def get_risk_model(
    model_version: str, request: Request, session: SessionDep, _user: CurrentUser
) -> dict[str, Any]:
    model = await session.scalar(
        select(ResearchModelVersion).where(ResearchModelVersion.version == model_version)
    )
    if model is None:
        raise ApplicationError(
            code="RESEARCH_MODEL_NOT_FOUND",
            message="Research model was not found.",
            status_code=404,
        )
    return _model_payload(model, _artifacts(request))


@router.get("/screenings/{screening_id}/capabilities")
async def research_capabilities(
    screening_id: uuid.UUID, request: Request, session: SessionDep, user: CurrentUser
) -> dict[str, Any]:
    await owned_screening(session, user.id, screening_id)
    enrollment = await enrollment_for_screening(session, user.id, screening_id)
    follow_up = None
    if enrollment is not None:
        follow_up = await session.scalar(
            select(ResearchFollowUpSnapshot)
            .where(ResearchFollowUpSnapshot.research_enrollment_id == enrollment.id)
            .order_by(ResearchFollowUpSnapshot.created_at.desc())
        )
    cohort_state = _cohorts(request).live_query_status()
    cohort_status = cohort_state["status"]
    return {
        "screening_id": screening_id,
        "dropout_prediction": {
            "status": "needs_enrollment"
            if enrollment is None
            else "ready"
            if follow_up and follow_up.status == "ready"
            else "needs_follow_up",
            "enrollment_id": enrollment.id if enrollment else None,
            "follow_up_snapshot_id": follow_up.id if follow_up else None,
        },
        "cohort_context": {
            "status": cohort_status,
            "representations": ["patient_fact", "screening_profile"],
            "active_run_id": cohort_state["run_id"],
            "message": cohort_state["message"],
        },
        "similarity": {
            "status": cohort_status,
            "representations": ["patient_fact", "screening_profile"],
            "active_run_id": cohort_state["run_id"],
            "message": cohort_state["message"],
        },
    }


@router.post("/screenings/{screening_id}/enrollment", status_code=status.HTTP_201_CREATED)
async def start_enrollment(
    screening_id: uuid.UUID, payload: EnrollmentCreate, session: SessionDep, user: CurrentUser
) -> dict[str, Any]:
    supplied = {
        name: SourcedFeatureValue(item.value, item.source)
        for name, item in payload.baseline.items()
    }
    invalid = sorted(set(supplied) - set(USER_BASELINE_FEATURES))
    if invalid:
        raise ApplicationError(
            code="RESEARCH_BASELINE_INVALID",
            message="Only enrollment-owned baseline fields may be submitted.",
            status_code=422,
            details=[{"field": name} for name in invalid],
        )
    existing = await enrollment_for_screening(session, user.id, screening_id)
    if existing is not None:
        existing_user_baseline = {
            name: (
                existing.baseline_values_json.get(name),
                existing.baseline_sources_json.get(name),
            )
            for name in USER_BASELINE_FEATURES
            if name in existing.baseline_values_json
        }
        requested_user_baseline = {
            name: (item.value, item.source) for name, item in supplied.items()
        }
        if (
            existing.enrollment_date == payload.enrollment_date
            and existing_user_baseline == requested_user_baseline
        ):
            return enrollment_payload(existing)
        raise ApplicationError(
            code="RESEARCH_ENROLLMENT_CONFLICT",
            message="The saved screening already has a different research enrollment context.",
            status_code=409,
        )
    try:
        enrollment = await create_enrollment(
            session,
            owner_id=user.id,
            screening_id=screening_id,
            enrollment_date=payload.enrollment_date,
            supplied_baseline=supplied,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApplicationError(
            code="RESEARCH_ENROLLMENT_CONFLICT",
            message="The saved screening already has a research enrollment.",
            status_code=409,
        ) from exc
    except Exception:
        await session.rollback()
        raise
    return enrollment_payload(enrollment)


@router.get("/enrollments/{enrollment_id}")
async def get_enrollment(
    enrollment_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> dict[str, Any]:
    return enrollment_payload(await owned_enrollment(session, user.id, enrollment_id))


@router.get("/enrollments/{enrollment_id}/events")
async def list_enrollment_events(
    enrollment_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    through_day: Annotated[int, Query(ge=0, le=3650)] = 30,
) -> dict[str, Any]:
    await owned_enrollment(session, user.id, enrollment_id)
    groups: dict[str, list[dict[str, Any]]] = {}
    for name, model in (
        ("dose_events", ResearchDoseEvent),
        ("visit_events", ResearchVisitEvent),
        ("measurements", ResearchMeasurement),
        ("adverse_events", ResearchAdverseEvent),
    ):
        rows = list(
            await session.scalars(
                select(model)
                .where(
                    model.owner_id == user.id,
                    model.research_enrollment_id == enrollment_id,
                    model.event_day <= through_day,
                )
                .order_by(model.event_day, model.recorded_at, model.id)
            )
        )
        superseded = {
            row.supersedes_event_id for row in rows if row.supersedes_event_id is not None
        }
        groups[name] = [
            {**_event_payload(row), "is_superseded": row.id in superseded} for row in rows
        ]
    return {
        "research_enrollment_id": enrollment_id,
        "through_day": through_day,
        **groups,
    }


async def _event_context(
    session: AsyncSession,
    user_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    model: Any,
    source: EventSource,
    event_date: date,
) -> tuple[ResearchEnrollment, Any | None, int]:
    enrollment = await owned_enrollment(session, user_id, enrollment_id)
    event_day = (event_date - enrollment.enrollment_date).days
    if event_day < 0:
        raise ApplicationError(
            code="RESEARCH_EVENT_DATE_INVALID",
            message="Event date cannot precede enrollment.",
            status_code=422,
        )
    previous = None
    if source.supersedes_event_id is not None:
        previous = await session.scalar(
            select(model).where(
                model.id == source.supersedes_event_id,
                model.owner_id == user_id,
                model.research_enrollment_id == enrollment_id,
            )
        )
        if previous is None:
            raise ApplicationError(
                code="RESEARCH_EVENT_NOT_FOUND",
                message="The event being corrected was not found.",
                status_code=404,
            )
    if source.source_document_id is not None:
        document = await session.scalar(
            select(Document.id).where(
                Document.id == source.source_document_id, Document.owner_id == user_id
            )
        )
        if document is None:
            raise ApplicationError(
                code="RESEARCH_EVENT_SOURCE_NOT_FOUND",
                message="The source document was not found.",
                status_code=404,
            )
    return enrollment, previous, event_day


def _event_payload(row: Any) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


async def _commit_event(session: AsyncSession, row: Any) -> dict[str, Any]:
    try:
        session.add(row)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApplicationError(
            code="RESEARCH_EVENT_CORRECTION_CONFLICT",
            message="That event has already been superseded.",
            status_code=409,
        ) from exc
    except Exception:
        await session.rollback()
        raise
    return _event_payload(row)


@router.post("/enrollments/{enrollment_id}/dose-events", status_code=201)
async def add_dose_event(
    enrollment_id: uuid.UUID, payload: DoseEventCreate, session: SessionDep, user: CurrentUser
) -> dict[str, Any]:
    _, _, event_day = await _event_context(
        session, user.id, enrollment_id, ResearchDoseEvent, payload, payload.scheduled_date
    )
    row = ResearchDoseEvent(
        owner_id=user.id,
        research_enrollment_id=enrollment_id,
        event_day=event_day,
        recorded_by_id=user.id,
        **payload.model_dump(),
    )
    return await _commit_event(session, row)


@router.post("/enrollments/{enrollment_id}/visit-events", status_code=201)
async def add_visit_event(
    enrollment_id: uuid.UUID, payload: VisitEventCreate, session: SessionDep, user: CurrentUser
) -> dict[str, Any]:
    _, _, event_day = await _event_context(
        session, user.id, enrollment_id, ResearchVisitEvent, payload, payload.scheduled_date
    )
    delay = (
        (payload.completed_date - payload.scheduled_date).days if payload.completed_date else None
    )
    row = ResearchVisitEvent(
        owner_id=user.id,
        research_enrollment_id=enrollment_id,
        event_day=event_day,
        delay_days=delay,
        recorded_by_id=user.id,
        **payload.model_dump(),
    )
    return await _commit_event(session, row)


@router.post("/enrollments/{enrollment_id}/measurements", status_code=201)
async def add_measurement(
    enrollment_id: uuid.UUID, payload: MeasurementCreate, session: SessionDep, user: CurrentUser
) -> dict[str, Any]:
    _, _, event_day = await _event_context(
        session, user.id, enrollment_id, ResearchMeasurement, payload, payload.observed_date
    )
    values = payload.model_dump()
    values["reference_range_json"] = values.pop("reference_range")
    row = ResearchMeasurement(
        owner_id=user.id,
        research_enrollment_id=enrollment_id,
        event_day=event_day,
        recorded_by_id=user.id,
        **values,
    )
    return await _commit_event(session, row)


@router.post("/enrollments/{enrollment_id}/adverse-events", status_code=201)
async def add_adverse_event(
    enrollment_id: uuid.UUID, payload: AdverseEventCreate, session: SessionDep, user: CurrentUser
) -> dict[str, Any]:
    _, _, event_day = await _event_context(
        session, user.id, enrollment_id, ResearchAdverseEvent, payload, payload.onset_date
    )
    row = ResearchAdverseEvent(
        owner_id=user.id,
        research_enrollment_id=enrollment_id,
        event_day=event_day,
        recorded_by_id=user.id,
        **payload.model_dump(),
    )
    return await _commit_event(session, row)


@router.post("/enrollments/{enrollment_id}/follow-up-snapshots", status_code=201)
async def create_follow_up(
    enrollment_id: uuid.UUID,
    payload: FollowUpSnapshotCreate,
    session: SessionDep,
    user: CurrentUser,
) -> dict[str, Any]:
    enrollment = await owned_enrollment(session, user.id, enrollment_id)
    try:
        snapshot = await build_follow_up_snapshot(
            session, enrollment=enrollment, confirmations=payload.model_dump()
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return follow_up_payload(snapshot)


@router.get("/enrollments/{enrollment_id}/follow-up-snapshots")
async def list_follow_ups(
    enrollment_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[dict[str, Any]]:
    await owned_enrollment(session, user.id, enrollment_id)
    rows = await session.scalars(
        select(ResearchFollowUpSnapshot)
        .where(ResearchFollowUpSnapshot.research_enrollment_id == enrollment_id)
        .order_by(ResearchFollowUpSnapshot.created_at.desc())
    )
    return [follow_up_payload(row) for row in rows]


@router.get("/risk/screenings/{screening_id}/context")
async def get_risk_context(
    screening_id: uuid.UUID, request: Request, session: SessionDep, user: CurrentUser
) -> dict[str, Any]:
    await owned_screening(session, user.id, screening_id)
    enrollment = await enrollment_for_screening(session, user.id, screening_id)
    follow_up = None
    if enrollment is not None:
        follow_up = await session.scalar(
            select(ResearchFollowUpSnapshot)
            .where(ResearchFollowUpSnapshot.research_enrollment_id == enrollment.id)
            .order_by(ResearchFollowUpSnapshot.created_at.desc())
        )
    model = await active_model(session)
    return {
        "screening_id": screening_id,
        "status": "unlinked"
        if enrollment is None
        else "ready"
        if follow_up and follow_up.status == "ready"
        else "incomplete",
        "enrollment": enrollment_payload(enrollment) if enrollment else None,
        "follow_up": follow_up_payload(follow_up) if follow_up else None,
        "model": _model_payload(model, _artifacts(request)),
    }


@router.post("/risk/predictions", status_code=201)
async def predict_dropout_risk(
    payload: PredictionCreate, request: Request, session: SessionDep, user: CurrentUser
) -> dict[str, Any]:
    try:
        prediction = await create_prediction(
            session,
            owner_id=user.id,
            follow_up_snapshot_id=payload.follow_up_snapshot_id,
            artifacts=_artifacts(request),
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    enrollment = await session.get(ResearchEnrollment, prediction.research_enrollment_id)
    model = await session.get(ResearchModelVersion, prediction.model_version_id)
    if enrollment is None or model is None:
        raise ApplicationError(
            code="RESEARCH_PREDICTION_INVALID",
            message="Stored prediction metadata is incomplete.",
            status_code=500,
        )
    return prediction_payload(prediction, enrollment, model)


def _prediction_statement(owner_id: uuid.UUID) -> Any:
    return (
        select(ResearchPrediction, ResearchEnrollment, ResearchModelVersion)
        .join(
            ResearchEnrollment, ResearchEnrollment.id == ResearchPrediction.research_enrollment_id
        )
        .join(ResearchModelVersion, ResearchModelVersion.id == ResearchPrediction.model_version_id)
        .where(ResearchPrediction.owner_id == owner_id)
    )


@router.get("/risk/predictions")
async def list_risk_predictions(
    session: SessionDep,
    user: CurrentUser,
    screening_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[dict[str, Any]]:
    statement = (
        _prediction_statement(user.id).order_by(ResearchPrediction.created_at.desc()).limit(limit)
    )
    if screening_id is not None:
        statement = statement.where(ResearchEnrollment.screening_id == screening_id)
    rows = (await session.execute(statement)).all()
    return [prediction_payload(*row) for row in rows]


@router.get("/risk/predictions/{prediction_id}")
async def get_risk_prediction(
    prediction_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> dict[str, Any]:
    row = (
        await session.execute(
            _prediction_statement(user.id).where(ResearchPrediction.id == prediction_id)
        )
    ).one_or_none()
    if row is None:
        raise ApplicationError(
            code="RESEARCH_PREDICTION_NOT_FOUND",
            message="Research prediction was not found.",
            status_code=404,
        )
    return prediction_payload(*row)


async def _overview(
    session: AsyncSession, owner_id: uuid.UUID, trial_version_id: uuid.UUID
) -> dict[str, Any]:
    screenings = list(
        await session.scalars(
            select(Screening).where(
                Screening.owner_id == owner_id, Screening.trial_version_id == trial_version_id
            )
        )
    )
    if not screenings:
        raise ApplicationError(
            code="RESEARCH_TRIAL_OVERVIEW_NOT_FOUND",
            message="No saved screenings exist for this approved trial version.",
            status_code=404,
        )
    states = [screening.overall_state.value for screening in screenings]
    eligible_ids = {
        screening.id
        for screening in screenings
        if screening.overall_state == OverallState.potentially_eligible
    }
    model = await active_model(session)
    predictions = (
        (
            await session.execute(
                select(ResearchPrediction, ResearchEnrollment)
                .join(
                    ResearchEnrollment,
                    ResearchEnrollment.id == ResearchPrediction.research_enrollment_id,
                )
                .where(
                    ResearchPrediction.owner_id == owner_id,
                    ResearchPrediction.model_version_id == model.id,
                    ResearchEnrollment.screening_id.in_(eligible_ids),
                )
                .order_by(ResearchPrediction.created_at.desc())
            )
        ).all()
        if eligible_ids
        else []
    )
    latest: dict[uuid.UUID, ResearchPrediction] = {}
    for prediction, enrollment in predictions:
        latest.setdefault(enrollment.id, prediction)
    labels = [prediction.research_label for prediction in latest.values()]
    first = screenings[0]
    return {
        "trial_version_id": trial_version_id,
        "trial": {
            "registry_id": first.trial_registry_id,
            "title": first.trial_title,
            "version": first.trial_version_number,
        },
        "screening_counts": {
            "potentially_eligible": states.count("potentially_eligible"),
            "needs_review": states.count("needs_review"),
            "likely_ineligible": states.count("likely_ineligible"),
        },
        "retention": {
            "eligible_total": len(eligible_ids),
            "linked_predictions": len(latest),
            "unlinked_eligible": len(eligible_ids) - len(latest),
            "risk_bands": {
                "lower": labels.count("lower"),
                "near_threshold": labels.count("near_threshold"),
                "higher": labels.count("higher"),
            },
            "model_version": f"{model.model_name}:{model.version}",
            "horizon_day": model.horizon_day,
            "band_policy_version": model.band_policy_version,
        },
    }


@router.get("/trial-overview")
async def list_trial_overview(session: SessionDep, user: CurrentUser) -> list[dict[str, Any]]:
    version_ids = list(
        await session.scalars(
            select(Screening.trial_version_id)
            .where(Screening.owner_id == user.id)
            .distinct()
            .order_by(Screening.trial_version_id)
        )
    )
    return [await _overview(session, user.id, version_id) for version_id in version_ids]


@router.get("/trial-overview/{trial_version_id}")
async def get_trial_overview(
    trial_version_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> dict[str, Any]:
    return await _overview(session, user.id, trial_version_id)
