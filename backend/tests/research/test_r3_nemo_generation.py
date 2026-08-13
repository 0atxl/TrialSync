from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import research.generate_r3_nemo as r3_generator
from data_designer.config import ExpressionColumnConfig, SamplerColumnConfig
from data_designer.config.config_builder import BuilderConfig
from data_designer.engine.column_generators.generators.expression import (
    ExpressionColumnGenerator,
)
from data_designer.engine.resources.resource_provider import ResourceProvider
from data_designer.engine.storage.artifact_storage import ArtifactStorage
from data_designer.interface import DataDesigner
from research.analyze_r3_dataset import analyze
from research.configs.r3_nemo import build_config
from research.generate_r3_nemo import (
    DATA_DESIGNER_VERSION,
    _build_views,
    _enrollment_seed,
    _outcome_seed,
    _run_participants,
    _schedule_frames,
    _validate_output_tables,
)
from research.schemas.r3_dataset import (
    COLUMN_PROVENANCE,
    DATASET_CONTRACT_VERSION,
    DERIVED_VIEW_NAMES,
    DROPOUT_PROBABILITY_BY_HIDDEN_TIER,
    ENROLLMENT_SNAPSHOT_COLUMNS,
    OUTPUT_COLUMNS,
    SCHEMA_FINGERPRINT,
    SITE_CONTEXT_COLUMN,
    SOURCE_TABLE_NAMES,
    TABLE_NAMES,
)


class _FakeDesigner:
    def set_run_config(self, _config: object) -> None:
        pass


def _fake_run_table(
    _designer: object,
    table: str,
    *,
    seed_path: Path | None,
    num_records: int,
    artifact_path: Path,
) -> pd.DataFrame:
    del artifact_path
    if table == "participants":
        conditions = ["metabolic", "cardiovascular", "renal", "oncology", "respiratory"]
        return pd.DataFrame(
            [
                {
                    "research_participant_id": f"participant-{index}",
                    "condition_category": conditions[index % len(conditions)],
                    "age": 40 + index,
                    "sex": "female" if index % 2 == 0 else "male",
                    "site_region": ("north", "south", "east", "west")[index % 4],
                    "baseline_functional_severity": 0.25 + 0.07 * (index % 8),
                    "patient_reported_burden": 0.20 + 0.08 * (index % 8),
                    "baseline_comorbidity_burden": index % 5,
                    "baseline_treatment_burden": 1 + index % 4,
                    "travel_access_burden": index % 5,
                    "support_availability": 4 - index % 5,
                    "medication_count": 1 + index % 8,
                }
                for index in range(num_records)
            ]
        )

    assert seed_path is not None
    frame = pd.read_parquet(seed_path)
    if table == "enrollments":
        frame["research_enrollment_id"] = [f"enrollment-{index}" for index in range(len(frame))]
        frame["patient_snapshot_id"] = [f"snapshot-{index}" for index in range(len(frame))]
        frame["screening_id"] = [f"screening-{index}" for index in range(len(frame))]
        frame["trial_version"] = "r3.1.0"
        frame["treatment_arm"] = [
            "active" if index % 2 == 0 else "control" for index in range(len(frame))
        ]
        return frame

    if table == "dose_events":
        frame["dose_event_id"] = [f"dose-{index}" for index in range(len(frame))]
        frame["administered_count"] = (frame["event_day"] % 11 != 0).astype(int)
        frame["missed_dose_reason"] = "participant_choice"
        frame["treatment_interruption"] = frame["administered_count"] == 0
        return frame

    if table == "visit_events":
        frame["visit_event_id"] = [f"visit-{index}" for index in range(len(frame))]
        frame["visit_status"] = frame["visit_number"].map(
            lambda number: "missed" if int(number) == 2 else "completed"
        )
        frame["delay_days"] = 0
        return frame

    if table == "measurements":
        frame["measurement_id"] = [f"measurement-{index}" for index in range(len(frame))]
        frame["observed"] = frame["measurement_day"] != 21
        frame["value"] = 0.55
        return frame

    if table == "adverse_events":
        frame["adverse_event_id"] = [f"adverse-{index}" for index in range(len(frame))]
        frame["event_present"] = frame["event_day"] == 7
        frame["category"] = "fatigue"
        frame["severity_grade"] = 2
        frame["treatment_related"] = True
        frame["resolved"] = True
        frame["treatment_interruption"] = False
        return frame

    if table == "outcomes":
        frame["research_outcome_id"] = [f"outcome-{index}" for index in range(len(frame))]
        frame["dropout_by_day90"] = [index % 4 == 0 for index in range(len(frame))]
        frame["dropout_day"] = [45 + index if index % 4 == 0 else 70 for index in range(len(frame))]
        frame["dropout_reason"] = "participant_decision"
        return frame

    raise AssertionError(f"Unexpected table {table}")


def _generate_stubbed_dataset(
    monkeypatch: pytest.MonkeyPatch, output: Path, *, num_records: int = 8
) -> dict[str, Any]:
    monkeypatch.setattr(r3_generator, "DataDesigner", _FakeDesigner)
    monkeypatch.setattr(r3_generator, "_run_table", _fake_run_table)
    return r3_generator.generate(num_records, output)


def test_generate_does_not_require_a_provider_api_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class DesignerConstructed(Exception):
        pass

    def stop_after_constructor() -> None:
        raise DesignerConstructed

    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setattr(r3_generator, "DataDesigner", stop_after_constructor)

    with pytest.raises(DesignerConstructed):
        r3_generator.generate(1, tmp_path)


def test_large_participant_generation_uses_bounded_data_designer_chunks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[int, Path]] = []

    def fake_chunk(
        _designer: object,
        table: str,
        *,
        seed_path: Path | None,
        num_records: int,
        artifact_path: Path,
    ) -> pd.DataFrame:
        assert table == "participants"
        assert seed_path is None
        call_index = len(calls)
        calls.append((num_records, artifact_path))
        return pd.DataFrame(
            {
                "research_participant_id": [
                    f"participant-{call_index}-{index}" for index in range(num_records)
                ]
            }
        )

    monkeypatch.setattr(r3_generator, "_run_table", fake_chunk)
    participants = _run_participants(
        object(),
        num_records=2500,
        artifact_path=tmp_path / "runs",
    )

    assert len(participants) == 2500
    assert calls == [
        (400, tmp_path / "runs" / "participant_chunks" / f"{index:04d}") for index in range(1, 7)
    ] + [(100, tmp_path / "runs" / "participant_chunks" / "0007")]
    assert participants["research_participant_id"].is_unique


def test_complete_tiny_generation_writes_exact_contract_and_reports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "r3-tiny"
    report = _generate_stubbed_dataset(monkeypatch, output)
    tables = {name: pd.read_parquet(output / f"{name}.parquet") for name in TABLE_NAMES}

    assert set(tables) == set(OUTPUT_COLUMNS)
    for table_name, expected_columns in OUTPUT_COLUMNS.items():
        assert tuple(tables[table_name].columns) == expected_columns

    assert report["requested_enrollments"] == 8
    assert report["attempted_enrollments"] == 8
    assert report["accepted_enrollments"] == 8
    assert report["rejected_enrollments"] == 0
    assert report["unfilled_requested_enrollments"] == 0
    assert report["acceptance_strategy"] == "single_pass_designed_eligible_no_resampling"
    assert report["data_designer_version"] == DATA_DESIGNER_VERSION == "0.8.0"
    assert report["dataset_contract_version"] == DATASET_CONTRACT_VERSION
    assert report["generation_run_id"].startswith("r3-run-")
    assert datetime.fromisoformat(report["generated_at_utc"]).tzinfo is not None
    assert report["schema_fingerprint_sha256"] == SCHEMA_FINGERPRINT
    assert report["dropout_count"] == 2
    assert all(report["validation"].values())
    assert report["table_row_counts"] == {name: len(frame) for name, frame in tables.items()}

    for view_name in DERIVED_VIEW_NAMES:
        assert not any(column.startswith("generation_") for column in tables[view_name])
    assert (tables["landmark_day30_features"]["scheduled_dose_count"] == 30).all()
    assert (
        tables["dynamic_landmarks"]["scheduled_dose_count"]
        == tables["dynamic_landmarks"]["prediction_day"]
    ).all()
    assert tables["research_dose_events"]["event_day"].max() > 30

    config = json.loads((output / "generation_config.json").read_text(encoding="utf-8"))
    validation = json.loads((output / "validation_report.json").read_text(encoding="utf-8"))
    assert config["source_tables"] == list(SOURCE_TABLE_NAMES)
    assert config["derived_views"] == list(DERIVED_VIEW_NAMES)
    assert config["physical_layout"] == {
        "fully_normalized": False,
        "intentional_denormalization": "immutable enrollment baseline snapshot",
        "enrollment_snapshot_columns": list(ENROLLMENT_SNAPSHOT_COLUMNS),
        "site_context_column": SITE_CONTEXT_COLUMN,
        "site_id_exported": False,
    }
    assert config["column_provenance"] == COLUMN_PROVENANCE
    assert config["dropout_probability_by_hidden_tier"] == DROPOUT_PROBABILITY_BY_HIDDEN_TIER
    assert config["dropout_prevalence_policy"]["forced_to_exact_target"] is False
    assert config["model_provider_execution"] == {
        "required_for_columns": False,
        "configured_model_columns": 0,
        "requests": 0,
    }
    assert config["participant_generation"] == {
        "chunk_size": 400,
        "chunk_count": 1,
        "purpose": (
            "avoid the Data Designer 0.8.0 scheduler wait observed when the dependent "
            "participant sampler exceeds the validated 400-row batch"
        ),
    }
    assert validation == report

    summary_path = tmp_path / "r3-tiny-summary.json"
    analysis = analyze(output, summary_output=summary_path)
    assert analysis["leakage_audit"]["no_forbidden_columns"] is True
    assert analysis["leakage_audit"]["participant_split_overlap_count"] == 0
    assert analysis["linkage"]["row_count"] == 8
    assert summary_path.is_file()
    assert (output / "analysis_report.json").is_file()
    assert (output / "dataset_card.md").is_file()
    assert (output / "feature_dictionary.md").is_file()
    assert (output / "linkage_manifest.json").is_file()
    checksums = json.loads((output / "checksums.json").read_text(encoding="utf-8"))
    assert "checksums.json" not in checksums["files"]
    assert "landmark_day30_features.parquet" in checksums["files"]


def test_recorded_400_row_result_is_observed_not_forced() -> None:
    report_path = Path(__file__).parents[2] / "research/reports/r3_demo_400_observed.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["accepted_enrollments"] == 400
    assert report["dropout_count"] == 64
    assert report["dropout_prevalence"] == 0.16
    assert report["dropout_prevalence_policy"]["forced_to_exact_target"] is False
    assert report["generation_run_id"] is None
    assert report["dropout_probability_by_hidden_tier"] == (DROPOUT_PROBABILITY_BY_HIDDEN_TIER)


def test_output_validation_rejects_schema_split_and_chronology_corruption(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "r3-corruption"
    _generate_stubbed_dataset(monkeypatch, output)
    tables = {name: pd.read_parquet(output / f"{name}.parquet") for name in TABLE_NAMES}

    wrong_schema = {name: frame.copy() for name, frame in tables.items()}
    wrong_schema["research_participants"] = wrong_schema["research_participants"].drop(
        columns="site_region"
    )
    with pytest.raises(ValueError, match="research_participants schema mismatch"):
        _validate_output_tables(wrong_schema)

    wrong_split = {name: frame.copy() for name, frame in tables.items()}
    first_enrollment = wrong_split["research_dose_events"].iloc[0]["research_enrollment_id"]
    canonical_split = (
        tables["research_enrollments"]
        .set_index("research_enrollment_id")
        .loc[first_enrollment, "dataset_split"]
    )
    wrong_split["research_dose_events"].loc[
        wrong_split["research_dose_events"]["research_enrollment_id"] == first_enrollment,
        "dataset_split",
    ] = "test" if canonical_split != "test" else "train"
    with pytest.raises(ValueError, match="canonical enrollment split"):
        _validate_output_tables(wrong_split)

    wrong_snapshot = {name: frame.copy() for name, frame in tables.items()}
    wrong_snapshot["research_enrollments"].loc[0, "site_region"] = "changed-region"
    with pytest.raises(ValueError, match="immutable participant snapshot"):
        _validate_output_tables(wrong_snapshot)

    wrong_chronology = {name: frame.copy() for name, frame in tables.items()}
    censored_id = (
        wrong_chronology["research_outcomes"]
        .loc[~wrong_chronology["research_outcomes"]["event_observed"], "research_enrollment_id"]
        .iloc[0]
    )
    event_index = wrong_chronology["research_dose_events"].index[
        wrong_chronology["research_dose_events"]["research_enrollment_id"] == censored_id
    ][0]
    wrong_chronology["research_dose_events"].loc[event_index, "event_day"] = 91
    with pytest.raises(ValueError, match="events after last observation"):
        _validate_output_tables(wrong_chronology)


def test_day30_features_ignore_future_events_and_recompute_pre_cutoff_dose_edits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "r3-feature-boundary"
    _generate_stubbed_dataset(monkeypatch, output)
    tables = {name: pd.read_parquet(output / f"{name}.parquet") for name in TABLE_NAMES}
    assignments = (
        tables["research_enrollments"]
        .set_index("research_enrollment_id")["dataset_split"]
        .to_dict()
    )

    baseline = (
        tables["landmark_day30_features"]
        .sort_values("research_enrollment_id")
        .reset_index(drop=True)
    )
    future_doses = tables["research_dose_events"].copy()
    future_doses.loc[future_doses["event_day"] > 30, "administered_count"] = 0
    future_doses.loc[future_doses["event_day"] > 30, "missed_count"] = 1
    future_visits = tables["research_visit_events"].copy()
    future_visits.loc[future_visits["event_day"] > 30, "visit_status"] = "missed"
    future_measures = tables["research_measurements"].copy()
    future_measures.loc[future_measures["measurement_day"] > 30, "value"] = 1.0

    future_view = (
        _build_views(
            tables["research_enrollments"],
            future_doses,
            future_visits,
            future_measures,
            tables["research_adverse_events"],
            tables["research_outcomes"],
            assignments,
        )["landmark_day30_features"]
        .sort_values("research_enrollment_id")
        .reset_index(drop=True)
    )
    pd.testing.assert_frame_equal(baseline, future_view, check_dtype=False)

    edited_doses = tables["research_dose_events"].copy()
    enrollment_id = str(edited_doses.iloc[0]["research_enrollment_id"])
    edit_index = edited_doses.index[
        (edited_doses["research_enrollment_id"] == enrollment_id) & (edited_doses["event_day"] == 2)
    ][0]
    edited_doses.loc[edit_index, ["administered_count", "missed_count"]] = [0, 1]
    edited_view = _build_views(
        tables["research_enrollments"],
        edited_doses,
        tables["research_visit_events"],
        tables["research_measurements"],
        tables["research_adverse_events"],
        tables["research_outcomes"],
        assignments,
    )["landmark_day30_features"].set_index("research_enrollment_id")
    original = baseline.set_index("research_enrollment_id").loc[enrollment_id]
    edited = edited_view.loc[enrollment_id]
    assert edited["administered_dose_count"] == original["administered_dose_count"] - 1
    assert edited["missed_dose_count"] == original["missed_dose_count"] + 1
    assert edited["missed_dose_rate"] > original["missed_dose_rate"]


def _enrollment(
    enrollment_id: str,
    *,
    severity: float,
    patient_burden: float,
    travel: int,
    support: int,
    treatment_burden: int,
    comorbidity: int,
    medication_count: int,
    treatment_arm: str = "active",
) -> dict[str, object]:
    return {
        "research_enrollment_id": enrollment_id,
        "research_participant_id": f"participant-{enrollment_id}",
        "patient_snapshot_id": f"snapshot-{enrollment_id}",
        "trial_version_id": "trial-oncology-r3-v1",
        "condition_category": "oncology",
        "site_region": "north",
        "treatment_arm": treatment_arm,
        "age": 55,
        "sex": "female",
        "baseline_functional_severity": severity,
        "patient_reported_burden": patient_burden,
        "baseline_comorbidity_burden": comorbidity,
        "baseline_treatment_burden": treatment_burden,
        "travel_access_burden": travel,
        "support_availability": support,
        "medication_count": medication_count,
    }


def test_schedule_frames_are_linked_and_use_normalized_measurements() -> None:
    enrollment = _enrollment(
        "high",
        severity=0.82,
        patient_burden=0.80,
        travel=4,
        support=0,
        treatment_burden=4,
        comorbidity=3,
        medication_count=7,
    )

    frames = _schedule_frames(pd.DataFrame([enrollment]))

    assert len(frames["dose_events"]) == 90
    assert len(frames["visit_events"]) == 12
    assert len(frames["measurements"]) == 26
    assert len(frames["adverse_events"]) == 12
    assert set(frames["measurements"]["unit"]) == {"normalized_0_1"}
    assert set(frames["dose_events"]["generation_adherence_tier"]) == {"high"}
    assert set(frames["adverse_events"]["generation_ae_risk_tier"]) == {"high"}


def test_enrollment_seed_maps_each_condition_to_one_shared_trial() -> None:
    participants = pd.DataFrame(
        {"condition_category": ["metabolic", "cardiovascular", "renal", "oncology", "respiratory"]}
    )

    seed = _enrollment_seed(participants)

    assert seed["trial_version_id"].tolist() == [
        "trial-metabolic-r3-v1",
        "trial-cardiovascular-r3-v1",
        "trial-renal-r3-v1",
        "trial-oncology-r3-v1",
        "trial-respiratory-r3-v1",
    ]


def test_outcome_seed_uses_multiple_observable_day30_risk_factors() -> None:
    enrollments = pd.DataFrame(
        [
            _enrollment(
                "low",
                severity=0.20,
                patient_burden=0.20,
                travel=0,
                support=4,
                treatment_burden=1,
                comorbidity=0,
                medication_count=1,
            ),
            _enrollment(
                "high",
                severity=0.85,
                patient_burden=0.90,
                travel=4,
                support=0,
                treatment_burden=4,
                comorbidity=4,
                medication_count=8,
            ),
        ]
    )
    doses = pd.DataFrame(
        [
            {
                "dose_event_id": f"dose-{enrollment_id}-{day}",
                "research_enrollment_id": enrollment_id,
                "event_day": day,
                "scheduled_count": 1,
                "missed_count": int(enrollment_id == "high" and day <= 10),
            }
            for enrollment_id in ("low", "high")
            for day in range(1, 31)
        ]
    )
    visits = pd.DataFrame(
        [
            {
                "visit_event_id": f"visit-{enrollment_id}-{day}",
                "research_enrollment_id": enrollment_id,
                "event_day": day,
                "visit_status": (
                    "missed" if enrollment_id == "high" and day in (7, 14) else "completed"
                ),
            }
            for enrollment_id in ("low", "high")
            for day in (7, 14, 21, 28)
        ]
    )
    adverse = pd.DataFrame(
        [
            {
                "adverse_event_id": "ae-high",
                "research_enrollment_id": "high",
                "event_day": 14,
                "severity_grade": 3,
            }
        ]
    )

    result = _outcome_seed(enrollments, doses, visits, adverse).set_index("research_enrollment_id")

    assert result.loc["low", "generation_dropout_risk_tier"] == "low"
    assert result.loc["high", "generation_dropout_risk_tier"] == "very_high"
    assert result.loc["high", "generation_primary_dropout_driver"] == "adverse_event_burden"


def test_dynamic_landmarks_keep_observed_positive_dropout_windows() -> None:
    enrollments = pd.DataFrame(
        [
            _enrollment(
                "event",
                severity=0.75,
                patient_burden=0.70,
                travel=2,
                support=2,
                treatment_burden=2,
                comorbidity=2,
                medication_count=4,
            )
        ]
    )
    doses = pd.DataFrame(
        [
            {
                "dose_event_id": f"dose-{day}",
                "research_enrollment_id": "event",
                "event_day": day,
                "scheduled_count": 1,
                "administered_count": 1,
                "missed_count": 0,
            }
            for day in range(1, 31)
        ]
    )
    visits = pd.DataFrame(
        [
            {
                "visit_event_id": f"visit-{day}",
                "research_enrollment_id": "event",
                "event_day": day,
                "visit_status": "completed",
                "delay_days": 0,
            }
            for day in (7, 14, 21, 28)
        ]
    )
    measures = pd.DataFrame(
        [
            {
                "measurement_id": f"measurement-{day}",
                "research_enrollment_id": "event",
                "measurement_day": day,
                "measurement_name": "functional_severity",
                "value": 0.75 - day / 1000,
                "observed": True,
            }
            for day in (0, 7, 14, 21, 28)
        ]
    )
    adverse = pd.DataFrame(
        columns=["adverse_event_id", "research_enrollment_id", "event_day", "severity_grade"]
    )
    outcomes = pd.DataFrame(
        [
            {
                "research_enrollment_id": "event",
                "dropout_by_day90": True,
                "dropout_day": 45,
                "event_observed": True,
                "last_observed_day": 45,
                "censor_day": 45,
            }
        ]
    )

    views = _build_views(
        enrollments,
        doses,
        visits,
        measures,
        adverse,
        outcomes,
        {"event": "train"},
    )

    dynamic = views["dynamic_landmarks"]
    assert dynamic["dropout_in_next_30_days"].any()
    assert set(dynamic.loc[dynamic["dropout_in_next_30_days"], "prediction_day"]) == {
        21,
        28,
        30,
    }


def test_dynamic_landmarks_exclude_unobserved_censored_windows() -> None:
    enrollments = pd.DataFrame(
        [
            _enrollment(
                "censored",
                severity=0.4,
                patient_burden=0.4,
                travel=1,
                support=3,
                treatment_burden=1,
                comorbidity=1,
                medication_count=2,
            )
        ]
    )
    doses = pd.DataFrame(
        [
            {
                "research_enrollment_id": "censored",
                "event_day": day,
                "scheduled_count": 1,
                "administered_count": 1,
                "missed_count": 0,
            }
            for day in range(1, 31)
        ]
    )
    visits = pd.DataFrame(
        columns=["research_enrollment_id", "event_day", "visit_status", "delay_days"]
    )
    measures = pd.DataFrame(
        columns=[
            "research_enrollment_id",
            "measurement_day",
            "measurement_name",
            "value",
            "observed",
        ]
    )
    adverse = pd.DataFrame(columns=["research_enrollment_id", "event_day", "severity_grade"])
    outcomes = pd.DataFrame(
        [
            {
                "research_enrollment_id": "censored",
                "dropout_by_day90": False,
                "dropout_day": None,
                "event_observed": False,
                "last_observed_day": 35,
                "censor_day": 35,
            }
        ]
    )

    dynamic = _build_views(
        enrollments,
        doses,
        visits,
        measures,
        adverse,
        outcomes,
        {"censored": "train"},
    )["dynamic_landmarks"]

    assert dynamic.empty
    assert tuple(dynamic.columns) == OUTPUT_COLUMNS["dynamic_landmarks"]


def test_every_seeded_nemo_table_configuration_validates(tmp_path: Path) -> None:
    seeds = {
        "enrollments": {
            "research_participant_id": "participant-1",
            "condition_category": "oncology",
            "age": 55,
            "trial_version_id": "trial-oncology-r3-v1",
        },
        "dose_events": {
            "research_enrollment_id": "enrollment-1",
            "event_day": 1,
            "scheduled_count": 1,
            "generation_adherence_tier": "moderate",
            "generation_primary_burden": "symptoms",
            "condition_category": "oncology",
            "treatment_arm": "active",
            "generation_ae_risk_tier": "moderate",
        },
        "visit_events": {
            "research_enrollment_id": "enrollment-1",
            "event_day": 7,
            "scheduled_day": 7,
            "visit_number": 1,
            "generation_adherence_tier": "moderate",
            "condition_category": "oncology",
            "treatment_arm": "active",
            "generation_primary_burden": "symptoms",
            "generation_ae_risk_tier": "moderate",
        },
        "measurements": {
            "research_enrollment_id": "enrollment-1",
            "measurement_day": 7,
            "measurement_name": "functional_severity",
            "unit": "normalized_0_1",
            "generation_measurement_band": "high",
            "generation_adherence_tier": "moderate",
            "condition_category": "oncology",
            "treatment_arm": "active",
            "generation_primary_burden": "symptoms",
            "generation_ae_risk_tier": "moderate",
        },
        "adverse_events": {
            "research_enrollment_id": "enrollment-1",
            "event_day": 7,
            "generation_ae_risk_tier": "moderate",
            "condition_category": "oncology",
            "treatment_arm": "active",
            "generation_adherence_tier": "moderate",
            "generation_primary_burden": "symptoms",
        },
        "outcomes": {
            "research_enrollment_id": "enrollment-1",
            "generation_dropout_risk_tier": "high",
            "generation_primary_dropout_driver": "adverse_event_burden",
        },
    }
    designer = DataDesigner()
    participants_config = build_config("participants")
    designer.validate(participants_config)
    BuilderConfig(data_designer=participants_config.build())
    for table_name, row in seeds.items():
        seed_path = tmp_path / f"{table_name}.parquet"
        pd.DataFrame([row]).to_parquet(seed_path, index=False)
        table_config = build_config(table_name, seed_path)
        designer.validate(table_config)
        BuilderConfig(data_designer=table_config.build())


def test_seeded_table_expressions_can_read_seed_and_sampler_columns(tmp_path: Path) -> None:
    seeds = {
        "enrollments": {
            "research_participant_id": "participant-1",
            "condition_category": "oncology",
            "trial_version_id": "trial-oncology-r3-v1",
        },
        "dose_events": {
            "research_enrollment_id": "enrollment-1",
            "generation_adherence_tier": "high",
            "generation_primary_burden": "access",
        },
        "visit_events": {
            "research_enrollment_id": "enrollment-1",
            "generation_adherence_tier": "high",
        },
        "measurements": {
            "research_enrollment_id": "enrollment-1",
            "generation_adherence_tier": "high",
            "generation_measurement_band": "very_high",
        },
        "adverse_events": {
            "research_enrollment_id": "enrollment-1",
            "generation_ae_risk_tier": "high",
            "condition_category": "oncology",
            "treatment_arm": "active",
        },
        "outcomes": {
            "research_enrollment_id": "enrollment-1",
            "generation_dropout_risk_tier": "very_high",
            "generation_primary_dropout_driver": "adverse_event_burden",
        },
    }
    resource_provider = ResourceProvider(
        artifact_storage=ArtifactStorage(artifact_path=tmp_path),
    )

    for table_name, seed_row in seeds.items():
        seed_path = tmp_path / f"{table_name}-expression-seed.parquet"
        pd.DataFrame([seed_row]).to_parquet(seed_path, index=False)
        config = build_config(table_name, seed_path).build()
        row = dict(seed_row)
        expressions = []
        for column in config.columns:
            if isinstance(column, SamplerColumnConfig):
                assert not column.conditional_params
                if column.sampler_type == "uuid":
                    row[column.name] = f"{column.name}-1"
                elif column.sampler_type == "gaussian":
                    row[column.name] = 0.0
                else:
                    row[column.name] = 0.5
            elif isinstance(column, ExpressionColumnConfig):
                expressions.append(column)

        frame = pd.DataFrame([row])
        for expression in expressions:
            frame = ExpressionColumnGenerator(expression, resource_provider).generate(frame)

        assert len(frame) == 1
        assert all(expression.name in frame.columns for expression in expressions)
