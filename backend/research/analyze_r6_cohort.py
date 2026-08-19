"""Build and verify R6 representations, clusters, projections, and similarity indexes."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import numpy as np

from research.configs.r6_cohort import R6_CONTRACT_VERSION
from research.configs.r6_v3 import V3_CONTRACT_VERSION
from research.schemas.r6_dataset import (
    ARTIFACT_FILENAMES,
    MANIFEST_FILENAME,
    R6_ARTIFACT_FORMAT,
    semantic_checksum,
    validate_forbidden_feature_leakage,
)
from research.schemas.r6_v3 import validate_private_source_absent
from trialsync.research.cohort_profiles import (
    R6CriterionResultRecord,
    R6FactRecord,
    R6PatientRecord,
    RepresentationArtifact,
    RepresentationContext,
    build_patient_fact_representation,
    build_screening_profile_representation,
)
from trialsync.research.cohorts import (
    DBSCANConfig,
    build_pca_projection,
    run_dbscan_analysis,
)
from trialsync.research.similarity import (
    build_exact_faiss_index,
    verify_exact_neighbors,
)

_SUPPORTED_CONTRACT_VERSIONS = frozenset({R6_CONTRACT_VERSION, V3_CONTRACT_VERSION})

DEFAULT_DBSCAN_CONFIG = DBSCANConfig(
    eps_values=(0.45, 0.6, 0.75, 0.9, 1.05, 1.2),
    min_samples_values=(5, 10, 15, 20),
    stability_repeats=5,
)


@dataclass(frozen=True, slots=True)
class LoadedR6Cohort:
    run_directory: Path
    manifest: dict[str, Any]
    patients: tuple[R6PatientRecord, ...]
    criterion_results: tuple[R6CriterionResultRecord, ...]
    labels: dict[str, str]
    conditions: dict[str, frozenset[str]]
    rule_signatures: dict[tuple[str, str], str]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq

        table = pq.read_table(path)  # type: ignore[no-untyped-call]
        return cast(list[dict[str, Any]], table.to_pylist())
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _validate_file(run_directory: Path, record: dict[str, Any]) -> Path:
    relative = Path(str(record["path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("R6 manifest contains an unsafe artifact path")
    resolved_run = run_directory.resolve()
    unresolved = resolved_run / relative
    try:
        path = unresolved.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"R6 artifact is missing: {relative}") from exc
    if unresolved.is_symlink() or not path.is_relative_to(resolved_run) or not path.is_file():
        raise ValueError(f"R6 artifact is outside its run directory: {relative}")
    expected = record.get("sha256")
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected is not None and observed != expected:
        raise ValueError(f"R6 artifact checksum mismatch: {relative}")
    return path


def _fact_value(record: dict[str, Any]) -> float | str | None:
    value = record.get("value")
    if value is None:
        return None
    if record["fact_type"] == "observation":
        return float(value)
    return str(value)


def load_materialized_cohort(
    run_directory: Path, *, expected_run_id: str | None = None
) -> LoadedR6Cohort:
    """Load a materialized run and reject missing, altered, or incomplete records."""

    run_directory = run_directory.resolve()
    manifest_path = run_directory / MANIFEST_FILENAME
    if manifest_path.is_symlink():
        raise ValueError("R6 manifest cannot be a symbolic link")
    manifest = _read_json(manifest_path)
    required_run_id = expected_run_id or run_directory.name
    if not isinstance(manifest, dict) or manifest.get("run_id") != required_run_id:
        raise ValueError("R6 manifest run_id does not match its directory")
    if manifest.get("contract_version") not in _SUPPORTED_CONTRACT_VERSIONS:
        raise ValueError("R6 cohort contract version is unsupported")
    if manifest.get("artifact_format") != R6_ARTIFACT_FORMAT:
        raise ValueError("R6 artifact format is unsupported")
    if not isinstance(manifest.get("generator_version"), str):
        raise ValueError("R6 generator version is missing")
    try:
        UUID(str(manifest["uuid_namespace"]))
    except (KeyError, ValueError) as exc:
        raise ValueError("R6 UUID namespace is missing or invalid") from exc
    file_records = manifest.get("files")
    if not isinstance(file_records, dict):
        raise ValueError("R6 manifest does not contain artifact file metadata")
    if not set(ARTIFACT_FILENAMES).issubset(file_records):
        raise ValueError("R6 manifest is missing required materialization artifacts")
    paths = {name: _validate_file(run_directory, record) for name, record in file_records.items()}
    patient_rows = _read_records(paths["patients"])
    fact_rows = _read_records(paths["patient_facts"])
    reference_panel = _read_json(paths["reference_panel"])
    screening_pairs = _read_records(paths["screening_pairs"])
    criterion_rows = _read_records(paths["criterion_results"])
    validate_forbidden_feature_leakage(
        (*patient_rows, *fact_rows, *screening_pairs, *criterion_rows, reference_panel)
    )
    validate_private_source_absent(
        (*patient_rows, *fact_rows, *screening_pairs, *criterion_rows, reference_panel)
    )
    expected_semantic = manifest["semantic_checksums"]
    observed_semantic = {
        "patient_snapshots": semantic_checksum(patient_rows),
        "patient_facts": semantic_checksum(fact_rows),
        "reference_panel": semantic_checksum(reference_panel),
        "criterion_order": semantic_checksum(
            [
                {
                    "trial_version_id": trial["trial_version_id"],
                    "criterion_id": criterion["criterion_id"],
                    "order": criterion["order"],
                }
                for trial in reference_panel["trials"]
                for criterion in trial["criteria"]
            ]
        ),
        "screening_pairs": semantic_checksum(screening_pairs),
        "criterion_results": semantic_checksum(criterion_rows),
    }
    observed_semantic["cohort"] = semantic_checksum(
        {
            "patient_snapshots": observed_semantic["patient_snapshots"],
            "patient_facts": observed_semantic["patient_facts"],
        }
    )
    for name, observed in observed_semantic.items():
        if expected_semantic.get(name) != observed:
            raise ValueError(f"R6 semantic checksum mismatch: {name}")
    if len(patient_rows) != manifest["patient_count"]:
        raise ValueError("R6 patient count does not match the manifest")
    if len(screening_pairs) != manifest["pair_count"]:
        raise ValueError("R6 pair count does not match the manifest")
    if len(criterion_rows) != manifest.get("criterion_result_count"):
        raise ValueError("R6 criterion-result count does not match the manifest")
    patient_ids = [str(row["patient_snapshot_id"]) for row in patient_rows]
    patient_id_set = set(patient_ids)
    if len(patient_id_set) != len(patient_ids):
        raise ValueError("R6 cohort contains duplicate patient identifiers")
    if any(str(row["patient_snapshot_id"]) not in patient_id_set for row in fact_rows):
        raise ValueError("R6 patient fact references an unknown cohort member")
    trials = reference_panel.get("trials") if isinstance(reference_panel, dict) else None
    if not isinstance(trials, list) or len(trials) != manifest["trial_count"]:
        raise ValueError("R6 reference-panel count does not match the manifest")
    trial_ids = {str(trial["trial_version_id"]) for trial in trials}
    if len(trial_ids) != len(trials):
        raise ValueError("R6 reference panel contains duplicate trial-version identifiers")
    expected_pairs = {
        (patient_id, trial_id) for patient_id in patient_ids for trial_id in trial_ids
    }
    observed_pairs = {
        (str(row["patient_snapshot_id"]), str(row["trial_version_id"])) for row in screening_pairs
    }
    if observed_pairs != expected_pairs or len(screening_pairs) != len(expected_pairs):
        raise ValueError("R6 screening-pair matrix is incomplete or duplicated")
    pair_by_id = {str(row["pair_id"]): row for row in screening_pairs}
    if len(pair_by_id) != len(screening_pairs):
        raise ValueError("R6 screening-pair identifiers are not unique")
    expected_criteria = {
        str(trial["trial_version_id"]): {
            str(criterion["criterion_id"]) for criterion in trial["criteria"]
        }
        for trial in trials
    }
    rule_signatures = {
        (str(trial["trial_version_id"]), str(criterion["criterion_id"])): json.dumps(
            criterion["expression"], sort_keys=True, separators=(",", ":")
        )
        for trial in trials
        for criterion in trial["criteria"]
    }
    expected_criterion_count = sum(
        len(expected_criteria[str(pair["trial_version_id"])]) for pair in screening_pairs
    )
    if len(criterion_rows) != expected_criterion_count:
        raise ValueError("R6 criterion-result matrix has an unexpected cardinality")
    observed_criteria: dict[str, set[str]] = defaultdict(set)
    criterion_ids: set[str] = set()
    for row in criterion_rows:
        result_id = str(row["criterion_result_id"])
        if result_id in criterion_ids:
            raise ValueError("R6 criterion-result identifiers are not unique")
        criterion_ids.add(result_id)
        pair = pair_by_id.get(str(row["pair_id"]))
        if pair is None or (
            str(row["patient_snapshot_id"]) != str(pair["patient_snapshot_id"])
            or str(row["trial_version_id"]) != str(pair["trial_version_id"])
        ):
            raise ValueError("R6 criterion result is not linked to its screening pair")
        observed_criteria[str(row["pair_id"])].add(str(row["criterion_id"]))
    if any(
        observed_criteria.get(pair_id) != expected_criteria[str(pair["trial_version_id"])]
        for pair_id, pair in pair_by_id.items()
    ):
        raise ValueError("R6 criterion-result matrix is incomplete or duplicated")

    facts_by_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in fact_rows:
        facts_by_member[str(fact["patient_snapshot_id"])].append(fact)
    patients: list[R6PatientRecord] = []
    labels: dict[str, str] = {}
    conditions: dict[str, frozenset[str]] = {}
    for patient in patient_rows:
        member_id = str(patient["patient_snapshot_id"])
        member_facts = facts_by_member[member_id]
        sex = next(
            (
                str(fact["concept"])
                for fact in member_facts
                if fact["fact_type"] == "demographic"
                and fact["assertion"] == "present"
                and fact["concept"] in {"female", "male"}
            ),
            None,
        )
        facts = tuple(
            R6FactRecord(
                fact_id=str(fact["fact_id"]),
                fact_type=str(fact["fact_type"]),  # type: ignore[arg-type]
                concept=str(fact["concept"]),
                value=_fact_value(fact),
                assertion=str(fact["assertion"]),  # type: ignore[arg-type]
                effective_date=(
                    date.fromisoformat(str(fact["effective_date"]))
                    if fact.get("effective_date")
                    else None
                ),
                unit=str(fact["unit"]) if fact.get("unit") is not None else None,
            )
            for fact in member_facts
        )
        patients.append(
            R6PatientRecord(
                member_id=member_id,
                date_of_birth=(
                    date.fromisoformat(str(patient["date_of_birth"]))
                    if patient.get("date_of_birth")
                    else None
                ),
                sex=sex,
                facts=facts,
            )
        )
        labels[member_id] = str(patient["label"])
        conditions[member_id] = frozenset(
            str(fact["concept"])
            for fact in member_facts
            if fact["fact_type"] == "condition" and fact["assertion"] == "present"
        )
    criterion_results = tuple(
        R6CriterionResultRecord(
            member_id=str(row["patient_snapshot_id"]),
            trial_version_id=str(row["trial_version_id"]),
            trial_order=int(row["trial_order"]),
            criterion_id=str(row["criterion_id"]),
            criterion_order=int(row["criterion_order"]),
            criterion_family=str(row["criterion_family"]),
            result=str(row["result"]),  # type: ignore[arg-type]
            missing_categories=tuple(
                sorted({str(item["reason"]) for item in row.get("missing", [])})
            ),
        )
        for row in criterion_rows
    )
    return LoadedR6Cohort(
        run_directory=run_directory,
        manifest=manifest,
        patients=tuple(patients),
        criterion_results=criterion_results,
        labels=labels,
        conditions=conditions,
        rule_signatures=rule_signatures,
    )


def build_representations(
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
        build_patient_fact_representation(cohort.patients, context),
        build_screening_profile_representation(cohort.patients, cohort.criterion_results, context),
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


def _add_file(manifest: dict[str, Any], logical_name: str, run_directory: Path, path: Path) -> None:
    manifest["files"][logical_name] = {
        "path": path.relative_to(run_directory).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def write_analysis_artifacts(
    cohort: LoadedR6Cohort,
    representations: tuple[RepresentationArtifact, RepresentationArtifact],
    *,
    dbscan_config: DBSCANConfig = DEFAULT_DBSCAN_CONFIG,
) -> dict[str, Any]:
    """Write both complete analysis spaces and fail unless both FAISS audits pass."""

    import faiss

    run_directory = cohort.run_directory
    manifest = dict(cohort.manifest)
    manifest["files"] = dict(manifest["files"])
    manifest["representations"] = {}
    members_path = run_directory / "members.json"
    _write_json(
        members_path,
        [
            {
                "member_id": patient.member_id,
                "label": cohort.labels[patient.member_id],
                "date_of_birth": patient.date_of_birth,
                "sex": patient.sex,
                "conditions": sorted(cohort.conditions[patient.member_id]),
            }
            for patient in cohort.patients
        ],
    )
    _add_file(manifest, "members", run_directory, members_path)

    for artifact in representations:
        representation_directory = run_directory / "representations" / artifact.name
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
            dbscan_config,
            condition_memberships=cohort.conditions if artifact.name == "patient_fact" else None,
        )
        cluster_path = run_directory / "clusters" / f"{artifact.name}.json"
        _write_json(cluster_path, report)
        projection = build_pca_projection(artifact)
        projection_path = run_directory / "projections" / f"{artifact.name}.json"
        _write_json(projection_path, projection)

        exact_index = build_exact_faiss_index(artifact)
        verification = verify_exact_neighbors(exact_index)
        if not verification.passed:
            raise ValueError(f"R6 {artifact.name} FAISS verification failed")
        index_path = run_directory / "indexes" / f"{artifact.name}.faiss"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(exact_index.index, str(index_path))
        index_metadata_path = run_directory / "indexes" / f"{artifact.name}.metadata.json"
        _write_json(index_metadata_path, exact_index.metadata)
        verification_path = run_directory / "indexes" / f"{artifact.name}.verification.json"
        _write_json(verification_path, verification)

        for suffix, path in {
            "vectors": vectors_path,
            "raw": raw_path,
            "representation_metadata": metadata_path,
            "clusters": cluster_path,
            "projection": projection_path,
            "index": index_path,
            "index_metadata": index_metadata_path,
            "index_verification": verification_path,
        }.items():
            _add_file(manifest, f"{artifact.name}_{suffix}", run_directory, path)
        manifest["representations"][artifact.name] = {
            "version": artifact.version,
            "feature_order_checksum": artifact.feature_order_checksum,
            "subject_order_checksum": artifact.subject_order_checksum,
            "dimension": len(artifact.feature_names),
            "cluster_count": report.selected.cluster_count,
            "noise_fraction": report.selected.noise_fraction,
            "index_type": exact_index.metadata.index_type,
            "index_verified": True,
        }

    manifest["analysis_status"] = "ready"
    manifest["analysis_completed_at"] = datetime.now(UTC).isoformat()
    _write_json(run_directory / MANIFEST_FILENAME, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze and index one materialized R6 cohort.")
    parser.add_argument("--run-directory", type=Path, required=True)
    args = parser.parse_args()
    cohort = load_materialized_cohort(args.run_directory)
    representations = build_representations(cohort)
    manifest = write_analysis_artifacts(cohort, representations)
    print(json.dumps(manifest, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
