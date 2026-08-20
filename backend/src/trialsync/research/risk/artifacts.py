from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trialsync.research.risk.features import FEATURE_NAMES, FeatureSnapshot

MODEL_PACKAGE_CONTRACT = "r5-risk-model-package-v1"


class RiskArtifactError(RuntimeError):
    """Raised when the optional local risk capability is unavailable or inconsistent."""


@dataclass(frozen=True)
class RiskModelDescriptor:
    model_id: str
    name: str
    version: str
    alias: str
    candidate_id: str
    threshold: float
    horizon_day: int
    dataset_version: str
    dataset_checksum: str
    feature_schema_version: str
    feature_schema_checksum: str
    band_policy_version: str
    artifact_checksum: str
    metrics: dict[str, float]


@dataclass(frozen=True)
class RiskContribution:
    feature: str
    value: str | int | float
    shap_value: float
    direction: str


@dataclass(frozen=True)
class RiskPredictionOutput:
    probability: float
    contributions: tuple[RiskContribution, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RiskArtifactService:
    """Lazy, checksum-verified loader for the approved local XGBoost package."""

    def __init__(self, root: Path, active_model: str | None):
        self.root = root
        self.active_model = active_model
        self._pipeline: Any | None = None
        self._descriptor: RiskModelDescriptor | None = None

    def _directory(self) -> Path:
        if not self.active_model:
            raise RiskArtifactError("No active R5 risk model is configured.")
        candidate = (self.root / self.active_model).resolve()
        root = self.root.resolve()
        if candidate.parent != root:
            raise RiskArtifactError("The configured R5 model path is invalid.")
        return candidate

    def descriptor(self) -> RiskModelDescriptor:
        if self._descriptor is not None:
            return self._descriptor
        directory = self._directory()
        manifest_path = directory / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise RiskArtifactError("The R5 model manifest is unavailable or invalid.") from exc
        if manifest.get("contract_version") != MODEL_PACKAGE_CONTRACT:
            raise RiskArtifactError("The R5 model package contract is unsupported.")
        if manifest.get("model_id") != self.active_model:
            raise RiskArtifactError("The R5 model package identity does not match configuration.")
        model_path = directory / str(manifest.get("artifact", {}).get("path", ""))
        schema_path = directory / str(manifest.get("feature_schema", {}).get("path", ""))
        if not model_path.is_file() or _sha256(model_path) != manifest["artifact"].get("sha256"):
            raise RiskArtifactError(
                "The R5 model artifact is missing or failed checksum validation."
            )
        if not schema_path.is_file() or _sha256(schema_path) != manifest["feature_schema"].get(
            "file_sha256"
        ):
            raise RiskArtifactError(
                "The R5 feature schema is missing or failed checksum validation."
            )
        try:
            schema = json.loads(schema_path.read_text())
            schema_names = tuple(item["name"] for item in schema["features"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RiskArtifactError("The R5 feature schema is invalid.") from exc
        if schema_names != FEATURE_NAMES:
            raise RiskArtifactError("The R5 feature order does not match the runtime contract.")
        descriptor = RiskModelDescriptor(
            model_id=str(manifest["model_id"]),
            name=str(manifest["name"]),
            version=str(manifest["version"]),
            alias=str(manifest["alias"]),
            candidate_id=str(manifest["candidate_id"]),
            threshold=float(manifest["threshold"]),
            horizon_day=int(manifest["horizon_day"]),
            dataset_version=str(manifest["dataset_version"]),
            dataset_checksum=str(manifest["dataset_checksum"]),
            feature_schema_version=str(manifest["feature_schema"]["version"]),
            feature_schema_checksum=str(manifest["feature_schema"]["semantic_sha256"]),
            band_policy_version=str(manifest["band_policy_version"]),
            artifact_checksum=str(manifest["artifact"]["sha256"]),
            metrics={str(key): float(value) for key, value in manifest["metrics"].items()},
        )
        if descriptor.candidate_id != "xgboost-05":
            raise RiskArtifactError("The configured R5 package is not the approved XGBoost model.")
        self._descriptor = descriptor
        return descriptor

    def _load_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        descriptor = self.descriptor()
        del descriptor
        try:
            import joblib
            import xgboost  # noqa: F401
        except ImportError as exc:
            raise RiskArtifactError(
                "R5 inference dependencies are not installed; install the research-risk extra."
            ) from exc
        model_path = self._directory() / "model.joblib"
        try:
            self._pipeline = joblib.load(model_path)
        except Exception as exc:
            raise RiskArtifactError("The approved R5 model could not be loaded.") from exc
        return self._pipeline

    def predict(self, snapshot: FeatureSnapshot, *, top_k: int = 8) -> RiskPredictionOutput:
        descriptor = self.descriptor()
        pipeline = self._load_pipeline()
        try:
            import numpy as np
            import pandas as pd
            import xgboost as xgb

            frame = pd.DataFrame(
                [[snapshot.values[name] for name in FEATURE_NAMES]], columns=FEATURE_NAMES
            )
            probability = float(pipeline.predict_proba(frame)[0, 1])
            preprocessor = pipeline.named_steps["preprocess"]
            model = pipeline.named_steps["model"]
            matrix = preprocessor.transform(frame)
            transformed_names = [str(name) for name in preprocessor.get_feature_names_out()]
            contributions = model.get_booster().predict(
                xgb.DMatrix(matrix), pred_contribs=True, validate_features=False
            )[0]
            if len(contributions) != len(transformed_names) + 1:
                raise ValueError("unexpected XGBoost contribution shape")
            grouped = {name: 0.0 for name in FEATURE_NAMES}
            categorical = ("condition_category", "site_region", "treatment_arm", "sex")
            for transformed_name, contribution in zip(
                transformed_names, contributions[:-1], strict=True
            ):
                plain = transformed_name.split("__", 1)[-1]
                original = next(
                    (name for name in categorical if plain.startswith(f"{name}_")), plain
                )
                if original not in grouped:
                    raise ValueError(f"unknown transformed feature: {transformed_name}")
                grouped[original] += float(contribution)
            ordered = sorted(grouped.items(), key=lambda item: (-abs(item[1]), item[0]))[:top_k]
            top = tuple(
                RiskContribution(
                    feature=name,
                    value=snapshot.values[name],
                    shap_value=float(np.float32(value)),
                    direction="higher" if value >= 0 else "lower",
                )
                for name, value in ordered
            )
        except RiskArtifactError:
            raise
        except Exception as exc:
            raise RiskArtifactError(
                "R5 inference failed for the validated feature snapshot."
            ) from exc
        if not 0.0 <= probability <= 1.0:
            raise RiskArtifactError("R5 inference returned an invalid probability.")
        if not 0.0 < descriptor.threshold < 1.0:
            raise RiskArtifactError("R5 model threshold metadata is invalid.")
        return RiskPredictionOutput(probability=probability, contributions=top)
