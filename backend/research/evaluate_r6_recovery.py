"""Reveal the sealed key and evaluate an already sealed controlled-recovery analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any, cast

from research.configs.r6_recovery import (
    BACKGROUND_GROUP,
    RECOVERY_ANSWER_KEY_VERSION,
    RECOVERY_EVALUATION_VERSION,
    STRUCTURED_GROUPS,
)
from research.schemas.r6_dataset import MANIFEST_FILENAME, semantic_checksum
from research.schemas.r6_recovery import (
    ANALYSIS_DIRECTORY,
    ANSWER_KEY_DIRECTORY,
    BENCHMARK_REPRESENTATIONS,
    COHORT_DIRECTORY,
    EVALUATION_DIRECTORY,
)

_DBSCAN_THRESHOLDS = {
    "minimum_cluster_count": 3,
    "maximum_cluster_count": 5,
    "minimum_noise_fraction": 0.05,
    "maximum_noise_fraction": 0.30,
    "minimum_smallest_assigned_cluster_fraction": 0.05,
    "maximum_largest_assigned_cluster_fraction": 0.45,
    "minimum_silhouette": 0.10,
    "minimum_subsample_adjusted_rand": 0.70,
    "minimum_nearby_adjusted_rand": 0.70,
    "minimum_all_member_adjusted_rand": 0.60,
    "minimum_structured_member_adjusted_rand": 0.65,
    "minimum_background_noise_f1": 0.50,
}
_FAISS_THRESHOLDS = {
    "minimum_structured_precision_at_10": 0.70,
    "minimum_macro_precision_at_10": 0.60,
    "minimum_lift_over_size_weighted_baseline": 2.5,
}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"controlled-recovery object is not a mapping: {path.name}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validated_files(root: Path, manifest: dict[str, Any]) -> dict[str, Path]:
    records = manifest.get("files")
    if not isinstance(records, dict):
        raise ValueError("controlled-recovery manifest has no file table")
    resolved_root = root.resolve()
    output: dict[str, Path] = {}
    for name, value in records.items():
        if not isinstance(name, str) or not isinstance(value, dict):
            raise ValueError("controlled-recovery file table is malformed")
        relative = Path(str(value.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("controlled-recovery manifest contains an unsafe path")
        unresolved = resolved_root / relative
        path = unresolved.resolve(strict=True)
        if unresolved.is_symlink() or not path.is_relative_to(resolved_root) or not path.is_file():
            raise ValueError("controlled-recovery artifact escapes its sealed directory")
        if _sha256(path) != value.get("sha256"):
            raise ValueError(f"controlled-recovery artifact checksum mismatch: {name}")
        output[name] = path
    return output


def _read_parquet(path: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    return cast(list[dict[str, Any]], pq.read_table(path).to_pylist())  # type: ignore[no-untyped-call]


def _load_sealed_inputs(
    run_directory: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Path],
    list[dict[str, Any]],
]:
    cohort_directory = run_directory / COHORT_DIRECTORY
    answer_directory = run_directory / ANSWER_KEY_DIRECTORY
    analysis_directory = run_directory / ANALYSIS_DIRECTORY
    cohort_manifest = _read_json(cohort_directory / MANIFEST_FILENAME)
    answer_manifest_path = answer_directory / MANIFEST_FILENAME
    analysis_manifest_path = analysis_directory / MANIFEST_FILENAME
    answer_manifest = _read_json(answer_manifest_path)
    analysis_manifest = _read_json(analysis_manifest_path)
    if cohort_manifest.get("run_id") != run_directory.name:
        raise ValueError("controlled-recovery cohort run_id mismatch")
    if answer_manifest.get("run_id") != run_directory.name:
        raise ValueError("controlled-recovery answer-key run_id mismatch")
    if analysis_manifest.get("run_id") != run_directory.name:
        raise ValueError("controlled-recovery analysis run_id mismatch")
    if answer_manifest.get("contract_version") != RECOVERY_ANSWER_KEY_VERSION:
        raise ValueError("controlled-recovery answer-key contract mismatch")
    if cohort_manifest.get("answer_key_manifest_sha256") != _sha256(answer_manifest_path):
        raise ValueError("controlled-recovery answer-key seal mismatch")
    if analysis_manifest.get("source_cohort_manifest_sha256") != _sha256(
        cohort_directory / MANIFEST_FILENAME
    ):
        raise ValueError("controlled-recovery analysis source seal mismatch")
    if answer_manifest.get("cohort_semantic_checksum") != cohort_manifest.get(
        "semantic_checksums", {}
    ).get("cohort"):
        raise ValueError("controlled-recovery answer key belongs to a different cohort")
    _validated_files(cohort_directory, cohort_manifest)
    answer_files = _validated_files(answer_directory, answer_manifest)
    analysis_files = _validated_files(analysis_directory, analysis_manifest)
    answer_rows = _read_parquet(answer_files["answer_key"])
    expected_columns = {
        "patient_snapshot_id",
        "latent_group_id",
        "is_background",
        "answer_key_version",
    }
    if any(set(row) != expected_columns for row in answer_rows):
        raise ValueError("controlled-recovery answer-key schema mismatch")
    if semantic_checksum(answer_rows) != answer_manifest.get("semantic_checksums", {}).get(
        "answer_key"
    ):
        raise ValueError("controlled-recovery answer-key semantic checksum mismatch")
    if len(answer_rows) != cohort_manifest.get("patient_count"):
        raise ValueError("controlled-recovery answer-key count mismatch")
    if cohort_manifest.get("patient_count") == 750:
        expected_counts = {
            "latent_group_01": 210,
            "latent_group_02": 180,
            "latent_group_03": 150,
            "latent_group_04": 120,
            "background": 90,
        }
        if (
            cohort_manifest.get("seed") != 60817
            or cohort_manifest.get("trial_count") != 20
            or cohort_manifest.get("pair_count") != 15_000
            or cohort_manifest.get("criterion_result_count") != 60_000
            or answer_manifest.get("group_counts") != expected_counts
        ):
            raise ValueError("controlled-recovery full-run contract mismatch")
    member_ids = [str(row["patient_snapshot_id"]) for row in answer_rows]
    if len(set(member_ids)) != len(member_ids):
        raise ValueError("controlled-recovery answer key contains duplicate members")
    if any(
        row["answer_key_version"] != RECOVERY_ANSWER_KEY_VERSION
        or bool(row["is_background"]) != (row["latent_group_id"] == BACKGROUND_GROUP)
        for row in answer_rows
    ):
        raise ValueError("controlled-recovery answer-key row invariant failed")
    return (
        cohort_manifest,
        answer_manifest,
        analysis_manifest,
        analysis_files,
        answer_rows,
    )


def _dbscan_metrics(
    report: dict[str, Any], groups: dict[str, str], background: dict[str, bool]
) -> dict[str, Any]:
    from sklearn.metrics import adjusted_rand_score, f1_score

    selected = report.get("selected_candidate")
    if not isinstance(selected, dict):
        return {
            "selected_candidate_present": False,
            "hidden_metrics": None,
            "checks": {name: False for name in _DBSCAN_THRESHOLDS},
            "passed": False,
        }
    member_ids = tuple(str(value) for value in report["member_ids"])
    labels = [int(value) for value in selected["labels"]]
    if len(member_ids) != len(labels) or set(member_ids) != set(groups):
        raise ValueError("controlled-recovery DBSCAN member order is invalid")
    truth = [groups[member_id] for member_id in member_ids]
    structured_indices = [
        index for index, member_id in enumerate(member_ids) if not background[member_id]
    ]
    all_adjusted_rand = float(adjusted_rand_score(truth, labels))
    structured_adjusted_rand = float(
        adjusted_rand_score(
            [truth[index] for index in structured_indices],
            [labels[index] for index in structured_indices],
        )
    )
    background_noise_f1 = float(
        f1_score(
            [background[member_id] for member_id in member_ids],
            [label == -1 for label in labels],
            zero_division=0.0,
        )
    )
    stability = selected["stability"]
    silhouette = selected.get("silhouette")
    checks = {
        "minimum_cluster_count": (
            int(selected["cluster_count"]) >= _DBSCAN_THRESHOLDS["minimum_cluster_count"]
        ),
        "maximum_cluster_count": (
            int(selected["cluster_count"]) <= _DBSCAN_THRESHOLDS["maximum_cluster_count"]
        ),
        "minimum_noise_fraction": (
            float(selected["noise_fraction"]) >= _DBSCAN_THRESHOLDS["minimum_noise_fraction"]
        ),
        "maximum_noise_fraction": (
            float(selected["noise_fraction"]) <= _DBSCAN_THRESHOLDS["maximum_noise_fraction"]
        ),
        "minimum_smallest_assigned_cluster_fraction": (
            float(selected["smallest_assigned_cluster_fraction"])
            >= _DBSCAN_THRESHOLDS["minimum_smallest_assigned_cluster_fraction"]
        ),
        "maximum_largest_assigned_cluster_fraction": (
            float(selected["largest_assigned_cluster_fraction"])
            <= _DBSCAN_THRESHOLDS["maximum_largest_assigned_cluster_fraction"]
        ),
        "minimum_silhouette": (
            silhouette is not None and float(silhouette) >= _DBSCAN_THRESHOLDS["minimum_silhouette"]
        ),
        "minimum_subsample_adjusted_rand": (
            float(stability["subsample_adjusted_rand_mean"])
            >= _DBSCAN_THRESHOLDS["minimum_subsample_adjusted_rand"]
        ),
        "minimum_nearby_adjusted_rand": (
            float(stability["nearby_adjusted_rand_mean"])
            >= _DBSCAN_THRESHOLDS["minimum_nearby_adjusted_rand"]
        ),
        "minimum_all_member_adjusted_rand": (
            all_adjusted_rand >= _DBSCAN_THRESHOLDS["minimum_all_member_adjusted_rand"]
        ),
        "minimum_structured_member_adjusted_rand": (
            structured_adjusted_rand
            >= _DBSCAN_THRESHOLDS["minimum_structured_member_adjusted_rand"]
        ),
        "minimum_background_noise_f1": (
            background_noise_f1 >= _DBSCAN_THRESHOLDS["minimum_background_noise_f1"]
        ),
    }
    return {
        "selected_candidate_present": True,
        "selected_parameters": {
            "eps": selected["eps"],
            "min_samples": selected["min_samples"],
        },
        "internal_metrics": {
            key: selected[key]
            for key in (
                "cluster_count",
                "cluster_sizes",
                "noise_fraction",
                "silhouette",
                "smallest_assigned_cluster_fraction",
                "largest_assigned_cluster_fraction",
                "stability",
            )
        },
        "hidden_metrics": {
            "all_member_adjusted_rand": all_adjusted_rand,
            "structured_member_adjusted_rand": structured_adjusted_rand,
            "background_noise_f1": background_noise_f1,
        },
        "thresholds": _DBSCAN_THRESHOLDS,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _entropy(values: list[str]) -> float:
    counts = Counter(values)
    total = len(values)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def _faiss_metrics(
    neighbors: dict[str, Any],
    groups: dict[str, str],
    background: dict[str, bool],
    *,
    exact_index_verified: bool,
) -> dict[str, Any]:
    rows = neighbors.get("members")
    if not isinstance(rows, list) or len(rows) != len(groups):
        raise ValueError("controlled-recovery neighbor table is incomplete")
    expected_count = min(10, len(groups) - 1)
    per_group: dict[str, list[float]] = defaultdict(list)
    structured_precision: list[float] = []
    top1: list[float] = []
    background_entropy: list[float] = []
    background_neighbor_rates: list[float] = []
    seen: set[str] = set()
    for row in rows:
        member_id = str(row["member_id"])
        if member_id not in groups or member_id in seen:
            raise ValueError("controlled-recovery neighbor query member is invalid")
        seen.add(member_id)
        items = row.get("neighbors")
        if not isinstance(items, list) or len(items) != expected_count:
            raise ValueError("controlled-recovery neighbor count is invalid")
        neighbor_ids = [str(item["member_id"]) for item in items]
        if member_id in neighbor_ids or len(set(neighbor_ids)) != len(neighbor_ids):
            raise ValueError("controlled-recovery neighbor table contains self or duplicates")
        if any(neighbor_id not in groups for neighbor_id in neighbor_ids):
            raise ValueError("controlled-recovery neighbor table references an unknown member")
        if background[member_id]:
            neighbor_groups = [groups[neighbor_id] for neighbor_id in neighbor_ids]
            background_entropy.append(_entropy(neighbor_groups))
            background_neighbor_rates.append(
                sum(background[neighbor_id] for neighbor_id in neighbor_ids) / expected_count
            )
            continue
        group = groups[member_id]
        precision = (
            sum(groups[neighbor_id] == group for neighbor_id in neighbor_ids) / expected_count
        )
        structured_precision.append(precision)
        per_group[group].append(precision)
        top1.append(float(groups[neighbor_ids[0]] == group))
    if seen != set(groups):
        raise ValueError("controlled-recovery neighbor table omitted members")
    group_counts = Counter(
        group for member_id, group in groups.items() if not background[member_id]
    )
    structured_count = sum(group_counts.values())
    baseline = sum(
        (count / structured_count) * ((count - 1) / (len(groups) - 1))
        for count in group_counts.values()
    )
    precision_at_10 = fmean(structured_precision)
    group_precision = {
        group: fmean(per_group[group]) if per_group[group] else 0.0 for group in STRUCTURED_GROUPS
    }
    macro_precision = fmean(group_precision.values())
    lift = precision_at_10 / baseline if baseline else None
    checks = {
        "minimum_structured_precision_at_10": (
            precision_at_10 >= _FAISS_THRESHOLDS["minimum_structured_precision_at_10"]
        ),
        "minimum_macro_precision_at_10": (
            macro_precision >= _FAISS_THRESHOLDS["minimum_macro_precision_at_10"]
        ),
        "minimum_lift_over_size_weighted_baseline": (
            lift is not None
            and lift >= _FAISS_THRESHOLDS["minimum_lift_over_size_weighted_baseline"]
        ),
        "exact_index_verified": exact_index_verified,
    }
    return {
        "neighbor_count": expected_count,
        "structured_member_precision_at_10": precision_at_10,
        "macro_group_precision_at_10": macro_precision,
        "group_precision_at_10": group_precision,
        "top_1_same_group_rate": fmean(top1),
        "exact_size_weighted_baseline": baseline,
        "lift_over_size_weighted_baseline": lift,
        "background_mean_neighbor_group_entropy_bits": fmean(background_entropy),
        "background_mean_background_neighbor_rate": fmean(background_neighbor_rates),
        "thresholds": _FAISS_THRESHOLDS,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _kmeans_metrics(
    report: dict[str, Any], groups: dict[str, str], background: dict[str, bool]
) -> dict[str, Any]:
    from sklearn.metrics import adjusted_rand_score

    member_ids = tuple(str(value) for value in report.get("member_ids", ()))
    # Older sealed payloads keep member order in representation metadata, so the caller fills it.
    if not member_ids:
        raise ValueError("controlled-recovery K-means evaluation has no member order")
    truth = [groups[member_id] for member_id in member_ids]
    structured = [index for index, member_id in enumerate(member_ids) if not background[member_id]]
    candidates = []
    for candidate in report["candidates"]:
        labels = [int(value) for value in candidate["labels"]]
        candidates.append(
            {
                "k": candidate["k"],
                "actual_cluster_count": candidate["actual_cluster_count"],
                "silhouette": candidate["silhouette"],
                "davies_bouldin": candidate["davies_bouldin"],
                "all_member_adjusted_rand": float(adjusted_rand_score(truth, labels)),
                "structured_member_adjusted_rand": float(
                    adjusted_rand_score(
                        [truth[index] for index in structured],
                        [labels[index] for index in structured],
                    )
                ),
            }
        )
    return {"non_activating": True, "candidates": candidates}


def _implementation_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and value else "unavailable"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _evaluate(
    run_directory: Path,
    cohort_manifest: dict[str, Any],
    answer_manifest: dict[str, Any],
    analysis_manifest: dict[str, Any],
    analysis_files: dict[str, Path],
    answer_rows: list[dict[str, Any]],
    output_directory: Path,
) -> dict[str, Any]:
    groups = {str(row["patient_snapshot_id"]): str(row["latent_group_id"]) for row in answer_rows}
    background = {
        str(row["patient_snapshot_id"]): bool(row["is_background"]) for row in answer_rows
    }
    representation_results: dict[str, Any] = {}
    for name in BENCHMARK_REPRESENTATIONS:
        metadata = _read_json(analysis_files[f"{name}_metadata"])
        cluster_report = _read_json(analysis_files[f"{name}_clusters"])
        kmeans_report = _read_json(analysis_files[f"{name}_kmeans"])
        neighbor_report = _read_json(analysis_files[f"{name}_neighbors"])
        verification = _read_json(analysis_files[f"{name}_index_verification"])
        member_ids = tuple(str(value) for value in metadata["member_ids"])
        if set(member_ids) != set(groups):
            raise ValueError("controlled-recovery representation and answer key differ")
        kmeans_report["member_ids"] = member_ids
        dbscan = _dbscan_metrics(cluster_report, groups, background)
        faiss = _faiss_metrics(
            neighbor_report,
            groups,
            background,
            exact_index_verified=(
                bool(verification.get("passed"))
                and int(verification.get("checked_member_count", 0)) == len(groups)
            ),
        )
        representation_results[name] = {
            "version": metadata["version"],
            "source_feature_version": metadata["source_feature_version"],
            "dbscan": dbscan,
            "faiss": faiss,
            "kmeans_diagnostic": _kmeans_metrics(kmeans_report, groups, background),
            "decisions": {
                "dbscan_controlled_recovery": bool(dbscan["passed"]),
                "faiss_controlled_recovery": bool(faiss["passed"]),
            },
        }
    patient_fact_pass = any(
        bool(representation_results[name]["decisions"]["dbscan_controlled_recovery"])
        for name in ("patient_fact_v1", "patient_fact_v2")
    )
    report: dict[str, Any] = {
        "run_id": run_directory.name,
        "evaluation_version": RECOVERY_EVALUATION_VERSION,
        "contract_hash": _sha256(run_directory / COHORT_DIRECTORY / "generation_config.json"),
        "implementation_commit": _implementation_commit(),
        "analysis_manifest_sha256": _sha256(run_directory / ANALYSIS_DIRECTORY / MANIFEST_FILENAME),
        "answer_key_manifest_sha256": _sha256(
            run_directory / ANSWER_KEY_DIRECTORY / MANIFEST_FILENAME
        ),
        "source_semantic_checksums": cohort_manifest["semantic_checksums"],
        "group_counts": dict(sorted(Counter(groups.values()).items())),
        "representations": representation_results,
        "benchmark_decision": {
            "patient_fact_dbscan_capability_established": patient_fact_pass,
            "status": "passed" if patient_fact_pass else "failed",
            "screening_profile_is_independent": True,
            "faiss_does_not_substitute_for_dbscan": True,
        },
        "integrity": {
            "cohort_manifest_matched": True,
            "analysis_seal_matched": True,
            "answer_key_seal_matched": True,
            "all_analysis_checks_passed": all(
                bool(value) for value in analysis_manifest["integrity_checks"].values()
            ),
            "answer_key_semantic_checksum_matched": True,
            "activation_changed": False,
        },
        "limitations": [
            "This single run does not establish generation-seed generalization.",
            "Recovered groups are benchmark assignments, not clinical phenotypes or diagnoses.",
            "Clusters and neighbors are not eligibility evidence.",
        ],
    }
    report_path = output_directory / "report.json"
    _write_json(report_path, report)
    manifest = {
        "run_id": run_directory.name,
        "evaluation_version": RECOVERY_EVALUATION_VERSION,
        "status": "complete",
        "analysis_manifest_sha256": report["analysis_manifest_sha256"],
        "answer_key_manifest_sha256": report["answer_key_manifest_sha256"],
        "cohort_manifest_sha256": _sha256(run_directory / COHORT_DIRECTORY / MANIFEST_FILENAME),
        "benchmark_decision": report["benchmark_decision"],
        "representations": {
            name: result["decisions"] for name, result in representation_results.items()
        },
        "integrity": report["integrity"],
        "activation_changed": False,
        "files": {
            "report": {
                "path": "report.json",
                "sha256": _sha256(report_path),
            }
        },
    }
    _write_json(output_directory / MANIFEST_FILENAME, manifest)
    return manifest


def run_evaluation(run_directory: Path) -> dict[str, object]:
    """Verify both seals, reveal once, and write post-reveal metrics atomically."""

    run_directory = run_directory.resolve()
    target = run_directory / EVALUATION_DIRECTORY
    if target.exists():
        raise FileExistsError("controlled-recovery evaluation already exists")
    inputs = _load_sealed_inputs(run_directory)
    analysis_manifest_before = (run_directory / ANALYSIS_DIRECTORY / MANIFEST_FILENAME).read_bytes()
    answer_manifest_before = (run_directory / ANSWER_KEY_DIRECTORY / MANIFEST_FILENAME).read_bytes()
    with tempfile.TemporaryDirectory(
        prefix=".evaluation-building-", dir=run_directory
    ) as temporary:
        staging = Path(temporary)
        manifest = _evaluate(run_directory, *inputs, staging)
        staging.replace(target)
    if (
        run_directory / ANALYSIS_DIRECTORY / MANIFEST_FILENAME
    ).read_bytes() != analysis_manifest_before or (
        run_directory / ANSWER_KEY_DIRECTORY / MANIFEST_FILENAME
    ).read_bytes() != answer_manifest_before:
        raise RuntimeError("controlled-recovery evaluation altered a sealed predecessor")
    return {
        "run_id": run_directory.name,
        "evaluation_directory": str(target),
        "manifest": manifest,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reveal and evaluate one sealed R6 controlled-recovery analysis."
    )
    parser.add_argument("--run-directory", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_evaluation(args.run_directory), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
