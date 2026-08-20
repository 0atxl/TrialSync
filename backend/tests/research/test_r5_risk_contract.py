from __future__ import annotations

import json
from pathlib import Path

import pytest
from research.package_r5_model import MODEL_ID, package_model

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
        "missed_dose_rate": 0.1,
        "delayed_visit_count": 0,
        "missed_visit_rate": 0.25,
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
    source = Path("artifacts/r4/imported/r4_manual")
    if not source.exists():
        pytest.skip("The ignored reviewed R4 package is not present in this checkout.")
    result = package_model(source, tmp_path)
    assert result["model"]["candidate_id"] == "xgboost-05"
    manifest = json.loads((tmp_path / MODEL_ID / "manifest.json").read_text())
    assert manifest["selection_status"] == "user_selected_runtime_after_review"
    assert manifest["source"]["retraining_performed"] is False
