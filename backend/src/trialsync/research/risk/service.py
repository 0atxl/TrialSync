from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from trialsync.api.errors import ApplicationError
from trialsync.db.models import (
    Assertion,
    ResearchAdverseEvent,
    ResearchDoseEvent,
    ResearchEnrollment,
    ResearchFollowUpSnapshot,
    ResearchMeasurement,
    ResearchModelVersion,
    ResearchPrediction,
    ResearchVisitEvent,
    Screening,
    TrialVersion,
)
from trialsync.research.risk.artifacts import (
    RiskArtifactError,
    RiskArtifactService,
    RiskModelDescriptor,
)
from trialsync.research.risk.features import (
    BASELINE_FEATURES,
    FEATURE_NAMES,
    FeatureSnapshotError,
    FeatureValue,
    SourcedFeatureValue,
    build_feature_snapshot,
    feature_group,
    validate_partial_features,
)

ACTIVE_MODEL_DATABASE_ID = uuid.UUID("886f64ca-8b57-5dd1-babb-7dfa72480fcf")
FEATURE_CONTRACT_VERSION = "r4-day30-features-v1"
OBSERVATION_CUTOFF_DAY = 30
PREDICTION_HORIZON_DAY = 90
DISCLAIMER = "Research prediction only; not a clinical or eligibility decision."
USER_BASELINE_FEATURES = (
    "site_region",
    "treatment_arm",
    "baseline_functional_severity",
    "patient_reported_burden",
    "baseline_treatment_burden",
    "travel_access_burden",
    "support_availability",
)


def _checksum(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


async def owned_screening(
    session: AsyncSession, owner_id: uuid.UUID, screening_id: uuid.UUID
) -> tuple[Screening, TrialVersion]:
    screening = await session.scalar(
        select(Screening)
        .options(selectinload(Screening.patient_snapshot))
        .where(Screening.id == screening_id, Screening.owner_id == owner_id)
    )
    if screening is None:
        raise ApplicationError(
            code="SCREENING_NOT_FOUND", message="Screening was not found.", status_code=404
        )
    version = await session.scalar(
        select(TrialVersion)
        .options(selectinload(TrialVersion.trial))
        .where(TrialVersion.id == screening.trial_version_id)
    )
    if version is None:
        raise ApplicationError(
            code="RESEARCH_CONTEXT_INVALID",
            message="The saved screening no longer resolves to its approved trial version.",
            status_code=409,
        )
    return screening, version


def _condition_category(condition: str) -> str | None:
    normalized = condition.casefold()
    mappings = {
        "metabolic": ("metabolic", "diabetes", "glucose"),
        "cardiovascular": ("cardiovascular", "hypertension", "cardiac"),
        "renal": ("renal", "kidney", "egfr"),
        "oncology": ("oncology", "cancer", "tumor"),
        "respiratory": ("respiratory", "asthma", "pulmonary"),
    }
    return next(
        (
            category
            for category, words in mappings.items()
            if any(word in normalized for word in words)
        ),
        None,
    )


def snapshot_baseline(
    screening: Screening, version: TrialVersion
) -> dict[str, SourcedFeatureValue]:
    snapshot = screening.patient_snapshot
    values: dict[str, SourcedFeatureValue] = {}
    if snapshot.date_of_birth is not None:
        born = snapshot.date_of_birth
        on = screening.screening_date
        age = on.year - born.year - ((on.month, on.day) < (born.month, born.day))
        values["age"] = SourcedFeatureValue(age, "immutable_patient_snapshot")
    sex = snapshot.source_summary.get("sex")
    if isinstance(sex, str):
        normalized_sex = sex.casefold()
        if normalized_sex in {"female", "male", "intersex_or_other", "not_recorded"}:
            values["sex"] = SourcedFeatureValue(normalized_sex, "immutable_patient_snapshot")
    condition_count = 0
    medication_count = 0
    for fact in snapshot.facts_json:
        if fact.get("assertion") != Assertion.present.value:
            continue
        if fact.get("fact_type") == "condition":
            condition_count += 1
        elif fact.get("fact_type") == "medication":
            medication_count += 1
    values["baseline_comorbidity_burden"] = SourcedFeatureValue(
        condition_count, "immutable_patient_snapshot"
    )
    values["medication_count"] = SourcedFeatureValue(medication_count, "immutable_patient_snapshot")
    category = _condition_category(version.trial.condition)
    if category is not None:
        values["condition_category"] = SourcedFeatureValue(category, "approved_trial_version")
    return values


def _enrollment_values(enrollment: ResearchEnrollment) -> dict[str, SourcedFeatureValue]:
    return {
        name: SourcedFeatureValue(
            value=cast(FeatureValue, value),
            source=str(enrollment.baseline_sources_json[name]),
        )
        for name, value in enrollment.baseline_values_json.items()
        if name in enrollment.baseline_sources_json
    }


async def enrollment_for_screening(
    session: AsyncSession, owner_id: uuid.UUID, screening_id: uuid.UUID
) -> ResearchEnrollment | None:
    return cast(
        ResearchEnrollment | None,
        await session.scalar(
            select(ResearchEnrollment).where(
                ResearchEnrollment.owner_id == owner_id,
                ResearchEnrollment.screening_id == screening_id,
            )
        ),
    )


async def owned_enrollment(
    session: AsyncSession, owner_id: uuid.UUID, enrollment_id: uuid.UUID
) -> ResearchEnrollment:
    enrollment = await session.scalar(
        select(ResearchEnrollment).where(
            ResearchEnrollment.id == enrollment_id, ResearchEnrollment.owner_id == owner_id
        )
    )
    if enrollment is None:
        raise ApplicationError(
            code="RESEARCH_ENROLLMENT_NOT_FOUND",
            message="Research enrollment was not found.",
            status_code=404,
        )
    return enrollment


async def create_enrollment(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    screening_id: uuid.UUID,
    enrollment_date: date,
    supplied_baseline: Mapping[str, SourcedFeatureValue],
) -> ResearchEnrollment:
    screening, version = await owned_screening(session, owner_id, screening_id)
    if enrollment_date < screening.screening_date:
        raise ApplicationError(
            code="RESEARCH_ENROLLMENT_DATE_INVALID",
            message="Enrollment date cannot precede the saved screening date.",
            status_code=422,
        )
    try:
        supplied = validate_partial_features(supplied_baseline, allowed=USER_BASELINE_FEATURES)
        baseline = snapshot_baseline(screening, version)
        baseline.update(supplied)
        baseline = validate_partial_features(baseline, allowed=BASELINE_FEATURES)
    except FeatureSnapshotError as exc:
        raise ApplicationError(
            code="RESEARCH_BASELINE_INVALID", message=str(exc), status_code=422
        ) from exc
    values = {name: item.value for name, item in baseline.items()}
    sources = {name: item.source for name, item in baseline.items()}
    baseline_hash = _checksum({"values": values, "sources": sources})
    context = {
        "owner_id": str(owner_id),
        "screening_id": str(screening.id),
        "patient_snapshot_id": str(screening.patient_snapshot_id),
        "patient_snapshot_hash": screening.patient_snapshot.content_hash,
        "trial_version_id": str(screening.trial_version_id),
        "trial_version": screening.trial_version_number,
        "screening_date": screening.screening_date.isoformat(),
        "engine_version": screening.engine_version,
        "dsl_version": screening.dsl_version,
        "terminology_version": screening.terminology_version,
        "unit_version": screening.unit_version,
    }
    enrollment = ResearchEnrollment(
        owner_id=owner_id,
        patient_snapshot_id=screening.patient_snapshot_id,
        trial_version_id=screening.trial_version_id,
        screening_id=screening.id,
        research_context_checksum=_checksum(context),
        enrollment_date=enrollment_date,
        observation_cutoff_day=OBSERVATION_CUTOFF_DAY,
        prediction_horizon_day=PREDICTION_HORIZON_DAY,
        baseline_values_json=values,
        baseline_sources_json=sources,
        baseline_snapshot_hash=baseline_hash,
        feature_contract_version=FEATURE_CONTRACT_VERSION,
        tracking_status="active",
        created_by_id=owner_id,
    )
    session.add(enrollment)
    await session.flush()
    return enrollment


async def _active_events(
    session: AsyncSession,
    model: Any,
    enrollment: ResearchEnrollment,
    cutoff_day: int,
) -> list[Any]:
    rows = list(
        await session.scalars(
            select(model)
            .where(
                model.owner_id == enrollment.owner_id,
                model.research_enrollment_id == enrollment.id,
                model.event_day <= cutoff_day,
            )
            .order_by(model.event_day, model.recorded_at, model.id)
        )
    )
    superseded = {row.supersedes_event_id for row in rows if row.supersedes_event_id is not None}
    return [row for row in rows if row.id not in superseded]


async def build_follow_up_snapshot(
    session: AsyncSession,
    *,
    enrollment: ResearchEnrollment,
    confirmations: Mapping[str, bool],
) -> ResearchFollowUpSnapshot:
    cutoff = enrollment.observation_cutoff_day
    doses = await _active_events(session, ResearchDoseEvent, enrollment, cutoff)
    visits = await _active_events(session, ResearchVisitEvent, enrollment, cutoff)
    measurements = await _active_events(session, ResearchMeasurement, enrollment, cutoff)
    adverse = await _active_events(session, ResearchAdverseEvent, enrollment, cutoff)
    values = _enrollment_values(enrollment)

    resolved_doses = [row for row in doses if row.status != "scheduled"]
    scheduled_doses = sum(row.scheduled_count for row in resolved_doses)
    if (
        confirmations.get("dose_record_complete") is True
        and len(resolved_doses) == len(doses)
        and scheduled_doses
    ):
        missed = sum(row.scheduled_count - row.administered_count for row in resolved_doses)
        values["missed_dose_rate"] = SourcedFeatureValue(
            missed / scheduled_doses, "derived:research_dose_events"
        )

    resolved_visits = [row for row in visits if row.status != "scheduled"]
    if (
        confirmations.get("visit_record_complete") is True
        and len(resolved_visits) == len(visits)
        and resolved_visits
    ):
        missed_visits = sum(row.status == "missed" for row in resolved_visits)
        delayed_visits = sum(row.status == "delayed" for row in resolved_visits)
        delays = [row.delay_days for row in resolved_visits if row.delay_days is not None]
        if len(delays) == len([row for row in resolved_visits if row.status != "missed"]):
            values["mean_visit_delay_days"] = SourcedFeatureValue(
                sum(delays) / len(delays) if delays else 0.0,
                "derived:research_visit_events",
            )
        values["missed_visit_rate"] = SourcedFeatureValue(
            missed_visits / len(resolved_visits), "derived:research_visit_events"
        )
        values["delayed_visit_count"] = SourcedFeatureValue(
            delayed_visits, "derived:research_visit_events"
        )

    if measurements and confirmations.get("measurement_record_complete") is True:
        missing_count = sum(not row.observed for row in measurements)
        values["measurement_missingness_rate"] = SourcedFeatureValue(
            missing_count / len(measurements), "derived:research_measurements"
        )
    functional = sorted(
        (
            row
            for row in measurements
            if row.concept == "functional_severity"
            and row.unit == "score"
            and row.observed
            and row.value_numeric is not None
        ),
        key=lambda row: (row.event_day, row.recorded_at, row.id),
    )
    if functional:
        values["latest_functional_severity"] = SourcedFeatureValue(
            float(functional[-1].value_numeric), "derived:research_measurements"
        )
        values["functional_observation_count"] = SourcedFeatureValue(
            len(functional), "derived:research_measurements"
        )
    baseline_severity = values.get("baseline_functional_severity")
    if functional and baseline_severity is not None and functional[-1].event_day > 0:
        last = functional[-1]
        slope = (float(last.value_numeric) - float(baseline_severity.value)) / last.event_day
        values["functional_severity_slope"] = SourcedFeatureValue(
            slope, "derived:research_measurements"
        )

    if adverse or confirmations.get("adverse_event_record_complete") is True:
        values["adverse_event_count"] = SourcedFeatureValue(
            len(adverse), "derived:research_adverse_events"
        )
        values["adverse_event_burden"] = SourcedFeatureValue(
            sum(row.severity_grade for row in adverse), "derived:research_adverse_events"
        )

    event_ids = {
        "dose": [str(row.id) for row in doses],
        "visit": [str(row.id) for row in visits],
        "measurement": [str(row.id) for row in measurements],
        "adverse_event": [str(row.id) for row in adverse],
        "confirmations": dict(sorted(confirmations.items())),
        "baseline_snapshot_hash": enrollment.baseline_snapshot_hash,
    }
    event_checksum = _checksum(event_ids)
    raw_values = {name: item.value for name, item in values.items()}
    raw_sources = {name: item.source for name, item in values.items()}
    missing = [name for name in FEATURE_NAMES if name not in values]
    snapshot_hash: str | None = None
    status = "incomplete"
    if not missing:
        try:
            complete = build_feature_snapshot(values)
        except FeatureSnapshotError as exc:
            raise ApplicationError(
                code="RESEARCH_FEATURE_SNAPSHOT_INVALID", message=str(exc), status_code=422
            ) from exc
        raw_values = complete.values
        raw_sources = complete.sources
        snapshot_hash = complete.checksum
        status = "ready"
    existing = await session.scalar(
        select(ResearchFollowUpSnapshot).where(
            ResearchFollowUpSnapshot.research_enrollment_id == enrollment.id,
            ResearchFollowUpSnapshot.cutoff_day == cutoff,
            ResearchFollowUpSnapshot.event_set_checksum == event_checksum,
        )
    )
    if existing is not None:
        return existing
    snapshot = ResearchFollowUpSnapshot(
        owner_id=enrollment.owner_id,
        research_enrollment_id=enrollment.id,
        cutoff_day=cutoff,
        feature_schema_version=FEATURE_CONTRACT_VERSION,
        feature_values_json=raw_values,
        feature_sources_json=raw_sources,
        feature_snapshot_hash=snapshot_hash,
        event_set_checksum=event_checksum,
        missing_features_json=missing,
        status=status,
    )
    session.add(snapshot)
    await session.flush()
    return snapshot


async def active_model(session: AsyncSession) -> ResearchModelVersion:
    model = await session.get(ResearchModelVersion, ACTIVE_MODEL_DATABASE_ID)
    if model is None:
        raise ApplicationError(
            code="RESEARCH_MODEL_UNAVAILABLE",
            message="The approved R5 model metadata is not installed.",
            status_code=503,
        )
    return model


def validate_descriptor(model: ResearchModelVersion, descriptor: RiskModelDescriptor) -> None:
    expected = {
        "candidate_id": model.candidate_id,
        "dataset_version": model.training_dataset_version,
        "dataset_checksum": model.training_dataset_checksum,
        "feature_schema_version": model.feature_schema_version,
        "feature_schema_checksum": model.feature_schema_checksum,
        "artifact_checksum": model.artifact_checksum,
        "band_policy_version": model.band_policy_version,
    }
    differences = [
        field
        for field, expected_value in expected.items()
        if getattr(descriptor, field) != expected_value
    ]
    if abs(descriptor.threshold - float(model.threshold)) > 1e-12:
        differences.append("threshold")
    if descriptor.horizon_day != model.horizon_day:
        differences.append("horizon_day")
    if differences:
        raise ApplicationError(
            code="RESEARCH_MODEL_DEGRADED",
            message="The configured R5 artifact does not match approved model metadata.",
            status_code=503,
            details=[{"field": field} for field in differences],
        )


def risk_band(probability: float, threshold: float) -> str:
    if probability < max(0.0, threshold - 0.05):
        return "lower"
    if probability <= min(1.0, threshold + 0.05):
        return "near_threshold"
    return "higher"


async def create_prediction(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    follow_up_snapshot_id: uuid.UUID,
    artifacts: RiskArtifactService,
) -> ResearchPrediction:
    follow_up = await session.scalar(
        select(ResearchFollowUpSnapshot).where(
            ResearchFollowUpSnapshot.id == follow_up_snapshot_id,
            ResearchFollowUpSnapshot.owner_id == owner_id,
        )
    )
    if follow_up is None:
        raise ApplicationError(
            code="RESEARCH_FOLLOW_UP_NOT_FOUND",
            message="Follow-up snapshot was not found.",
            status_code=404,
        )
    if follow_up.status != "ready" or follow_up.feature_snapshot_hash is None:
        raise ApplicationError(
            code="RESEARCH_FEATURE_SNAPSHOT_INCOMPLETE",
            message="The day-30 follow-up snapshot is incomplete.",
            status_code=409,
            details=[{"field": name} for name in follow_up.missing_features_json],
        )
    enrollment = await owned_enrollment(session, owner_id, follow_up.research_enrollment_id)
    sourced = {
        name: SourcedFeatureValue(
            value=cast(FeatureValue, value),
            source=str(follow_up.feature_sources_json[name]),
        )
        for name, value in follow_up.feature_values_json.items()
    }
    try:
        snapshot = build_feature_snapshot(sourced)
    except FeatureSnapshotError as exc:
        raise ApplicationError(
            code="RESEARCH_FEATURE_SNAPSHOT_INVALID", message=str(exc), status_code=409
        ) from exc
    if snapshot.checksum != follow_up.feature_snapshot_hash:
        raise ApplicationError(
            code="RESEARCH_FEATURE_SNAPSHOT_INVALID",
            message="The stored follow-up snapshot checksum does not match its values.",
            status_code=409,
        )
    model = await active_model(session)
    try:
        descriptor = artifacts.descriptor()
        validate_descriptor(model, descriptor)
        output = artifacts.predict(snapshot)
    except RiskArtifactError as exc:
        raise ApplicationError(
            code="RESEARCH_MODEL_DEGRADED", message=str(exc), status_code=503
        ) from exc
    existing = await session.scalar(
        select(ResearchPrediction).where(
            ResearchPrediction.owner_id == owner_id,
            ResearchPrediction.research_enrollment_id == enrollment.id,
            ResearchPrediction.model_version_id == model.id,
            ResearchPrediction.feature_snapshot_hash == snapshot.checksum,
        )
    )
    if existing is not None:
        return existing
    prediction = ResearchPrediction(
        owner_id=owner_id,
        research_enrollment_id=enrollment.id,
        follow_up_snapshot_id=follow_up.id,
        model_version_id=model.id,
        feature_snapshot_json={"values": snapshot.values, "sources": snapshot.sources},
        feature_snapshot_hash=snapshot.checksum,
        probability=Decimal(str(output.probability)),
        research_label=risk_band(output.probability, descriptor.threshold),
        top_contributions_json=[contribution.__dict__ for contribution in output.contributions],
    )
    session.add(prediction)
    await session.flush()
    return prediction


def enrollment_payload(enrollment: ResearchEnrollment) -> dict[str, Any]:
    missing = [name for name in BASELINE_FEATURES if name not in enrollment.baseline_values_json]
    return {
        "id": enrollment.id,
        "screening_id": enrollment.screening_id,
        "patient_snapshot_id": enrollment.patient_snapshot_id,
        "trial_version_id": enrollment.trial_version_id,
        "research_context_checksum": enrollment.research_context_checksum,
        "enrollment_date": enrollment.enrollment_date,
        "observation_cutoff_day": enrollment.observation_cutoff_day,
        "prediction_horizon_day": enrollment.prediction_horizon_day,
        "feature_contract_version": enrollment.feature_contract_version,
        "tracking_status": enrollment.tracking_status,
        "baseline": [
            {
                "name": name,
                "value": enrollment.baseline_values_json.get(name),
                "source": enrollment.baseline_sources_json.get(name),
                "missing": name in missing,
            }
            for name in BASELINE_FEATURES
        ],
        "missing_baseline_features": missing,
        "created_at": enrollment.created_at,
    }


def follow_up_payload(snapshot: ResearchFollowUpSnapshot) -> dict[str, Any]:
    return {
        "id": snapshot.id,
        "research_enrollment_id": snapshot.research_enrollment_id,
        "cutoff_day": snapshot.cutoff_day,
        "feature_schema_version": snapshot.feature_schema_version,
        "feature_snapshot_hash": snapshot.feature_snapshot_hash,
        "event_set_checksum": snapshot.event_set_checksum,
        "status": snapshot.status,
        "features": [
            {
                "name": name,
                "group": feature_group(name),
                "value": snapshot.feature_values_json.get(name),
                "source": snapshot.feature_sources_json.get(name),
                "missing": name in snapshot.missing_features_json,
            }
            for name in FEATURE_NAMES
        ],
        "missing_features": snapshot.missing_features_json,
        "created_at": snapshot.created_at,
    }


def prediction_payload(
    prediction: ResearchPrediction,
    enrollment: ResearchEnrollment,
    model: ResearchModelVersion,
) -> dict[str, Any]:
    return {
        "id": prediction.id,
        "screening_id": enrollment.screening_id,
        "research_enrollment_id": enrollment.id,
        "follow_up_snapshot_id": prediction.follow_up_snapshot_id,
        "risk_type": "trial_dropout_by_day90",
        "probability": float(prediction.probability),
        "threshold": float(model.threshold),
        "research_label": prediction.research_label,
        "observation_cutoff_day": enrollment.observation_cutoff_day,
        "horizon_day": model.horizon_day,
        "model": {
            "name": model.model_name,
            "version": model.version,
            "alias": model.alias,
            "candidate_id": model.candidate_id,
        },
        "feature_schema_version": model.feature_schema_version,
        "feature_snapshot_hash": prediction.feature_snapshot_hash,
        "top_contributions": prediction.top_contributions_json,
        "created_at": prediction.created_at,
        "disclaimer": DISCLAIMER,
    }
