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
    ResearchEnrollment,
    ResearchEnrollmentBaselineRevision,
    ResearchFollowUpSnapshot,
    ResearchModelVersion,
    ResearchPrediction,
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

ACTIVE_MODEL_DATABASE_ID = uuid.UUID("c53eac18-2c71-55f5-a247-5228516fcf3f")
FEATURE_CONTRACT_VERSION = "r4-day30-features-v2"
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


def condition_category(condition: str) -> str | None:
    normalized = condition.casefold()
    mappings = {
        "metabolic": (
            "metabolic",
            "diabetes",
            "glucose",
            "glycemic",
            "lipid",
            "dyslipidemia",
            "cholesterol",
            "obesity",
            "hepatic",
            "liver",
            "mash",
            "nash",
            "fatty",
            "endocrine",
            "t1d",
            "t2d",
            "hba1c",
        ),
        "cardiovascular": (
            "cardiovascular",
            "hypertension",
            "cardiac",
            "heart",
            "artery",
            "vascular",
            "blood pressure",
            "coronary",
            "stroke",
            "atherosclerosis",
            "arrhythmia",
        ),
        "renal": (
            "renal",
            "kidney",
            "egfr",
            "nephr",
            "ckd",
            "dialysis",
            "glomerul",
            "proteinuria",
        ),
        "oncology": (
            "oncology",
            "cancer",
            "tumor",
            "carcinoma",
            "lymphoma",
            "melanoma",
            "leukemia",
            "neoplasm",
            "malignan",
            "sarcoma",
        ),
        "respiratory": (
            "respiratory",
            "asthma",
            "pulmonary",
            "copd",
            "bronch",
            "lung",
            "airway",
        ),
    }
    return next(
        (
            category
            for category, words in mappings.items()
            if any(word in normalized for word in words)
        ),
        None,
    )


def unsupported_condition_message(condition: str) -> str:
    return (
        f"The condition {condition!r} is not supported by the current dropout model. "
        "The saved eligibility result is unchanged."
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
    category = condition_category(version.trial.condition)
    if category is not None:
        values["condition_category"] = SourcedFeatureValue(category, "approved_trial_version")
    return values


def _baseline_values(
    baseline_revision: ResearchEnrollmentBaselineRevision,
) -> dict[str, SourcedFeatureValue]:
    return {
        name: SourcedFeatureValue(
            value=cast(FeatureValue, value),
            source=str(baseline_revision.baseline_sources_json[name]),
        )
        for name, value in baseline_revision.baseline_values_json.items()
        if name in baseline_revision.baseline_sources_json
    }


async def latest_baseline_revision(
    session: AsyncSession, enrollment: ResearchEnrollment
) -> ResearchEnrollmentBaselineRevision:
    revision = await session.scalar(
        select(ResearchEnrollmentBaselineRevision)
        .where(
            ResearchEnrollmentBaselineRevision.research_enrollment_id == enrollment.id,
            ResearchEnrollmentBaselineRevision.owner_id == enrollment.owner_id,
        )
        .order_by(
            ResearchEnrollmentBaselineRevision.created_at.desc(),
            ResearchEnrollmentBaselineRevision.id.desc(),
        )
    )
    if revision is None:
        raise ApplicationError(
            code="RESEARCH_BASELINE_REVISION_MISSING",
            message="The enrollment baseline history is incomplete.",
            status_code=409,
        )
    return revision


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
    if condition_category(version.trial.condition) is None:
        raise ApplicationError(
            code="RESEARCH_MODEL_INPUT_UNSUPPORTED",
            message=unsupported_condition_message(version.trial.condition),
            status_code=422,
        )
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
    session.add(
        ResearchEnrollmentBaselineRevision(
            owner_id=owner_id,
            research_enrollment_id=enrollment.id,
            enrollment_date=enrollment_date,
            baseline_values_json=values,
            baseline_sources_json=sources,
            baseline_snapshot_hash=baseline_hash,
            feature_contract_version=FEATURE_CONTRACT_VERSION,
            supersedes_revision_id=None,
            correction_reason=None,
            created_by_id=owner_id,
        )
    )
    await session.flush()
    return enrollment


async def update_enrollment(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    screening_id: uuid.UUID,
    enrollment_date: date,
    supplied_baseline: Mapping[str, SourcedFeatureValue],
) -> tuple[ResearchEnrollment, ResearchEnrollmentBaselineRevision]:
    screening, version = await owned_screening(session, owner_id, screening_id)
    if condition_category(version.trial.condition) is None:
        raise ApplicationError(
            code="RESEARCH_MODEL_INPUT_UNSUPPORTED",
            message=unsupported_condition_message(version.trial.condition),
            status_code=422,
        )
    if enrollment_date < screening.screening_date:
        raise ApplicationError(
            code="RESEARCH_ENROLLMENT_DATE_INVALID",
            message="Enrollment date cannot precede the saved screening date.",
            status_code=422,
        )
    enrollment = await enrollment_for_screening(session, owner_id, screening_id)
    if enrollment is None:
        raise ApplicationError(
            code="RESEARCH_ENROLLMENT_NOT_FOUND",
            message="Research enrollment was not found.",
            status_code=404,
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
    current = await latest_baseline_revision(session, enrollment)
    if (
        current.enrollment_date == enrollment_date
        and current.baseline_snapshot_hash == baseline_hash
    ):
        return enrollment, current

    latest_follow_up = await session.scalar(
        select(ResearchFollowUpSnapshot)
        .where(ResearchFollowUpSnapshot.research_enrollment_id == enrollment.id)
        .order_by(
            ResearchFollowUpSnapshot.created_at.desc(),
            ResearchFollowUpSnapshot.id.desc(),
        )
    )
    revision = ResearchEnrollmentBaselineRevision(
        owner_id=owner_id,
        research_enrollment_id=enrollment.id,
        enrollment_date=enrollment_date,
        baseline_values_json=values,
        baseline_sources_json=sources,
        baseline_snapshot_hash=baseline_hash,
        feature_contract_version=FEATURE_CONTRACT_VERSION,
        supersedes_revision_id=current.id,
        correction_reason="Enrollment baseline correction",
        created_by_id=owner_id,
    )
    session.add(revision)
    await session.flush()
    if latest_follow_up is not None and latest_follow_up.input_summary_json:
        summary = dict(latest_follow_up.input_summary_json)
        # Older compact summaries predate the explicit streak fields. The v2
        # snapshot already stores those values, so carry them forward during a
        # baseline-only correction instead of inventing defaults or forcing a
        # second data-entry step.
        for name in (
            "longest_missed_dose_streak",
            "longest_missed_visit_streak",
        ):
            if name not in summary and name in latest_follow_up.feature_values_json:
                summary[name] = latest_follow_up.feature_values_json[name]
        await build_follow_up_summary(
            session,
            enrollment=enrollment,
            summary={name: cast(int | float, value) for name, value in summary.items()},
            baseline_revision=revision,
        )
    return enrollment, revision


def _day30_features(
    baseline_revision: ResearchEnrollmentBaselineRevision,
    summary: Mapping[str, int | float],
) -> dict[str, SourcedFeatureValue]:
    values = _baseline_values(baseline_revision)
    scheduled_doses = int(summary["scheduled_doses"])
    missed_doses = int(summary["missed_doses"])
    scheduled_visits = int(summary["scheduled_visits"])
    missed_visits = int(summary["missed_visits"])
    completed_visits = scheduled_visits - missed_visits
    expected_assessments = int(summary["expected_assessments"])
    completed_assessments = int(summary["completed_assessments"])
    latest_severity = float(summary["latest_functional_severity"])
    latest_day = int(summary["latest_assessment_day"])
    baseline_severity = float(values["baseline_functional_severity"].value)
    source = "derived:day30_summary"
    values.update(
        {
            "latest_functional_severity": SourcedFeatureValue(latest_severity, source),
            "functional_severity_slope": SourcedFeatureValue(
                (latest_severity - baseline_severity) / latest_day, source
            ),
            "functional_observation_count": SourcedFeatureValue(completed_assessments, source),
            "scheduled_dose_count": SourcedFeatureValue(scheduled_doses, source),
            "missed_dose_count": SourcedFeatureValue(missed_doses, source),
            "missed_dose_rate": SourcedFeatureValue(missed_doses / scheduled_doses, source),
            "longest_missed_dose_streak": SourcedFeatureValue(
                int(summary["longest_missed_dose_streak"]), source
            ),
            "delayed_visit_count": SourcedFeatureValue(int(summary["delayed_visits"]), source),
            "missed_visit_count": SourcedFeatureValue(missed_visits, source),
            "missed_visit_rate": SourcedFeatureValue(missed_visits / scheduled_visits, source),
            "longest_missed_visit_streak": SourcedFeatureValue(
                int(summary["longest_missed_visit_streak"]), source
            ),
            "mean_visit_delay_days": SourcedFeatureValue(
                float(summary["total_visit_delay_days"]) / completed_visits
                if completed_visits
                else 0.0,
                source,
            ),
            "measurement_missingness_rate": SourcedFeatureValue(
                (expected_assessments - completed_assessments) / expected_assessments,
                source,
            ),
            "adverse_event_count": SourcedFeatureValue(int(summary["adverse_event_count"]), source),
            "adverse_event_burden": SourcedFeatureValue(
                int(summary["adverse_event_burden"]), source
            ),
        }
    )
    return values


async def build_follow_up_summary(
    session: AsyncSession,
    *,
    enrollment: ResearchEnrollment,
    summary: Mapping[str, int | float],
    baseline_revision: ResearchEnrollmentBaselineRevision | None = None,
) -> ResearchFollowUpSnapshot:
    revision = baseline_revision or await latest_baseline_revision(session, enrollment)
    cutoff = enrollment.observation_cutoff_day
    normalized_summary = dict(summary)
    input_checksum = _checksum(
        {"summary": normalized_summary, "baseline_snapshot_hash": revision.baseline_snapshot_hash}
    )
    existing = await session.scalar(
        select(ResearchFollowUpSnapshot).where(
            ResearchFollowUpSnapshot.research_enrollment_id == enrollment.id,
            ResearchFollowUpSnapshot.cutoff_day == cutoff,
            ResearchFollowUpSnapshot.event_set_checksum == input_checksum,
        )
    )
    if existing is not None:
        return existing
    try:
        complete = build_feature_snapshot(_day30_features(revision, normalized_summary))
    except (FeatureSnapshotError, KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise ApplicationError(
            code="RESEARCH_DAY30_SUMMARY_INVALID", message=str(exc), status_code=422
        ) from exc
    snapshot = ResearchFollowUpSnapshot(
        owner_id=enrollment.owner_id,
        research_enrollment_id=enrollment.id,
        baseline_revision_id=revision.id,
        cutoff_day=cutoff,
        feature_schema_version=FEATURE_CONTRACT_VERSION,
        feature_values_json=complete.values,
        feature_sources_json=complete.sources,
        feature_snapshot_hash=complete.checksum,
        input_summary_json=normalized_summary,
        event_set_checksum=input_checksum,
        missing_features_json=[],
        status="ready",
    )
    session.add(snapshot)
    await session.flush()
    return snapshot


def missed_dose_scenarios(
    snapshot: ResearchFollowUpSnapshot,
    artifacts: RiskArtifactService,
) -> list[dict[str, int | float]]:
    summary = snapshot.input_summary_json
    if not summary:
        raise ApplicationError(
            code="RESEARCH_DAY30_SUMMARY_REQUIRED",
            message="Enter the compact day-30 inputs before calculating scenarios.",
            status_code=409,
        )
    base_scheduled = int(cast(int | float, summary["scheduled_doses"]))
    base_missed = int(cast(int | float, summary["missed_doses"]))
    base_values = {
        name: SourcedFeatureValue(
            cast(FeatureValue, snapshot.feature_values_json[name]), "scenario"
        )
        for name in FEATURE_NAMES
    }
    base_streak = int(cast(int | float, base_values["longest_missed_dose_streak"].value))
    points: list[dict[str, int | float]] = []
    for additional in (0, 1, 2):
        scheduled = base_scheduled + additional
        missed = base_missed + additional
        rate = missed / scheduled
        streak = base_streak + additional
        values = dict(base_values)
        values["scheduled_dose_count"] = SourcedFeatureValue(
            scheduled, "scenario:additional_consecutive_missed_dose"
        )
        values["missed_dose_count"] = SourcedFeatureValue(
            missed, "scenario:additional_consecutive_missed_dose"
        )
        values["missed_dose_rate"] = SourcedFeatureValue(
            rate, "scenario:additional_consecutive_missed_dose"
        )
        values["longest_missed_dose_streak"] = SourcedFeatureValue(
            min(streak, missed), "scenario:additional_consecutive_missed_dose"
        )
        output = artifacts.predict(build_feature_snapshot(values), top_k=0)
        points.append(
            {
                "additional_missed_doses": additional,
                "scheduled_doses": scheduled,
                "missed_doses": missed,
                "missed_dose_rate": rate,
                "longest_missed_dose_streak": min(streak, missed),
                "probability": output.probability,
            }
        )
    return points


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
    current_revision = await latest_baseline_revision(session, enrollment)
    if follow_up.baseline_revision_id != current_revision.id:
        raise ApplicationError(
            code="RESEARCH_FOLLOW_UP_STALE",
            message="The baseline was corrected after these day-30 inputs were assembled.",
            status_code=409,
        )
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


def enrollment_payload(
    enrollment: ResearchEnrollment,
    baseline_revision: ResearchEnrollmentBaselineRevision | None = None,
) -> dict[str, Any]:
    values = (
        baseline_revision.baseline_values_json
        if baseline_revision is not None
        else enrollment.baseline_values_json
    )
    sources = (
        baseline_revision.baseline_sources_json
        if baseline_revision is not None
        else enrollment.baseline_sources_json
    )
    enrollment_date = (
        baseline_revision.enrollment_date
        if baseline_revision is not None
        else enrollment.enrollment_date
    )
    missing = [name for name in BASELINE_FEATURES if name not in values]
    return {
        "id": enrollment.id,
        "screening_id": enrollment.screening_id,
        "patient_snapshot_id": enrollment.patient_snapshot_id,
        "trial_version_id": enrollment.trial_version_id,
        "research_context_checksum": enrollment.research_context_checksum,
        "enrollment_date": enrollment_date,
        "observation_cutoff_day": enrollment.observation_cutoff_day,
        "prediction_horizon_day": enrollment.prediction_horizon_day,
        "feature_contract_version": (
            baseline_revision.feature_contract_version
            if baseline_revision is not None
            else enrollment.feature_contract_version
        ),
        "tracking_status": enrollment.tracking_status,
        "baseline": [
            {
                "name": name,
                "value": values.get(name),
                "source": sources.get(name),
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
        "input_summary": snapshot.input_summary_json,
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
