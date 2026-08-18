from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest
import research.analyze_r6_recovery as recovery_analysis
from research.analyze_r6_cohort import load_materialized_cohort
from research.analyze_r6_recovery import run_analysis
from research.build_r6_recovery import materialize_recovery, write_recovery_artifacts
from research.configs.r6_recovery import DEFAULT_RECOVERY_CONFIG, R6RecoveryConfig
from research.evaluate_r6_recovery import run_evaluation


@pytest.fixture
def recovery_config() -> R6RecoveryConfig:
    return R6RecoveryConfig(
        group_counts=(8, 7, 6, 5),
        background_count=4,
        crossover_counts=(1, 1, 1, 1),
        trial_count=4,
    )


def _written_run(tmp_path: Path, config: R6RecoveryConfig) -> Path:
    run_directory, _manifest = write_recovery_artifacts(
        materialize_recovery(config), tmp_path / "controlled-recovery"
    )
    return run_directory


def test_recovery_generation_is_deterministic_and_keeps_key_separate(
    recovery_config: R6RecoveryConfig,
) -> None:
    first = materialize_recovery(recovery_config)
    second = materialize_recovery(recovery_config)

    assert first.run_id == second.run_id
    assert first.semantic_checksums == second.semantic_checksums
    assert first.patient_records == second.patient_records
    assert first.patient_fact_records == second.patient_fact_records
    assert first.answer_key == second.answer_key
    assert len(first.patients) == 30
    assert len(first.screening_pairs) == 120
    assert len(first.criterion_results) == 480
    assert Counter(row["latent_group_id"] for row in first.answer_key) == {
        "latent_group_01": 8,
        "latent_group_02": 7,
        "latent_group_03": 6,
        "latent_group_04": 5,
        "background": 4,
    }
    assert sum(bool(row["is_crossover"]) for row in first.generation_audit) == 4
    assert all(
        fact["value"] is None
        for fact in first.patient_fact_records
        if fact["fact_type"] == "observation" and fact["assertion"] == "unknown"
    )
    assert not any(
        "latent_group" in json.dumps(record, sort_keys=True)
        for record in (
            *first.patient_records,
            *first.patient_fact_records,
            *first.screening_pairs,
            *first.criterion_results,
        )
    )


def test_default_contract_freezes_the_only_full_run() -> None:
    assert DEFAULT_RECOVERY_CONFIG.patient_count == 750
    assert DEFAULT_RECOVERY_CONFIG.group_counts == (210, 180, 150, 120)
    assert DEFAULT_RECOVERY_CONFIG.background_count == 90
    assert DEFAULT_RECOVERY_CONFIG.crossover_counts == (25, 22, 18, 14)
    assert DEFAULT_RECOVERY_CONFIG.trial_count == 20
    assert DEFAULT_RECOVERY_CONFIG.seed == 60817


def test_label_free_analyzer_has_no_answer_key_dependency() -> None:
    source = Path(recovery_analysis.__file__).read_text(encoding="utf-8")

    assert "ANSWER_KEY_DIRECTORY" not in source
    assert "answer_key.parquet" not in source
    assert "latent_group" not in source


def test_recovery_analysis_seals_before_reveal_and_evaluates_without_activation(
    tmp_path: Path, recovery_config: R6RecoveryConfig
) -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("faiss")
    run_directory = _written_run(tmp_path, recovery_config)
    cohort_manifest_path = run_directory / "cohort/manifest.json"
    answer_manifest_path = run_directory / "answer-key/manifest.json"
    cohort_before = cohort_manifest_path.read_bytes()
    answer_before = answer_manifest_path.read_bytes()

    loaded = load_materialized_cohort(run_directory / "cohort", expected_run_id=run_directory.name)
    assert len(loaded.patients) == 30
    analysis_result = run_analysis(run_directory / "cohort")

    assert cohort_manifest_path.read_bytes() == cohort_before
    assert answer_manifest_path.read_bytes() == answer_before
    analysis_directory = Path(analysis_result["analysis_directory"])
    analysis_manifest_path = analysis_directory / "manifest.json"
    assert (
        analysis_result["analysis_manifest_sha256"]
        == hashlib.sha256(analysis_manifest_path.read_bytes()).hexdigest()
    )
    manifest = json.loads(analysis_manifest_path.read_text())
    assert manifest["status"] == "sealed_ready_for_evaluation"
    assert manifest["activation_changed"] is False
    assert set(manifest["representations"]) == {
        "patient_fact_v1",
        "patient_fact_v2",
        "screening_profile_v1",
        "screening_profile_v2",
    }
    assert all(
        value["exact_index_verified"] is True and value["verified_member_count"] == 30
        for value in manifest["representations"].values()
    )
    assert "latent_group" not in analysis_manifest_path.read_text()
    assert not (run_directory / "evaluation").exists()

    evaluation_result = run_evaluation(run_directory)

    assert cohort_manifest_path.read_bytes() == cohort_before
    assert answer_manifest_path.read_bytes() == answer_before
    assert (
        analysis_manifest_path.read_bytes() == (analysis_directory / "manifest.json").read_bytes()
    )
    evaluation_manifest = evaluation_result["manifest"]
    assert evaluation_manifest["status"] == "complete"
    assert evaluation_manifest["activation_changed"] is False
    assert set(evaluation_manifest["representations"]) == set(manifest["representations"])
    assert all(
        set(decisions) == {"dbscan_controlled_recovery", "faiss_controlled_recovery"}
        for decisions in evaluation_manifest["representations"].values()
    )

    with pytest.raises(FileExistsError, match="analysis already exists"):
        run_analysis(run_directory / "cohort")
    with pytest.raises(FileExistsError, match="evaluation already exists"):
        run_evaluation(run_directory)


def test_evaluation_rejects_an_altered_answer_key(
    tmp_path: Path, recovery_config: R6RecoveryConfig
) -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("faiss")
    run_directory = _written_run(tmp_path, recovery_config)
    run_analysis(run_directory / "cohort")
    answer_path = run_directory / "answer-key/answer_key.parquet"
    content = bytearray(answer_path.read_bytes())
    content[len(content) // 2] ^= 1
    answer_path.write_bytes(content)

    with pytest.raises(ValueError, match="artifact checksum mismatch"):
        run_evaluation(run_directory)
    assert not (run_directory / "evaluation").exists()
