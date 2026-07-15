"""Pure deterministic screening domain.

This package deliberately has no framework, persistence, network, model, or clock dependency.
"""

from trialsync.domain.engine import screen
from trialsync.domain.types import (
    ApprovedTrialVersion,
    Assertion,
    Criterion,
    CriterionEvaluation,
    CriterionKind,
    CriterionResult,
    EvidenceReference,
    Fact,
    FactType,
    MissingRequirement,
    OverallState,
    PatientSnapshot,
    ReasonCode,
    ScreeningContext,
    ScreeningResult,
    Temporality,
    TruthValue,
)

__all__ = [
    "ApprovedTrialVersion",
    "Assertion",
    "Criterion",
    "CriterionEvaluation",
    "CriterionKind",
    "CriterionResult",
    "EvidenceReference",
    "Fact",
    "FactType",
    "MissingRequirement",
    "OverallState",
    "PatientSnapshot",
    "ReasonCode",
    "ScreeningContext",
    "ScreeningResult",
    "Temporality",
    "TruthValue",
    "screen",
]
