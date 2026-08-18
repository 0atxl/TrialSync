"""Pure in-memory contracts for the R6 cohort analysis.

These types deliberately do not import the R6 materializer or database ORM.  An adapter at the
materialization boundary may create them from the existing immutable snapshot and screening
objects, while fixtures can instantiate them directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np

PATIENT_FACT_REPRESENTATION_VERSION = "r6.patient_fact.v1"
SCREENING_PROFILE_REPRESENTATION_VERSION = "r6.screening_profile.v1"
PREPROCESSING_VERSION = "r6.standardize-median-l2.v1"

FactType = Literal["condition", "medication", "observation", "demographic"]
Assertion = Literal["present", "absent", "unknown"]
CriterionState = Literal["pass", "fail", "unknown"]

# These are source domains which must never define an R6 vector.  Checking input identifiers as
# well as final feature names makes an accidental future field addition fail closed.
FORBIDDEN_FEATURE_TOKENS = frozenset(
    {
        "dropout",
        "shap",
        "chat",
        "rag",
        "llm",
        "generator_tier",
        "hidden_generator",
        "random_draw",
        "risk_probability",
        "risk_band",
    }
)


class FeatureContractError(ValueError):
    """Raised when an input cannot be represented without changing its meaning."""


@dataclass(frozen=True, slots=True)
class R6FactRecord:
    """A fact from one immutable patient snapshot in the frozen cohort."""

    fact_id: str
    fact_type: FactType
    concept: str
    value: float | int | str | None = None
    assertion: Assertion = "present"
    effective_date: date | None = None
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class R6PatientRecord:
    """The R6-facing subset of a patient snapshot, one per cohort member."""

    member_id: str
    date_of_birth: date | None
    sex: str | None
    facts: tuple[R6FactRecord, ...]


@dataclass(frozen=True, slots=True)
class R6CriterionResultRecord:
    """One materialized deterministic criterion evaluation.

    ``criterion_family`` is a frozen panel-defined grouping, not an inferred diagnosis.  Missing
    categories come from the canonical evaluation's missing-information requirements.
    """

    member_id: str
    trial_version_id: str
    trial_order: int
    criterion_id: str
    criterion_order: int
    criterion_family: str
    result: CriterionState
    missing_categories: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RepresentationContext:
    """Checksums and dates that make a representation safe to compare or serialize."""

    cohort_checksum: str
    reference_panel_checksum: str
    criterion_order_checksum: str
    as_of_date: date
    subject_order_checksum: str | None = None


@dataclass(frozen=True, slots=True)
class PreprocessingParameters:
    version: str
    numeric_feature_names: tuple[str, ...]
    medians: tuple[float, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class BalancedPreprocessingParameters:
    """Complete fitted preprocessing record for an R6 V2 representation."""

    version: str
    source_version: str
    numeric_feature_names: tuple[str, ...]
    medians: tuple[float, ...]
    clip_lower: tuple[float, ...]
    clip_upper: tuple[float, ...]
    centers: tuple[float, ...]
    scales: tuple[float, ...]
    removed_feature_names: tuple[str, ...]
    feature_blocks: tuple[str, ...]
    block_weights: tuple[tuple[str, float], ...]
    feature_weights: tuple[float, ...]
    rule_signature_checksum: str | None = None


@dataclass(frozen=True, slots=True)
class RepresentationArtifact:
    """Raw, standardized, and normalized matrices for one immutable R6 representation."""

    name: Literal["patient_fact", "screening_profile"]
    version: str
    member_ids: tuple[str, ...]
    feature_names: tuple[str, ...]
    raw_matrix: np.ndarray
    standardized_matrix: np.ndarray
    normalized_matrix: np.ndarray
    preprocessing: PreprocessingParameters | BalancedPreprocessingParameters
    cohort_checksum: str
    reference_panel_checksum: str
    criterion_order_checksum: str
    subject_order_checksum: str
    feature_order_checksum: str

    def __post_init__(self) -> None:
        expected = (len(self.member_ids), len(self.feature_names))
        for matrix_name in ("raw_matrix", "standardized_matrix", "normalized_matrix"):
            matrix = getattr(self, matrix_name)
            if matrix.shape != expected:
                raise FeatureContractError(
                    f"{matrix_name} has shape {matrix.shape}, expected {expected}"
                )
        if (
            self.standardized_matrix.dtype != np.float32
            or self.normalized_matrix.dtype != np.float32
        ):
            raise FeatureContractError("preprocessed R6 matrices must be float32")
