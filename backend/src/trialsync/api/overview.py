from __future__ import annotations

import uuid
from collections import Counter
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Request
from sqlalchemy import func, select
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
from trialsync.research.risk.artifacts import RiskArtifactError
from trialsync.research.risk.service import ACTIVE_MODEL_DATABASE_ID, validate_descriptor
from trialsync.schemas import (
    OverviewActivityPoint,
    OverviewAttentionItem,
    OverviewDropout,
    OverviewDropoutCounts,
    OverviewEligibility,
    OverviewRead,
    OverviewScreeningSummary,
)

router = APIRouter(prefix="/api/v1", tags=["overview"])
ACTIVITY_WINDOW_DAYS = 56
ATTENTION_LIMIT = 6
RECENT_LIMIT = 6
WorkflowKind = Literal[
    "dropout_not_started",
    "dropout_information_needed",
    "dropout_ready",
    "predicted",
]


def _patient_name(screening: Screening) -> str:
    value = screening.patient_snapshot.source_summary.get("display_name")
    return str(value).strip() if value else "Patient"


def _screening_summary(screening: Screening) -> OverviewScreeningSummary:
    return OverviewScreeningSummary(
        screening_id=screening.id,
        patient_name=_patient_name(screening),
        trial_title=screening.trial_title,
        trial_registry_id=screening.trial_registry_id,
        overall_state=screening.overall_state.value,
        screening_date=screening.screening_date,
        created_at=screening.created_at,
    )


def _workflow_kind(
    enrollment: ResearchEnrollment | None,
    follow_up: ResearchFollowUpSnapshot | None,
    prediction: ResearchPrediction | None,
) -> WorkflowKind:
    if enrollment is None:
        return "dropout_not_started"
    if prediction is not None:
        return "predicted"
    if follow_up is not None and follow_up.status == "ready":
        return "dropout_ready"
    return "dropout_information_needed"


async def _research_status(
    request: Request, session: AsyncSession
) -> tuple[Literal["available", "degraded"], str | None]:
    model = await session.get(ResearchModelVersion, ACTIVE_MODEL_DATABASE_ID)
    if model is None:
        return "degraded", "Dropout workflow summary is temporarily unavailable."
    try:
        descriptor = request.app.state.research_risk.descriptor()
        validate_descriptor(model, descriptor)
    except (RiskArtifactError, ApplicationError):
        return "degraded", "Dropout workflow summary is temporarily unavailable."
    return "available", None


@router.get("/overview", response_model=OverviewRead)
async def overview(request: Request, session: SessionDep, user: CurrentUser) -> OverviewRead:
    today = date.today()
    activity_start = today - timedelta(days=ACTIVITY_WINDOW_DAYS - 1)

    eligibility_rows = (
        await session.execute(
            select(Screening.overall_state, func.count(Screening.id))
            .where(Screening.owner_id == user.id)
            .group_by(Screening.overall_state)
        )
    ).all()
    eligibility_counts = {state.value: int(count) for state, count in eligibility_rows}
    eligibility = OverviewEligibility(
        total=sum(eligibility_counts.values()),
        potentially_eligible=eligibility_counts.get("potentially_eligible", 0),
        likely_ineligible=eligibility_counts.get("likely_ineligible", 0),
        needs_review=eligibility_counts.get("needs_review", 0),
    )

    activity_rows = (
        await session.execute(
            select(Screening.screening_date, func.count(Screening.id))
            .where(
                Screening.owner_id == user.id,
                Screening.screening_date >= activity_start,
                Screening.screening_date <= today,
            )
            .group_by(Screening.screening_date)
            .order_by(Screening.screening_date)
        )
    ).all()
    activity_by_date = {screening_date: int(count) for screening_date, count in activity_rows}
    activity = [
        OverviewActivityPoint(
            date=activity_start + timedelta(days=offset),
            count=activity_by_date.get(activity_start + timedelta(days=offset), 0),
        )
        for offset in range(ACTIVITY_WINDOW_DAYS)
    ]

    recent = list(
        await session.scalars(
            select(Screening)
            .options(selectinload(Screening.patient_snapshot))
            .where(Screening.owner_id == user.id)
            .order_by(Screening.created_at.desc(), Screening.id.desc())
            .limit(RECENT_LIMIT)
        )
    )
    needs_review = list(
        await session.scalars(
            select(Screening)
            .options(selectinload(Screening.patient_snapshot))
            .where(
                Screening.owner_id == user.id,
                Screening.overall_state == OverallState.needs_review,
            )
            .order_by(Screening.created_at.desc(), Screening.id.desc())
            .limit(ATTENTION_LIMIT)
        )
    )
    eligible = list(
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

    screening_ids = [item.id for item in eligible]
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
    enrollment_by_screening = {item.screening_id: item for item in enrollments}
    enrollment_ids = [item.id for item in enrollments]
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
    predictions = (
        list(
            await session.scalars(
                select(ResearchPrediction)
                .where(
                    ResearchPrediction.owner_id == user.id,
                    ResearchPrediction.research_enrollment_id.in_(enrollment_ids),
                    ResearchPrediction.model_version_id == ACTIVE_MODEL_DATABASE_ID,
                )
                .order_by(ResearchPrediction.created_at.desc(), ResearchPrediction.id.desc())
            )
        )
        if enrollment_ids
        else []
    )
    follow_up_by_enrollment: dict[uuid.UUID, ResearchFollowUpSnapshot] = {}
    for follow_up_snapshot in follow_ups:
        follow_up_by_enrollment.setdefault(
            follow_up_snapshot.research_enrollment_id, follow_up_snapshot
        )
    prediction_by_enrollment: dict[uuid.UUID, ResearchPrediction] = {}
    for prediction in predictions:
        prediction_by_enrollment.setdefault(prediction.research_enrollment_id, prediction)

    workflow_by_screening: dict[uuid.UUID, WorkflowKind] = {}
    for screening in eligible:
        enrollment = enrollment_by_screening.get(screening.id)
        current_follow_up = follow_up_by_enrollment.get(enrollment.id) if enrollment else None
        current_prediction = prediction_by_enrollment.get(enrollment.id) if enrollment else None
        if (
            current_prediction is not None
            and (
                current_follow_up is None
                or current_prediction.follow_up_snapshot_id != current_follow_up.id
            )
        ):
            current_prediction = None
        workflow_by_screening[screening.id] = _workflow_kind(
            enrollment,
            current_follow_up,
            current_prediction,
        )
    workflow_counts = Counter(workflow_by_screening.values())
    research_status, research_message = await _research_status(request, session)
    dropout = OverviewDropout(
        status=research_status,
        message=research_message,
        eligible_total=len(eligible),
        counts=OverviewDropoutCounts(
            not_started=workflow_counts["dropout_not_started"],
            information_needed=workflow_counts["dropout_information_needed"],
            ready=workflow_counts["dropout_ready"],
            predicted=workflow_counts["predicted"],
        ),
    )

    attention = [
        OverviewAttentionItem(
            kind="eligibility_review",
            screening_id=item.id,
            patient_name=_patient_name(item),
            trial_title=item.trial_title,
            screening_date=item.screening_date,
        )
        for item in needs_review
    ]
    for eligible_screening in eligible:
        kind = workflow_by_screening[eligible_screening.id]
        if kind == "predicted" or len(attention) >= ATTENTION_LIMIT:
            continue
        attention.append(
            OverviewAttentionItem(
                kind=kind,
                screening_id=eligible_screening.id,
                patient_name=_patient_name(eligible_screening),
                trial_title=eligible_screening.trial_title,
                screening_date=eligible_screening.screening_date,
            )
        )

    return OverviewRead(
        generated_on=today,
        activity_start_date=activity_start,
        activity_end_date=today,
        eligibility=eligibility,
        activity=activity,
        dropout=dropout,
        attention=attention[:ATTENTION_LIMIT],
        recent_screenings=[_screening_summary(item) for item in recent],
    )
