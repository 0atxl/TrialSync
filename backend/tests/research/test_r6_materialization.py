from __future__ import annotations

import json
import re
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from research.build_r6_cohort import materialize, write_artifacts
from research.configs.r6_cohort import R6CohortConfig
from research.schemas.r6_dataset import (
    ARTIFACT_FILENAMES,
    CRITERION_RESULTS_FILENAME,
    FORBIDDEN_FEATURE_TOKENS,
    MANIFEST_FILENAME,
    REFERENCE_PANEL_FILENAME,
    validate_forbidden_feature_leakage,
)

from trialsync.domain import CriterionResult, ScreeningContext, screen


def _tiny_config() -> R6CohortConfig:
    return R6CohortConfig(patient_count=4, trial_count=3, seed=61)


def test_tiny_materialization_is_deterministic_and_has_exact_pair_matrix() -> None:
    first = materialize(_tiny_config())
    second = materialize(_tiny_config())

    assert first.run_id == second.run_id
    assert first.semantic_checksums == second.semantic_checksums
    assert first.screening_pairs == second.screening_pairs
    assert first.criterion_results == second.criterion_results
    assert len(first.patients) == 4
    assert len(first.trials) == 3
    assert len(first.screening_pairs) == 12
    assert len({record["patient_snapshot_id"] for record in first.screening_pairs}) == 4
    assert len(first.criterion_results) == 48
    assert first.run_id.startswith("r6-")
    assert all(
        character.islower() or character.isdigit() or character == "-" for character in first.run_id
    )
    allowed_concepts = {
        "female",
        "male",
        "type1_diabetes",
        "type2_diabetes",
        "hypertension",
        "asthma",
        "metformin",
        "atorvastatin",
        "insulin",
        "semaglutide",
        "hba1c",
        "fasting_glucose",
        "egfr",
        "creatinine",
        "hemoglobin",
        "platelets",
        "bmi",
        "systolic_bp",
        "diastolic_bp",
        "potassium",
    }
    assert {record["concept"] for record in first.patient_fact_records} <= allowed_concepts
    materialized_text = json.dumps(
        {
            "patients": first.patient_records,
            "facts": first.patient_fact_records,
            "panel": first.reference_panel,
        }
    ).casefold()
    blocked_labels = ("syn" + "thetic", "de" + "mo", "aca" + "demic", "bt" + "ech")
    assert not re.search(rf"\b({'|'.join(blocked_labels)})\b", materialized_text)


def test_materialized_pair_and_criterion_records_agree_with_pure_screening_engine() -> None:
    cohort = materialize(_tiny_config())
    patient = cohort.patients[0]
    trial = cohort.trials[0]
    result = screen(
        patient,
        trial,
        ScreeningContext(
            screening_date=cohort.config.screening_date,
            engine_version=cohort.config.engine_version,
            terminology_version=cohort.config.terminology_version,
            unit_version=cohort.config.unit_version,
        ),
    )
    pair = next(
        record
        for record in cohort.screening_pairs
        if record["patient_snapshot_id"] == patient.id and record["trial_version_id"] == trial.id
    )
    criterion_records = [
        record for record in cohort.criterion_results if record["pair_id"] == pair["pair_id"]
    ]

    assert pair["overall_state"] == result.overall_state.value
    assert pair["pass_count"] == result.counts[CriterionResult.pass_]
    assert pair["fail_count"] == result.counts[CriterionResult.fail]
    assert pair["unknown_count"] == result.counts[CriterionResult.unknown]
    assert [(record["criterion_id"], record["result"]) for record in criterion_records] == [
        (evaluation.criterion_id, evaluation.result.value) for evaluation in result.evaluations
    ]


def test_jsonl_artifacts_and_manifest_are_complete_and_reproducible(tmp_path: Path) -> None:
    cohort = materialize(_tiny_config())
    first_manifest = write_artifacts(cohort, tmp_path / "first")
    second_manifest = write_artifacts(materialize(_tiny_config()), tmp_path / "second")

    assert {
        key: value for key, value in first_manifest.items() if key != "generated_at"
    } == {key: value for key, value in second_manifest.items() if key != "generated_at"}
    assert first_manifest["pair_count"] == 12
    assert first_manifest["criterion_result_count"] == 48
    assert set(first_manifest["files"]) == set(ARTIFACT_FILENAMES)
    assert set(first_manifest["semantic_checksums"]) == {
        "patient_snapshots",
        "patient_facts",
        "reference_panel",
        "criterion_order",
        "screening_pairs",
        "criterion_results",
        "cohort",
    }
    first = tmp_path / "first"
    assert {path.name for path in first.iterdir()} == {
        *ARTIFACT_FILENAMES.values(),
        MANIFEST_FILENAME,
    }
    assert json.loads((first / MANIFEST_FILENAME).read_text(encoding="utf-8")) == first_manifest
    assert pq.read_table(first / ARTIFACT_FILENAMES["screening_pairs"]).num_rows == 12
    assert pq.read_table(first / CRITERION_RESULTS_FILENAME).num_rows == 48
    panel = json.loads((first / REFERENCE_PANEL_FILENAME).read_text(encoding="utf-8"))
    assert len(panel["trials"]) == 3


def test_forbidden_feature_leakage_guard_rejects_prohibited_fields() -> None:
    for token in FORBIDDEN_FEATURE_TOKENS:
        with pytest.raises(ValueError, match="Forbidden R6 feature leakage"):
            validate_forbidden_feature_leakage([{f"derived_{token}_value": 1}])
