from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType


class TruthValue(StrEnum):
    true = "true"
    false = "false"
    unknown = "unknown"


class CriterionResult(StrEnum):
    pass_ = "pass"
    fail = "fail"
    unknown = "unknown"


class CriterionKind(StrEnum):
    inclusion = "inclusion"
    exclusion = "exclusion"


class OverallState(StrEnum):
    potentially_eligible = "potentially_eligible"
    likely_ineligible = "likely_ineligible"
    needs_review = "needs_review"


class FactType(StrEnum):
    demographic = "demographic"
    condition = "condition"
    medication = "medication"
    observation = "observation"


class Assertion(StrEnum):
    present = "present"
    absent = "absent"
    unknown = "unknown"


class Temporality(StrEnum):
    current = "current"
    historical = "historical"
    resolved = "resolved"
    unknown = "unknown"


class ReasonCode(StrEnum):
    evaluated_true = "EVALUATED_TRUE"
    evaluated_false = "EVALUATED_FALSE"
    missing_fact = "MISSING_FACT"
    stale_evidence = "STALE_EVIDENCE"
    conflicting_evidence = "CONFLICTING_EVIDENCE"
    incompatible_unit = "INCOMPATIBLE_UNIT"
    unsupported_rule = "UNSUPPORTED_RULE"
    invalid_rule = "INVALID_RULE"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    fact_id: str
    source_label: str
    value: str
    unit: str | None = None
    effective_date: date | None = None


@dataclass(frozen=True, slots=True)
class MissingRequirement:
    fact: str
    reason: ReasonCode
    detail: str


@dataclass(frozen=True, slots=True)
class Fact:
    id: str
    fact_type: FactType
    concept: str
    value: Decimal | str | None = None
    unit: str | None = None
    assertion: Assertion = Assertion.present
    temporality: Temporality = Temporality.current
    effective_date: date | None = None
    source_label: str = "Manual entry"
    experiencer: str = "patient"


@dataclass(frozen=True, slots=True)
class PatientSnapshot:
    id: str
    version: str
    date_of_birth: date | None = None
    facts: tuple[Fact, ...] = ()


RuleExpression = Mapping[str, object]


def immutable_expression(value: Mapping[str, object]) -> RuleExpression:
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class Criterion:
    id: str
    kind: CriterionKind
    order: int
    source_text: str
    expression: RuleExpression
    required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "expression", immutable_expression(self.expression))


@dataclass(frozen=True, slots=True)
class ApprovedTrialVersion:
    id: str
    version: str
    criteria: tuple[Criterion, ...]
    dsl_version: str = "1.0"


@dataclass(frozen=True, slots=True)
class ScreeningContext:
    screening_date: date
    engine_version: str = "0.1.0"
    terminology_version: str = "local-1"
    unit_version: str = "units-1"


@dataclass(frozen=True, slots=True)
class CriterionEvaluation:
    criterion_id: str
    criterion_kind: CriterionKind
    criterion_order: int
    source_text: str
    required: bool
    truth: TruthValue
    result: CriterionResult
    reason_code: ReasonCode
    explanation: str
    evidence: tuple[EvidenceReference, ...] = ()
    rejected_evidence: tuple[EvidenceReference, ...] = ()
    missing: tuple[MissingRequirement, ...] = ()


@dataclass(frozen=True, slots=True)
class ScreeningResult:
    patient_snapshot_id: str
    patient_snapshot_version: str
    trial_version_id: str
    trial_version: str
    screening_date: date
    overall_state: OverallState
    evaluations: tuple[CriterionEvaluation, ...]
    engine_version: str
    dsl_version: str
    terminology_version: str
    unit_version: str
    counts: Mapping[CriterionResult, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "counts", MappingProxyType(dict(self.counts)))
