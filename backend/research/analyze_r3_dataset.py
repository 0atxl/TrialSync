"""Build the R3 experiment-cohort review and freeze evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pandas as pd

try:
    from .schemas.r3_dataset import (
        COLUMN_PROVENANCE,
        DERIVED_VIEW_NAMES,
        FORBIDDEN_MODEL_FEATURE_COLUMNS,
        SOURCE_TABLE_NAMES,
    )
except ImportError:
    from schemas.r3_dataset import (  # type: ignore[import-not-found, no-redef]
        COLUMN_PROVENANCE,
        DERIVED_VIEW_NAMES,
        FORBIDDEN_MODEL_FEATURE_COLUMNS,
        SOURCE_TABLE_NAMES,
    )

TABLE_NAMES = (*SOURCE_TABLE_NAMES, *DERIVED_VIEW_NAMES)
PRIMARY_VIEW = "landmark_day30_features"
TARGET = "dropout_by_day90"
IDENTIFIERS = {
    "research_enrollment_id",
    "research_participant_id",
    "patient_snapshot_id",
    "trial_version_id",
}
MODEL_METADATA = {"feature_cutoff_day", "target_observed", "dataset_split"}
REDUNDANT_OR_CONSTANT_FEATURES = {
    "scheduled_dose_count",
    "administered_dose_count",
    "missed_dose_count",
    "scheduled_visit_count",
    "attended_visit_count",
    "missed_visit_count",
    "measurement_observation_count",
    "measurement_missing_count",
}
DESCRIPTIONS = {
    "condition_category": "Synthetic study-condition portfolio category.",
    "site_region": "Fictional broad site region; no real site identifier is exported.",
    "treatment_arm": "Synthetic active or control assignment.",
    "age": "Age in whole years at the synthetic screening date.",
    "sex": "Synthetic recorded sex category, including not-recorded values.",
    "baseline_functional_severity": "Normalized baseline functional-severity score from 0 to 1.",
    "patient_reported_burden": "Normalized synthetic patient-reported burden score from 0 to 1.",
    "baseline_comorbidity_burden": "Ordinal synthetic comorbidity burden from 0 to 4.",
    "baseline_treatment_burden": "Ordinal synthetic treatment burden from 0 to 4.",
    "travel_access_burden": "Ordinal synthetic travel/access burden from 0 to 4.",
    "support_availability": (
        "Ordinal synthetic support availability from 0 to 4; higher is more support."
    ),
    "medication_count": "Synthetic baseline count of concurrent medications.",
    "latest_functional_severity": (
        "Latest observed normalized functional severity through the cutoff."
    ),
    "functional_severity_slope": (
        "Change per day between first and latest observed functional measurements."
    ),
    "functional_observation_count": "Observed functional-severity measurements through the cutoff.",
    "scheduled_dose_count": "Scheduled doses through the cutoff.",
    "administered_dose_count": "Administered scheduled doses through the cutoff.",
    "missed_dose_count": "Missed scheduled doses through the cutoff.",
    "missed_dose_rate": "Missed doses divided by scheduled doses through the cutoff.",
    "scheduled_visit_count": "Scheduled visits through the cutoff.",
    "attended_visit_count": "Completed visits through the cutoff.",
    "missed_visit_count": "Missed visits through the cutoff.",
    "delayed_visit_count": "Delayed visits through the cutoff.",
    "missed_visit_rate": "Missed visits divided by scheduled visits through the cutoff.",
    "mean_visit_delay_days": "Mean delay among scheduled visits through the cutoff.",
    "measurement_observation_count": "Observed longitudinal measurements through the cutoff.",
    "measurement_missing_count": "Unobserved scheduled measurements through the cutoff.",
    "measurement_missingness_rate": (
        "Unobserved divided by scheduled measurements through the cutoff."
    ),
    "adverse_event_count": "Observed synthetic adverse events through the cutoff.",
    "adverse_event_burden": "Sum of synthetic adverse-event severity grades through the cutoff.",
    "feature_cutoff_day": "Last day from which predictors may use information; fixed at day 30.",
    "dropout_by_day90": "Primary target: synthetic dropout during days 31 through 90.",
    "target_observed": "Whether the fixed-horizon target is known under the censoring rule.",
    "dataset_split": "Frozen participant-level train, validation, or test assignment.",
}


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_tables(artifact: Path) -> dict[str, pd.DataFrame]:
    missing = [name for name in TABLE_NAMES if not (artifact / f"{name}.parquet").is_file()]
    if missing:
        raise ValueError(f"Missing R3 Parquet tables/views: {missing}")
    return {name: pd.read_parquet(artifact / f"{name}.parquet") for name in TABLE_NAMES}


def _group_rates(frame: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    grouped = (
        frame.groupby(columns, dropna=False, observed=True)[TARGET]
        .agg(rows="size", dropouts="sum", prevalence="mean")
        .reset_index()
    )
    records: list[dict[str, Any]] = []
    for record in grouped.to_dict("records"):
        records.append(
            {
                key: (
                    int(value)
                    if key in {"rows", "dropouts"}
                    else float(value)
                    if key == "prevalence"
                    else str(value)
                )
                for key, value in record.items()
            }
        )
    return records


def _relationship(
    frame: pd.DataFrame,
    *,
    name: str,
    low: pd.Series,
    high: pd.Series,
) -> dict[str, Any]:
    low_rate = float(frame.loc[low, TARGET].mean()) if bool(low.any()) else None
    high_rate = float(frame.loc[high, TARGET].mean()) if bool(high.any()) else None
    difference = high_rate - low_rate if low_rate is not None and high_rate is not None else None
    return {
        "name": name,
        "lower_risk_rows": int(low.sum()),
        "lower_risk_dropout_prevalence": low_rate,
        "higher_risk_rows": int(high.sum()),
        "higher_risk_dropout_prevalence": high_rate,
        "absolute_prevalence_difference": difference,
        "declared_direction_observed": (
            high_rate >= low_rate if low_rate is not None and high_rate is not None else None
        ),
    }


def _relationship_report(primary: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        _relationship(
            primary,
            name="high versus low travel/access burden",
            low=primary["travel_access_burden"] <= 1,
            high=primary["travel_access_burden"] >= 3,
        ),
        _relationship(
            primary,
            name="limited versus strong support availability",
            low=primary["support_availability"] >= 3,
            high=primary["support_availability"] <= 1,
        ),
        _relationship(
            primary,
            name="high versus low patient-reported burden",
            low=primary["patient_reported_burden"] < 0.35,
            high=primary["patient_reported_burden"] >= 0.70,
        ),
        _relationship(
            primary,
            name="high versus low missed-dose rate",
            low=primary["missed_dose_rate"] < 0.05,
            high=primary["missed_dose_rate"] >= 0.15,
        ),
        _relationship(
            primary,
            name="high versus zero adverse-event burden",
            low=primary["adverse_event_burden"] == 0,
            high=primary["adverse_event_burden"] >= 2,
        ),
    ]


def _missingness(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for name, frame in tables.items():
        missing = frame.isna().sum()
        report[name] = {
            column: {"count": int(count), "rate": float(count / max(1, len(frame)))}
            for column, count in missing.items()
            if count
        }
    return report


def _numeric_summary(primary: pd.DataFrame) -> dict[str, Any]:
    candidates = primary.drop(columns=[TARGET], errors="ignore").select_dtypes(include="number")
    described = candidates.describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]).transpose()
    return {
        column: {key: float(value) for key, value in row.items()}
        for column, row in described.to_dict("index").items()
    }


def _all_boolean_checks_pass(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return all(_all_boolean_checks_pass(item) for item in value.values())
    return True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_linkage_manifest(artifact: Path, enrollments: pd.DataFrame) -> dict[str, Any]:
    columns = [
        "research_participant_id",
        "research_enrollment_id",
        "patient_snapshot_id",
        "trial_version_id",
        "screening_id",
        "dataset_split",
    ]
    rows = enrollments.loc[:, columns].sort_values("research_enrollment_id").to_dict("records")
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    manifest = {
        "manifest_version": "r3-linkage-manifest-v1",
        "row_count": len(rows),
        "linkage_sha256": hashlib.sha256(canonical).hexdigest(),
        "rows": rows,
    }
    _write_json(artifact / "linkage_manifest.json", manifest)
    return {key: value for key, value in manifest.items() if key != "rows"}


def _feature_role(column: str) -> tuple[str, str]:
    if column in IDENTIFIERS:
        return "identifier", "exclude"
    if column == TARGET:
        return "target", "exclude"
    if column in MODEL_METADATA:
        return "metadata", "exclude"
    if column in REDUNDANT_OR_CONSTANT_FEATURES:
        return "redundant/constant", "exclude"
    return "predictor", "include"


def _write_feature_dictionary(artifact: Path, primary: pd.DataFrame) -> None:
    lines = [
        "# R3 day-30 feature dictionary",
        "",
        "This dictionary covers the primary `landmark_day30_features.parquet` modeling view.",
        "Identifiers, metadata, constants, redundant counts, and the target are",
        "not model predictors. Rates retain the relevant adherence or missingness signal.",
        "All values are fictional synthetic research data.",
        "",
        "| Column | Type | Role | Model use | Provenance | Definition |",
        "|---|---|---|---|---|---|",
    ]
    provenance = COLUMN_PROVENANCE[PRIMARY_VIEW]
    for column in primary.columns:
        role, model_use = _feature_role(column)
        description = DESCRIPTIONS.get(column, column.replace("_", " ").capitalize() + ".")
        lines.append(
            f"| `{column}` | `{primary[column].dtype}` | {role} | {model_use} | "
            f"`{provenance[column]}` | {description} |"
        )
    (artifact / "feature_dictionary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_dataset_card(artifact: Path, report: dict[str, Any]) -> None:
    generation = report["generation"]
    relationship_count = sum(
        item["declared_direction_observed"] is True for item in report["relationship_checks"]
    )
    lines = [
        "# TrialSync R3 synthetic dropout dataset card",
        "",
        "## Summary",
        "",
        f"- Generator: `{generation['generator']}` / `{generation['generator_version']}`.",
        f"- Data Designer: `{generation['data_designer_version']}`.",
        f"- Contract: `{generation['dataset_contract_version']}`.",
        f"- Enrollments: {generation['accepted_enrollments']:,} fictional participants.",
        f"- Synthetic dropouts: {generation['dropout_count']:,} "
        f"({generation['dropout_prevalence']:.1%}).",
        "- Primary task: day-30 features predict synthetic dropout during days 31-90.",
        "- Generation used Data Designer samplers/expressions locally with zero model requests.",
        "",
        "## Intended use",
        "",
        "Academic comparison of dummy, logistic-regression, XGBoost, and LightGBM classifiers; "
        "leakage-safe feature engineering; calibration; and SHAP demonstrations.",
        "",
        "## Prohibited interpretation",
        "",
        "This is not real patient data, an empirical clinical estimate, clinical validation, "
        "or evidence that the resulting model predicts real participant behavior.",
        "",
        "## Split and outcome summary",
        "",
        "| Split | Rows | Dropouts | Prevalence |",
        "|---|---:|---:|---:|",
    ]
    for split, values in generation["dropout_by_split"].items():
        lines.append(
            f"| {split} | {values['rows']:,} | {values['dropouts']:,} | "
            f"{values['prevalence']:.1%} |"
        )
    lines.extend(
        [
            "",
            "## Quality and limitations",
            "",
            "- Seven source tables and three derived views pass schema, foreign-key, chronology, "
            "censoring, value-range, split, and leakage checks.",
            f"- {relationship_count}/{len(report['relationship_checks'])} reviewed directional "
            "relationship checks are observed in this stochastic cohort.",
            "- Missing measurements are feature-dependent; nulls in outcome timing and "
            "reason fields also represent censoring by design.",
            "- Data Designer 0.8.0 has no project-level sampler seed, so byte-for-byte "
            "regeneration is not claimed. This review candidate is frozen by checksums.",
            "- The held-out test split must not be used for tuning after acceptance.",
            "",
            "## Files",
            "",
            "The artifact contains seven source tables, three model-oriented views, generation and "
            "validation metadata, a linkage manifest, this card, the feature dictionary, "
            "the EDA/review report, and SHA-256 checksums.",
        ]
    )
    (artifact / "dataset_card.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_checksums(artifact: Path) -> dict[str, str]:
    checksum_path = artifact / "checksums.json"
    files = sorted(path for path in artifact.rglob("*") if path.is_file() and path != checksum_path)
    checksums = {str(path.relative_to(artifact)): _sha256(path) for path in files}
    _write_json(checksum_path, {"algorithm": "sha256", "files": checksums})
    return checksums


def analyze(artifact: Path, *, summary_output: Path | None = None) -> dict[str, Any]:
    tables = _load_tables(artifact)
    generation = _read_json(artifact / "validation_report.json")
    primary = tables[PRIMARY_VIEW]
    linkage = _write_linkage_manifest(artifact, tables["research_enrollments"])
    forbidden = sorted(
        column
        for column in primary.columns
        if column.startswith("generation_") or column in FORBIDDEN_MODEL_FEATURE_COLUMNS
    )
    participant_splits = (
        tables["research_enrollments"].groupby("research_participant_id")["dataset_split"].nunique()
    )
    relationships = _relationship_report(primary)
    report: dict[str, Any] = {
        "report_version": "r3-experiment-review-v1",
        "artifact_directory": str(artifact),
        "generation": generation,
        "linkage": linkage,
        "table_row_counts": {name: len(frame) for name, frame in tables.items()},
        "missingness": _missingness(tables),
        "numeric_feature_summary": _numeric_summary(primary),
        "dropout_by_condition": _group_rates(primary, ["condition_category"]),
        "dropout_by_trial_version": _group_rates(primary, ["trial_version_id"]),
        "dropout_by_treatment_arm": _group_rates(primary, ["treatment_arm"]),
        "relationship_checks": relationships,
        "primary_model_feature_selection": {
            "included_predictors": [
                column
                for column in primary.columns
                if _feature_role(column)[1] == "include"
            ],
            "excluded_columns": {
                column: _feature_role(column)[0]
                for column in primary.columns
                if _feature_role(column)[1] == "exclude"
            },
        },
        "data_quality": {
            "generator_validation_passed": _all_boolean_checks_pass(
                generation["validation"]
            ),
            "all_evaluable_relationship_directions_observed": all(
                item["declared_direction_observed"] is not False for item in relationships
            ),
            "primary_view_row_count_matches_enrollments": len(primary)
            == generation["accepted_enrollments"],
        },
        "leakage_audit": {
            "forbidden_columns_in_primary_view": forbidden,
            "no_forbidden_columns": not forbidden,
            "all_feature_cutoffs_are_day30": bool((primary["feature_cutoff_day"] == 30).all()),
            "all_targets_observed": bool(primary["target_observed"].astype(bool).all()),
            "all_primary_scheduled_dose_counts_are_30": bool(
                (primary["scheduled_dose_count"] == 30).all()
            ),
            "participant_split_overlap_count": int((participant_splits > 1).sum()),
            "hidden_generation_columns_exported": sorted(
                column for column in primary.columns if column.startswith("generation_")
            ),
        },
    }
    _write_json(artifact / "analysis_report.json", report)
    _write_feature_dictionary(artifact, primary)
    _write_dataset_card(artifact, report)
    checksums = _write_checksums(artifact)
    report["checksum_file_count"] = len(checksums)
    if summary_output is not None:
        summary_output.parent.mkdir(parents=True, exist_ok=True)
        _write_json(summary_output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()
    report = analyze(args.artifact, summary_output=args.summary_output)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
