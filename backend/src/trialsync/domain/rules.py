from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

SUPPORTED_DSL_VERSION = "1.0"
SUPPORTED_OPERATORS = frozenset(
    {
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
)

UNIT_ALIASES = {
    "%": "%",
    "percent": "%",
    "year": "year",
    "years": "year",
    "ml/min/1.73m2": "ml/min/1.73m2",
    "ml/min/1.73m²": "ml/min/1.73m2",
}


@dataclass(frozen=True, slots=True)
class RuleFactSpec:
    """Catalog-backed information needed to validate a fact path."""

    numeric: bool
    units: tuple[str, ...] = ()
    screening_supported: bool = True


@dataclass(frozen=True, slots=True)
class RuleValidationIssue:
    code: str
    path: str
    message: str


def _unit_key(value: str) -> str:
    return value.strip().lower().replace(" ", "")


def units_match(actual: str | None, expected: object) -> bool:
    if not isinstance(expected, str) or actual is None:
        return False
    return UNIT_ALIASES.get(_unit_key(actual), _unit_key(actual)) == UNIT_ALIASES.get(
        _unit_key(expected), _unit_key(expected)
    )


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _issue(issues: list[RuleValidationIssue], code: str, path: str, message: str) -> None:
    issues.append(RuleValidationIssue(code=code, path=path, message=message))


def _fact_path(
    value: object,
    *,
    path: str,
    issues: list[RuleValidationIssue],
    fact_specs: Mapping[str, RuleFactSpec] | None,
) -> tuple[str | None, RuleFactSpec | None]:
    if not isinstance(value, str) or not value.strip():
        _issue(issues, "RULE_FACT_INVALID", path, "A fact path is required.")
        return None, None
    fact = value.strip().lower()
    if value.strip() != fact:
        _issue(
            issues,
            "RULE_FACT_INVALID",
            path,
            f'Fact path "{value}" must use lowercase canonical identifiers.',
        )
        return None, None
    if "." not in fact or fact.startswith(".") or fact.endswith("."):
        _issue(
            issues,
            "RULE_FACT_INVALID",
            path,
            'Use a fact path such as "condition.diabetes".',
        )
        return None, None
    fact_type, concept = fact.split(".", 1)
    if fact_type not in {"demographic", "condition", "medication", "observation"} or not concept:
        _issue(issues, "RULE_FACT_INVALID", path, f'Fact path "{value}" is not supported.')
        return None, None
    if fact_specs is None:
        return fact, None
    spec = fact_specs.get(fact)
    if spec is None:
        _issue(
            issues,
            "RULE_FACT_UNKNOWN",
            path,
            f'Fact "{value}" is not present in the active clinical catalog.',
        )
        return fact, None
    if not spec.screening_supported:
        _issue(
            issues,
            "RULE_FACT_NOT_SCREENING_SUPPORTED",
            path,
            f'Fact "{value}" is available for records but not trial screening.',
        )
    return fact, spec


def _check_fields[RuleField](
    expression: Mapping[RuleField, object],
    *,
    allowed: set[str],
    path: str,
    issues: list[RuleValidationIssue],
) -> None:
    for key in expression:
        if not isinstance(key, str):
            _issue(issues, "RULE_FIELD_INVALID", path, "Rule field names must be text.")
        elif key not in allowed:
            _issue(
                issues,
                "RULE_FIELD_UNEXPECTED",
                f"{path}.{key}",
                f'Field "{key}" is not used by this rule operator.',
            )


def _nested_rule(
    value: object,
    *,
    path: str,
    issues: list[RuleValidationIssue],
    fact_specs: Mapping[str, RuleFactSpec] | None,
    depth: int,
) -> None:
    if not isinstance(value, Mapping):
        _issue(issues, "RULE_NESTED_INVALID", path, "A nested rule object is required.")
        return
    _validate_expression(value, path=path, issues=issues, fact_specs=fact_specs, depth=depth + 1)


def _numeric_rule(
    expression: Mapping[str, object],
    *,
    op: str,
    path: str,
    issues: list[RuleValidationIssue],
    fact_specs: Mapping[str, RuleFactSpec] | None,
) -> None:
    fact, spec = _fact_path(
        expression.get("fact"),
        path=f"{path}.fact",
        issues=issues,
        fact_specs=fact_specs,
    )
    expected_units: tuple[str, ...]
    if fact == "demographic.age":
        expected_units = ("year",)
    elif spec is not None:
        if not spec.numeric:
            _issue(
                issues,
                "RULE_FACT_NOT_NUMERIC",
                f"{path}.fact",
                f'Fact "{fact}" does not support numeric comparison.',
            )
        expected_units = spec.units
    else:
        expected_units = ()

    unit = expression.get("unit")
    if not isinstance(unit, str) or not unit.strip():
        _issue(issues, "RULE_UNIT_REQUIRED", f"{path}.unit", "A comparison unit is required.")
    elif expected_units and not any(units_match(unit, expected) for expected in expected_units):
        expected = ", ".join(expected_units)
        _issue(
            issues,
            "RULE_UNIT_INCOMPATIBLE",
            f"{path}.unit",
            f'Unit "{unit}" is incompatible; expected {expected}.',
        )

    selection = expression.get("selection", "latest")
    if selection not in {"latest", "any"}:
        _issue(
            issues,
            "RULE_SELECTION_INVALID",
            f"{path}.selection",
            'Selection must be "latest" or "any".',
        )

    if op == "between":
        minimum = _decimal(expression.get("min"))
        maximum = _decimal(expression.get("max"))
        if minimum is None:
            _issue(issues, "RULE_VALUE_INVALID", f"{path}.min", "A numeric minimum is required.")
        if maximum is None:
            _issue(issues, "RULE_VALUE_INVALID", f"{path}.max", "A numeric maximum is required.")
        if minimum is not None and maximum is not None and minimum > maximum:
            _issue(
                issues,
                "RULE_RANGE_INVALID",
                path,
                "The minimum must be less than or equal to the maximum.",
            )
        return

    if _decimal(expression.get("value")) is None:
        _issue(
            issues,
            "RULE_VALUE_INVALID",
            f"{path}.value",
            "A numeric comparison value is required.",
        )


def _validate_expression(
    expression: Mapping[str, object],
    *,
    path: str,
    issues: list[RuleValidationIssue],
    fact_specs: Mapping[str, RuleFactSpec] | None,
    depth: int,
) -> None:
    if depth > 32:
        _issue(issues, "RULE_DEPTH_EXCEEDED", path, "Rule nesting cannot exceed 32 levels.")
        return
    op_value = expression.get("op")
    if not isinstance(op_value, str):
        _issue(issues, "RULE_OPERATOR_INVALID", f"{path}.op", "A rule operator is required.")
        return
    op = op_value.strip().lower()
    allowed_fields: dict[str, set[str]] = {
        "and": {"op", "args"},
        "or": {"op", "args"},
        "not": {"op", "arg"},
        "present": {"op", "fact"},
        "absent": {"op", "fact"},
        "eq": {"op", "fact", "value", "unit", "selection"},
        "lt": {"op", "fact", "value", "unit", "selection"},
        "lte": {"op", "fact", "value", "unit", "selection"},
        "gt": {"op", "fact", "value", "unit", "selection"},
        "gte": {"op", "fact", "value", "unit", "selection"},
        "between": {"op", "fact", "min", "max", "unit", "selection"},
        "concept_is": {"op", "fact_type", "concept"},
        "concept_in": {"op", "fact_type", "concepts"},
        "current": {"op", "arg"},
        "within_before": {"op", "days", "arg"},
    }
    if op_value != op:
        _issue(
            issues,
            "RULE_OPERATOR_INVALID",
            f"{path}.op",
            f'Operator "{op_value}" must use lowercase canonical spelling.',
        )
    if op not in SUPPORTED_OPERATORS:
        _issue(
            issues,
            "RULE_OPERATOR_UNSUPPORTED",
            f"{path}.op",
            f'Unsupported rule operator "{op_value}".',
        )
        return
    _check_fields(expression, allowed=allowed_fields[op], path=path, issues=issues)

    if op in {"and", "or"}:
        args = expression.get("args")
        if not isinstance(args, list | tuple) or not args:
            _issue(
                issues,
                "RULE_ARGS_INVALID",
                f"{path}.args",
                "At least one nested rule is required.",
            )
            return
        for index, arg in enumerate(args):
            _nested_rule(
                arg,
                path=f"{path}.args[{index}]",
                issues=issues,
                fact_specs=fact_specs,
                depth=depth,
            )
        return

    if op in {"not", "current"}:
        _nested_rule(
            expression.get("arg"),
            path=f"{path}.arg",
            issues=issues,
            fact_specs=fact_specs,
            depth=depth,
        )
        return

    if op == "within_before":
        days = expression.get("days")
        if not isinstance(days, int) or isinstance(days, bool) or days < 0:
            _issue(
                issues,
                "RULE_DAYS_INVALID",
                f"{path}.days",
                "The day window must be a non-negative integer.",
            )
        _nested_rule(
            expression.get("arg"),
            path=f"{path}.arg",
            issues=issues,
            fact_specs=fact_specs,
            depth=depth,
        )
        return

    if op in {"present", "absent"}:
        _fact_path(
            expression.get("fact"),
            path=f"{path}.fact",
            issues=issues,
            fact_specs=fact_specs,
        )
        return

    if op in {"eq", "lt", "lte", "gt", "gte", "between"}:
        _numeric_rule(
            expression,
            op=op,
            path=path,
            issues=issues,
            fact_specs=fact_specs,
        )
        return

    if op in {"concept_is", "concept_in"}:
        fact_type = expression.get("fact_type")
        if not isinstance(fact_type, str) or fact_type.strip().lower() not in {
            "demographic",
            "condition",
            "medication",
            "observation",
        }:
            _issue(
                issues,
                "RULE_FACT_TYPE_INVALID",
                f"{path}.fact_type",
                "A supported fact type is required.",
            )
            return
        if fact_type.strip() != fact_type.strip().lower():
            _issue(
                issues,
                "RULE_FACT_TYPE_INVALID",
                f"{path}.fact_type",
                "Fact types must use lowercase canonical identifiers.",
            )
        if op == "concept_is":
            concepts = [expression.get("concept")]
        else:
            raw_concepts = expression.get("concepts")
            if not isinstance(raw_concepts, list | tuple) or not raw_concepts:
                _issue(
                    issues,
                    "RULE_CONCEPTS_INVALID",
                    f"{path}.concepts",
                    "At least one concept is required.",
                )
                return
            concepts = list(raw_concepts)
        for index, concept in enumerate(concepts):
            if not isinstance(concept, str) or not concept.strip():
                field = "concept" if op == "concept_is" else f"concepts[{index}]"
                _issue(issues, "RULE_CONCEPT_INVALID", f"{path}.{field}", "A concept is required.")
                continue
            _fact_path(
                f"{fact_type}.{concept}",
                path=f"{path}.concept" if op == "concept_is" else f"{path}.concepts[{index}]",
                issues=issues,
                fact_specs=fact_specs,
            )


def validate_rule(
    expression: object,
    *,
    fact_specs: Mapping[str, RuleFactSpec] | None = None,
) -> tuple[RuleValidationIssue, ...]:
    """Return all structural and catalog errors in a normalized rule expression."""

    if not isinstance(expression, Mapping):
        return (
            RuleValidationIssue(
                code="RULE_OBJECT_INVALID",
                path="$",
                message="A normalized rule object is required.",
            ),
        )
    issues: list[RuleValidationIssue] = []
    _validate_expression(expression, path="$", issues=issues, fact_specs=fact_specs, depth=0)
    return tuple(issues)
