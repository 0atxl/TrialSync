"""Tests for the R6 V3 controlled-group cohort pipeline."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from research.analyze_r6_cohort import (
    build_representations,
    load_materialized_cohort,
    write_analysis_artifacts,
)
from research.build_r6_v3_cohort import materialize_v3, write_artifacts_v3
from research.configs.r6_v3 import (
    PATIENT_GROUPS,
    PatientGroup,
    R6V3Config,
)
from research.evaluate_r6_v3 import evaluate_run
from research.run_r6_v3_pipeline import run_pipeline
from research.schemas.r6_v3 import (
    ANSWER_KEY_FILENAME,
    EVALUATION_DIRECTORY,
    PRIVATE_DIRECTORY,
    PRIVATE_MANIFEST_FILENAME,
)

from trialsync.db.models import PatientSnapshot
from trialsync.research.artifacts import CohortArtifactService


def _mini_groups() -> tuple[PatientGroup, ...]:
    return tuple(
        PatientGroup(
            name=group.name,
            target_count=2,
            age_min=group.age_min,
            age_max=group.age_max,
            condition_probabilities=group.condition_probabilities,
            medication_probabilities=group.medication_probabilities,
            observation_centers=group.observation_centers,
            observation_spreads=group.observation_spreads,
        )
        for group in PATIENT_GROUPS[:3]
    )


def _written_v3_run(tmp_path: Path) -> Path:
    config = R6V3Config(patient_count=6, trial_count=2, patient_groups=_mini_groups())
    cohort, assignments = materialize_v3(config)
    run_directory = tmp_path / cohort.run_id
    write_artifacts_v3(cohort, run_directory, assignments)
    return run_directory


def test_v3_materialization_and_audit_isolation(tmp_path: Path) -> None:
    run_dir = _written_v3_run(tmp_path)
    loaded = load_materialized_cohort(run_dir)
    assert len(loaded.patients) == 6
    assert (run_dir / PRIVATE_DIRECTORY / ANSWER_KEY_FILENAME).exists()
    assert (run_dir / PRIVATE_DIRECTORY / PRIVATE_MANIFEST_FILENAME).exists()


def test_v3_representations_and_analysis(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("faiss")
    run_dir = _written_v3_run(tmp_path)
    loaded = load_materialized_cohort(run_dir)
    representations = build_representations(loaded)
    manifest = write_analysis_artifacts(loaded, representations)
    assert manifest["analysis_status"] == "ready"
    assert "patient_fact" in manifest["representations"]
    assert "screening_profile" in manifest["representations"]
    report = evaluate_run(run_dir)
    assert report["status"] == "verified_for_review"
    assert report["representations"]["patient_fact"]["exact_index_verified"] is True
    assert report["representations"]["screening_profile"]["exact_index_verified"] is True
    assert (run_dir / EVALUATION_DIRECTORY / "report.json").exists()


def test_v3_materialization_is_deterministic() -> None:
    """Running materialize_v3 twice with identical config produces identical checksums."""
    config = R6V3Config(patient_count=6, trial_count=2, patient_groups=_mini_groups())
    cohort_a, _ = materialize_v3(config)
    cohort_b, _ = materialize_v3(config)
    assert cohort_a.run_id == cohort_b.run_id
    assert cohort_a.semantic_checksums == cohort_b.semantic_checksums


def test_v3_group_assignments_match_config() -> None:
    """The sealed answer key contains the expected group distribution."""
    config = R6V3Config(patient_count=6, trial_count=2, patient_groups=_mini_groups())
    _cohort, assignments = materialize_v3(config)
    counts = Counter(assignments.values())
    for group in config.patient_groups:
        assert counts[group.name] == group.target_count
    assert len(assignments) == config.patient_count


def test_v3_group_labels_do_not_leak_into_records() -> None:
    """Group names must not appear in patient records, facts, or screening pairs."""
    config = R6V3Config(patient_count=6, trial_count=2, patient_groups=_mini_groups())
    cohort, _assignments = materialize_v3(config)
    group_names = {group.name for group in config.patient_groups}
    all_records = (
        *cohort.patient_records,
        *cohort.patient_fact_records,
        *cohort.screening_pairs,
        *cohort.criterion_results,
    )
    for record in all_records:
        serialized = json.dumps(record, default=str)
        for name in group_names:
            assert name not in serialized, (
                f"Patient-group name '{name}' leaked into record: {record}"
            )


def test_v3_encounter_date_cohesion() -> None:
    """All facts for a given patient should share a base encounter date ± 2 days."""
    config = R6V3Config(patient_count=6, trial_count=2, patient_groups=_mini_groups())
    cohort, _ = materialize_v3(config)
    for patient in cohort.patients:
        non_demographic_dates = [
            f.effective_date
            for f in patient.facts
            if f.fact_type.value != "demographic" and f.effective_date is not None
        ]
        if len(non_demographic_dates) < 2:
            continue
        earliest = min(non_demographic_dates)
        latest = max(non_demographic_dates)
        spread = (latest - earliest).days
        assert spread <= 4, (
            f"Patient {patient.id}: fact dates span {spread} days "
            f"({earliest} to {latest}), expected ≤ 4"
        )


def test_v3_config_rejects_patient_count_exceeding_limit() -> None:
    with pytest.raises(ValueError, match="exceeds 750"):
        R6V3Config(patient_count=751, patient_groups=_mini_groups())


def test_v3_config_rejects_mismatched_group_sum() -> None:
    with pytest.raises(ValueError, match="must equal patient_count"):
        R6V3Config(patient_count=10, trial_count=2, patient_groups=_mini_groups())


def test_v3_answer_key_is_sealed_but_not_in_public_file_table(tmp_path: Path) -> None:
    run_dir = _written_v3_run(tmp_path)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    file_paths = {record["path"] for record in manifest.get("files", {}).values()}
    assert not any(PRIVATE_DIRECTORY in path for path in file_paths)
    assert isinstance(manifest["answer_key_manifest_sha256"], str)
    assert (run_dir / PRIVATE_DIRECTORY / ANSWER_KEY_FILENAME).exists()


def test_v3_public_runtime_payloads_do_not_expose_answer_key(tmp_path: Path) -> None:
    run_dir = _written_v3_run(tmp_path)
    pytest.importorskip("sklearn")
    pytest.importorskip("faiss")
    loaded = load_materialized_cohort(run_dir)
    write_analysis_artifacts(loaded, build_representations(loaded))
    service = CohortArtifactService(tmp_path, run_dir.name)
    payload = {
        "runs": service.list_runs(),
        "clusters": service.clusters(run_dir.name, "patient_fact"),
        "member": service.member(run_dir.name, loaded.patients[0].member_id),
    }
    serialized = json.dumps(payload, sort_keys=True)
    for group in _mini_groups():
        assert group.name not in serialized
    assert "cohort_group" not in serialized


def test_saved_snapshot_projects_into_both_frozen_v3_spaces(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("faiss")
    run_dir = _written_v3_run(tmp_path)
    loaded = load_materialized_cohort(run_dir)
    write_analysis_artifacts(loaded, build_representations(loaded))
    patient = loaded.patients[0]
    snapshot = PatientSnapshot(
        id=uuid.UUID(patient.member_id),
        owner_id=uuid.uuid4(),
        patient_id=None,
        content_hash="1" * 64,
        snapshot_version="test-snapshot-v1",
        date_of_birth=patient.date_of_birth,
        source_summary={"sex": patient.sex},
        facts_json=[
            {
                "id": fact.fact_id,
                "fact_type": fact.fact_type,
                "concept": fact.concept,
                "value_numeric": fact.value,
                "value_text": None,
                "unit": fact.unit,
                "assertion": fact.assertion,
                "effective_date": fact.effective_date.isoformat() if fact.effective_date else None,
                "source_label": "Stored patient fact",
            }
            for fact in patient.facts
            if fact.fact_type != "demographic"
        ],
    )
    service = CohortArtifactService(tmp_path, run_dir.name)
    assert service.live_query_status()["status"] == "ready"

    fact_neighbors = service.screening_similarity(
        snapshot,
        screening_date=date.fromisoformat(loaded.manifest["screening_date"]),
        representation="patient_fact",
        neighbor_count=3,
    )
    screening_neighbors = service.screening_similarity(
        snapshot,
        screening_date=date.fromisoformat(loaded.manifest["screening_date"]),
        representation="screening_profile",
        neighbor_count=3,
    )
    context = service.screening_cohort_context(
        snapshot,
        screening_date=date.fromisoformat(loaded.manifest["screening_date"]),
        representation="patient_fact",
    )

    assert fact_neighbors["neighbors"][0]["member_id"] == patient.member_id
    assert fact_neighbors["neighbors"][0]["cosine_similarity"] == pytest.approx(1.0)
    assert screening_neighbors["neighbors"][0]["member_id"] == patient.member_id
    assert screening_neighbors["neighbors"][0]["cosine_similarity"] == pytest.approx(1.0)
    assert context["out_of_sample"] is True
    assert context["projection"]["display_only"] is True
    metadata = json.loads(
        (run_dir / "representations/patient_fact/metadata.json").read_text(encoding="utf-8")
    )
    vectors = np.load(run_dir / "representations/patient_fact/vectors.npy", allow_pickle=False)
    query_index = metadata["member_ids"].index(patient.member_id)
    expected = sorted(
        zip(vectors @ vectors[query_index], metadata["member_ids"], strict=True),
        key=lambda item: (-float(item[0]), item[1]),
    )[:3]
    assert [item["member_id"] for item in fact_neighbors["neighbors"]] == [
        item[1] for item in expected
    ]


def test_v3_private_seal_rejects_changed_answer_key(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("faiss")
    run_dir = _written_v3_run(tmp_path)
    loaded = load_materialized_cohort(run_dir)
    write_analysis_artifacts(loaded, build_representations(loaded))
    answer_path = run_dir / PRIVATE_DIRECTORY / ANSWER_KEY_FILENAME
    value = json.loads(answer_path.read_text(encoding="utf-8"))
    value["members"][0]["cohort_group"] = "changed_group"
    answer_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        evaluate_run(run_dir)


def test_v3_run_directory_cannot_be_overwritten(tmp_path: Path) -> None:
    run_dir = _written_v3_run(tmp_path)
    config = R6V3Config(patient_count=6, trial_count=2, patient_groups=_mini_groups())
    cohort, assignments = materialize_v3(config)
    with pytest.raises(FileExistsError, match="already exists"):
        write_artifacts_v3(cohort, run_dir, assignments)


def test_v3_manifest_seals_generation_contract_and_implementation(tmp_path: Path) -> None:
    run_dir = _written_v3_run(tmp_path)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["generator_version"] == "r6-controlled-groups-v3.1"
    assert manifest["semantic_checksums"]["generation_config"]
    assert manifest["implementation_checksums"] == {
        "analysis": manifest["implementation_checksums"]["analysis"],
        "dbscan": manifest["implementation_checksums"]["dbscan"],
        "feature_builder": manifest["implementation_checksums"]["feature_builder"],
        "materializer": manifest["implementation_checksums"]["materializer"],
        "similarity": manifest["implementation_checksums"]["similarity"],
        "v3_config": manifest["implementation_checksums"]["v3_config"],
        "v3_generator": manifest["implementation_checksums"]["v3_generator"],
    }
    assert all(len(value) == 64 for value in manifest["implementation_checksums"].values())


def test_v3_runner_publishes_atomically_and_rejects_rerun(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("faiss")
    config = R6V3Config(patient_count=6, trial_count=2, patient_groups=_mini_groups())
    result = run_pipeline(tmp_path, config)
    run_directory = Path(str(result["run_directory"]))
    assert run_directory.is_dir()
    assert not any(path.name.startswith(".r6-v3-staging-") for path in tmp_path.iterdir())
    assert result["evaluation"]["status"] == "verified_for_review"
    with pytest.raises(FileExistsError, match="immutable"):
        run_pipeline(tmp_path, config)
