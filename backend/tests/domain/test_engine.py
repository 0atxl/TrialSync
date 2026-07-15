from __future__ import annotations

import ast
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from trialsync.domain import (
    ApprovedTrialVersion,
    Assertion,
    Criterion,
    CriterionKind,
    CriterionResult,
    Fact,
    FactType,
    OverallState,
    PatientSnapshot,
    ReasonCode,
    ScreeningContext,
    Temporality,
    TruthValue,
    screen,
)

SCREENING_DATE = date(2026, 7, 15)
CONTEXT = ScreeningContext(screening_date=SCREENING_DATE, engine_version="test-engine")


def criterion(
    expression: dict[str, Any],
    *,
    kind: CriterionKind = CriterionKind.inclusion,
    criterion_id: str = "criterion-1",
    order: int = 1,
    required: bool = True,
) -> Criterion:
    return Criterion(
        id=criterion_id,
        kind=kind,
        order=order,
        source_text=f"Synthetic rule {criterion_id}",
        expression=expression,
        required=required,
    )


def evaluate(
    patient: PatientSnapshot,
    *criteria: Criterion,
    dsl_version: str = "1.0",
):
    trial = ApprovedTrialVersion(
        id="trial-version-1",
        version="1",
        criteria=tuple(criteria),
        dsl_version=dsl_version,
    )
    return screen(patient, trial, CONTEXT)


def patient(*facts: Fact, dob: date | None = None) -> PatientSnapshot:
    return PatientSnapshot(id="snapshot-1", version="1", date_of_birth=dob, facts=facts)


def fact(
    fact_id: str,
    fact_type: FactType,
    concept: str,
    *,
    value: Decimal | str | None = None,
    unit: str | None = None,
    assertion: Assertion = Assertion.present,
    effective_date: date | None = None,
    temporality: Temporality = Temporality.current,
    experiencer: str = "patient",
) -> Fact:
    return Fact(
        id=fact_id,
        fact_type=fact_type,
        concept=concept,
        value=value,
        unit=unit,
        assertion=assertion,
        effective_date=effective_date,
        temporality=temporality,
        experiencer=experiencer,
        source_label="Synthetic fixture",
    )


AGE_RULE = criterion(
    {"op": "between", "fact": "demographic.age", "min": 18, "max": 75, "unit": "year"}
)


@pytest.mark.parametrize(
    ("dob", "expected"),
    [
        (date(2008, 7, 15), CriterionResult.pass_),
        (date(2008, 7, 16), CriterionResult.fail),
        (date(1951, 7, 15), CriterionResult.pass_),
        (date(1950, 7, 15), CriterionResult.fail),
        (date(1980, 2, 29), CriterionResult.pass_),
    ],
)
def test_age_boundaries_use_completed_years(dob: date, expected: CriterionResult) -> None:
    result = evaluate(patient(dob=dob), AGE_RULE)
    assert result.evaluations[0].result is expected


def test_missing_dob_is_unknown_with_requirement() -> None:
    result = evaluate(patient(), AGE_RULE)
    evaluation = result.evaluations[0]
    assert evaluation.result is CriterionResult.unknown
    assert evaluation.reason_code is ReasonCode.missing_fact
    assert evaluation.missing[0].fact == "date_of_birth"
    assert result.overall_state is OverallState.needs_review


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("6.5"), CriterionResult.pass_),
        (Decimal("8.0"), CriterionResult.pass_),
        (Decimal("8.1"), CriterionResult.fail),
    ],
)
def test_hba1c_numeric_range(value: Decimal, expected: CriterionResult) -> None:
    rule = criterion(
        {
            "op": "between",
            "fact": "observation.hba1c",
            "min": "6.5",
            "max": "8.0",
            "unit": "%",
            "selection": "latest",
        }
    )
    result = evaluate(
        patient(
            fact(
                "hba1c-1",
                FactType.observation,
                "hba1c",
                value=value,
                unit="percent",
                effective_date=SCREENING_DATE - timedelta(days=5),
            )
        ),
        rule,
    )
    assert result.evaluations[0].result is expected
    assert result.evaluations[0].evidence[0].fact_id == "hba1c-1"


@pytest.mark.parametrize(
    ("value", "age_days", "expected", "reason"),
    [
        (Decimal("28"), 10, CriterionResult.fail, ReasonCode.evaluated_true),
        (Decimal("72"), 10, CriterionResult.pass_, ReasonCode.evaluated_false),
        (Decimal("72"), 240, CriterionResult.unknown, ReasonCode.stale_evidence),
    ],
)
def test_egfr_exclusion_requires_recent_evidence(
    value: Decimal,
    age_days: int,
    expected: CriterionResult,
    reason: ReasonCode,
) -> None:
    rule = criterion(
        {
            "op": "within_before",
            "days": 30,
            "arg": {
                "op": "lt",
                "fact": "observation.egfr",
                "value": 30,
                "unit": "mL/min/1.73m2",
                "selection": "latest",
            },
        },
        kind=CriterionKind.exclusion,
    )
    result = evaluate(
        patient(
            fact(
                "egfr-1",
                FactType.observation,
                "egfr",
                value=value,
                unit="mL/min/1.73m²",
                effective_date=SCREENING_DATE - timedelta(days=age_days),
            )
        ),
        rule,
    )
    assert result.evaluations[0].result is expected
    assert result.evaluations[0].reason_code is reason


def test_no_egfr_is_unknown_not_exclusion_pass() -> None:
    rule = criterion(
        {
            "op": "lt",
            "fact": "observation.egfr",
            "value": 30,
            "unit": "mL/min/1.73m2",
        },
        kind=CriterionKind.exclusion,
    )
    assert evaluate(patient(), rule).evaluations[0].result is CriterionResult.unknown


def test_explicit_diagnosis_absence_differs_from_missing_information() -> None:
    rule = criterion({"op": "present", "fact": "condition.type2_diabetes"})
    absent = patient(
        fact(
            "diagnosis-negative",
            FactType.condition,
            "type2_diabetes",
            assertion=Assertion.absent,
        )
    )
    assert evaluate(absent, rule).evaluations[0].result is CriterionResult.fail
    assert evaluate(patient(), rule).evaluations[0].result is CriterionResult.unknown


def test_type1_does_not_satisfy_type2_concept() -> None:
    rule = criterion({"op": "present", "fact": "condition.type2_diabetes"})
    type1 = patient(fact("dx-1", FactType.condition, "type1_diabetes"))
    assert evaluate(type1, rule).evaluations[0].result is CriterionResult.unknown


def test_exclusion_conversion_requires_explicit_negative_evidence() -> None:
    rule = criterion(
        {"op": "present", "fact": "condition.pregnancy"},
        kind=CriterionKind.exclusion,
    )
    triggered = patient(fact("pregnant", FactType.condition, "pregnancy"))
    negative = patient(
        fact("not-pregnant", FactType.condition, "pregnancy", assertion=Assertion.absent)
    )
    assert evaluate(triggered, rule).evaluations[0].result is CriterionResult.fail
    assert evaluate(negative, rule).evaluations[0].result is CriterionResult.pass_
    assert evaluate(patient(), rule).evaluations[0].result is CriterionResult.unknown


def test_absent_operator_requires_explicit_absence() -> None:
    rule = criterion({"op": "absent", "fact": "medication.insulin"})
    explicit_absence = patient(
        fact("no-insulin", FactType.medication, "insulin", assertion=Assertion.absent)
    )
    assert evaluate(explicit_absence, rule).evaluations[0].result is CriterionResult.pass_
    assert evaluate(patient(), rule).evaluations[0].result is CriterionResult.unknown


def test_concept_operators_use_exact_reviewed_concepts() -> None:
    exact = criterion(
        {"op": "concept_is", "fact_type": "condition", "concept": "type2_diabetes"}
    )
    one_of = criterion(
        {
            "op": "concept_in",
            "fact_type": "medication",
            "concepts": ["metformin", "semaglutide"],
        },
        criterion_id="medication-set",
        order=2,
    )
    snapshot = patient(
        fact("dx", FactType.condition, "type2_diabetes"),
        fact("med", FactType.medication, "semaglutide"),
    )
    result = evaluate(snapshot, exact, one_of)
    assert [item.result for item in result.evaluations] == [
        CriterionResult.pass_,
        CriterionResult.pass_,
    ]


def test_family_history_is_not_patient_evidence() -> None:
    rule = criterion({"op": "present", "fact": "condition.asthma"})
    family_fact = patient(
        fact("family-asthma", FactType.condition, "asthma", experiencer="family")
    )
    assert evaluate(family_fact, rule).evaluations[0].result is CriterionResult.unknown


def test_logical_expression_propagates_unknown() -> None:
    rule = criterion(
        {
            "op": "and",
            "args": [
                {"op": "present", "fact": "condition.type2_diabetes"},
                {
                    "op": "not",
                    "arg": {"op": "present", "fact": "medication.insulin"},
                },
            ],
        }
    )
    snapshot = patient(fact("dx", FactType.condition, "type2_diabetes"))
    assert evaluate(snapshot, rule).evaluations[0].truth is TruthValue.unknown


def test_current_rejects_historical_fact() -> None:
    rule = criterion(
        {
            "op": "current",
            "arg": {"op": "present", "fact": "medication.metformin"},
        }
    )
    snapshot = patient(
        fact(
            "old-med",
            FactType.medication,
            "metformin",
            temporality=Temporality.historical,
        )
    )
    evaluation = evaluate(snapshot, rule).evaluations[0]
    assert evaluation.result is CriterionResult.unknown
    assert evaluation.reason_code is ReasonCode.missing_fact


def test_future_fact_is_rejected_for_historical_reproducibility() -> None:
    rule = criterion({"op": "present", "fact": "condition.asthma"})
    snapshot = patient(
        fact(
            "future-asthma",
            FactType.condition,
            "asthma",
            effective_date=SCREENING_DATE + timedelta(days=1),
        )
    )
    evaluation = evaluate(snapshot, rule).evaluations[0]
    assert evaluation.result is CriterionResult.unknown
    assert evaluation.rejected_evidence[0].fact_id == "future-asthma"


def test_conflicting_assertions_are_unknown() -> None:
    rule = criterion({"op": "present", "fact": "condition.asthma"})
    snapshot = patient(
        fact("asthma-positive", FactType.condition, "asthma"),
        fact("asthma-negative", FactType.condition, "asthma", assertion=Assertion.absent),
    )
    evaluation = evaluate(snapshot, rule).evaluations[0]
    assert evaluation.result is CriterionResult.unknown
    assert evaluation.reason_code is ReasonCode.conflicting_evidence
    assert {item.fact_id for item in evaluation.evidence} == {
        "asthma-positive",
        "asthma-negative",
    }


def test_conflicting_latest_numeric_values_are_unknown() -> None:
    rule = criterion(
        {"op": "gte", "fact": "observation.hba1c", "value": 6, "unit": "%"}
    )
    snapshot = patient(
        fact(
            "lab-a",
            FactType.observation,
            "hba1c",
            value=Decimal("6.5"),
            unit="%",
            effective_date=SCREENING_DATE,
        ),
        fact(
            "lab-b",
            FactType.observation,
            "hba1c",
            value=Decimal("7.2"),
            unit="%",
            effective_date=SCREENING_DATE,
        ),
    )
    evaluation = evaluate(snapshot, rule).evaluations[0]
    assert evaluation.result is CriterionResult.unknown
    assert evaluation.reason_code is ReasonCode.conflicting_evidence


def test_any_numeric_selection_is_true_when_any_compatible_value_matches() -> None:
    rule = criterion(
        {
            "op": "gte",
            "fact": "observation.hba1c",
            "value": 8,
            "unit": "%",
            "selection": "any",
        }
    )
    snapshot = patient(
        fact("lab-low", FactType.observation, "hba1c", value=Decimal("7"), unit="%"),
        fact("lab-high", FactType.observation, "hba1c", value=Decimal("8.2"), unit="%"),
    )
    assert evaluate(snapshot, rule).evaluations[0].result is CriterionResult.pass_


def test_incompatible_unit_is_unknown() -> None:
    rule = criterion(
        {"op": "gte", "fact": "observation.hba1c", "value": 6.5, "unit": "%"}
    )
    snapshot = patient(
        fact(
            "lab-mmol",
            FactType.observation,
            "hba1c",
            value=Decimal("48"),
            unit="mmol/mol",
        )
    )
    evaluation = evaluate(snapshot, rule).evaluations[0]
    assert evaluation.result is CriterionResult.unknown
    assert evaluation.reason_code is ReasonCode.incompatible_unit
    assert evaluation.rejected_evidence[0].fact_id == "lab-mmol"


def test_unsupported_rule_and_dsl_version_are_unknown() -> None:
    unsupported = criterion({"op": "semantic_similarity", "text": "looks eligible"})
    evaluation = evaluate(patient(), unsupported).evaluations[0]
    assert evaluation.result is CriterionResult.unknown
    assert evaluation.reason_code is ReasonCode.unsupported_rule
    version_evaluation = evaluate(patient(), AGE_RULE, dsl_version="99").evaluations[0]
    assert version_evaluation.reason_code is ReasonCode.unsupported_rule


def test_overall_state_uses_required_criterion_policy_and_returns_every_result() -> None:
    passed = criterion(
        {"op": "present", "fact": "condition.type2_diabetes"},
        criterion_id="required-pass",
        order=1,
    )
    failed = criterion(
        {"op": "present", "fact": "condition.type1_diabetes"},
        criterion_id="required-fail",
        order=2,
    )
    optional_unknown = criterion(
        {"op": "present", "fact": "medication.metformin"},
        criterion_id="optional",
        order=3,
        required=False,
    )
    snapshot = patient(
        fact("type2", FactType.condition, "type2_diabetes"),
        fact("not-type1", FactType.condition, "type1_diabetes", assertion=Assertion.absent),
    )
    result = evaluate(snapshot, optional_unknown, failed, passed)
    assert result.overall_state is OverallState.likely_ineligible
    assert [item.criterion_id for item in result.evaluations] == [
        "required-pass",
        "required-fail",
        "optional",
    ]
    assert len(result.evaluations) == 3


def test_all_required_pass_is_potentially_eligible() -> None:
    inclusion = criterion({"op": "present", "fact": "condition.type2_diabetes"})
    exclusion = criterion(
        {"op": "present", "fact": "condition.type1_diabetes"},
        kind=CriterionKind.exclusion,
        criterion_id="exclusion",
        order=2,
    )
    snapshot = patient(
        fact("type2", FactType.condition, "type2_diabetes"),
        fact("no-type1", FactType.condition, "type1_diabetes", assertion=Assertion.absent),
    )
    result = evaluate(snapshot, inclusion, exclusion)
    assert result.overall_state is OverallState.potentially_eligible
    assert result.counts[CriterionResult.pass_] == 2


def test_result_is_deterministic_and_contains_reproducible_metadata() -> None:
    snapshot = patient(dob=date(1985, 1, 1))
    first = evaluate(snapshot, AGE_RULE)
    second = evaluate(snapshot, AGE_RULE)
    assert first == second
    assert first.engine_version == "test-engine"
    assert first.dsl_version == "1.0"
    assert first.patient_snapshot_id == "snapshot-1"
    assert "Synthetic rule criterion-1" in first.evaluations[0].explanation


def test_domain_package_has_no_forbidden_framework_or_clock_imports() -> None:
    domain_path = Path(__file__).parents[2] / "src" / "trialsync" / "domain"
    forbidden = {"fastapi", "sqlalchemy", "psycopg", "groq", "torch", "time"}
    imported: set[str] = set()
    for source_path in domain_path.glob("*.py"):
        tree = ast.parse(source_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(forbidden)
