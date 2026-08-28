from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from research.package_r5_model import (
    FIXED_INPUT_ABS_TOLERANCE,
    FIXED_INPUT_PROBABILITY,
    MODEL_ID,
    package_model,
)
from research.train_xgboost_v2 import compute_streaks_if_needed, validate_streak_features

from trialsync.research.risk.artifacts import RiskArtifactError, RiskArtifactService
from trialsync.research.risk.features import (
    FEATURE_NAMES,
    FeatureSnapshotError,
    SourcedFeatureValue,
    build_feature_snapshot,
)


def _complete_values() -> dict[str, SourcedFeatureValue]:
    raw: dict[str, str | int | float] = {
        "condition_category": "cardiovascular",
        "site_region": "west",
        "treatment_arm": "active",
        "age": 55,
        "sex": "female",
        "baseline_functional_severity": 0.3,
        "patient_reported_burden": 0.2,
        "baseline_comorbidity_burden": 1,
        "baseline_treatment_burden": 2,
        "travel_access_burden": 2,
        "support_availability": 1,
        "medication_count": 1,
        "latest_functional_severity": 0.4,
        "functional_severity_slope": 0.01,
        "functional_observation_count": 4,
        "scheduled_dose_count": 10,
        "missed_dose_count": 1,
        "missed_dose_rate": 0.1,
        "longest_missed_dose_streak": 1,
        "delayed_visit_count": 0,
        "missed_visit_count": 1,
        "missed_visit_rate": 0.25,
        "longest_missed_visit_streak": 1,
        "mean_visit_delay_days": 0.0,
        "measurement_missingness_rate": 0.1,
        "adverse_event_count": 0,
        "adverse_event_burden": 0,
    }
    return {name: SourcedFeatureValue(value=value, source="test") for name, value in raw.items()}


def test_feature_snapshot_requires_every_value_and_explicit_sources() -> None:
    values = _complete_values()
    snapshot = build_feature_snapshot(values)
    assert tuple(snapshot.values) == FEATURE_NAMES
    assert len(snapshot.checksum) == 64

    del values["missed_visit_rate"]
    with pytest.raises(FeatureSnapshotError, match="missing R5 features: missed_visit_rate"):
        build_feature_snapshot(values)

    values = _complete_values()
    values["missed_visit_rate"] = SourcedFeatureValue(value=0.0, source="")
    with pytest.raises(FeatureSnapshotError, match="requires an explicit source"):
        build_feature_snapshot(values)


def test_feature_snapshot_rejects_invalid_values_instead_of_coercing_missing_to_zero() -> None:
    values = _complete_values()
    values["missed_dose_rate"] = SourcedFeatureValue(value=float("nan"), source="test")
    with pytest.raises(FeatureSnapshotError, match="must be finite"):
        build_feature_snapshot(values)

    values = _complete_values()
    values["missed_dose_rate"] = SourcedFeatureValue(value=1.1, source="test")
    with pytest.raises(FeatureSnapshotError, match=r"between 0\.0 and 1\.0"):
        build_feature_snapshot(values)


def test_feature_snapshot_rejects_invented_or_inconsistent_streaks() -> None:
    values = _complete_values()
    del values["longest_missed_dose_streak"]
    with pytest.raises(FeatureSnapshotError, match="longest_missed_dose_streak"):
        build_feature_snapshot(values)

    values = _complete_values()
    values["longest_missed_visit_streak"] = SourcedFeatureValue(value=2, source="test")
    with pytest.raises(FeatureSnapshotError, match="cannot exceed missed_visit_count"):
        build_feature_snapshot(values)


def test_unconfigured_artifact_service_is_explicitly_degraded(tmp_path: Path) -> None:
    with pytest.raises(RiskArtifactError, match="No active R5 risk model"):
        RiskArtifactService(tmp_path, None).descriptor()


def test_packager_rejects_an_unreviewed_model(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "models").mkdir(parents=True)
    (source / "models" / "xgboost_pipeline.joblib").write_bytes(b"wrong")
    (source / "feature_schema.json").write_text(json.dumps({"features": []}))
    with pytest.raises(ValueError, match="checksum"):
        package_model(source, tmp_path / "output")


def test_reviewed_local_model_packages_without_retraining(tmp_path: Path) -> None:
    source = Path("artifacts/r4/imported/xgboost_06")
    if not source.exists():
        bundle = Path("/home/rinzler/Downloads/trialsync_v2_bundle.zip")
        if not bundle.exists():
            pytest.skip("The ignored reviewed XGBoost-06 source bundle is not present.")
        source = tmp_path / "reviewed-source"
        with zipfile.ZipFile(bundle) as archive:
            for name in (
                "models/xgboost_pipeline.joblib",
                "feature_schema.json",
                "input_example.json",
            ):
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
    result = package_model(source, tmp_path)
    assert result["model"]["candidate_id"] == "xgboost-06"
    assert result["model"]["feature_schema_version"] == "r4-day30-features-v2"
    assert result["verification"]["input_example_probability"] == pytest.approx(
        FIXED_INPUT_PROBABILITY, abs=FIXED_INPUT_ABS_TOLERANCE
    )
    assert result["verification"]["contribution_count"] == 8
    manifest = json.loads((tmp_path / MODEL_ID / "manifest.json").read_text())
    assert manifest["selection_status"] == "user_selected_runtime_after_review"
    assert manifest["source"]["retraining_performed"] is False


def test_training_requires_explicit_streak_features(tmp_path: Path) -> None:
    valid_df = pd.DataFrame(
        [
            {
                "scheduled_dose_count": 10,
                "missed_dose_count": 2,
                "longest_missed_dose_streak": 2,
                "scheduled_visit_count": 4,
                "missed_visit_count": 1,
                "longest_missed_visit_streak": 1,
            }
        ]
    )
    validate_streak_features(valid_df)

    # Missing streak column fails with actionable error
    missing_streak = valid_df.drop(columns=["longest_missed_dose_streak"])
    with pytest.raises(
        ValueError, match=r"Missing required training column.*longest_missed_dose_streak"
    ):
        validate_streak_features(missing_streak)

    # compute_streaks_if_needed fails without approximation when columns missing and parquets absent
    with pytest.raises(ValueError, match="Missing required training column"):
        compute_streaks_if_needed(tmp_path, missing_streak)


def test_training_rejects_inconsistent_streak_bounds() -> None:
    base = {
        "scheduled_dose_count": 10,
        "missed_dose_count": 2,
        "longest_missed_dose_streak": 2,
        "scheduled_visit_count": 4,
        "missed_visit_count": 1,
        "longest_missed_visit_streak": 1,
    }

    # Streak exceeds missed count
    streak_exceeds_missed = pd.DataFrame([dict(base, longest_missed_dose_streak=3)])
    with pytest.raises(ValueError, match="longest_missed_dose_streak exceeds missed_dose_count"):
        validate_streak_features(streak_exceeds_missed)

    # Missed count exceeds scheduled count
    missed_exceeds_sched = pd.DataFrame([dict(base, missed_visit_count=5)])
    with pytest.raises(ValueError, match="missed_visit_count exceeds scheduled_visit_count"):
        validate_streak_features(missed_exceeds_sched)

    # Negative values
    negative_streak = pd.DataFrame([dict(base, longest_missed_visit_streak=-1)])
    with pytest.raises(ValueError, match="contains negative values"):
        validate_streak_features(negative_streak)

    # Non-integer values
    float_streak = pd.DataFrame([dict(base, longest_missed_dose_streak=1.5)])
    with pytest.raises(ValueError, match="must contain integer values"):
        validate_streak_features(float_streak)
