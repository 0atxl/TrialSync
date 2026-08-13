"""Generate the linked R3 source tables through NeMo Data Designer.

NeMo owns synthetic field generation. This module only creates relational seed
rows, calls the table configurations, applies canonical screening linkage,
normalizes event rows, and derives leakage-safe model views.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import UTC, date, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

import pandas as pd
from data_designer.config import RunConfig
from data_designer.interface import DataDesigner

try:
    from .configs.r3_nemo import build_config
except ImportError:
    from configs.r3_nemo import build_config  # type: ignore[import-not-found, no-redef]

try:
    from .schemas.r3_dataset import (
        COLUMN_PROVENANCE,
        DATASET_CONTRACT_VERSION,
        DERIVED_VIEW_NAMES,
        DROPOUT_PROBABILITY_BY_HIDDEN_TIER,
        ENROLLMENT_SNAPSHOT_COLUMNS,
        FORBIDDEN_MODEL_FEATURE_COLUMNS,
        OUTPUT_COLUMNS,
        SCHEMA_FINGERPRINT,
        SITE_CONTEXT_COLUMN,
        SOURCE_TABLE_NAMES,
    )
except ImportError:
    from schemas.r3_dataset import (  # type: ignore[import-not-found, no-redef]
        COLUMN_PROVENANCE,
        DATASET_CONTRACT_VERSION,
        DERIVED_VIEW_NAMES,
        DROPOUT_PROBABILITY_BY_HIDDEN_TIER,
        ENROLLMENT_SNAPSHOT_COLUMNS,
        FORBIDDEN_MODEL_FEATURE_COLUMNS,
        OUTPUT_COLUMNS,
        SCHEMA_FINGERPRINT,
        SITE_CONTEXT_COLUMN,
        SOURCE_TABLE_NAMES,
    )

from trialsync.domain import (
    ApprovedTrialVersion,
    Assertion,
    Criterion,
    CriterionKind,
    Fact,
    FactType,
    OverallState,
    PatientSnapshot,
    ScreeningContext,
    screen,
)

SCREENING_DATE = date(2026, 1, 1)
GENERATOR_VERSION = "r3-nemo-btech-v3"
DATA_DESIGNER_VERSION = version("data-designer")
OBSERVATION_CUTOFF_DAY = 30
PREDICTION_HORIZON_DAY = 90
DYNAMIC_LANDMARK_DAYS = (7, 14, 21, 28, 30)
DATA_DESIGNER_PARTICIPANT_CHUNK_SIZE = 400
TRIAL_VERSION_BY_CONDITION = {
    "metabolic": "trial-metabolic-r3-v1",
    "cardiovascular": "trial-cardiovascular-r3-v1",
    "renal": "trial-renal-r3-v1",
    "oncology": "trial-oncology-r3-v1",
    "respiratory": "trial-respiratory-r3-v1",
}


def _stable_id(kind: str, value: object) -> str:
    return str(uuid5(NAMESPACE_URL, f"trialsync:r3:nemo:{kind}:{value}"))


def _write_seed(frame: pd.DataFrame, path: Path) -> None:
    frame.to_parquet(path, index=False)


def _enrollment_seed(participants: pd.DataFrame) -> pd.DataFrame:
    seed = participants.copy()
    seed["trial_version_id"] = seed["condition_category"].map(TRIAL_VERSION_BY_CONDITION)
    if seed["trial_version_id"].isna().any():
        unknown = sorted(seed.loc[seed["trial_version_id"].isna(), "condition_category"].unique())
        raise ValueError(f"No trial version is configured for conditions: {unknown}")
    return seed


def _run_table(
    designer: DataDesigner,
    table: str,
    *,
    seed_path: Path | None,
    num_records: int,
    artifact_path: Path,
) -> pd.DataFrame:
    builder = build_config(table, seed_path)
    designer.validate(builder)
    result = designer.create(
        builder,
        num_records=num_records,
        dataset_name=table,
        artifact_path=artifact_path,
    )
    return result.load_dataset()


def _run_participants(
    designer: DataDesigner,
    *,
    num_records: int,
    artifact_path: Path,
) -> pd.DataFrame:
    if num_records <= DATA_DESIGNER_PARTICIPANT_CHUNK_SIZE:
        return _run_table(
            designer,
            "participants",
            seed_path=None,
            num_records=num_records,
            artifact_path=artifact_path,
        )

    frames = []
    for chunk_index, start in enumerate(
        range(0, num_records, DATA_DESIGNER_PARTICIPANT_CHUNK_SIZE),
        start=1,
    ):
        chunk_size = min(DATA_DESIGNER_PARTICIPANT_CHUNK_SIZE, num_records - start)
        frames.append(
            _run_table(
                designer,
                "participants",
                seed_path=None,
                num_records=chunk_size,
                artifact_path=artifact_path / "participant_chunks" / f"{chunk_index:04d}",
            )
        )
    return pd.concat(frames, ignore_index=True)


def _trial(condition: str, trial_id: str) -> ApprovedTrialVersion:
    return ApprovedTrialVersion(
        id=trial_id,
        version="r3.1.0",
        criteria=(
            Criterion(
                id=f"{trial_id}:age-min",
                kind=CriterionKind.inclusion,
                order=1,
                source_text="Age is at least 18 years.",
                expression={
                    "op": "gte",
                    "fact": "demographic.age",
                    "value": 18,
                    "unit": "year",
                },
            ),
            Criterion(
                id=f"{trial_id}:age-max",
                kind=CriterionKind.inclusion,
                order=2,
                source_text="Age is no more than 80 years.",
                expression={
                    "op": "lte",
                    "fact": "demographic.age",
                    "value": 80,
                    "unit": "year",
                },
            ),
            Criterion(
                id=f"{trial_id}:condition",
                kind=CriterionKind.inclusion,
                order=3,
                source_text=f"Participant has the {condition} study condition.",
                expression={"op": "present", "fact": f"condition.{condition}"},
            ),
        ),
    )


def _link_enrollments(frame: pd.DataFrame) -> pd.DataFrame:
    linked = frame.copy()
    states: list[str] = []
    engines: list[str] = []
    for row in linked.to_dict("records"):
        participant_id = str(row["research_participant_id"])
        condition = str(row["condition_category"])
        snapshot_id = str(row["patient_snapshot_id"])
        trial_id = str(row["trial_version_id"])
        snapshot = PatientSnapshot(
            id=snapshot_id,
            version="r3-nemo-snapshot-1",
            date_of_birth=date(SCREENING_DATE.year - int(row["age"]), 1, 1),
            facts=(
                Fact(
                    id=_stable_id("condition-fact", participant_id),
                    fact_type=FactType.condition,
                    concept=condition,
                    assertion=Assertion.present,
                    effective_date=SCREENING_DATE,
                    source_label="NeMo Data Designer synthetic seed",
                ),
            ),
        )
        result = screen(
            snapshot,
            _trial(condition, trial_id),
            ScreeningContext(screening_date=SCREENING_DATE),
        )
        if result.overall_state is not OverallState.potentially_eligible:
            raise ValueError(f"Canonical screening failed for {participant_id}")
        states.append(result.overall_state.value)
        engines.append(result.engine_version)
    linked["screening_state"] = states
    linked["screening_engine_version"] = engines
    linked["screening_date"] = SCREENING_DATE.isoformat()
    linked["enrollment_day"] = 0
    linked["observation_cutoff_day"] = OBSERVATION_CUTOFF_DAY
    linked["prediction_horizon_day"] = PREDICTION_HORIZON_DAY
    linked["linkage_source"] = "trialsync.domain.screen_with_nemo_seed"
    return linked


def _adherence_tier(row: dict[str, Any]) -> str:
    points = sum(
        (
            int(int(row["travel_access_burden"]) >= 3),
            int(int(row["support_availability"]) <= 1),
            int(int(row["baseline_treatment_burden"]) >= 3),
            int(float(row["patient_reported_burden"]) >= 0.70),
        )
    )
    return "high" if points >= 3 else "moderate" if points >= 1 else "low"


def _primary_burden(row: dict[str, Any]) -> str:
    if int(row["travel_access_burden"]) >= 3 or int(row["support_availability"]) <= 1:
        return "access"
    if (
        float(row["baseline_functional_severity"]) >= 0.70
        or float(row["patient_reported_burden"]) >= 0.70
    ):
        return "symptoms"
    return "participant_choice"


def _ae_risk_tier(row: dict[str, Any]) -> str:
    points = sum(
        (
            int(float(row["baseline_functional_severity"]) >= 0.70),
            int(int(row["baseline_comorbidity_burden"]) >= 3),
            int(int(row["medication_count"]) >= 6),
            int(int(row["baseline_treatment_burden"]) >= 3),
        )
    )
    return "high" if points >= 3 else "moderate" if points >= 1 else "low"


def _measurement_band(row: dict[str, Any], day: int, measurement_name: str) -> str:
    baseline = float(row["baseline_functional_severity"])
    if measurement_name != "functional_severity":
        baseline = 0.65 * baseline + 0.35 * float(row["patient_reported_burden"])
    improvement = (0.12 if row["treatment_arm"] == "active" else 0.03) * (
        day / PREDICTION_HORIZON_DAY
    )
    expected = min(1.0, max(0.0, baseline - improvement))
    if expected < 0.20:
        return "very_low"
    if expected < 0.40:
        return "low"
    if expected < 0.60:
        return "moderate"
    if expected < 0.80:
        return "high"
    return "very_high"


def _schedule_frames(enrollments: pd.DataFrame) -> dict[str, pd.DataFrame]:
    marker_by_condition = {
        "metabolic": "metabolic_control",
        "cardiovascular": "cardiovascular_control",
        "renal": "renal_function",
        "oncology": "tumor_burden",
        "respiratory": "respiratory_function",
    }
    dose_rows: list[dict[str, Any]] = []
    visit_rows: list[dict[str, Any]] = []
    measurement_rows: list[dict[str, Any]] = []
    adverse_rows: list[dict[str, Any]] = []
    for row in enrollments.to_dict("records"):
        enrollment_id = str(row["research_enrollment_id"])
        condition = str(row["condition_category"])
        generation_context = {
            "condition_category": condition,
            "treatment_arm": row["treatment_arm"],
            "generation_adherence_tier": _adherence_tier(row),
            "generation_primary_burden": _primary_burden(row),
            "generation_ae_risk_tier": _ae_risk_tier(row),
        }
        for day in range(1, PREDICTION_HORIZON_DAY + 1):
            dose_rows.append(
                {
                    "research_enrollment_id": enrollment_id,
                    "event_day": day,
                    "scheduled_count": 1,
                    **generation_context,
                }
            )
        for day in range(7, PREDICTION_HORIZON_DAY + 1, 7):
            visit_rows.append(
                {
                    "research_enrollment_id": enrollment_id,
                    "visit_number": day // 7,
                    "event_day": day,
                    "scheduled_day": day,
                    **generation_context,
                }
            )
            adverse_rows.append(
                {
                    "research_enrollment_id": enrollment_id,
                    "event_day": day,
                    **generation_context,
                }
            )
        marker = marker_by_condition[condition]
        for day in range(0, PREDICTION_HORIZON_DAY + 1, 7):
            for name in ("functional_severity", marker):
                measurement_rows.append(
                    {
                        "research_enrollment_id": enrollment_id,
                        "measurement_day": day,
                        "measurement_name": name,
                        "unit": "normalized_0_1",
                        "generation_measurement_band": _measurement_band(row, day, name),
                        **generation_context,
                    }
                )
    return {
        "dose_events": pd.DataFrame(dose_rows),
        "visit_events": pd.DataFrame(visit_rows),
        "measurements": pd.DataFrame(measurement_rows),
        "adverse_events": pd.DataFrame(adverse_rows),
    }


def _normalize_events(
    dose_events: pd.DataFrame,
    visit_events: pd.DataFrame,
    measurements: pd.DataFrame,
    adverse_events: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    doses = dose_events.copy()
    doses["administered_count"] = doses["administered_count"].astype(int)
    doses["scheduled_count"] = doses["scheduled_count"].astype(int)
    doses["missed_count"] = doses["scheduled_count"] - doses["administered_count"]
    doses.loc[doses["missed_count"] == 0, "missed_dose_reason"] = None
    doses["treatment_interruption"] = doses["treatment_interruption"].astype(bool)
    doses = doses[
        [
            "dose_event_id",
            "research_enrollment_id",
            "event_day",
            "scheduled_count",
            "administered_count",
            "missed_count",
            "missed_dose_reason",
            "treatment_interruption",
        ]
    ]

    visits = visit_events.copy()
    visits["delay_days"] = visits["delay_days"].astype(int)
    visits["active_status"] = "active"
    visits = visits[
        [
            "visit_event_id",
            "research_enrollment_id",
            "visit_number",
            "event_day",
            "scheduled_day",
            "visit_status",
            "delay_days",
            "active_status",
        ]
    ]

    measures = measurements.copy()
    measures["observed"] = measures["observed"].astype(bool)
    measures["value"] = measures["value"].astype(float).clip(0.0, 1.0)
    measures.loc[~measures["observed"], "value"] = None
    measures = measures[
        [
            "measurement_id",
            "research_enrollment_id",
            "measurement_day",
            "measurement_name",
            "value",
            "unit",
            "observed",
        ]
    ]

    adverse = adverse_events[adverse_events["event_present"].astype(bool)].copy()
    adverse["severity_grade"] = adverse["severity_grade"].clip(1, 3).astype(int)
    for column in ("treatment_related", "resolved", "treatment_interruption"):
        adverse[column] = adverse[column].astype(bool)
    adverse = adverse[
        [
            "adverse_event_id",
            "research_enrollment_id",
            "event_day",
            "category",
            "severity_grade",
            "treatment_related",
            "resolved",
            "treatment_interruption",
        ]
    ]
    return doses, visits, measures, adverse


def _outcome_seed(
    enrollments: pd.DataFrame,
    doses: pd.DataFrame,
    visits: pd.DataFrame,
    adverse: pd.DataFrame,
) -> pd.DataFrame:
    dose30 = doses[doses["event_day"] <= OBSERVATION_CUTOFF_DAY]
    visit30 = visits[visits["event_day"] <= OBSERVATION_CUTOFF_DAY]
    ae30 = adverse[adverse["event_day"] <= OBSERVATION_CUTOFF_DAY]
    dose_summary = dose30.groupby("research_enrollment_id").agg(
        scheduled_dose_count_30d=("scheduled_count", "sum"),
        missed_dose_count_30d=("missed_count", "sum"),
    )
    visit_summary = visit30.groupby("research_enrollment_id").agg(
        scheduled_visit_count_30d=("visit_event_id", "count"),
        missed_visit_count_30d=(
            "visit_status",
            lambda values: int((values == "missed").sum()),
        ),
    )
    ae_summary = ae30.groupby("research_enrollment_id").agg(
        adverse_event_count_30d=("adverse_event_id", "count"),
        adverse_event_burden_30d=("severity_grade", "sum"),
    )
    result = enrollments.merge(dose_summary, on="research_enrollment_id", how="left")
    result = result.merge(visit_summary, on="research_enrollment_id", how="left")
    result = result.merge(ae_summary, on="research_enrollment_id", how="left")
    for column in (
        "scheduled_dose_count_30d",
        "missed_dose_count_30d",
        "scheduled_visit_count_30d",
        "missed_visit_count_30d",
        "adverse_event_count_30d",
        "adverse_event_burden_30d",
    ):
        result[column] = result[column].fillna(0).astype(int)
    result["missed_dose_rate_30d"] = result["missed_dose_count_30d"] / result[
        "scheduled_dose_count_30d"
    ].clip(lower=1)
    result["missed_visit_rate_30d"] = result["missed_visit_count_30d"] / result[
        "scheduled_visit_count_30d"
    ].clip(lower=1)
    result["generation_dropout_risk_points"] = (
        2 * (result["baseline_functional_severity"] >= 0.70).astype(int)
        + 2 * (result["missed_dose_rate_30d"] >= 0.15).astype(int)
        + (result["missed_visit_rate_30d"] >= 0.15).astype(int)
        + (result["adverse_event_burden_30d"] >= 2).astype(int)
        + (result["travel_access_burden"] >= 3).astype(int)
        + (result["support_availability"] <= 1).astype(int)
        + (result["baseline_treatment_burden"] >= 3).astype(int)
        + (result["patient_reported_burden"] >= 0.70).astype(int)
    )
    result["generation_dropout_risk_tier"] = result["generation_dropout_risk_points"].map(
        lambda points: (
            "very_high"
            if points >= 7
            else "high"
            if points >= 5
            else "moderate"
            if points >= 2
            else "low"
        )
    )

    def primary_driver(row: pd.Series) -> str:
        if int(row["adverse_event_burden_30d"]) >= 3:
            return "adverse_event_burden"
        if int(row["travel_access_burden"]) >= 3 and int(row["support_availability"]) <= 1:
            return "access_or_travel"
        if (
            float(row["missed_dose_rate_30d"]) >= 0.15
            or float(row["missed_visit_rate_30d"]) >= 0.15
        ):
            return "loss_to_follow_up"
        return "participant_decision"

    result["generation_primary_dropout_driver"] = result.apply(primary_driver, axis=1)
    return result


def _normalize_outcomes(frame: pd.DataFrame) -> pd.DataFrame:
    outcomes = frame.copy()
    outcomes["dropout_by_day90"] = outcomes["dropout_by_day90"].astype(bool)
    outcomes["dropout_day"] = outcomes["dropout_day"].where(outcomes["dropout_by_day90"], None)
    outcomes["dropout_reason"] = outcomes["dropout_reason"].where(
        outcomes["dropout_by_day90"], None
    )
    outcomes["event_observed"] = outcomes["dropout_by_day90"]
    outcomes["censored"] = ~outcomes["dropout_by_day90"]
    outcomes["censor_day"] = outcomes["dropout_day"].where(
        outcomes["dropout_by_day90"], PREDICTION_HORIZON_DAY
    )
    outcomes["last_observed_day"] = outcomes["censor_day"]
    outcomes["trial_completed"] = ~outcomes["dropout_by_day90"]
    outcomes["outcome_definition"] = "dropout during days 31-90 after day-30 cutoff"
    return outcomes[
        [
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
        ]
    ]


def _apply_censoring(
    doses: pd.DataFrame,
    visits: pd.DataFrame,
    measures: pd.DataFrame,
    adverse: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    last_day = outcomes.set_index("research_enrollment_id")["last_observed_day"]
    return (
        doses[
            doses["event_day"] <= doses["research_enrollment_id"].map(last_day)
        ],
        visits[
            visits["event_day"] <= visits["research_enrollment_id"].map(last_day)
        ],
        measures[
            measures["measurement_day"] <= measures["research_enrollment_id"].map(last_day)
        ],
        adverse[
            adverse["event_day"] <= adverse["research_enrollment_id"].map(last_day)
        ],
    )


def _assign_splits(outcomes: pd.DataFrame) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for _label, group in outcomes.groupby("dropout_by_day90", sort=True):
        keys = sorted(
            group["research_enrollment_id"].astype(str),
            key=lambda value: hashlib.sha256(value.encode()).hexdigest(),
        )
        train_end = round(len(keys) * 0.70)
        validation_end = train_end + round(len(keys) * 0.15)
        for index, enrollment_id in enumerate(keys):
            assignments[enrollment_id] = (
                "train" if index < train_end else "validation" if index < validation_end else "test"
            )
    if set(assignments) != set(outcomes["research_enrollment_id"].astype(str)):
        raise ValueError("Split assignment did not cover every enrollment")
    return assignments


def _add_split(frame: pd.DataFrame, assignments: dict[str, str]) -> pd.DataFrame:
    result = frame.copy()
    result["dataset_split"] = result["research_enrollment_id"].map(assignments)
    return result


def _has_no_post_observation_events(
    doses: pd.DataFrame,
    visits: pd.DataFrame,
    measures: pd.DataFrame,
    adverse: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> bool:
    last_day = outcomes.set_index("research_enrollment_id")["last_observed_day"]
    checks = (
        doses["event_day"] <= doses["research_enrollment_id"].map(last_day),
        visits["event_day"] <= visits["research_enrollment_id"].map(last_day),
        measures["measurement_day"] <= measures["research_enrollment_id"].map(last_day),
        adverse["event_day"] <= adverse["research_enrollment_id"].map(last_day),
    )
    return all(bool(check.all()) for check in checks)


def _validate_schema_contracts(tables: dict[str, pd.DataFrame]) -> None:
    missing_tables = sorted(set(OUTPUT_COLUMNS) - set(tables))
    unexpected_tables = sorted(set(tables) - set(OUTPUT_COLUMNS))
    if missing_tables or unexpected_tables:
        raise ValueError(
            f"Output table contract mismatch: missing={missing_tables}, "
            f"unexpected={unexpected_tables}"
        )
    for table_name, expected_columns in OUTPUT_COLUMNS.items():
        actual_columns = tuple(tables[table_name].columns)
        if actual_columns != expected_columns:
            raise ValueError(
                f"{table_name} schema mismatch: expected={expected_columns}, "
                f"actual={actual_columns}"
            )


def _order_output_columns(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    ordered: dict[str, pd.DataFrame] = {}
    for table_name, expected_columns in OUTPUT_COLUMNS.items():
        frame = tables[table_name]
        missing_columns = sorted(set(expected_columns) - set(frame.columns))
        unexpected_columns = sorted(set(frame.columns) - set(expected_columns))
        if missing_columns or unexpected_columns:
            raise ValueError(
                f"{table_name} column set mismatch: missing={missing_columns}, "
                f"unexpected={unexpected_columns}"
            )
        ordered[table_name] = frame.loc[:, expected_columns].copy()
    return ordered


def _validate_enrollment_snapshot(
    participants: pd.DataFrame,
    enrollments: pd.DataFrame,
) -> None:
    participant_snapshot = participants.set_index("research_participant_id").sort_index()
    enrollment_snapshot = enrollments.set_index("research_participant_id").sort_index()
    for column in ENROLLMENT_SNAPSHOT_COLUMNS:
        if column == "research_participant_id":
            continue
        participant_values = participant_snapshot[column].astype(object)
        enrollment_values = enrollment_snapshot[column].astype(object)
        equal = (participant_values == enrollment_values) | (
            participant_values.isna() & enrollment_values.isna()
        )
        if not bool(equal.all()):
            raise ValueError(
                f"research_enrollments.{column} must match the immutable participant snapshot"
            )


def _validate_model_views(tables: dict[str, pd.DataFrame]) -> None:
    for view_name in DERIVED_VIEW_NAMES:
        columns = set(tables[view_name].columns)
        forbidden = sorted(
            column
            for column in columns
            if column.startswith("generation_") or column in FORBIDDEN_MODEL_FEATURE_COLUMNS
        )
        if forbidden:
            raise ValueError(f"{view_name} exports forbidden model columns: {forbidden}")

    primary = tables["landmark_day30_features"]
    if not (primary["feature_cutoff_day"] == OBSERVATION_CUTOFF_DAY).all():
        raise ValueError("Every primary feature row must use the day-30 cutoff")
    if not primary["target_observed"].astype(bool).all():
        raise ValueError("Every primary fixed-horizon target must be observed")

    dynamic = tables["dynamic_landmarks"]
    if not dynamic.empty:
        if not (dynamic["feature_cutoff_day"] == dynamic["prediction_day"]).all():
            raise ValueError("Dynamic feature cutoffs must equal their prediction landmarks")
        if not dynamic["prediction_day"].isin(DYNAMIC_LANDMARK_DAYS).all():
            raise ValueError("Dynamic views contain an undeclared prediction landmark")
        if not dynamic["target_observed"].astype(bool).all():
            raise ValueError("Dynamic views must exclude unobserved target windows")

    survival = tables["survival_features"]
    if not (survival["feature_cutoff_day"] == OBSERVATION_CUTOFF_DAY).all():
        raise ValueError("Every survival feature row must use the day-30 cutoff")


def _validate_chronology_and_values(tables: dict[str, pd.DataFrame]) -> None:
    outcomes = tables["research_outcomes"]
    observed = outcomes["dropout_by_day90"].astype(bool)
    dropout_days = pd.to_numeric(outcomes["dropout_day"], errors="coerce")
    if not dropout_days[observed].between(OBSERVATION_CUTOFF_DAY + 1, PREDICTION_HORIZON_DAY).all():
        raise ValueError("Observed dropout days must fall during days 31-90")
    if dropout_days[~observed].notna().any():
        raise ValueError("Censored rows must not have a dropout day")

    expected_censor = dropout_days.where(observed, PREDICTION_HORIZON_DAY).astype("int64")
    if not (pd.to_numeric(outcomes["censor_day"]) == expected_censor).all():
        raise ValueError("censor_day must equal dropout_day or the day-90 horizon")
    if not (
        pd.to_numeric(outcomes["last_observed_day"]) == pd.to_numeric(outcomes["censor_day"])
    ).all():
        raise ValueError("last_observed_day must equal censor_day")
    if not outcomes["event_observed"].astype(bool).equals(observed):
        raise ValueError("event_observed must match dropout_by_day90")
    if not outcomes["censored"].astype(bool).equals(~observed):
        raise ValueError("censored must be the inverse of event_observed")
    if not outcomes["trial_completed"].astype(bool).equals(~observed):
        raise ValueError("trial_completed must be false for observed dropout")

    if not _has_no_post_observation_events(
        tables["research_dose_events"],
        tables["research_visit_events"],
        tables["research_measurements"],
        tables["research_adverse_events"],
        outcomes,
    ):
        raise ValueError("Longitudinal tables contain events after last observation")

    for table_name, day_column in (
        ("research_dose_events", "event_day"),
        ("research_visit_events", "event_day"),
        ("research_measurements", "measurement_day"),
        ("research_adverse_events", "event_day"),
    ):
        if (tables[table_name][day_column] < 0).any():
            raise ValueError(f"{table_name}.{day_column} must be non-negative")

    doses = tables["research_dose_events"]
    if not (doses["scheduled_count"] == doses["administered_count"] + doses["missed_count"]).all():
        raise ValueError("Dose counts must satisfy scheduled = administered + missed")
    if (doses[["scheduled_count", "administered_count", "missed_count"]] < 0).any().any():
        raise ValueError("Dose counts must be non-negative")

    measurements = tables["research_measurements"]
    observed_measurements = measurements["observed"].astype(bool)
    if measurements.loc[~observed_measurements, "value"].notna().any():
        raise ValueError("Unobserved measurements must not contain a value")
    if not measurements.loc[observed_measurements, "value"].between(0.0, 1.0).all():
        raise ValueError("Observed normalized measurements must stay within 0-1")

    adverse = tables["research_adverse_events"]
    if not adverse.empty and not adverse["severity_grade"].between(1, 3).all():
        raise ValueError("Adverse-event severity grades must stay within 1-3")


def _validate_output_tables(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Check relational, label, split, and leakage invariants before export."""
    _validate_schema_contracts(tables)
    enrollments = tables["research_enrollments"]
    outcomes = tables["research_outcomes"]
    enrollment_ids = set(enrollments["research_enrollment_id"].astype(str))

    for table_name, id_column in (
        ("research_participants", "research_participant_id"),
        ("research_enrollments", "research_enrollment_id"),
        ("research_outcomes", "research_outcome_id"),
        ("research_dose_events", "dose_event_id"),
        ("research_visit_events", "visit_event_id"),
        ("research_measurements", "measurement_id"),
        ("research_adverse_events", "adverse_event_id"),
    ):
        frame = tables[table_name]
        if frame[id_column].isna().any() or frame[id_column].duplicated().any():
            raise ValueError(f"{table_name}.{id_column} must be non-null and unique")

    for table_name in (
        "research_dose_events",
        "research_visit_events",
        "research_measurements",
        "research_adverse_events",
        "research_outcomes",
        "landmark_day30_features",
        "dynamic_landmarks",
        "survival_features",
    ):
        foreign_keys = set(tables[table_name]["research_enrollment_id"].astype(str))
        if not foreign_keys <= enrollment_ids:
            raise ValueError(f"{table_name} contains an unknown enrollment foreign key")

    for table_name, frame in tables.items():
        if "dataset_split" in frame and frame["dataset_split"].isna().any():
            raise ValueError(f"{table_name} contains an unassigned dataset split")

    participants = tables["research_participants"]
    if set(participants["research_enrollment_id"].astype(str)) != enrollment_ids:
        raise ValueError("Every participant must resolve to exactly one enrollment")
    if set(enrollments["research_participant_id"].astype(str)) != set(
        participants["research_participant_id"].astype(str)
    ):
        raise ValueError("Every enrollment must resolve to exactly one participant")
    for id_column in ("research_participant_id", "patient_snapshot_id", "screening_id"):
        if enrollments[id_column].isna().any() or enrollments[id_column].duplicated().any():
            raise ValueError(f"research_enrollments.{id_column} must be non-null and unique")
    if not (enrollments["screening_state"] == OverallState.potentially_eligible.value).all():
        raise ValueError("Every enrollment must link to a potentially eligible screening")
    _validate_enrollment_snapshot(participants, enrollments)

    canonical_splits = enrollments.set_index("research_enrollment_id")["dataset_split"]
    split_consistency = {}
    for table_name, frame in tables.items():
        if "dataset_split" not in frame or "research_enrollment_id" not in frame:
            continue
        expected_splits = frame["research_enrollment_id"].map(canonical_splits)
        split_consistency[table_name] = bool(
            (frame["dataset_split"].astype(str) == expected_splits.astype(str)).all()
        )
    if not all(split_consistency.values()):
        raise ValueError("A table split does not match its canonical enrollment split")

    participant_level_splits = bool(
        (enrollments.groupby("research_participant_id")["dataset_split"].nunique() == 1).all()
    )
    if not participant_level_splits:
        raise ValueError("A participant appears in more than one dataset split")

    if (
        not outcomes["event_observed"]
        .astype(bool)
        .equals(outcomes["dropout_by_day90"].astype(bool))
    ):
        raise ValueError("event_observed must match the fixed-horizon dropout label")
    if outcomes.loc[outcomes["dropout_by_day90"], "dropout_day"].isna().any():
        raise ValueError("Observed dropout rows must have a dropout_day")
    if outcomes.loc[~outcomes["dropout_by_day90"], "dropout_day"].notna().any():
        raise ValueError("Censored rows must not have a dropout_day")

    _validate_chronology_and_values(tables)
    _validate_model_views(tables)

    return {
        "schema_contracts_match": True,
        "foreign_keys_resolve": True,
        "unique_ids": True,
        "split_consistency": split_consistency,
        "split_counts": {
            str(split): int(count)
            for split, count in outcomes["dataset_split"].value_counts().sort_index().items()
        },
        "label_and_censoring_consistent": True,
        "chronology_and_ranges_valid": True,
        "model_views_leakage_safe": True,
        "participant_level_splits": participant_level_splits,
        "enrollment_snapshot_consistent": True,
    }


def _feature_row(
    enrollment: pd.Series,
    enrollment_doses: pd.DataFrame,
    enrollment_visits: pd.DataFrame,
    enrollment_measures: pd.DataFrame,
    enrollment_adverse: pd.DataFrame,
    cutoff: int,
) -> dict[str, Any]:
    enrollment_id = str(enrollment["research_enrollment_id"])
    dose = enrollment_doses[enrollment_doses["event_day"] <= cutoff]
    visit = enrollment_visits[enrollment_visits["event_day"] <= cutoff]
    measure = enrollment_measures[enrollment_measures["measurement_day"] <= cutoff]
    ae = enrollment_adverse[enrollment_adverse["event_day"] <= cutoff]
    functional = measure[
        (measure["measurement_name"] == "functional_severity") & measure["observed"]
    ].sort_values("measurement_day")
    values = functional["value"].astype(float).tolist()
    slope = None
    if len(values) >= 2:
        first = functional.iloc[0]
        last = functional.iloc[-1]
        days = int(last["measurement_day"]) - int(first["measurement_day"])
        slope = (float(last["value"]) - float(first["value"])) / days if days else 0.0
    scheduled_doses = int(dose["scheduled_count"].sum())
    missed_doses = int(dose["missed_count"].sum())
    scheduled_visits = len(visit)
    missed_visits = int((visit["visit_status"] == "missed").sum())
    missing_measurements = int((~measure["observed"]).sum())
    return {
        "research_enrollment_id": enrollment_id,
        "research_participant_id": enrollment["research_participant_id"],
        "patient_snapshot_id": enrollment["patient_snapshot_id"],
        "trial_version_id": enrollment["trial_version_id"],
        "condition_category": enrollment["condition_category"],
        "site_region": enrollment["site_region"],
        "treatment_arm": enrollment["treatment_arm"],
        "age": enrollment["age"],
        "sex": enrollment["sex"],
        "baseline_functional_severity": enrollment["baseline_functional_severity"],
        "patient_reported_burden": enrollment["patient_reported_burden"],
        "baseline_comorbidity_burden": enrollment["baseline_comorbidity_burden"],
        "baseline_treatment_burden": enrollment["baseline_treatment_burden"],
        "travel_access_burden": enrollment["travel_access_burden"],
        "support_availability": enrollment["support_availability"],
        "medication_count": enrollment["medication_count"],
        "latest_functional_severity": values[-1] if values else None,
        "functional_severity_slope": slope,
        "functional_observation_count": len(functional),
        "scheduled_dose_count": scheduled_doses,
        "administered_dose_count": int(dose["administered_count"].sum()),
        "missed_dose_count": missed_doses,
        "missed_dose_rate": missed_doses / max(1, scheduled_doses),
        "scheduled_visit_count": scheduled_visits,
        "attended_visit_count": int((visit["visit_status"] == "completed").sum()),
        "missed_visit_count": missed_visits,
        "delayed_visit_count": int((visit["visit_status"] == "delayed").sum()),
        "missed_visit_rate": missed_visits / max(1, scheduled_visits),
        "mean_visit_delay_days": float(visit["delay_days"].mean()) if scheduled_visits else 0.0,
        "measurement_observation_count": int(measure["observed"].sum()),
        "measurement_missing_count": missing_measurements,
        "measurement_missingness_rate": missing_measurements / max(1, len(measure)),
        "adverse_event_count": len(ae),
        "adverse_event_burden": int(ae["severity_grade"].sum()) if len(ae) else 0,
        "feature_cutoff_day": cutoff,
    }


def _build_views(
    enrollments: pd.DataFrame,
    doses: pd.DataFrame,
    visits: pd.DataFrame,
    measures: pd.DataFrame,
    adverse: pd.DataFrame,
    outcomes: pd.DataFrame,
    assignments: dict[str, str],
) -> dict[str, pd.DataFrame]:
    outcome_map = outcomes.set_index("research_enrollment_id")
    event_tables = (doses, visits, measures, adverse)
    grouped_tables = [
        {
            str(enrollment_id): group
            for enrollment_id, group in frame.groupby(
                "research_enrollment_id", sort=False, observed=True
            )
        }
        for frame in event_tables
    ]
    dose_groups, visit_groups, measure_groups, adverse_groups = grouped_tables
    empty_doses, empty_visits, empty_measures, empty_adverse = (
        frame.iloc[0:0] for frame in event_tables
    )
    primary_rows = []
    survival_rows = []
    dynamic_rows = []
    for _, enrollment in enrollments.iterrows():
        enrollment_id = str(enrollment["research_enrollment_id"])
        enrollment_doses = dose_groups.get(enrollment_id, empty_doses)
        enrollment_visits = visit_groups.get(enrollment_id, empty_visits)
        enrollment_measures = measure_groups.get(enrollment_id, empty_measures)
        enrollment_adverse = adverse_groups.get(enrollment_id, empty_adverse)
        base = _feature_row(
            enrollment,
            enrollment_doses,
            enrollment_visits,
            enrollment_measures,
            enrollment_adverse,
            OBSERVATION_CUTOFF_DAY,
        )
        outcome = outcome_map.loc[enrollment_id]
        primary_rows.append(
            {
                **base,
                "dropout_by_day90": bool(outcome["dropout_by_day90"]),
                "target_observed": True,
            }
        )
        survival_rows.append(
            {
                **base,
                "time_to_dropout_or_censor_days": int(outcome["last_observed_day"]),
                "event_observed": bool(outcome["event_observed"]),
                "censor_day": outcome["censor_day"],
            }
        )
        for prediction_day in DYNAMIC_LANDMARK_DAYS:
            dropout_day = outcome["dropout_day"]
            if pd.notna(dropout_day) and int(dropout_day) <= prediction_day:
                continue
            target_end = prediction_day + 30
            event_in_window = bool(
                pd.notna(dropout_day) and prediction_day < int(dropout_day) <= target_end
            )
            target_observed = event_in_window or int(outcome["last_observed_day"]) >= target_end
            if not target_observed:
                continue
            dynamic_rows.append(
                {
                    **_feature_row(
                        enrollment,
                        enrollment_doses,
                        enrollment_visits,
                        enrollment_measures,
                        enrollment_adverse,
                        prediction_day,
                    ),
                    "prediction_day": prediction_day,
                    "dropout_in_next_30_days": event_in_window,
                    "target_observed": True,
                }
            )
    primary = pd.DataFrame(primary_rows)
    dynamic = pd.DataFrame(dynamic_rows)
    if dynamic.empty:
        dynamic = pd.DataFrame(
            columns=[
                *[
                    column
                    for column in primary.columns
                    if column not in {"dropout_by_day90", "target_observed"}
                ],
                "prediction_day",
                "dropout_in_next_30_days",
                "target_observed",
            ]
        )
    return {
        "landmark_day30_features": _add_split(primary, assignments),
        "dynamic_landmarks": _add_split(dynamic, assignments),
        "survival_features": _add_split(pd.DataFrame(survival_rows), assignments),
    }


def _write_outputs(
    output: Path,
    tables: dict[str, pd.DataFrame],
    *,
    num_records: int,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    invariant_report = _validate_output_tables(tables)
    for name, frame in tables.items():
        frame.to_parquet(output / f"{name}.parquet", index=False)
    outcome = tables["research_outcomes"]
    attempted_enrollments = len(tables["research_participants"])
    accepted_enrollments = len(tables["research_enrollments"])
    dropout_count = int(outcome["dropout_by_day90"].sum())
    generation_run_id = f"r3-run-{uuid4()}"
    generated_at_utc = datetime.now(UTC).isoformat()
    report = {
        "generator": "nvidia_nemo_data_designer",
        "generator_version": GENERATOR_VERSION,
        "data_designer_version": DATA_DESIGNER_VERSION,
        "dataset_contract_version": DATASET_CONTRACT_VERSION,
        "generation_run_id": generation_run_id,
        "generated_at_utc": generated_at_utc,
        "schema_fingerprint_sha256": SCHEMA_FINGERPRINT,
        "requested_enrollments": num_records,
        "attempted_enrollments": attempted_enrollments,
        "accepted_enrollments": accepted_enrollments,
        "rejected_enrollments": attempted_enrollments - accepted_enrollments,
        "unfilled_requested_enrollments": max(0, num_records - accepted_enrollments),
        "acceptance_strategy": "single_pass_designed_eligible_no_resampling",
        "observation_cutoff_day": OBSERVATION_CUTOFF_DAY,
        "prediction_horizon_day": PREDICTION_HORIZON_DAY,
        "dropout_count": dropout_count,
        "dropout_prevalence": dropout_count / max(1, len(outcome)),
        "dropout_by_split": {
            str(split): {
                "rows": len(group),
                "dropouts": int(group["dropout_by_day90"].sum()),
                "prevalence": float(group["dropout_by_day90"].mean()),
            }
            for split, group in outcome.groupby("dataset_split", sort=True)
        },
        "dynamic_landmark_positive_rows": int(
            tables["dynamic_landmarks"]["dropout_in_next_30_days"].sum()
        ),
        "table_row_counts": {name: len(frame) for name, frame in tables.items()},
        "model_usage": "sampler_and_expression_columns_only",
        "validation": {
            **invariant_report,
            "all_enrollments_potentially_eligible": bool(
                (
                    tables["research_enrollments"]["screening_state"]
                    == OverallState.potentially_eligible.value
                ).all()
            ),
            "all_primary_rows_have_day30_cutoff": bool(
                (
                    tables["landmark_day30_features"]["feature_cutoff_day"]
                    == OBSERVATION_CUTOFF_DAY
                ).all()
            ),
            "no_post_observation_events": _has_no_post_observation_events(
                tables["research_dose_events"],
                tables["research_visit_events"],
                tables["research_measurements"],
                tables["research_adverse_events"],
                outcome,
            ),
            "participant_level_splits": invariant_report["split_consistency"][
                "research_enrollments"
            ]
            and invariant_report["participant_level_splits"],
        },
    }
    (output / "generation_config.json").write_text(
        json.dumps(
            {
                "generator": report["generator"],
                "generator_version": GENERATOR_VERSION,
                "data_designer_version": report["data_designer_version"],
                "dataset_contract_version": DATASET_CONTRACT_VERSION,
                "generation_run_id": generation_run_id,
                "generated_at_utc": generated_at_utc,
                "schema_fingerprint_sha256": SCHEMA_FINGERPRINT,
                "source_tables": list(SOURCE_TABLE_NAMES),
                "derived_views": list(DERIVED_VIEW_NAMES),
                "artifact_format": "parquet",
                "physical_layout": {
                    "fully_normalized": False,
                    "intentional_denormalization": "immutable enrollment baseline snapshot",
                    "enrollment_snapshot_columns": list(ENROLLMENT_SNAPSHOT_COLUMNS),
                    "site_context_column": SITE_CONTEXT_COLUMN,
                    "site_id_exported": False,
                },
                "column_provenance": COLUMN_PROVENANCE,
                "nvidia_data_designer_used": True,
                "labels": (
                    "NeMo uniform sampler draw plus reviewed dependent expression; synthetic only"
                ),
                "dropout_probability_by_hidden_tier": DROPOUT_PROBABILITY_BY_HIDDEN_TIER,
                "dropout_prevalence_policy": {
                    "forced_to_exact_target": False,
                    "interpretation": "emergent synthetic run statistic",
                },
                "hidden_tier_inputs": {
                    "two_points": [
                        "baseline_functional_severity >= 0.70",
                        "missed_dose_rate_30d >= 0.15",
                    ],
                    "one_point": [
                        "missed_visit_rate_30d >= 0.15",
                        "adverse_event_burden_30d >= 2",
                        "travel_access_burden >= 3",
                        "support_availability <= 1",
                        "baseline_treatment_burden >= 3",
                        "patient_reported_burden >= 0.70",
                    ],
                },
                "event_dependencies": {
                    "dose_adherence": [
                        "travel_access_burden",
                        "support_availability",
                        "baseline_treatment_burden",
                        "patient_reported_burden",
                    ],
                    "visit_attendance": "same reviewed adherence tier as dose events",
                    "adverse_events": [
                        "baseline_functional_severity",
                        "baseline_comorbidity_burden",
                        "medication_count",
                        "baseline_treatment_burden",
                    ],
                    "measurements": [
                        "baseline_functional_severity",
                        "patient_reported_burden",
                        "treatment_arm",
                        "measurement_day",
                    ],
                },
                "hidden_tier_exported_as_model_feature": False,
                "measurement_scale": "normalized_0_1",
                "trial_panel_size": 5,
                "provider_credentials": "not recorded",
                "model_provider_execution": {
                    "required_for_columns": False,
                    "configured_model_columns": 0,
                    "requests": 0,
                },
                "participant_generation": {
                    "chunk_size": DATA_DESIGNER_PARTICIPANT_CHUNK_SIZE,
                    "chunk_count": (num_records + DATA_DESIGNER_PARTICIPANT_CHUNK_SIZE - 1)
                    // DATA_DESIGNER_PARTICIPANT_CHUNK_SIZE,
                    "purpose": (
                        "avoid the Data Designer 0.8.0 scheduler wait observed when the "
                        "dependent participant sampler exceeds the validated 400-row batch"
                    ),
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "validation_report.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return report


def generate(num_records: int, output: Path) -> dict[str, Any]:
    if num_records < 1:
        raise ValueError("num_records must be positive")
    designer = DataDesigner()
    # The metrics endpoint is optional and cannot bind in some restricted local
    # shells. Disabling it does not change generation or dataset contents.
    designer.set_run_config(RunConfig(otel_metrics_port=None, display_tui=False))
    with tempfile.TemporaryDirectory(prefix="trialsync-r3-nemo-") as temporary:
        temp = Path(temporary)
        runs = output / "_nemo_runs"
        participants = _run_participants(
            designer,
            num_records=num_records,
            artifact_path=runs,
        )
        participants["generation_source"] = "nemo_data_designer_sampler_expression"
        participant_path = temp / "participants.parquet"
        _write_seed(_enrollment_seed(participants), participant_path)

        enrollments = _run_table(
            designer,
            "enrollments",
            seed_path=participant_path,
            num_records=num_records,
            artifact_path=runs,
        )
        enrollments = _link_enrollments(enrollments)
        participants = participants.merge(
            enrollments[["research_participant_id", "research_enrollment_id"]],
            on="research_participant_id",
            how="left",
            validate="one_to_one",
        )
        enrollment_path = temp / "enrollments.parquet"
        _write_seed(enrollments, enrollment_path)

        schedules = _schedule_frames(enrollments)
        event_frames: dict[str, pd.DataFrame] = {}
        for table in ("dose_events", "visit_events", "measurements", "adverse_events"):
            seed_path = temp / f"{table}.parquet"
            _write_seed(schedules[table], seed_path)
            event_frames[table] = _run_table(
                designer,
                table,
                seed_path=seed_path,
                num_records=len(schedules[table]),
                artifact_path=runs,
            )
        doses, visits, measures, adverse = _normalize_events(
            event_frames["dose_events"],
            event_frames["visit_events"],
            event_frames["measurements"],
            event_frames["adverse_events"],
        )
        outcome_seed = _outcome_seed(enrollments, doses, visits, adverse)
        outcome_seed_path = temp / "outcomes.parquet"
        _write_seed(outcome_seed, outcome_seed_path)
        outcomes = _run_table(
            designer,
            "outcomes",
            seed_path=outcome_seed_path,
            num_records=num_records,
            artifact_path=runs,
        )
        outcomes = _normalize_outcomes(outcomes)
        doses, visits, measures, adverse = _apply_censoring(
            doses, visits, measures, adverse, outcomes
        )
        assignments = _assign_splits(outcomes)
        participants = _add_split(participants, assignments)
        enrollments = _add_split(enrollments, assignments)
        doses = _add_split(doses, assignments)
        visits = _add_split(visits, assignments)
        measures = _add_split(measures, assignments)
        adverse = _add_split(adverse, assignments)
        outcomes = _add_split(outcomes, assignments)
        tables = {
            "research_participants": participants,
            "research_enrollments": enrollments,
            "research_dose_events": doses,
            "research_visit_events": visits,
            "research_measurements": measures,
            "research_adverse_events": adverse,
            "research_outcomes": outcomes,
        }
        tables.update(
            _build_views(
                enrollments,
                doses,
                visits,
                measures,
                adverse,
                outcomes,
                assignments,
            )
        )
        tables = _order_output_columns(tables)
        return _write_outputs(output, tables, num_records=num_records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-records", type=int, default=400)
    parser.add_argument("--output", type=Path, default=Path("artifacts/nemo/r3_demo"))
    args = parser.parse_args()
    report = generate(args.num_records, args.output)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
