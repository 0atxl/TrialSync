from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from trialsync.research.risk.artifacts import MODEL_PACKAGE_CONTRACT, RiskArtifactService
from trialsync.research.risk.features import SourcedFeatureValue, build_feature_snapshot

MODEL_ID = "dropout-xgboost-05-v1"
MODEL_SHA256 = "ab2377e9a6a81fa39d77805f0f2fe3bfc09b2c957fcd934b62b7a205051b5de7"
DATASET_SHA256 = "746a6f63a02c0948205b53767801a775b16fe35d08aafccc522e3fd975e35982"
FEATURE_SCHEMA_SEMANTIC_SHA256 = (
    "6d0fe2185247cda50f69fc7954bf958c1c61c5cb4ef160cd34b445170236ca83"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_model(source_directory: Path, output_root: Path) -> dict[str, Any]:
    source_model = source_directory / "models" / "xgboost_pipeline.joblib"
    source_schema = source_directory / "feature_schema.json"
    if _sha256(source_model) != MODEL_SHA256:
        raise ValueError("The R4 xgboost-05 artifact checksum does not match the reviewed model.")
    schema_file_sha256 = _sha256(source_schema)

    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / MODEL_ID
    with tempfile.TemporaryDirectory(prefix="trialsync-r5-", dir=output_root) as temporary:
        staging = Path(temporary)
        shutil.copyfile(source_model, staging / "model.joblib")
        shutil.copyfile(source_schema, staging / "feature_schema.json")
        manifest: dict[str, Any] = {
            "contract_version": MODEL_PACKAGE_CONTRACT,
            "model_id": MODEL_ID,
            "name": "dropout-xgboost",
            "version": "1",
            "alias": "r5_runtime",
            "candidate_id": "xgboost-05",
            "selection_status": "user_selected_runtime_after_review",
            "threshold": 0.21347740292549133,
            "threshold_objective": "maximum_validation_f1",
            "horizon_day": 90,
            "observation_cutoff_day": 30,
            "dataset_version": "r3-dataset-contract-v1",
            "dataset_checksum": DATASET_SHA256,
            "band_policy_version": "r5-risk-bands-v1",
            "artifact": {"path": "model.joblib", "sha256": MODEL_SHA256},
            "feature_schema": {
                "path": "feature_schema.json",
                "version": "r4-day30-features-v1",
                "file_sha256": schema_file_sha256,
                "semantic_sha256": FEATURE_SCHEMA_SEMANTIC_SHA256,
            },
            "metrics": {
                "test_auroc": 0.6807348560079444,
                "test_auprc": 0.36168335306293786,
                "test_brier": 0.13310516191712304,
                "test_f1": 0.4090909090909091,
            },
            "disclaimer_version": "r5-research-risk-v1",
            "source": {
                "experiment_version": "r4-kaggle-track-a-v1",
                "artifact_import_version": "r4-artifact-import-v1",
                "retraining_performed": False,
            },
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        if target.exists():
            existing = json.loads((target / "manifest.json").read_text())
            if existing != manifest:
                raise ValueError("The existing R5 package differs from the reviewed package.")
        else:
            staging.rename(target)

    service = RiskArtifactService(output_root, MODEL_ID)
    descriptor = service.descriptor()
    input_example = json.loads((source_directory / "input_example.json").read_text())[0]
    snapshot = build_feature_snapshot(
        {
            name: SourcedFeatureValue(value=value, source="reviewed_r4_input_example")
            for name, value in input_example.items()
        }
    )
    prediction = service.predict(snapshot)
    if abs(prediction.probability - 0.0646870881319046) > 1e-8:
        raise ValueError("The packaged R5 model did not reproduce the reviewed inference result.")
    return {
        "model_directory": str(target),
        "active_model_setting": f"TRIALSYNC_RESEARCH_RISK_ACTIVE_MODEL={MODEL_ID}",
        "model": descriptor.__dict__,
        "verification": {
            "input_example_probability": prediction.probability,
            "contribution_count": len(prediction.contributions),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Package the reviewed R4 XGBoost model for R5.")
    parser.add_argument(
        "--source-directory",
        type=Path,
        default=Path("artifacts/r4/imported/r4_manual"),
    )
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/r5"))
    args = parser.parse_args()
    print(json.dumps(package_model(args.source_directory, args.output_root), sort_keys=True))


if __name__ == "__main__":
    main()
