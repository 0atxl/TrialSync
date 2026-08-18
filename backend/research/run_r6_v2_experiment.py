"""Run the frozen one-shot R6 V2 representation comparison without altering V1."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import fmean
from typing import Any

import numpy as np

from research.analyze_r6_cohort import (
    DEFAULT_DBSCAN_CONFIG,
    LoadedR6Cohort,
    build_representations,
    load_materialized_cohort,
)
from research.configs.r6_v2 import (
    R6_V2_ACCEPTANCE,
    R6_V2_EXPECTED_COUNTS,
    R6_V2_EXPECTED_SEMANTIC_CHECKSUMS,
    R6_V2_EXPERIMENT_VERSION,
    R6_V2_SOURCE_RUN_ID,
)
from trialsync.research.cohort_profiles import (
    RepresentationArtifact,
    RepresentationContext,
    build_patient_fact_representation_v2,
    build_screening_profile_representation_v2,
)
from trialsync.research.cohort_profiles.contracts import BalancedPreprocessingParameters
from trialsync.research.cohorts import build_pca_projection, run_dbscan_analysis
from trialsync.research.similarity import (
    build_exact_faiss_index,
    query_neighbors,
    verify_exact_neighbors,
)


def _jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _add_file(files: dict[str, dict[str, Any]], root: Path, name: str, path: Path) -> None:
    files[name] = {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _validate_frozen_source(cohort: LoadedR6Cohort) -> None:
    manifest = cohort.manifest
    if manifest.get("run_id") != R6_V2_SOURCE_RUN_ID:
        raise ValueError("R6 V2 must run against the frozen accepted source run")
    for field, expected_count in R6_V2_EXPECTED_COUNTS.items():
        if manifest.get(field) != expected_count:
            raise ValueError(f"R6 V2 frozen source count mismatch: {field}")
    checksums = manifest.get("semantic_checksums", {})
    for field, expected_checksum in R6_V2_EXPECTED_SEMANTIC_CHECKSUMS.items():
        if checksums.get(field) != expected_checksum:
            raise ValueError(f"R6 V2 frozen source checksum mismatch: {field}")


def build_v2_representations(
    cohort: LoadedR6Cohort,
) -> tuple[RepresentationArtifact, RepresentationArtifact]:
    checksums = cohort.manifest["semantic_checksums"]
    context = RepresentationContext(
        cohort_checksum=str(checksums["cohort"]),
        reference_panel_checksum=str(checksums["reference_panel"]),
        criterion_order_checksum=str(checksums["criterion_order"]),
        as_of_date=date.fromisoformat(str(cohort.manifest["screening_date"])),
    )
    return (
        build_patient_fact_representation_v2(cohort.patients, context),
        build_screening_profile_representation_v2(
            cohort.patients,
            cohort.criterion_results,
            context,
            rule_signatures=cohort.rule_signatures,
        ),
    )


def _acceptance(report: Any, integrity_checks: dict[str, bool]) -> dict[str, Any]:
    selected = report.selected
    cluster_sizes = [size for _label, size in selected.cluster_sizes]
    assigned = sum(cluster_sizes)
    largest_fraction = max(cluster_sizes, default=0) / assigned if assigned else 0.0
    bootstrap = selected.stability.bootstrap_adjusted_rand_mean
    nearby = selected.stability.nearby_parameter_adjusted_rand_mean
    silhouette = selected.silhouette_score
    checks = {
        "cluster_count": selected.cluster_count >= R6_V2_ACCEPTANCE["minimum_cluster_count"],
        "noise_fraction": (
            R6_V2_ACCEPTANCE["minimum_noise_fraction"]
            <= selected.noise_fraction
            <= R6_V2_ACCEPTANCE["maximum_noise_fraction"]
        ),
        "silhouette": (
            silhouette is not None and silhouette >= R6_V2_ACCEPTANCE["minimum_silhouette"]
        ),
        "bootstrap_ari": (
            bootstrap is not None and bootstrap >= R6_V2_ACCEPTANCE["minimum_bootstrap_ari"]
        ),
        "nearby_parameter_ari": (
            nearby is not None
            and nearby >= R6_V2_ACCEPTANCE["minimum_nearby_parameter_ari"]
        ),
        "largest_cluster_fraction": (
            largest_fraction <= R6_V2_ACCEPTANCE["maximum_largest_cluster_fraction"]
        ),
    }
    return {
        "criteria": R6_V2_ACCEPTANCE,
        "checks": checks,
        "integrity_checks": integrity_checks,
        "automated_pass": all(checks.values()) and all(integrity_checks.values()),
        "largest_cluster_fraction": largest_fraction,
        "final_decision": "pending_review",
    }


def _neighbor_overlap(v1_index: Any, v2_index: Any, *, neighbor_count: int = 10) -> dict[str, Any]:
    values: list[float] = []
    for member_id in v1_index.member_ids:
        v1_neighbors = {
            item.member_id
            for item in query_neighbors(v1_index, member_id, neighbor_count).neighbors
        }
        v2_neighbors = {
            item.member_id
            for item in query_neighbors(v2_index, member_id, neighbor_count).neighbors
        }
        union = v1_neighbors | v2_neighbors
        values.append(len(v1_neighbors & v2_neighbors) / len(union) if union else 1.0)
    return {
        "neighbor_count": min(neighbor_count, len(v1_index.member_ids) - 1),
        "checked_member_count": len(values),
        "mean_jaccard": fmean(values),
        "minimum_jaccard": min(values),
        "maximum_jaccard": max(values),
    }


def _write_experiment(
    cohort: LoadedR6Cohort,
    v2_representations: tuple[RepresentationArtifact, RepresentationArtifact],
    output_directory: Path,
) -> dict[str, Any]:
    import faiss

    v1_by_name = {artifact.name: artifact for artifact in build_representations(cohort)}
    files: dict[str, dict[str, Any]] = {}
    summaries: dict[str, Any] = {}
    for artifact in v2_representations:
        if not isinstance(artifact.preprocessing, BalancedPreprocessingParameters):
            raise TypeError("R6 V2 artifact has the wrong preprocessing contract")
        representation_directory = output_directory / "representations" / artifact.name
        vectors_path = representation_directory / "vectors.npy"
        raw_path = representation_directory / "raw.npy"
        metadata_path = representation_directory / "metadata.json"
        representation_directory.mkdir(parents=True, exist_ok=True)
        np.save(vectors_path, artifact.normalized_matrix, allow_pickle=False)
        np.save(raw_path, artifact.raw_matrix, allow_pickle=False)
        _write_json(
            metadata_path,
            {
                "name": artifact.name,
                "version": artifact.version,
                "member_ids": artifact.member_ids,
                "feature_names": artifact.feature_names,
                "preprocessing": artifact.preprocessing,
                "cohort_checksum": artifact.cohort_checksum,
                "reference_panel_checksum": artifact.reference_panel_checksum,
                "criterion_order_checksum": artifact.criterion_order_checksum,
                "subject_order_checksum": artifact.subject_order_checksum,
                "feature_order_checksum": artifact.feature_order_checksum,
                "dimension": len(artifact.feature_names),
                "member_count": len(artifact.member_ids),
            },
        )
        report = run_dbscan_analysis(
            artifact,
            DEFAULT_DBSCAN_CONFIG,
            condition_memberships=cohort.conditions if artifact.name == "patient_fact" else None,
        )
        cluster_path = output_directory / "clusters" / f"{artifact.name}.json"
        _write_json(cluster_path, report)
        projection_path = output_directory / "projections" / f"{artifact.name}.json"
        _write_json(projection_path, build_pca_projection(artifact))

        v2_index = build_exact_faiss_index(artifact)
        verification = verify_exact_neighbors(v2_index)
        if not verification.passed:
            raise ValueError(f"R6 V2 {artifact.name} exact-index verification failed")
        index_path = output_directory / "indexes" / f"{artifact.name}.faiss"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(v2_index.index, str(index_path))
        index_metadata_path = output_directory / "indexes" / f"{artifact.name}.metadata.json"
        _write_json(index_metadata_path, v2_index.metadata)
        verification_path = output_directory / "indexes" / f"{artifact.name}.verification.json"
        _write_json(verification_path, verification)
        overlap_path = output_directory / "comparisons" / f"{artifact.name}.neighbors.json"
        v1_index = build_exact_faiss_index(v1_by_name[artifact.name])
        overlap = _neighbor_overlap(v1_index, v2_index)
        _write_json(overlap_path, overlap)

        source = v1_by_name[artifact.name]
        required_explicit = {
            name
            for name in source.feature_names
            if (
                name.startswith(("age_band:", "sex:", "criterion:"))
                or ":state:" in name
                or name.endswith(("value_missing", "evidence_age_missing"))
            )
        }
        integrity_checks = {
            "member_count": len(artifact.member_ids) == len(cohort.patients),
            "subject_order": artifact.subject_order_checksum == source.subject_order_checksum,
            "cohort_checksum": artifact.cohort_checksum == source.cohort_checksum,
            "reference_panel_checksum": (
                artifact.reference_panel_checksum == source.reference_panel_checksum
            ),
            "criterion_order_checksum": (
                artifact.criterion_order_checksum == source.criterion_order_checksum
            ),
            "explicit_state_features": required_explicit.issubset(artifact.feature_names),
            "finite_processed_values": bool(np.isfinite(artifact.standardized_matrix).all()),
            "l2_normalized": bool(
                np.allclose(np.linalg.norm(artifact.normalized_matrix, axis=1), 1.0, atol=1e-5)
            ),
            "exact_index_verified": verification.passed,
        }

        for suffix, path in {
            "vectors": vectors_path,
            "raw": raw_path,
            "metadata": metadata_path,
            "clusters": cluster_path,
            "projection": projection_path,
            "index": index_path,
            "index_metadata": index_metadata_path,
            "index_verification": verification_path,
            "neighbor_overlap": overlap_path,
        }.items():
            _add_file(files, output_directory, f"{artifact.name}_{suffix}", path)
        summaries[artifact.name] = {
            "version": artifact.version,
            "source_version": artifact.preprocessing.source_version,
            "dimension": len(artifact.feature_names),
            "removed_feature_count": len(artifact.preprocessing.removed_feature_names),
            "feature_order_checksum": artifact.feature_order_checksum,
            "subject_order_checksum": artifact.subject_order_checksum,
            "cluster_count": report.selected.cluster_count,
            "noise_fraction": report.selected.noise_fraction,
            "silhouette": report.selected.silhouette_score,
            "bootstrap_ari": report.selected.stability.bootstrap_adjusted_rand_mean,
            "nearby_parameter_ari": (
                report.selected.stability.nearby_parameter_adjusted_rand_mean
            ),
            "acceptance": _acceptance(report, integrity_checks),
            "condition_composition_review_required": artifact.name == "patient_fact",
            "index_type": v2_index.metadata.index_type,
            "index_verified": verification.passed,
            "neighbor_overlap_with_v1": overlap,
        }

    manifest = {
        "experiment_version": R6_V2_EXPERIMENT_VERSION,
        "status": "ready_for_review",
        "source_run_id": cohort.manifest["run_id"],
        "source_manifest_sha256": hashlib.sha256(
            (cohort.run_directory / "manifest.json").read_bytes()
        ).hexdigest(),
        "source_counts": {
            field: cohort.manifest[field] for field in R6_V2_EXPECTED_COUNTS
        },
        "semantic_checksums": {
            field: cohort.manifest["semantic_checksums"][field]
            for field in R6_V2_EXPECTED_SEMANTIC_CHECKSUMS
        },
        "dbscan_grid": {
            "eps_values": DEFAULT_DBSCAN_CONFIG.eps_values,
            "min_samples_values": DEFAULT_DBSCAN_CONFIG.min_samples_values,
            "stability_repeats": DEFAULT_DBSCAN_CONFIG.stability_repeats,
            "sample_fraction": DEFAULT_DBSCAN_CONFIG.sample_fraction,
        },
        "representations": summaries,
        "files": files,
        "completed_at": datetime.now(UTC).isoformat(),
        "activation_changed": False,
    }
    _write_json(output_directory / "manifest.json", manifest)
    return manifest


def run_experiment(
    run_directory: Path,
    *,
    enforce_frozen_source: bool = True,
) -> dict[str, Any]:
    """Write V2 atomically beneath the accepted run and never mutate the V1 manifest."""

    cohort = load_materialized_cohort(run_directory)
    if enforce_frozen_source:
        _validate_frozen_source(cohort)
    target = cohort.run_directory / "experiments" / "v2"
    if target.exists():
        raise FileExistsError("R6 V2 has already been executed for this run")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".v2-building-", dir=target.parent) as temporary:
        staging = Path(temporary)
        manifest = _write_experiment(cohort, build_v2_representations(cohort), staging)
        staging.replace(target)
    return {
        "source_run_id": cohort.manifest["run_id"],
        "experiment_directory": str(target),
        "manifest": manifest,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen one-shot R6 V2 comparison.")
    parser.add_argument("--run-directory", type=Path, required=True)
    args = parser.parse_args()
    result = run_experiment(args.run_directory)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
