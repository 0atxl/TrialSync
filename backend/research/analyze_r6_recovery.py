"""Run and seal label-free analysis for the R6 controlled-recovery benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import fmean
from typing import Any

import numpy as np

from research.analyze_r6_cohort import (
    LoadedR6Cohort,
    build_representations,
    load_materialized_cohort,
)
from research.run_r6_v2_experiment import build_v2_representations
from research.schemas.r6_recovery import (
    ANALYSIS_DIRECTORY,
    BENCHMARK_REPRESENTATIONS,
    COHORT_DIRECTORY,
    validate_label_free_payload,
)
from trialsync.research.cohort_profiles import RepresentationArtifact
from trialsync.research.cohorts import build_pca_projection
from trialsync.research.similarity import (
    build_exact_faiss_index,
    query_neighbors,
    verify_exact_neighbors,
)

_ANALYSIS_VERSION = "r6-controlled-recovery-analysis-v1"
_RECOVERY_CONTRACT_VERSION = "r6-controlled-recovery-v1"
_MIN_SAMPLES_VALUES = (5, 10, 15, 20)
_EPS_QUANTILES = (0.50, 0.65, 0.80, 0.90, 0.95)
_STABILITY_REPEATS = 5
_SAMPLE_FRACTION = 0.8
_RANDOM_STATE = 20260816
_REPRESENTATION_VERSIONS = {
    "patient_fact_v1": "r6.recovery.patient_fact.v1",
    "patient_fact_v2": "r6.recovery.patient_fact.v2",
    "screening_profile_v1": "r6.recovery.screening_profile.v1",
    "screening_profile_v2": "r6.recovery.screening_profile.v2",
}


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
    serializable = _jsonable(value)
    validate_label_free_payload(serializable, location=path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(serializable, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _add_file(files: dict[str, dict[str, object]], root: Path, name: str, path: Path) -> None:
    files[name] = {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _load_source(cohort_directory: Path) -> LoadedR6Cohort:
    cohort_directory = cohort_directory.resolve()
    if cohort_directory.name != COHORT_DIRECTORY:
        raise ValueError("controlled-recovery analysis requires the cohort directory")
    cohort = load_materialized_cohort(
        cohort_directory, expected_run_id=cohort_directory.parent.name
    )
    if cohort.manifest.get("recovery_contract_version") != _RECOVERY_CONTRACT_VERSION:
        raise ValueError("unsupported controlled-recovery cohort contract")
    return cohort


def build_recovery_representations(
    cohort: LoadedR6Cohort,
) -> dict[str, RepresentationArtifact]:
    """Build unchanged V1/V2 transforms and apply benchmark wrapper versions."""

    fact_v1, screening_v1 = build_representations(cohort)
    fact_v2, screening_v2 = build_v2_representations(cohort)
    source = {
        "patient_fact_v1": fact_v1,
        "patient_fact_v2": fact_v2,
        "screening_profile_v1": screening_v1,
        "screening_profile_v2": screening_v2,
    }
    return {
        name: replace(artifact, version=_REPRESENTATION_VERSIONS[name])
        for name, artifact in source.items()
    }


def _distance_matrix(vectors: np.ndarray) -> np.ndarray:
    similarities = np.clip(vectors @ vectors.T, -1.0, 1.0)
    distances = np.sqrt(np.maximum(0.0, 2.0 - 2.0 * similarities))
    np.fill_diagonal(distances, np.inf)
    return np.asarray(distances, dtype=np.float32)


def _adaptive_grid(vectors: np.ndarray) -> tuple[list[dict[str, Any]], list[tuple[float, int]]]:
    if len(vectors) <= max(_MIN_SAMPLES_VALUES):
        raise ValueError("controlled-recovery analysis requires more than 20 members")
    distances = _distance_matrix(vectors)
    grid: list[dict[str, Any]] = []
    pairs: list[tuple[float, int]] = []
    observed: set[tuple[float, int]] = set()
    for min_samples in _MIN_SAMPLES_VALUES:
        # DBSCAN counts the member itself, so this is the (min_samples - 1)-th other member.
        neighbor_distances = np.partition(distances, min_samples - 2, axis=1)[:, min_samples - 2]
        quantile_records: list[dict[str, object]] = []
        for quantile in _EPS_QUANTILES:
            eps = round(float(np.quantile(neighbor_distances, quantile)), 6)
            pair = (eps, min_samples)
            duplicate = pair in observed
            quantile_records.append({"quantile": quantile, "eps": eps, "duplicate_pair": duplicate})
            if not duplicate:
                observed.add(pair)
                pairs.append(pair)
        grid.append(
            {
                "min_samples": min_samples,
                "other_neighbor_rank": min_samples - 1,
                "distance_min": float(np.min(neighbor_distances)),
                "distance_max": float(np.max(neighbor_distances)),
                "quantiles": quantile_records,
            }
        )
    return grid, pairs


def _fit_dbscan(vectors: np.ndarray, eps: float, min_samples: int) -> tuple[np.ndarray, int]:
    from sklearn.cluster import DBSCAN

    model = DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean").fit(vectors)
    return np.asarray(model.labels_, dtype=np.int64), len(model.core_sample_indices_)


def _partition_metrics(
    vectors: np.ndarray, labels: np.ndarray
) -> tuple[int, list[list[int]], float, float | None, float, float]:
    from sklearn.metrics import silhouette_score

    label_counts = Counter(int(value) for value in labels if value >= 0)
    cluster_sizes = [[label, label_counts[label]] for label in sorted(label_counts)]
    assigned = sum(label_counts.values())
    cluster_count = len(label_counts)
    noise_fraction = float(np.mean(labels == -1))
    smallest = min(label_counts.values(), default=0) / assigned if assigned else 0.0
    largest = max(label_counts.values(), default=0) / assigned if assigned else 0.0
    non_noise = labels >= 0
    non_noise_labels = labels[non_noise]
    silhouette = (
        float(silhouette_score(vectors[non_noise], non_noise_labels, metric="euclidean"))
        if cluster_count >= 2 and int(non_noise.sum()) > cluster_count
        else None
    )
    return cluster_count, cluster_sizes, noise_fraction, silhouette, smallest, largest


def _stability(
    vectors: np.ndarray, labels: np.ndarray, eps: float, min_samples: int
) -> dict[str, Any]:
    from sklearn.metrics import adjusted_rand_score

    sample_size = max(2, round(len(vectors) * _SAMPLE_FRACTION))
    bootstrap: list[float] = []
    for offset in range(_STABILITY_REPEATS):
        rng = np.random.default_rng(_RANDOM_STATE + offset)
        indices = np.sort(rng.choice(len(vectors), size=sample_size, replace=False))
        sampled, _core = _fit_dbscan(vectors[indices], eps, min_samples)
        bootstrap.append(float(adjusted_rand_score(labels[indices], sampled)))
    nearby: list[dict[str, Any]] = []
    parameters = (
        (round(eps * 0.95, 12), min_samples),
        (round(eps * 1.05, 12), min_samples),
        (eps, max(2, min_samples - 1)),
        (eps, min_samples + 1),
    )
    for nearby_eps, nearby_min_samples in parameters:
        nearby_labels, _core = _fit_dbscan(vectors, nearby_eps, nearby_min_samples)
        nearby.append(
            {
                "eps": nearby_eps,
                "min_samples": nearby_min_samples,
                "adjusted_rand": float(adjusted_rand_score(labels, nearby_labels)),
            }
        )
    return {
        "subsample_fraction": _SAMPLE_FRACTION,
        "subsample_values": bootstrap,
        "subsample_adjusted_rand_mean": fmean(bootstrap),
        "nearby_values": nearby,
        "nearby_adjusted_rand_mean": fmean(float(item["adjusted_rand"]) for item in nearby),
    }


def _condition_composition(
    member_ids: tuple[str, ...], labels: Sequence[int], conditions: dict[str, frozenset[str]]
) -> list[dict[str, Any]]:
    concepts = sorted({concept for values in conditions.values() for concept in values})
    records: list[dict[str, Any]] = []
    for label in sorted(set(labels).difference({-1})):
        members = [
            member_id for member_id, found in zip(member_ids, labels, strict=True) if found == label
        ]
        for concept in concepts:
            cohort_prevalence = sum(
                concept in conditions.get(member, frozenset()) for member in member_ids
            ) / len(member_ids)
            cluster_prevalence = sum(
                concept in conditions.get(member, frozenset()) for member in members
            ) / len(members)
            records.append(
                {
                    "cluster_label": label,
                    "condition": concept,
                    "cluster_member_count": len(members),
                    "condition_member_count": sum(
                        concept in conditions.get(member, frozenset()) for member in members
                    ),
                    "cluster_prevalence": cluster_prevalence,
                    "cohort_prevalence": cohort_prevalence,
                    "prevalence_lift": (
                        cluster_prevalence / cohort_prevalence if cohort_prevalence else None
                    ),
                }
            )
    return records


def _candidate_rank(candidate: dict[str, Any]) -> tuple[float, float, float, float, float, int]:
    stability = candidate["stability"]
    if not isinstance(stability, dict):
        raise TypeError("controlled-recovery stability record is invalid")
    silhouette = candidate["silhouette"]
    return (
        float(stability["subsample_adjusted_rand_mean"]),
        float(stability["nearby_adjusted_rand_mean"]),
        float(silhouette) if silhouette is not None else -1.0,
        -float(candidate["noise_fraction"]),
        -float(candidate["eps"]),
        -int(candidate["min_samples"]),
    )


def _run_adaptive_dbscan(
    artifact: RepresentationArtifact, conditions: dict[str, frozenset[str]] | None
) -> dict[str, Any]:
    vectors = artifact.normalized_matrix.astype(np.float32, copy=False)
    grid, pairs = _adaptive_grid(vectors)
    candidates: list[dict[str, Any]] = []
    for eps, min_samples in pairs:
        labels, core_count = _fit_dbscan(vectors, eps, min_samples)
        cluster_count, sizes, noise, silhouette, smallest, largest = _partition_metrics(
            vectors, labels
        )
        candidates.append(
            {
                "eps": eps,
                "min_samples": min_samples,
                "labels": labels.tolist(),
                "cluster_count": cluster_count,
                "cluster_sizes": sizes,
                "core_member_count": core_count,
                "noise_fraction": noise,
                "silhouette": silhouette,
                "smallest_assigned_cluster_fraction": smallest,
                "largest_assigned_cluster_fraction": largest,
                "stability": _stability(vectors, labels, eps, min_samples),
            }
        )
    eligible = [
        candidate
        for candidate in candidates
        if 3 <= int(candidate["cluster_count"]) <= 5
        and 0.05 <= float(candidate["noise_fraction"]) <= 0.35
        and float(candidate["smallest_assigned_cluster_fraction"]) >= 0.05
        and float(candidate["largest_assigned_cluster_fraction"]) <= 0.50
    ]
    selected = max(eligible, key=_candidate_rank) if eligible else None
    report: dict[str, Any] = {
        "representation_version": artifact.version,
        "cohort_checksum": artifact.cohort_checksum,
        "feature_order_checksum": artifact.feature_order_checksum,
        "subject_order_checksum": artifact.subject_order_checksum,
        "member_ids": artifact.member_ids,
        "grid_protocol": {
            "min_samples_values": _MIN_SAMPLES_VALUES,
            "eps_quantiles": _EPS_QUANTILES,
            "round_digits": 6,
            "evaluated_pair_count": len(pairs),
            "duplicate_pair_count": 20 - len(pairs),
            "distance_grid": grid,
        },
        "structural_filter": {
            "minimum_clusters": 3,
            "maximum_clusters": 5,
            "minimum_noise_fraction": 0.05,
            "maximum_noise_fraction": 0.35,
            "minimum_smallest_assigned_cluster_fraction": 0.05,
            "maximum_largest_assigned_cluster_fraction": 0.50,
        },
        "candidates": candidates,
        "selected_candidate": selected,
        "selection_status": "selected" if selected is not None else "no_structural_candidate",
        "selection_reason": (
            "Ranked structurally eligible candidates by subsample stability, nearby-parameter "
            "stability, silhouette, lower noise, smaller radius, and smaller min_samples."
            if selected is not None
            else "No candidate passed the frozen label-free structural filter."
        ),
    }
    if selected is not None and conditions is not None:
        report["condition_composition"] = _condition_composition(
            artifact.member_ids,
            [int(value) for value in selected["labels"]],
            conditions,
        )
    else:
        report["condition_composition"] = []
    return report


def _run_kmeans(artifact: RepresentationArtifact) -> dict[str, Any]:
    from sklearn.cluster import KMeans
    from sklearn.metrics import davies_bouldin_score, silhouette_score

    vectors = artifact.normalized_matrix.astype(np.float32, copy=False)
    candidates: list[dict[str, Any]] = []
    for cluster_count in range(2, min(6, len(vectors) - 1) + 1):
        labels = np.asarray(
            KMeans(
                n_clusters=cluster_count,
                random_state=_RANDOM_STATE,
                n_init=20,
            ).fit_predict(vectors),
            dtype=np.int64,
        )
        actual_count = len(set(int(value) for value in labels))
        sizes = Counter(int(value) for value in labels)
        candidates.append(
            {
                "k": cluster_count,
                "actual_cluster_count": actual_count,
                "labels": labels.tolist(),
                "cluster_sizes": [[label, sizes[label]] for label in sorted(sizes)],
                "silhouette": (
                    float(silhouette_score(vectors, labels, metric="euclidean"))
                    if actual_count >= 2
                    else None
                ),
                "davies_bouldin": (
                    float(davies_bouldin_score(vectors, labels)) if actual_count >= 2 else None
                ),
            }
        )
    return {
        "representation_version": artifact.version,
        "random_state": _RANDOM_STATE,
        "n_init": 20,
        "non_activating": True,
        "candidates": candidates,
    }


def _neighbors(index: Any, *, neighbor_count: int = 10) -> dict[str, Any]:
    return {
        "neighbor_count": min(neighbor_count, len(index.member_ids) - 1),
        "members": [
            {
                "member_id": member_id,
                "neighbors": [
                    {"member_id": item.member_id, "cosine_similarity": item.cosine_similarity}
                    for item in query_neighbors(index, member_id, neighbor_count).neighbors
                ],
            }
            for member_id in index.member_ids
        ],
    }


def _write_analysis(
    cohort: LoadedR6Cohort,
    representations: dict[str, RepresentationArtifact],
    output_directory: Path,
) -> dict[str, Any]:
    import faiss

    files: dict[str, dict[str, object]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    members_path = output_directory / "members.json"
    _write_json(
        members_path,
        [
            {"member_id": patient.member_id, "label": cohort.labels[patient.member_id]}
            for patient in cohort.patients
        ],
    )
    _add_file(files, output_directory, "members", members_path)
    for name in BENCHMARK_REPRESENTATIONS:
        artifact = representations[name]
        representation_directory = output_directory / "representations" / name
        raw_path = representation_directory / "raw.npy"
        vectors_path = representation_directory / "vectors.npy"
        metadata_path = representation_directory / "metadata.json"
        representation_directory.mkdir(parents=True, exist_ok=True)
        np.save(raw_path, artifact.raw_matrix, allow_pickle=False)
        np.save(vectors_path, artifact.normalized_matrix, allow_pickle=False)
        metadata = {
            "benchmark_name": name,
            "representation": artifact.name,
            "version": artifact.version,
            "source_feature_version": (
                "r6.patient_fact.v1"
                if name == "patient_fact_v1"
                else "r6.patient_fact.v2"
                if name == "patient_fact_v2"
                else "r6.screening_profile.v1"
                if name == "screening_profile_v1"
                else "r6.screening_profile.v2"
            ),
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
        }
        _write_json(metadata_path, metadata)
        cluster_report = _run_adaptive_dbscan(
            artifact, cohort.conditions if artifact.name == "patient_fact" else None
        )
        cluster_path = output_directory / "clusters" / f"{name}.json"
        _write_json(cluster_path, cluster_report)
        kmeans_path = output_directory / "kmeans" / f"{name}.json"
        _write_json(kmeans_path, _run_kmeans(artifact))
        projection_path = output_directory / "projections" / f"{name}.json"
        _write_json(projection_path, build_pca_projection(artifact))

        exact_index = build_exact_faiss_index(artifact)
        verification = verify_exact_neighbors(exact_index, neighbor_count=10)
        if not verification.passed or verification.checked_member_count != len(artifact.member_ids):
            raise ValueError(f"controlled-recovery exact-index verification failed: {name}")
        index_path = output_directory / "indexes" / f"{name}.faiss"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(exact_index.index, str(index_path))
        index_metadata_path = output_directory / "indexes" / f"{name}.metadata.json"
        _write_json(index_metadata_path, exact_index.metadata)
        verification_path = output_directory / "indexes" / f"{name}.verification.json"
        _write_json(verification_path, verification)
        neighbors_path = output_directory / "neighbors" / f"{name}.json"
        _write_json(neighbors_path, _neighbors(exact_index))

        paths = {
            "raw": raw_path,
            "vectors": vectors_path,
            "metadata": metadata_path,
            "clusters": cluster_path,
            "kmeans": kmeans_path,
            "projection": projection_path,
            "index": index_path,
            "index_metadata": index_metadata_path,
            "index_verification": verification_path,
            "neighbors": neighbors_path,
        }
        for suffix, path in paths.items():
            _add_file(files, output_directory, f"{name}_{suffix}", path)
        selected = cluster_report["selected_candidate"]
        summaries[name] = {
            "version": artifact.version,
            "source_feature_version": metadata["source_feature_version"],
            "dimension": len(artifact.feature_names),
            "member_count": len(artifact.member_ids),
            "feature_order_checksum": artifact.feature_order_checksum,
            "subject_order_checksum": artifact.subject_order_checksum,
            "selected_dbscan": (
                {
                    key: selected[key]
                    for key in (
                        "eps",
                        "min_samples",
                        "cluster_count",
                        "noise_fraction",
                        "silhouette",
                        "smallest_assigned_cluster_fraction",
                        "largest_assigned_cluster_fraction",
                    )
                }
                if isinstance(selected, dict)
                else None
            ),
            "exact_index_type": exact_index.metadata.index_type,
            "exact_index_verified": verification.passed,
            "verified_member_count": verification.checked_member_count,
        }
    cohort_manifest_path = cohort.run_directory / "manifest.json"
    integrity_checks = {
        "member_count": all(
            len(artifact.member_ids) == len(cohort.patients)
            for artifact in representations.values()
        ),
        "unique_members": all(
            len(set(artifact.member_ids)) == len(artifact.member_ids)
            for artifact in representations.values()
        ),
        "shared_subject_order": len(
            {artifact.subject_order_checksum for artifact in representations.values()}
        )
        == 1,
        "finite_processed_values": all(
            np.isfinite(artifact.standardized_matrix).all() for artifact in representations.values()
        ),
        "l2_normalized": all(
            np.allclose(np.linalg.norm(artifact.normalized_matrix, axis=1), 1.0, atol=1e-5)
            for artifact in representations.values()
        ),
        "all_exact_indexes_verified": all(
            bool(summary["exact_index_verified"]) for summary in summaries.values()
        ),
        "explicit_missing_unknown_states": all(
            (
                any(":state:unknown" in name for name in artifact.feature_names)
                and any(
                    ":state:missing" in name or name.endswith(":value_missing")
                    for name in artifact.feature_names
                )
                if artifact.name == "patient_fact"
                else any(name.endswith(":result:unknown") for name in artifact.feature_names)
            )
            for artifact in representations.values()
        ),
        "label_free_analysis": True,
    }
    manifest: dict[str, Any] = {
        "run_id": str(cohort.manifest["run_id"]),
        "analysis_version": _ANALYSIS_VERSION,
        "status": "sealed_ready_for_evaluation",
        "completed_at": datetime.now(UTC).isoformat(),
        "source_cohort_manifest_sha256": hashlib.sha256(
            cohort_manifest_path.read_bytes()
        ).hexdigest(),
        "source_semantic_checksums": {
            key: cohort.manifest["semantic_checksums"][key]
            for key in ("cohort", "reference_panel", "criterion_order")
        },
        "representations": summaries,
        "analysis_protocol": {
            "dbscan_grid": {
                "min_samples_values": _MIN_SAMPLES_VALUES,
                "eps_quantiles": _EPS_QUANTILES,
                "stability_repeats": _STABILITY_REPEATS,
                "sample_fraction": _SAMPLE_FRACTION,
            },
            "kmeans": {"k_values": [2, 3, 4, 5, 6], "random_state": _RANDOM_STATE, "n_init": 20},
            "neighbor_count": 10,
        },
        "integrity_checks": integrity_checks,
        "activation_changed": False,
        "files": files,
    }
    if not all(integrity_checks.values()):
        raise ValueError("controlled-recovery analysis integrity check failed")
    _write_json(output_directory / "manifest.json", manifest)
    return manifest


def run_analysis(cohort_directory: Path) -> dict[str, object]:
    """Atomically seal one label-free analysis; the source cohort remains unchanged."""

    cohort_directory = cohort_directory.resolve()
    run_directory = cohort_directory.parent
    cohort = _load_source(cohort_directory)
    target = run_directory / ANALYSIS_DIRECTORY
    if target.exists():
        raise FileExistsError("controlled-recovery analysis already exists")
    source_manifest_before = (cohort.run_directory / "manifest.json").read_bytes()
    with tempfile.TemporaryDirectory(prefix=".analysis-building-", dir=run_directory) as temporary:
        staging = Path(temporary)
        manifest = _write_analysis(cohort, build_recovery_representations(cohort), staging)
        staging.replace(target)
    if (cohort.run_directory / "manifest.json").read_bytes() != source_manifest_before:
        raise RuntimeError("controlled-recovery analysis altered its source manifest")
    analysis_seal = hashlib.sha256((target / "manifest.json").read_bytes()).hexdigest()
    return {
        "run_id": str(cohort.manifest["run_id"]),
        "analysis_directory": str(target),
        "analysis_manifest_sha256": analysis_seal,
        "manifest": manifest,
        "next_command": (
            "backend/.venv/bin/python -m research.evaluate_r6_recovery "
            f"--run-directory {run_directory}"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze and seal one R6 controlled-recovery cohort."
    )
    parser.add_argument("--cohort-directory", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_analysis(args.cohort_directory), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
