from __future__ import annotations

import json
from pathlib import Path

import pytest
from research.analyze_r6_cohort import (
    build_representations,
    load_materialized_cohort,
    write_analysis_artifacts,
)
from research.build_r6_cohort import materialize, write_artifacts
from research.configs.r6_cohort import R6CohortConfig
from research.run_r6_v2_experiment import run_experiment


def _v1_run(tmp_path: Path) -> Path:
    cohort = materialize(R6CohortConfig(patient_count=8, trial_count=4, seed=97))
    run_directory = tmp_path / cohort.run_id
    write_artifacts(cohort, run_directory)
    loaded = load_materialized_cohort(run_directory)
    write_analysis_artifacts(loaded, build_representations(loaded))
    return run_directory


def test_v2_experiment_is_separate_versioned_verified_and_one_shot(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("faiss")
    run_directory = _v1_run(tmp_path)
    source_manifest_before = (run_directory / "manifest.json").read_bytes()

    result = run_experiment(run_directory, enforce_frozen_source=False)

    assert (run_directory / "manifest.json").read_bytes() == source_manifest_before
    experiment_directory = Path(result["experiment_directory"])
    manifest = json.loads((experiment_directory / "manifest.json").read_text())
    assert manifest["status"] == "ready_for_review"
    assert manifest["activation_changed"] is False
    assert set(manifest["representations"]) == {"patient_fact", "screening_profile"}
    assert all(
        value["version"].endswith(".v2")
        and value["index_verified"] is True
        and value["acceptance"]["final_decision"] == "pending_review"
        and all(value["acceptance"]["integrity_checks"].values())
        for value in manifest["representations"].values()
    )
    assert (experiment_directory / "indexes/patient_fact.faiss").is_file()
    assert (experiment_directory / "indexes/screening_profile.faiss").is_file()
    assert all(
        value["neighbor_overlap_with_v1"]["checked_member_count"] == 8
        for value in manifest["representations"].values()
    )

    with pytest.raises(FileExistsError, match="already been executed"):
        run_experiment(run_directory, enforce_frozen_source=False)


def test_v2_public_entrypoint_rejects_any_non_frozen_source_run(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("faiss")
    run_directory = _v1_run(tmp_path)

    with pytest.raises(ValueError, match="frozen accepted source run"):
        run_experiment(run_directory)
    assert not (run_directory / "experiments/v2").exists()
