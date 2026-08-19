"""Evaluate a sealed R6 V3 run after label-free analysis is complete."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

import numpy as np

from research.configs.r6_v3 import V3_BACKGROUND_GROUP, V3_CONTRACT_VERSION
from research.schemas.r6_dataset import MANIFEST_FILENAME, canonical_json, semantic_checksum
from research.schemas.r6_v3 import (
    EVALUATION_DIRECTORY,
    EVALUATION_MANIFEST_FILENAME,
    EVALUATION_REPORT_FILENAME,
    PRIVATE_DIRECTORY,
    PRIVATE_MANIFEST_FILENAME,
    V3_ANSWER_KEY_VERSION,
    V3_EVALUATION_VERSION,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"R6 V3 object is not a mapping: {path.name}")
    return value


def _write_object(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{canonical_json(value)}\n", encoding="utf-8", newline="\n")


def _validated_file(root: Path, record: object) -> Path:
    if not isinstance(record, dict):
        raise ValueError("R6 V3 file record is malformed")
    relative = Path(str(record.get("path", "")))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("R6 V3 file record contains an unsafe path")
    resolved_root = root.resolve()
    unresolved = resolved_root / relative
    path = unresolved.resolve(strict=True)
    if unresolved.is_symlink() or not path.is_relative_to(resolved_root) or not path.is_file():
        raise ValueError("R6 V3 file escapes its sealed directory")
    if _sha256(path) != record.get("sha256"):
        raise ValueError(f"R6 V3 file checksum mismatch: {relative}")
    return path


def _load_inputs(
    run_directory: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str], dict[str, Path]]:
    run_directory = run_directory.resolve()
    public_manifest_path = run_directory / MANIFEST_FILENAME
    public_manifest = _read_object(public_manifest_path)
    if public_manifest.get("run_id") != run_directory.name:
        raise ValueError("R6 V3 run identifier does not match its directory")
    if public_manifest.get("contract_version") != V3_CONTRACT_VERSION:
        raise ValueError("R6 V3 public contract version mismatch")
    if public_manifest.get("analysis_status") != "ready":
        raise ValueError("R6 V3 analysis must be complete before evaluation")

    public_records = public_manifest.get("files")
    if not isinstance(public_records, dict):
        raise ValueError("R6 V3 public manifest has no file table")
    required = {
        "generation_config",
        "members",
        "patient_fact_clusters",
        "screening_profile_clusters",
        "patient_fact_vectors",
        "screening_profile_vectors",
        "patient_fact_representation_metadata",
        "screening_profile_representation_metadata",
        "patient_fact_index_verification",
        "screening_profile_index_verification",
    }
    if not required.issubset(public_records):
        raise ValueError("R6 V3 public manifest is missing evaluation inputs")
    public_paths = {
        name: _validated_file(run_directory, public_records[name]) for name in required
    }

    private_directory = run_directory / PRIVATE_DIRECTORY
    private_manifest_path = private_directory / PRIVATE_MANIFEST_FILENAME
    private_manifest = _read_object(private_manifest_path)
    if _sha256(private_manifest_path) != public_manifest.get("answer_key_manifest_sha256"):
        raise ValueError("R6 V3 private-manifest seal mismatch")
    if (
        private_manifest.get("run_id") != run_directory.name
        or private_manifest.get("contract_version") != V3_ANSWER_KEY_VERSION
        or private_manifest.get("cohort_semantic_checksum")
        != public_manifest.get("semantic_checksums", {}).get("cohort")
    ):
        raise ValueError("R6 V3 private answer key belongs to a different run")
    private_records = private_manifest.get("files")
    if not isinstance(private_records, dict) or "answer_key" not in private_records:
        raise ValueError("R6 V3 private manifest has no answer key")
    answer_key_path = _validated_file(private_directory, private_records["answer_key"])
    answer_key = _read_object(answer_key_path)
    if answer_key.get("answer_key_version") != V3_ANSWER_KEY_VERSION:
        raise ValueError("R6 V3 answer-key version mismatch")
    if semantic_checksum(answer_key) != private_manifest.get("answer_key_semantic_checksum"):
        raise ValueError("R6 V3 answer-key semantic checksum mismatch")
    members = answer_key.get("members")
    if not isinstance(members, list) or len(members) != public_manifest.get("patient_count"):
        raise ValueError("R6 V3 answer-key member count mismatch")
    groups: dict[str, str] = {}
    for member in members:
        if not isinstance(member, dict):
            raise ValueError("R6 V3 answer-key row is malformed")
        member_id = str(member.get("patient_snapshot_id", ""))
        group = str(member.get("cohort_group", ""))
        if not member_id or not group or member_id in groups:
            raise ValueError("R6 V3 answer-key row is invalid or duplicated")
        groups[member_id] = group
    if dict(sorted(Counter(groups.values()).items())) != private_manifest.get("group_counts"):
        raise ValueError("R6 V3 answer-key group counts mismatch")
    return public_manifest, private_manifest, groups, public_paths


def _cluster_metrics(
    report: dict[str, Any], groups: dict[str, str]
) -> dict[str, Any]:
    from sklearn.metrics import adjusted_rand_score

    member_ids = [str(value) for value in report.get("member_ids", [])]
    selected = report.get("selected")
    if not isinstance(selected, dict):
        raise ValueError("R6 V3 cluster report has no selected result")
    labels = [int(value) for value in selected.get("labels", [])]
    if len(member_ids) != len(labels) or set(member_ids) != set(groups):
        raise ValueError("R6 V3 cluster report member order is invalid")

    assigned: dict[int, list[str]] = defaultdict(list)
    for member_id, label in zip(member_ids, labels, strict=True):
        if label >= 0:
            assigned[label].append(groups[member_id])
    assigned_count = sum(len(values) for values in assigned.values())
    majority_by_cluster = {
        label: Counter(values).most_common(1)[0][0] for label, values in assigned.items()
    }
    correct_count = sum(
        max(Counter(values).values()) for values in assigned.values()
    )
    cluster_purities = [
        max(Counter(values).values()) / len(values) for values in assigned.values()
    ]
    per_group: dict[str, dict[str, float | int]] = {}
    for group in sorted(set(groups.values())):
        indices = [
            index
            for index, member_id in enumerate(member_ids)
            if groups[member_id] == group
        ]
        group_assigned = sum(labels[index] >= 0 for index in indices)
        group_correct = sum(
            labels[index] >= 0 and majority_by_cluster[labels[index]] == group
            for index in indices
        )
        per_group[group] = {
            "member_count": len(indices),
            "assigned_count": group_assigned,
            "assignment_recall": group_assigned / len(indices),
            "majority_aligned_recall": group_correct / len(indices),
            "noise_count": len(indices) - group_assigned,
        }
    background_indices = [
        index
        for index, member_id in enumerate(member_ids)
        if groups[member_id] == V3_BACKGROUND_GROUP
    ]
    background_noise_recall = (
        sum(labels[index] == -1 for index in background_indices) / len(background_indices)
        if background_indices
        else None
    )
    stability = selected.get("stability", {})
    return {
        "selected_parameters": {
            "eps": float(selected["eps"]),
            "min_samples": int(selected["min_samples"]),
        },
        "cluster_count": int(selected["cluster_count"]),
        "noise_fraction": float(selected["noise_fraction"]),
        "silhouette": selected.get("silhouette_score"),
        "bootstrap_adjusted_rand": stability.get("bootstrap_adjusted_rand_mean"),
        "nearby_parameter_adjusted_rand": stability.get(
            "nearby_parameter_adjusted_rand_mean"
        ),
        "assigned_member_count": assigned_count,
        "assignment_coverage": assigned_count / len(member_ids),
        "weighted_cluster_purity": correct_count / assigned_count if assigned_count else None,
        "macro_cluster_purity": fmean(cluster_purities) if cluster_purities else None,
        "all_member_adjusted_rand": float(
            adjusted_rand_score([groups[item] for item in member_ids], labels)
        ),
        "background_noise_recall": background_noise_recall,
        "per_group": per_group,
    }


def _neighbor_metrics(
    vectors_path: Path,
    metadata_path: Path,
    groups: dict[str, str],
    *,
    neighbor_count: int = 10,
) -> dict[str, Any]:
    metadata = _read_object(metadata_path)
    member_ids = [str(value) for value in metadata.get("member_ids", [])]
    vectors = np.load(vectors_path, allow_pickle=False)
    if vectors.shape[0] != len(member_ids) or set(member_ids) != set(groups):
        raise ValueError("R6 V3 vector member order is invalid")
    scores = np.asarray(vectors @ vectors.T, dtype=np.float64)
    precisions: list[float] = []
    top_one: list[float] = []
    by_group: dict[str, list[float]] = defaultdict(list)
    baselines: list[float] = []
    for index, member_id in enumerate(member_ids):
        ordered = sorted(
            (candidate for candidate in range(len(member_ids)) if candidate != index),
            key=lambda candidate: (-float(scores[index, candidate]), member_ids[candidate]),
        )[:neighbor_count]
        precision = sum(groups[member_ids[item]] == groups[member_id] for item in ordered) / len(
            ordered
        )
        precisions.append(precision)
        by_group[groups[member_id]].append(precision)
        top_one.append(float(groups[member_ids[ordered[0]]] == groups[member_id]))
        group_size = sum(value == groups[member_id] for value in groups.values())
        baselines.append((group_size - 1) / (len(member_ids) - 1))
    structured_groups = [group for group in sorted(by_group) if group != V3_BACKGROUND_GROUP]
    structured_values = [
        value
        for group in structured_groups
        for value in by_group[group]
    ]
    structured_baseline = fmean(
        baselines[index]
        for index, member_id in enumerate(member_ids)
        if groups[member_id] != V3_BACKGROUND_GROUP
    )
    structured_precision = fmean(structured_values)
    return {
        "neighbor_count": neighbor_count,
        "all_member_precision": fmean(precisions),
        "structured_member_precision": structured_precision,
        "structured_macro_precision": fmean(
            fmean(by_group[group]) for group in structured_groups
        ),
        "top_one_same_group_rate": fmean(top_one),
        "structured_lift_over_size_weighted_baseline": (
            structured_precision / structured_baseline if structured_baseline else None
        ),
        "per_group_precision": {
            group: fmean(values) for group, values in sorted(by_group.items())
        },
    }


def evaluate_run(run_directory: Path) -> dict[str, Any]:
    """Validate all seals and write one private post-analysis evaluation."""

    public_manifest, private_manifest, groups, paths = _load_inputs(run_directory)
    reports = {
        representation: _read_object(paths[f"{representation}_clusters"])
        for representation in ("patient_fact", "screening_profile")
    }
    verification = {
        representation: _read_object(paths[f"{representation}_index_verification"])
        for representation in ("patient_fact", "screening_profile")
    }
    representations: dict[str, Any] = {}
    for representation in ("patient_fact", "screening_profile"):
        exact_verified = verification[representation].get("passed") is True
        if not exact_verified:
            raise ValueError(f"R6 V3 {representation} exact-index verification failed")
        representations[representation] = {
            "dbscan": _cluster_metrics(reports[representation], groups),
            "similarity": _neighbor_metrics(
                paths[f"{representation}_vectors"],
                paths[f"{representation}_representation_metadata"],
                groups,
            ),
            "exact_index_verified": exact_verified,
        }

    report: dict[str, Any] = {
        "run_id": public_manifest["run_id"],
        "evaluation_version": V3_EVALUATION_VERSION,
        "status": "verified_for_review",
        "interpretation": {
            "population_design": "controlled_correlated_groups",
            "cluster_labels_are_diagnostic": False,
            "screening_groups_are_eligibility_evidence_profiles": True,
            "similarity_is_screening_evidence": False,
        },
        "source_seals": {
            "public_manifest_sha256": _sha256(run_directory / MANIFEST_FILENAME),
            "private_manifest_sha256": _sha256(
                run_directory / PRIVATE_DIRECTORY / PRIVATE_MANIFEST_FILENAME
            ),
            "cohort_semantic_checksum": public_manifest["semantic_checksums"]["cohort"],
            "answer_key_semantic_checksum": private_manifest[
                "answer_key_semantic_checksum"
            ],
        },
        "representations": representations,
    }
    evaluation_directory = run_directory / EVALUATION_DIRECTORY
    if evaluation_directory.exists():
        raise FileExistsError(f"R6 V3 evaluation already exists: {evaluation_directory}")
    evaluation_directory.mkdir()
    report_path = evaluation_directory / EVALUATION_REPORT_FILENAME
    _write_object(report_path, report)
    evaluation_manifest = {
        "run_id": public_manifest["run_id"],
        "evaluation_version": V3_EVALUATION_VERSION,
        "status": "complete",
        "files": {
            "report": {
                "path": EVALUATION_REPORT_FILENAME,
                "sha256": _sha256(report_path),
            }
        },
    }
    _write_object(
        evaluation_directory / EVALUATION_MANIFEST_FILENAME,
        evaluation_manifest,
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate one sealed R6 V3 cohort run.")
    parser.add_argument("--run-directory", type=Path, required=True)
    args = parser.parse_args()
    print(canonical_json(evaluate_run(args.run_directory)))


if __name__ == "__main__":
    main()
