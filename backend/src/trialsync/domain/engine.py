from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import cast

from trialsync.domain.logic import truth_and, truth_not, truth_or
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
    RuleExpression,
    ScreeningContext,
    ScreeningResult,
    Temporality,
    TruthValue,
)

SUPPORTED_DSL_VERSION = "1.0"
SUPPORTED_OPERATORS = {
    "and",
    "or",
    "not",
    "present",
    "absent",
    "eq",
    "lt",
    "lte",
    "gt",
    "gte",
    "between",
    "concept_is",
    "concept_in",
    "current",
    "within_before",
}


@dataclass(frozen=True, slots=True)
class _Constraints:
    current_only: bool = False
    within_days: int | None = None


DEFAULT_CONSTRAINTS = _Constraints()


@dataclass(frozen=True, slots=True)
class _Outcome:
    truth: TruthValue
    reason: ReasonCode
    evidence: tuple[EvidenceReference, ...] = ()
    rejected: tuple[EvidenceReference, ...] = ()
    missing: tuple[MissingRequirement, ...] = ()


def _evidence(fact: Fact) -> EvidenceReference:
    value = fact.assertion.value if fact.value is None else str(fact.value)
    return EvidenceReference(
        fact_id=fact.id,
        source_label=fact.source_label,
        value=value,
        unit=fact.unit,
        effective_date=fact.effective_date,
    )


def _unique_evidence(items: tuple[EvidenceReference, ...]) -> tuple[EvidenceReference, ...]:
    return tuple({item.fact_id: item for item in items}.values())


def _unique_missing(items: tuple[MissingRequirement, ...]) -> tuple[MissingRequirement, ...]:
    return tuple({(item.fact, item.reason, item.detail): item for item in items}.values())


def _merge(outcomes: tuple[_Outcome, ...], truth: TruthValue) -> _Outcome:
    evidence = _unique_evidence(tuple(item for outcome in outcomes for item in outcome.evidence))
    rejected = _unique_evidence(tuple(item for outcome in outcomes for item in outcome.rejected))
    missing = _unique_missing(tuple(item for outcome in outcomes for item in outcome.missing))
    if truth is TruthValue.true:
        reason = ReasonCode.evaluated_true
    elif truth is TruthValue.false:
        reason = ReasonCode.evaluated_false
    else:
        reason = next(
            (outcome.reason for outcome in outcomes if outcome.truth is TruthValue.unknown),
            ReasonCode.missing_fact,
        )
    return _Outcome(truth, reason, evidence, rejected, missing)


def _invalid(fact: str, detail: str, reason: ReasonCode) -> _Outcome:
    return _Outcome(
        TruthValue.unknown,
        reason,
        missing=(MissingRequirement(fact=fact, reason=reason, detail=detail),),
    )


def _fact_parts(path: object) -> tuple[FactType, str] | None:
    if not isinstance(path, str) or "." not in path:
        return None
    prefix, concept = path.split(".", 1)
    try:
        return FactType(prefix), concept.strip().lower()
    except ValueError:
        return None


def _matching_facts(patient: PatientSnapshot, path: str) -> tuple[Fact, ...]:
    parts = _fact_parts(path)
    if parts is None:
        return ()
    fact_type, concept = parts
    return tuple(
        fact
        for fact in patient.facts
        if fact.fact_type is fact_type
        and fact.concept.strip().lower() == concept
        and fact.experiencer == "patient"
    )


def _apply_constraints(
    facts: tuple[Fact, ...],
    path: str,
    context: ScreeningContext,
    constraints: _Constraints,
) -> tuple[tuple[Fact, ...], tuple[EvidenceReference, ...], _Outcome | None]:
    future = tuple(
        fact
        for fact in facts
        if fact.effective_date is not None and fact.effective_date > context.screening_date
    )
    accepted = tuple(fact for fact in facts if fact not in future)
    rejected = tuple(_evidence(fact) for fact in future)
    if not accepted:
        return (), rejected, _Outcome(
            TruthValue.unknown,
            ReasonCode.missing_fact,
            rejected=rejected,
            missing=(
                MissingRequirement(
                    path,
                    ReasonCode.missing_fact,
                    "Evidence recorded after the screening date cannot be used.",
                ),
            ),
        )
    if constraints.current_only:
        current = tuple(fact for fact in accepted if fact.temporality is Temporality.current)
        rejected += tuple(_evidence(fact) for fact in accepted if fact not in current)
        if not current:
            return (), rejected, _Outcome(
                TruthValue.unknown,
                ReasonCode.missing_fact,
                rejected=rejected,
                missing=(
                    MissingRequirement(
                        path,
                        ReasonCode.missing_fact,
                        "A current patient fact is required.",
                    ),
                ),
            )
        accepted = current
    if constraints.within_days is not None:
        recent = tuple(
            fact
            for fact in accepted
            if fact.effective_date is not None
            and 0 <= (context.screening_date - fact.effective_date).days <= constraints.within_days
        )
        rejected += tuple(_evidence(fact) for fact in accepted if fact not in recent)
        if not recent:
            return (), rejected, _Outcome(
                TruthValue.unknown,
                ReasonCode.stale_evidence,
                rejected=rejected,
                missing=(
                    MissingRequirement(
                        fact=path,
                        reason=ReasonCode.stale_evidence,
                        detail=(
                            f"A value within {constraints.within_days} days before screening "
                            "is required."
                        ),
                    ),
                ),
            )
        accepted = recent
    return accepted, _unique_evidence(rejected), None


def _presence(
    patient: PatientSnapshot,
    path: str,
    context: ScreeningContext,
    constraints: _Constraints,
) -> _Outcome:
    facts = _matching_facts(patient, path)
    if not facts:
        return _invalid(
            path, "Explicit present or absent evidence is required.", ReasonCode.missing_fact
        )
    facts, constraint_rejected, constraint_error = _apply_constraints(
        facts, path, context, constraints
    )
    if constraint_error:
        return constraint_error
    present = tuple(fact for fact in facts if fact.assertion is Assertion.present)
    absent = tuple(fact for fact in facts if fact.assertion is Assertion.absent)
    unresolved = tuple(fact for fact in facts if fact.assertion is Assertion.unknown)
    if present and absent:
        return _Outcome(
            TruthValue.unknown,
            ReasonCode.conflicting_evidence,
            evidence=tuple(_evidence(fact) for fact in present + absent),
            rejected=constraint_rejected,
            missing=(
                MissingRequirement(
                    path,
                    ReasonCode.conflicting_evidence,
                    "Conflicting present and absent assertions must be resolved.",
                ),
            ),
        )
    if present:
        return _Outcome(
            TruthValue.true,
            ReasonCode.evaluated_true,
            evidence=tuple(_evidence(fact) for fact in present),
            rejected=_unique_evidence(
                constraint_rejected + tuple(_evidence(fact) for fact in unresolved)
            ),
        )
    if absent:
        return _Outcome(
            TruthValue.false,
            ReasonCode.evaluated_false,
            evidence=tuple(_evidence(fact) for fact in absent),
            rejected=_unique_evidence(
                constraint_rejected + tuple(_evidence(fact) for fact in unresolved)
            ),
        )
    return _Outcome(
        TruthValue.unknown,
        ReasonCode.missing_fact,
        rejected=_unique_evidence(
            constraint_rejected + tuple(_evidence(fact) for fact in unresolved)
        ),
        missing=(
            MissingRequirement(
                path,
                ReasonCode.missing_fact,
                "The recorded assertion is unknown.",
            ),
        ),
    )


def _age(patient: PatientSnapshot, context: ScreeningContext) -> Decimal | None:
    born = patient.date_of_birth
    if born is None or born > context.screening_date:
        return None
    years = context.screening_date.year - born.year
    if (context.screening_date.month, context.screening_date.day) < (born.month, born.day):
        years -= 1
    return Decimal(years)


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _unit_key(value: str) -> str:
    return value.strip().lower().replace(" ", "")


UNIT_ALIASES = {
    "%": "%",
    "percent": "%",
    "year": "year",
    "years": "year",
    "ml/min/1.73m2": "ml/min/1.73m2",
    "ml/min/1.73m²": "ml/min/1.73m2",
}


def _units_match(actual: str | None, expected: object) -> bool:
    if not isinstance(expected, str):
        return actual is None
    if actual is None:
        return False
    return UNIT_ALIASES.get(_unit_key(actual), _unit_key(actual)) == UNIT_ALIASES.get(
        _unit_key(expected), _unit_key(expected)
    )


def _compare(op: str, value: Decimal, expression: RuleExpression) -> bool | None:
    if op == "between":
        minimum = _decimal(expression.get("min"))
        maximum = _decimal(expression.get("max"))
        if minimum is None or maximum is None or minimum > maximum:
            return None
        return minimum <= value <= maximum
    target = _decimal(expression.get("value"))
    if target is None:
        return None
    return {
        "eq": value == target,
        "lt": value < target,
        "lte": value <= target,
        "gt": value > target,
        "gte": value >= target,
    }[op]


def _numeric(
    op: str,
    expression: RuleExpression,
    patient: PatientSnapshot,
    context: ScreeningContext,
    constraints: _Constraints,
) -> _Outcome:
    path = expression.get("fact")
    if not isinstance(path, str):
        return _invalid(
            "expression.fact", "A numeric fact path is required.", ReasonCode.invalid_rule
        )
    if path == "demographic.age":
        age = _age(patient, context)
        if age is None:
            return _invalid(
                "date_of_birth",
                "Date of birth is required to calculate age.",
                ReasonCode.missing_fact,
            )
        if not _units_match("year", expression.get("unit")):
            return _invalid(
                path, "The age rule requires a compatible year unit.", ReasonCode.incompatible_unit
            )
        age_result = _compare(op, age, expression)
        if age_result is None:
            return _invalid(path, "The numeric rule is invalid.", ReasonCode.invalid_rule)
        return _Outcome(
            TruthValue.true if age_result else TruthValue.false,
            ReasonCode.evaluated_true if age_result else ReasonCode.evaluated_false,
            evidence=(
                EvidenceReference(
                    fact_id="date_of_birth",
                    source_label="Patient snapshot",
                    value=str(age),
                    unit="year",
                    effective_date=context.screening_date,
                ),
            ),
        )
    facts = _matching_facts(patient, path)
    if not facts:
        return _invalid(path, "A numeric observation is required.", ReasonCode.missing_fact)
    facts, constraint_rejected, constraint_error = _apply_constraints(
        facts, path, context, constraints
    )
    if constraint_error:
        return constraint_error
    compatible = tuple(
        fact
        for fact in facts
        if isinstance(fact.value, Decimal)
        and fact.assertion is Assertion.present
        and _units_match(fact.unit, expression.get("unit"))
    )
    if not compatible:
        return _Outcome(
            TruthValue.unknown,
            ReasonCode.incompatible_unit,
            rejected=_unique_evidence(
                constraint_rejected + tuple(_evidence(fact) for fact in facts)
            ),
            missing=(
                MissingRequirement(
                    path,
                    ReasonCode.incompatible_unit,
                    f"A value compatible with unit {expression.get('unit')!s} is required.",
                ),
            ),
        )
    selection = expression.get("selection", "latest")
    selected = compatible
    if selection == "latest":
        dated = tuple(fact for fact in compatible if fact.effective_date is not None)
        if dated:
            latest_date = max(cast(date, fact.effective_date) for fact in dated)
            selected = tuple(fact for fact in dated if fact.effective_date == latest_date)
        elif len(compatible) > 1:
            return _invalid(
                path,
                "Effective dates are required to select the latest value.",
                ReasonCode.conflicting_evidence,
            )
    elif selection != "any":
        return _invalid(
            path, f"Selection {selection!s} is unsupported.", ReasonCode.unsupported_rule
        )
    comparison_results = tuple(
        _compare(op, cast(Decimal, fact.value), expression) for fact in selected
    )
    if any(value is None for value in comparison_results):
        return _invalid(path, "The numeric rule is invalid.", ReasonCode.invalid_rule)
    if selection == "latest" and len({fact.value for fact in selected}) > 1:
        return _Outcome(
            TruthValue.unknown,
            ReasonCode.conflicting_evidence,
            evidence=tuple(_evidence(fact) for fact in selected),
            missing=(
                MissingRequirement(
                    path, ReasonCode.conflicting_evidence, "Latest values conflict."
                ),
            ),
        )
    truth = TruthValue.true if any(comparison_results) else TruthValue.false
    return _Outcome(
        truth,
        ReasonCode.evaluated_true if truth is TruthValue.true else ReasonCode.evaluated_false,
        evidence=tuple(_evidence(fact) for fact in selected),
        rejected=_unique_evidence(
            constraint_rejected
            + tuple(_evidence(fact) for fact in facts if fact not in selected)
        ),
    )


def _evaluate(
    expression: RuleExpression,
    patient: PatientSnapshot,
    context: ScreeningContext,
    constraints: _Constraints = DEFAULT_CONSTRAINTS,
) -> _Outcome:
    op_value = expression.get("op")
    if not isinstance(op_value, str) or op_value not in SUPPORTED_OPERATORS:
        return _invalid(
            "expression", "The rule operator is unsupported.", ReasonCode.unsupported_rule
        )
    op = op_value
    if op in {"and", "or"}:
        args = expression.get("args")
        if not isinstance(args, list | tuple) or not args:
            return _invalid(
                "expression.args", "Logical rules require arguments.", ReasonCode.invalid_rule
            )
        if not all(isinstance(arg, Mapping) for arg in args):
            return _invalid(
                "expression.args", "Every logical argument must be a rule.", ReasonCode.invalid_rule
            )
        outcomes = tuple(_evaluate(arg, patient, context, constraints) for arg in args)
        truth = (
            truth_and(item.truth for item in outcomes)
            if op == "and"
            else truth_or(item.truth for item in outcomes)
        )
        return _merge(outcomes, truth)
    if op == "not":
        arg = expression.get("arg")
        if not isinstance(arg, Mapping):
            return _invalid("expression.arg", "NOT requires one rule.", ReasonCode.invalid_rule)
        outcome = _evaluate(arg, patient, context, constraints)
        truth = truth_not(outcome.truth)
        reason = (
            ReasonCode.evaluated_true
            if truth is TruthValue.true
            else ReasonCode.evaluated_false
            if truth is TruthValue.false
            else outcome.reason
        )
        return _Outcome(truth, reason, outcome.evidence, outcome.rejected, outcome.missing)
    if op in {"current", "within_before"}:
        arg = expression.get("arg")
        if not isinstance(arg, Mapping):
            return _invalid(
                "expression.arg", f"{op} requires one nested rule.", ReasonCode.invalid_rule
            )
        if op == "current":
            nested = _Constraints(current_only=True, within_days=constraints.within_days)
        else:
            days = expression.get("days")
            if not isinstance(days, int) or isinstance(days, bool) or days < 0:
                return _invalid(
                    "expression.days",
                    "A non-negative day window is required.",
                    ReasonCode.invalid_rule,
                )
            nested = _Constraints(current_only=constraints.current_only, within_days=days)
        return _evaluate(arg, patient, context, nested)
    if op in {"present", "absent"}:
        path = expression.get("fact")
        if not isinstance(path, str):
            return _invalid("expression.fact", "A fact path is required.", ReasonCode.invalid_rule)
        outcome = _presence(patient, path, context, constraints)
        if op == "absent":
            truth = truth_not(outcome.truth)
            reason = (
                outcome.reason
                if truth is TruthValue.unknown
                else (
                    ReasonCode.evaluated_true
                    if truth is TruthValue.true
                    else ReasonCode.evaluated_false
                )
            )
            return _Outcome(truth, reason, outcome.evidence, outcome.rejected, outcome.missing)
        return outcome
    if op in {"eq", "lt", "lte", "gt", "gte", "between"}:
        return _numeric(op, expression, patient, context, constraints)
    if op == "concept_is":
        fact_type = expression.get("fact_type")
        concept = expression.get("concept")
        if not isinstance(fact_type, str) or not isinstance(concept, str):
            return _invalid(
                "expression",
                "Concept rules require fact_type and concept.",
                ReasonCode.invalid_rule,
            )
        return _presence(patient, f"{fact_type}.{concept}", context, constraints)
    if op == "concept_in":
        fact_type = expression.get("fact_type")
        concepts = expression.get("concepts")
        if (
            not isinstance(fact_type, str)
            or not isinstance(concepts, list | tuple)
            or not concepts
        ):
            return _invalid(
                "expression",
                "Concept-in requires a fact type and concepts.",
                ReasonCode.invalid_rule,
            )
        if not all(isinstance(concept, str) for concept in concepts):
            return _invalid(
                "expression.concepts", "Every concept must be text.", ReasonCode.invalid_rule
            )
        outcomes = tuple(
            _presence(patient, f"{fact_type}.{concept}", context, constraints)
            for concept in concepts
        )
        return _merge(outcomes, truth_or(outcome.truth for outcome in outcomes))
    return _invalid("expression", "The rule operator is unsupported.", ReasonCode.unsupported_rule)


def _criterion_result(kind: CriterionKind, truth: TruthValue) -> CriterionResult:
    if truth is TruthValue.unknown:
        return CriterionResult.unknown
    if kind is CriterionKind.inclusion:
        return CriterionResult.pass_ if truth is TruthValue.true else CriterionResult.fail
    return CriterionResult.fail if truth is TruthValue.true else CriterionResult.pass_


def _explanation(criterion: Criterion, result: CriterionResult, outcome: _Outcome) -> str:
    evidence_ids = ", ".join(item.fact_id for item in outcome.evidence)
    if result is CriterionResult.unknown:
        needed = "; ".join(item.detail for item in outcome.missing)
        return f"Criterion {criterion.id} is unknown: {needed or outcome.reason.value}."
    basis = f" using evidence {evidence_ids}" if evidence_ids else ""
    return f"Criterion {criterion.id} {result.value}ed{basis} ({outcome.reason.value})."


def _evaluate_criterion(
    criterion: Criterion,
    patient: PatientSnapshot,
    trial: ApprovedTrialVersion,
    context: ScreeningContext,
) -> CriterionEvaluation:
    outcome = (
        _evaluate(criterion.expression, patient, context)
        if trial.dsl_version == SUPPORTED_DSL_VERSION
        else _invalid(
            "dsl_version",
            f"DSL version {trial.dsl_version} is unsupported.",
            ReasonCode.unsupported_rule,
        )
    )
    result = _criterion_result(criterion.kind, outcome.truth)
    return CriterionEvaluation(
        criterion_id=criterion.id,
        criterion_kind=criterion.kind,
        criterion_order=criterion.order,
        source_text=criterion.source_text,
        required=criterion.required,
        truth=outcome.truth,
        result=result,
        reason_code=outcome.reason,
        explanation=_explanation(criterion, result, outcome),
        evidence=outcome.evidence,
        rejected_evidence=outcome.rejected,
        missing=outcome.missing,
    )


def screen(
    patient: PatientSnapshot,
    trial: ApprovedTrialVersion,
    context: ScreeningContext,
) -> ScreeningResult:
    """Evaluate every criterion without database, network, model, clock, or mutable state."""
    evaluations = tuple(
        _evaluate_criterion(criterion, patient, trial, context)
        for criterion in sorted(trial.criteria, key=lambda item: (item.order, item.id))
    )
    required = tuple(item for item in evaluations if item.required)
    if any(item.result is CriterionResult.fail for item in required):
        overall = OverallState.likely_ineligible
    elif required and all(item.result is CriterionResult.pass_ for item in required):
        overall = OverallState.potentially_eligible
    else:
        overall = OverallState.needs_review
    counts = {
        result: sum(item.result is result for item in evaluations) for result in CriterionResult
    }
    return ScreeningResult(
        patient_snapshot_id=patient.id,
        patient_snapshot_version=patient.version,
        trial_version_id=trial.id,
        trial_version=trial.version,
        screening_date=context.screening_date,
        overall_state=overall,
        evaluations=evaluations,
        engine_version=context.engine_version,
        dsl_version=trial.dsl_version,
        terminology_version=context.terminology_version,
        unit_version=context.unit_version,
        counts=counts,
    )
