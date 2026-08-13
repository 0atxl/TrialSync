"""Frozen physical schema and provenance contract for the R3 dataset."""

from __future__ import annotations

import hashlib
import json

DATASET_CONTRACT_VERSION = "r3-dataset-contract-v1"
SITE_CONTEXT_COLUMN = "site_region"
SOURCE_TABLE_NAMES = (
    "research_participants",
    "research_enrollments",
    "research_dose_events",
    "research_visit_events",
    "research_measurements",
    "research_adverse_events",
    "research_outcomes",
)
DERIVED_VIEW_NAMES = (
    "landmark_day30_features",
    "dynamic_landmarks",
    "survival_features",
)
TABLE_NAMES = (*SOURCE_TABLE_NAMES, *DERIVED_VIEW_NAMES)
PARTICIPANT_BASELINE_COLUMNS = (
    "research_participant_id",
    "condition_category",
    "age",
    "sex",
    SITE_CONTEXT_COLUMN,
    "baseline_functional_severity",
    "patient_reported_burden",
    "baseline_comorbidity_burden",
    "baseline_treatment_burden",
    "travel_access_burden",
    "support_availability",
    "medication_count",
    "generation_source",
)
ENROLLMENT_SNAPSHOT_COLUMNS = PARTICIPANT_BASELINE_COLUMNS
MODEL_FEATURE_COLUMNS = (
    "research_enrollment_id",
    "research_participant_id",
    "patient_snapshot_id",
    "trial_version_id",
    "condition_category",
    SITE_CONTEXT_COLUMN,
    "treatment_arm",
    "age",
    "sex",
    "baseline_functional_severity",
    "patient_reported_burden",
    "baseline_comorbidity_burden",
    "baseline_treatment_burden",
    "travel_access_burden",
    "support_availability",
    "medication_count",
    "latest_functional_severity",
    "functional_severity_slope",
    "functional_observation_count",
    "scheduled_dose_count",
    "administered_dose_count",
    "missed_dose_count",
    "missed_dose_rate",
    "scheduled_visit_count",
    "attended_visit_count",
    "missed_visit_count",
    "delayed_visit_count",
    "missed_visit_rate",
    "mean_visit_delay_days",
    "measurement_observation_count",
    "measurement_missing_count",
    "measurement_missingness_rate",
    "adverse_event_count",
    "adverse_event_burden",
    "feature_cutoff_day",
)
OUTPUT_COLUMNS = {
    "research_participants": (
        *PARTICIPANT_BASELINE_COLUMNS,
        "research_enrollment_id",
        "dataset_split",
    ),
    "research_enrollments": (
        *ENROLLMENT_SNAPSHOT_COLUMNS,
        "trial_version_id",
        "research_enrollment_id",
        "patient_snapshot_id",
        "screening_id",
        "trial_version",
        "treatment_arm",
        "screening_state",
        "screening_engine_version",
        "screening_date",
        "enrollment_day",
        "observation_cutoff_day",
        "prediction_horizon_day",
        "linkage_source",
        "dataset_split",
    ),
    "research_dose_events": (
        "dose_event_id",
        "research_enrollment_id",
        "event_day",
        "scheduled_count",
        "administered_count",
        "missed_count",
        "missed_dose_reason",
        "treatment_interruption",
        "dataset_split",
    ),
    "research_visit_events": (
        "visit_event_id",
        "research_enrollment_id",
        "visit_number",
        "event_day",
        "scheduled_day",
        "visit_status",
        "delay_days",
        "active_status",
        "dataset_split",
    ),
    "research_measurements": (
        "measurement_id",
        "research_enrollment_id",
        "measurement_day",
        "measurement_name",
        "value",
        "unit",
        "observed",
        "dataset_split",
    ),
    "research_adverse_events": (
        "adverse_event_id",
        "research_enrollment_id",
        "event_day",
        "category",
        "severity_grade",
        "treatment_related",
        "resolved",
        "treatment_interruption",
        "dataset_split",
    ),
    "research_outcomes": (
        "research_outcome_id",
        "research_enrollment_id",
        "dropout_by_day90",
        "dropout_day",
        "dropout_reason",
        "event_observed",
        "censored",
        "censor_day",
        "last_observed_day",
        "trial_completed",
        "outcome_definition",
        "dataset_split",
    ),
    "landmark_day30_features": (
        *MODEL_FEATURE_COLUMNS,
        "dropout_by_day90",
        "target_observed",
        "dataset_split",
    ),
    "dynamic_landmarks": (
        *MODEL_FEATURE_COLUMNS,
        "prediction_day",
        "dropout_in_next_30_days",
        "target_observed",
        "dataset_split",
    ),
    "survival_features": (
        *MODEL_FEATURE_COLUMNS,
        "time_to_dropout_or_censor_days",
        "event_observed",
        "censor_day",
        "dataset_split",
    ),
}
FORBIDDEN_MODEL_FEATURE_COLUMNS = frozenset(
    {
        "dropout_day",
        "dropout_reason",
        "trial_completed",
        "screening_state",
        "screening_engine_version",
        "generation_dropout_draw",
        "generation_dropout_risk_points",
        "generation_dropout_risk_tier",
        "generation_primary_dropout_driver",
    }
)
DROPOUT_PROBABILITY_BY_HIDDEN_TIER = {
    "low": 0.08,
    "moderate": 0.18,
    "high": 0.35,
    "very_high": 0.55,
}


def _provenance(
    table_name: str,
    default: str,
    overrides: dict[str, str],
) -> dict[str, str]:
    return {column: overrides.get(column, default) for column in OUTPUT_COLUMNS[table_name]}


COLUMN_PROVENANCE = {
    "research_participants": _provenance(
        "research_participants",
        "data_designer_sampler",
        {
            "generation_source": "trialsync_constant",
            "research_enrollment_id": "trialsync_linkage",
            "dataset_split": "trialsync_deterministic_split",
        },
    ),
    "research_enrollments": _provenance(
        "research_enrollments",
        "immutable_participant_snapshot_copy",
        {
            "trial_version_id": "trialsync_condition_trial_map",
            "research_enrollment_id": "data_designer_sampler",
            "patient_snapshot_id": "data_designer_sampler",
            "screening_id": "data_designer_sampler",
            "trial_version": "data_designer_sampler",
            "treatment_arm": "data_designer_sampler",
            "screening_state": "trialsync_canonical_screening",
            "screening_engine_version": "trialsync_canonical_screening",
            "screening_date": "trialsync_constant",
            "enrollment_day": "trialsync_constant",
            "observation_cutoff_day": "trialsync_constant",
            "prediction_horizon_day": "trialsync_constant",
            "linkage_source": "trialsync_constant",
            "dataset_split": "trialsync_deterministic_split",
        },
    ),
    "research_dose_events": _provenance(
        "research_dose_events",
        "data_designer_sampler_or_expression",
        {
            "research_enrollment_id": "trialsync_relational_seed",
            "event_day": "trialsync_schedule",
            "scheduled_count": "trialsync_schedule",
            "missed_count": "trialsync_normalization",
            "dataset_split": "trialsync_deterministic_split",
        },
    ),
    "research_visit_events": _provenance(
        "research_visit_events",
        "data_designer_sampler_or_expression",
        {
            "research_enrollment_id": "trialsync_relational_seed",
            "visit_number": "trialsync_schedule",
            "event_day": "trialsync_schedule",
            "scheduled_day": "trialsync_schedule",
            "active_status": "trialsync_constant",
            "dataset_split": "trialsync_deterministic_split",
        },
    ),
    "research_measurements": _provenance(
        "research_measurements",
        "data_designer_sampler_or_expression",
        {
            "research_enrollment_id": "trialsync_relational_seed",
            "measurement_day": "trialsync_schedule",
            "measurement_name": "trialsync_condition_marker_map",
            "unit": "trialsync_constant",
            "dataset_split": "trialsync_deterministic_split",
        },
    ),
    "research_adverse_events": _provenance(
        "research_adverse_events",
        "data_designer_sampler_or_expression",
        {
            "research_enrollment_id": "trialsync_relational_seed",
            "event_day": "trialsync_schedule",
            "dataset_split": "trialsync_deterministic_split",
        },
    ),
    "research_outcomes": _provenance(
        "research_outcomes",
        "data_designer_sampler_or_expression",
        {
            "research_enrollment_id": "trialsync_relational_seed",
            "event_observed": "trialsync_censoring_derivation",
            "censored": "trialsync_censoring_derivation",
            "censor_day": "trialsync_censoring_derivation",
            "last_observed_day": "trialsync_censoring_derivation",
            "trial_completed": "trialsync_censoring_derivation",
            "outcome_definition": "trialsync_constant",
            "dataset_split": "trialsync_deterministic_split",
        },
    ),
    **{
        view_name: _provenance(
            view_name,
            "trialsync_leakage_safe_derivation",
            {"dataset_split": "trialsync_deterministic_split"},
        )
        for view_name in DERIVED_VIEW_NAMES
    },
}

SCHEMA_FINGERPRINT = hashlib.sha256(
    json.dumps(OUTPUT_COLUMNS, sort_keys=True).encode("utf-8")
).hexdigest()

assert SITE_CONTEXT_COLUMN == "site_region"
assert all("site_id" not in columns for columns in OUTPUT_COLUMNS.values())
assert all(
    set(COLUMN_PROVENANCE[table_name]) == set(columns)
    for table_name, columns in OUTPUT_COLUMNS.items()
)
