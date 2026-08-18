from __future__ import annotations

from dataclasses import replace
from datetime import date
from importlib.util import find_spec

import numpy as np
import pytest

from trialsync.research.cohort_profiles.contracts import (
    FeatureContractError,
    R6FactRecord,
    R6PatientRecord,
    RepresentationContext,
)
from trialsync.research.cohort_profiles.features import build_patient_fact_representation
from trialsync.research.similarity.index import (
    IndexMetadataMismatchError,
    ResearchDependencyError,
    _ordered_neighbors,
    build_exact_faiss_index,
    query_neighbors,
    verify_exact_neighbors,
)


def _artifact():
    patients = tuple(
        R6PatientRecord(
            member_id=f"participant-{index}",
            date_of_birth=date(1970 + index, 1, 1),
            sex="female" if index % 2 else "male",
            facts=(
                R6FactRecord(
                    "condition",
                    "condition",
                    "hypertension",
                    assertion="present",
                    effective_date=date(2026, 8, 1),
                ),
                R6FactRecord(
                    "observation",
                    "observation",
                    "hba1c",
                    value=5.0 + index,
                    effective_date=date(2026, 8, 1),
                ),
            ),
        )
        for index in range(3)
    )
    return build_patient_fact_representation(
        patients,
        RepresentationContext("cohort", "panel", "criteria", date(2026, 8, 16)),
    )


def test_missing_faiss_reports_a_clear_optional_dependency_error() -> None:
    if find_spec("faiss") is not None:
        pytest.skip("FAISS is installed; the missing-dependency path is environment-specific")
    with pytest.raises(ResearchDependencyError, match="faiss-cpu"):
        build_exact_faiss_index(_artifact())


def test_faiss_builder_rejects_vectors_that_are_not_l2_normalized() -> None:
    artifact = _artifact()
    invalid = replace(artifact, normalized_matrix=artifact.normalized_matrix * 2.0)

    with pytest.raises(FeatureContractError, match="L2-normalized"):
        build_exact_faiss_index(invalid)


def test_numerically_tied_scores_use_member_identifier_order() -> None:
    neighbors = _ordered_neighbors(
        ("query", "member-b", "member-a", "member-c"),
        # The first two candidate scores differ only by ordinary float32 accumulation noise.
        np.array([1.0, 0.90000004, 0.9, 0.8], dtype=np.float32),
        query_index=0,
        limit=2,
    )

    assert [neighbor.member_id for neighbor in neighbors] == ["member-a", "member-b"]


@pytest.mark.skipif(
    find_spec("faiss") is None, reason="R6 exact-index test requires optional faiss-cpu"
)
def test_exact_faiss_neighbors_exclude_self_match_brute_force_and_reject_mismatch() -> None:
    artifact = _artifact()
    index = build_exact_faiss_index(artifact)
    result = query_neighbors(index, "participant-0", 10)

    assert len(result.neighbors) == 2
    assert all(neighbor.member_id != "participant-0" for neighbor in result.neighbors)
    assert verify_exact_neighbors(index).passed
    wrong_metadata = replace(index.metadata, cohort_checksum="wrong")
    with pytest.raises(IndexMetadataMismatchError, match="cohort_checksum"):
        query_neighbors(index, "participant-0", 1, expected_metadata=wrong_metadata)
