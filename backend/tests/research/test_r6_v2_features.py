from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from trialsync.research.cohort_profiles.contracts import (
    BalancedPreprocessingParameters,
    FeatureContractError,
    R6CriterionResultRecord,
    R6FactRecord,
    R6PatientRecord,
    RepresentationContext,
)
from trialsync.research.cohort_profiles.v2 import (
    build_patient_fact_representation_v2,
    build_screening_profile_representation_v2,
)


def _context() -> RepresentationContext:
    return RepresentationContext("cohort", "panel", "criteria", date(2026, 8, 16))


def _patients() -> tuple[R6PatientRecord, ...]:
    return tuple(
        R6PatientRecord(
            member_id=f"participant-{index}",
            date_of_birth=date(1970 + index * 10, 1, 1),
            sex="female" if index % 2 else "male",
            facts=(
                R6FactRecord(
                    f"condition-{index}",
                    "condition",
                    "hypertension",
                    assertion="present" if index != 2 else "unknown",
                    effective_date=date(2026, 8, 1 + index),
                ),
                *(
                    (
                        R6FactRecord(
                            f"observation-{index}",
                            "observation",
                            "hba1c",
                            value=5.0 + index * 2,
                            effective_date=date(2026, 8, 2 + index),
                        ),
                    )
                    if index != 2
                    else ()
                ),
            ),
        )
        for index in range(3)
    )


def _criterion_results() -> tuple[R6CriterionResultRecord, ...]:
    states = (("pass", "unknown"), ("fail", "pass"), ("unknown", "fail"))
    records: list[R6CriterionResultRecord] = []
    for member_index, member_states in enumerate(states):
        for trial_index, state in enumerate(member_states, start=1):
            records.append(
                R6CriterionResultRecord(
                    member_id=f"participant-{member_index}",
                    trial_version_id=f"trial-{trial_index}",
                    trial_order=trial_index,
                    criterion_id=f"criterion-{trial_index}",
                    criterion_order=1,
                    criterion_family="condition",
                    result=state,  # type: ignore[arg-type]
                    missing_categories=("missing_fact",) if state == "unknown" else (),
                )
            )
    return tuple(records)


def test_patient_fact_v2_is_deterministic_balanced_and_preserves_missingness() -> None:
    first = build_patient_fact_representation_v2(_patients(), _context())
    second = build_patient_fact_representation_v2(_patients(), _context())

    assert first.version == "r6.patient_fact.v2"
    assert isinstance(first.preprocessing, BalancedPreprocessingParameters)
    assert first.preprocessing.source_version == "r6.patient_fact.v1"
    assert {name for name, _weight in first.preprocessing.block_weights} == {
        "demographic",
        "condition",
        "observation",
    }
    value = first.feature_names.index("observation:hba1c:value")
    missing = first.feature_names.index("observation:hba1c:value_missing")
    assert np.isnan(first.raw_matrix[2, value])
    assert first.raw_matrix[2, missing] == 1.0
    assert np.isfinite(first.standardized_matrix).all()
    assert np.allclose(np.linalg.norm(first.normalized_matrix, axis=1), 1.0)
    assert first.feature_order_checksum == second.feature_order_checksum
    assert np.array_equal(first.normalized_matrix, second.normalized_matrix)


def test_screening_profile_v2_keeps_states_and_records_repeated_rule_weighting() -> None:
    signatures = {
        ("trial-1", "criterion-1"): '{"fact":"condition.hypertension","op":"present"}',
        ("trial-2", "criterion-2"): '{"fact":"condition.hypertension","op":"present"}',
    }
    artifact = build_screening_profile_representation_v2(
        _patients(),
        _criterion_results(),
        _context(),
        rule_signatures=signatures,
    )

    assert artifact.version == "r6.screening_profile.v2"
    assert isinstance(artifact.preprocessing, BalancedPreprocessingParameters)
    assert artifact.preprocessing.rule_signature_checksum
    assert all(
        f"criterion:trial-1:criterion-1:result:{state}" in artifact.feature_names
        for state in ("pass", "fail", "unknown")
    )
    criterion_weight = artifact.preprocessing.feature_weights[
        artifact.feature_names.index("criterion:trial-1:criterion-1:result:pass")
    ]
    assert criterion_weight < dict(artifact.preprocessing.block_weights)["criterion_state"]
    assert np.allclose(np.linalg.norm(artifact.normalized_matrix, axis=1), 1.0)

    with pytest.raises(FeatureContractError, match="signatures"):
        build_screening_profile_representation_v2(
            _patients(),
            _criterion_results(),
            _context(),
            rule_signatures={("trial-1", "criterion-1"): "incomplete"},
        )
