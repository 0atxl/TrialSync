from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from trialsync.api.deps import CurrentUser, SessionDep
from trialsync.api.errors import ApplicationError
from trialsync.db.models import (
    OverallState,
    ResearchEnrollment,
    ResearchFollowUpSnapshot,
    ResearchModelVersion,
    ResearchPrediction,
    Screening,
)
from trialsync.research.artifacts import CohortArtifactService
from trialsync.research.risk import RiskArtifactError, RiskArtifactService, SourcedFeatureValue
from trialsync.research.risk.service import (
    ACTIVE_MODEL_DATABASE_ID,
    USER_BASELINE_FEATURES,
    active_model,
    build_follow_up_summary,
    create_enrollment,
    create_prediction,
    enrollment_for_screening,
    enrollment_payload,
    follow_up_payload,
    missed_dose_scenarios,
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


class Day30SummaryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scheduled_doses: int = Field(ge=1, le=1000)
    missed_doses: int = Field(ge=0, le=1000)
    scheduled_visits: int = Field(ge=1, le=100)
    missed_visits: int = Field(ge=0, le=100)
    delayed_visits: int = Field(ge=0, le=100)
    total_visit_delay_days: int = Field(ge=0, le=3000)
    expected_assessments: int = Field(ge=1, le=100)
    completed_assessments: int = Field(ge=1, le=100)
    latest_functional_severity: float = Field(ge=0, le=1)
    latest_assessment_day: int = Field(ge=1, le=30)
    adverse_event_count: int = Field(ge=0, le=100)
    adverse_event_burden: int = Field(ge=0, le=400)

    @model_validator(mode="after")
    def validate_totals(self) -> Day30SummaryCreate:
        if self.missed_doses > self.scheduled_doses:
            raise ValueError("missed_doses cannot exceed scheduled_doses")
        if self.missed_visits > self.scheduled_visits:
            raise ValueError("missed_visits cannot exceed scheduled_visits")
        completed_visits = self.scheduled_visits - self.missed_visits
        if self.delayed_visits > completed_visits:
            raise ValueError("delayed_visits cannot exceed completed visits")
        if self.delayed_visits == 0 and self.total_visit_delay_days != 0:
            raise ValueError("total_visit_delay_days must be zero when no visits were delayed")
        if self.delayed_visits and self.total_visit_delay_days < self.delayed_visits:
            raise ValueError(
                "total_visit_delay_days must include at least one day per delayed visit"
            )
        if self.total_visit_delay_days > completed_visits * 30:
            raise ValueError("total_visit_delay_days exceeds the day-30 observation window")
        if self.completed_assessments > self.expected_assessments:
            raise ValueError("completed_assessments cannot exceed expected_assessments")
        if self.adverse_event_count == 0 and self.adverse_event_burden != 0:
            raise ValueError("adverse_event_burden must be zero when no events occurred")
        if self.adverse_event_count and not (
            self.adverse_event_count <= self.adverse_event_burden <= self.adverse_event_count * 4
        ):
            raise ValueError("adverse_event_burden must equal the sum of grades 1 through 4")
        return self


class PredictionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    follow_up_snapshot_id: uuid.UUID


class ScenarioCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    follow_up_snapshot_id: uuid.UUID


def _artifacts(request: Request) -> RiskArtifactService:
    return cast(RiskArtifactService, request.app.state.research_risk)


def _cohorts(request: Request) -> CohortArtifactService:
    return cast(CohortArtifactService, request.app.state.research_cohorts)


def _patient_display_name(screening: Screening) -> str:
    value = screening.patient_snapshot.source_summary.get("display_name")
    return str(value).strip() if value else "Patient"


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


@router.post("/enrollments/{enrollment_id}/day30-summary", status_code=201)
async def create_day30_summary(
    enrollment_id: uuid.UUID,
    payload: Day30SummaryCreate,
    session: SessionDep,
    user: CurrentUser,
) -> dict[str, Any]:
    enrollment = await owned_enrollment(session, user.id, enrollment_id)
    try:
        snapshot = await build_follow_up_summary(
            session, enrollment=enrollment, summary=payload.model_dump()
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
        "follow_up_stale": False,
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


@router.post("/risk/scenarios")
async def dropout_scenarios(
    payload: ScenarioCreate, request: Request, session: SessionDep, user: CurrentUser
) -> dict[str, Any]:
    snapshot = await session.scalar(
        select(ResearchFollowUpSnapshot).where(
            ResearchFollowUpSnapshot.id == payload.follow_up_snapshot_id,
            ResearchFollowUpSnapshot.owner_id == user.id,
        )
    )
    if snapshot is None:
        raise ApplicationError(
            code="RESEARCH_FOLLOW_UP_NOT_FOUND",
            message="Day-30 inputs were not found.",
            status_code=404,
        )
    model = await active_model(session)
    artifacts = _artifacts(request)
    validate_descriptor(model, artifacts.descriptor())
    return {
        "follow_up_snapshot_id": snapshot.id,
        "scenario": "additional_missed_doses",
        "points": missed_dose_scenarios(snapshot, artifacts),
        "threshold": float(model.threshold),
        "horizon_day": model.horizon_day,
    }


def _prediction_statement(owner_id: uuid.UUID) -> Any:
    return (
        select(ResearchPrediction, ResearchEnrollment, ResearchModelVersion)
        .join(
            ResearchEnrollment, ResearchEnrollment.id == ResearchPrediction.research_enrollment_id
        )
        .join(ResearchModelVersion, ResearchModelVersion.id == ResearchPrediction.model_version_id)
        .where(ResearchPrediction.owner_id == owner_id)
    )


@router.get("/risk/worklist")
async def dropout_worklist(session: SessionDep, user: CurrentUser) -> list[dict[str, Any]]:
    screenings = list(
        await session.scalars(
            select(Screening)
            .options(selectinload(Screening.patient_snapshot))
            .where(
                Screening.owner_id == user.id,
                Screening.overall_state == OverallState.potentially_eligible,
            )
            .order_by(Screening.created_at.desc(), Screening.id.desc())
        )
    )
    screening_ids = [screening.id for screening in screenings]
    enrollments = (
        list(
            await session.scalars(
                select(ResearchEnrollment).where(
                    ResearchEnrollment.owner_id == user.id,
                    ResearchEnrollment.screening_id.in_(screening_ids),
                )
            )
        )
        if screening_ids
        else []
    )
    enrollment_by_screening = {enrollment.screening_id: enrollment for enrollment in enrollments}
    enrollment_ids = [enrollment.id for enrollment in enrollments]
    follow_ups = (
        list(
            await session.scalars(
                select(ResearchFollowUpSnapshot)
                .where(
                    ResearchFollowUpSnapshot.owner_id == user.id,
                    ResearchFollowUpSnapshot.research_enrollment_id.in_(enrollment_ids),
                )
                .order_by(
                    ResearchFollowUpSnapshot.created_at.desc(),
                    ResearchFollowUpSnapshot.id.desc(),
                )
            )
        )
        if enrollment_ids
        else []
    )
    latest_follow_up: dict[uuid.UUID, ResearchFollowUpSnapshot] = {}
    for follow_up_row in follow_ups:
        latest_follow_up.setdefault(follow_up_row.research_enrollment_id, follow_up_row)

    prediction_rows = (
        (
            await session.execute(
                _prediction_statement(user.id)
                .where(
                    ResearchPrediction.model_version_id == ACTIVE_MODEL_DATABASE_ID,
                    ResearchEnrollment.id.in_(enrollment_ids),
                )
                .order_by(ResearchPrediction.created_at.desc(), ResearchPrediction.id.desc())
            )
        ).all()
        if enrollment_ids
        else []
    )
    latest_prediction: dict[uuid.UUID, tuple[ResearchPrediction, ResearchModelVersion]] = {}
    for prediction_row, enrollment_row, model_row in prediction_rows:
        latest_prediction.setdefault(enrollment_row.id, (prediction_row, model_row))

    rows: list[dict[str, Any]] = []
    for screening in screenings:
        current_enrollment = enrollment_by_screening.get(screening.id)
        current_follow_up = (
            latest_follow_up.get(current_enrollment.id) if current_enrollment else None
        )
        prediction_pair = (
            latest_prediction.get(current_enrollment.id) if current_enrollment else None
        )
        current_prediction_row = prediction_pair[0] if prediction_pair else None
        current_model = prediction_pair[1] if prediction_pair else None
        current_prediction = bool(
            current_prediction_row
            and current_follow_up
            and current_prediction_row.follow_up_snapshot_id == current_follow_up.id
        )
        if current_enrollment is None:
            workflow_status = "not_started"
            next_action = "start_follow_up"
        elif current_follow_up is None or current_follow_up.status != "ready":
            workflow_status = "information_needed"
            next_action = "review_day30"
        elif not current_prediction:
            workflow_status = "ready"
            next_action = "predict"
        else:
            workflow_status = "predicted"
            next_action = "view_prediction"
        timestamps = [screening.created_at]
        if current_enrollment:
            timestamps.append(current_enrollment.created_at)
        if current_follow_up:
            timestamps.append(current_follow_up.created_at)
        if current_prediction and current_prediction_row:
            timestamps.append(current_prediction_row.created_at)
        rows.append(
            {
                "screening_id": screening.id,
                "patient_name": _patient_display_name(screening),
                "trial_title": screening.trial_title,
                "screening_date": screening.screening_date,
                "workflow_status": workflow_status,
                "next_action": next_action,
                "updated_at": max(timestamps),
                "estimate": {
                    "probability": float(current_prediction_row.probability),
                    "threshold": float(current_model.threshold),
                    "research_label": current_prediction_row.research_label,
                    "horizon_day": current_model.horizon_day,
                    "created_at": current_prediction_row.created_at,
                }
                if current_prediction and current_prediction_row and current_model
                else None,
            }
        )
    return rows


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
