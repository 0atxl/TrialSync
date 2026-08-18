from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from trialsync.research.cohort_profiles.contracts import (
    FeatureContractError,
    R6CriterionResultRecord,
    R6FactRecord,
    R6PatientRecord,
    RepresentationContext,
)
from trialsync.research.cohort_profiles.features import (
    build_patient_fact_representation,
    build_screening_profile_representation,
)


@pytest.fixture
def context() -> RepresentationContext:
    return RepresentationContext(
        cohort_checksum="cohort-checksum",
        reference_panel_checksum="panel-checksum",
        criterion_order_checksum="criterion-checksum",
        as_of_date=date(2026, 8, 16),
    )


@pytest.fixture
def patients() -> tuple[R6PatientRecord, ...]:
    return (
        R6PatientRecord(
            member_id="participant-b",
            date_of_birth=date(1980, 3, 2),
            sex="female",
            facts=(
                R6FactRecord(
                    "c-b",
                    "condition",
                    "hypertension",
                    assertion="present",
                    effective_date=date(2026, 8, 1),
                ),
                R6FactRecord(
                    "m-b",
                    "medication",
                    "metformin",
                    assertion="absent",
                    effective_date=date(2026, 8, 2),
                ),
                R6FactRecord(
                    "o-b", "observation", "hba1c", value=6.8, effective_date=date(2026, 8, 3)
                ),
            ),
        ),
        R6PatientRecord(
            member_id="participant-a",
            date_of_birth=None,
            sex=None,
            facts=(
                R6FactRecord(
                    "c-a",
                    "condition",
                    "hypertension",
                    assertion="unknown",
                    effective_date=date(2026, 8, 4),
                ),
                R6FactRecord(
                    "m-a",
                    "medication",
                    "metformin",
                    assertion="present",
                    effective_date=date(2026, 8, 5),
                ),
                R6FactRecord(
                    "o-a", "observation", "hba1c", value=7.2, effective_date=date(2026, 8, 6)
                ),
            ),
        ),
    )


def test_patient_fact_features_preserve_missingness_and_are_normalized(
    patients: tuple[R6PatientRecord, ...], context: RepresentationContext
) -> None:
    artifact = build_patient_fact_representation(patients, context)

    assert artifact.member_ids == ("participant-a", "participant-b")
    assert "condition:hypertension:state:unknown" in artifact.feature_names
    assert "condition:hypertension:state:missing" in artifact.feature_names
    assert "observation:hba1c:value_missing" in artifact.feature_names
    assert artifact.normalized_matrix.dtype == np.float32
    assert np.allclose(np.linalg.norm(artifact.normalized_matrix, axis=1), 1.0)
    assert artifact.preprocessing.numeric_feature_names
    assert not np.isnan(artifact.standardized_matrix).any()


def test_screening_profile_unknown_is_its_own_one_hot_state(
    patients: tuple[R6PatientRecord, ...], context: RepresentationContext
) -> None:
    results = (
        R6CriterionResultRecord(
            "participant-a",
            "trial-1",
            1,
            "criterion-1",
            1,
            "metabolic",
            "unknown",
            ("missing_fact",),
        ),
        R6CriterionResultRecord(
            "participant-b", "trial-1", 1, "criterion-1", 1, "metabolic", "pass"
        ),
    )
    artifact = build_screening_profile_representation(patients, results, context)

    unknown = artifact.feature_names.index("criterion:trial-1:criterion-1:result:unknown")
    passed = artifact.feature_names.index("criterion:trial-1:criterion-1:result:pass")
    assert artifact.raw_matrix[0, unknown] == 1.0
    assert artifact.raw_matrix[0, passed] == 0.0
    assert "missing_category:missing_fact:rate" in artifact.feature_names
    assert artifact.version == "r6.screening_profile.v1"


def test_incomplete_screening_matrix_and_forbidden_sources_fail_closed(
    patients: tuple[R6PatientRecord, ...], context: RepresentationContext
) -> None:
    with pytest.raises(FeatureContractError, match="incomplete"):
        build_screening_profile_representation(
            patients,
            (
                R6CriterionResultRecord(
                    "participant-a", "trial-1", 1, "criterion-1", 1, "metabolic", "pass"
                ),
            ),
            context,
        )

    forbidden = R6PatientRecord(
        member_id="participant-c",
        date_of_birth=date(1980, 1, 1),
        sex="male",
        facts=(
            R6FactRecord(
                "bad", "observation", "dropout_probability", 0.2, effective_date=date(2026, 8, 1)
            ),
        ),
    )
    with pytest.raises(FeatureContractError, match="forbidden"):
        build_patient_fact_representation((forbidden,), context)
