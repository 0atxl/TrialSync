from __future__ import annotations

import hashlib
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

from trialsync.api.errors import ApplicationError
from trialsync.research.artifacts import CohortArtifactService


def _written_run(tmp_path: Path) -> Path:
    cohort = materialize(R6CohortConfig(patient_count=8, trial_count=4, seed=73))
    run_directory = tmp_path / cohort.run_id
    write_artifacts(cohort, run_directory)
    return run_directory


def test_materialized_run_adapts_to_two_distinct_patient_level_spaces(tmp_path: Path) -> None:
    loaded = load_materialized_cohort(_written_run(tmp_path))
    fact_space, screening_space = build_representations(loaded)

    assert fact_space.name == "patient_fact"
    assert screening_space.name == "screening_profile"
    assert fact_space.member_ids == screening_space.member_ids
    assert len(fact_space.member_ids) == 8
    assert fact_space.feature_names != screening_space.feature_names
    assert fact_space.feature_order_checksum != screening_space.feature_order_checksum
    assert all(name.count(":result:") == 1 for name in screening_space.feature_names[:48])
    assert any(name.endswith(":result:unknown") for name in screening_space.feature_names)


def test_loader_rejects_changed_materialized_artifact(tmp_path: Path) -> None:
    run_directory = _written_run(tmp_path)
    patients_path = run_directory / "patients.parquet"
    content = bytearray(patients_path.read_bytes())
    content[len(content) // 2] ^= 1
    patients_path.write_bytes(content)

    with pytest.raises(ValueError, match="checksum mismatch"):
        load_materialized_cohort(run_directory)


def test_full_analysis_bundle_is_written_and_both_indexes_are_verified(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("faiss")
    run_directory = _written_run(tmp_path)
    loaded = load_materialized_cohort(run_directory)

    manifest = write_analysis_artifacts(loaded, build_representations(loaded))

    assert manifest["analysis_status"] == "ready"
    assert set(manifest["representations"]) == {"patient_fact", "screening_profile"}
    assert all(
        metadata["index_type"] == "IndexFlatIP" and metadata["index_verified"] is True
        for metadata in manifest["representations"].values()
    )
    assert (run_directory / "indexes/patient_fact.faiss").is_file()
    assert (run_directory / "indexes/screening_profile.faiss").is_file()

    index_path = run_directory / "indexes/patient_fact.faiss"
    index_path.write_bytes(b"not-a-faiss-index")
    stored_manifest = json.loads((run_directory / "manifest.json").read_text())
    stored_manifest["files"]["patient_fact_index"]["sha256"] = hashlib.sha256(
        index_path.read_bytes()
    ).hexdigest()
    (run_directory / "manifest.json").write_text(
        json.dumps(stored_manifest, sort_keys=True, separators=(",", ":")) + "\n"
    )
    service = CohortArtifactService(tmp_path, run_directory.name)
    with pytest.raises(ApplicationError) as raised:
        service.similarity(
            run_directory.name,
            "patient_fact",
            loaded.patients[0].member_id,
            3,
        )
    assert raised.value.code == "RESEARCH_COHORT_DEGRADED"
