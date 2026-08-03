from __future__ import annotations

from trialsync.domain.rules import RuleFactSpec, validate_rule

FACT_SPECS = {
    "demographic.age": RuleFactSpec(numeric=True, units=("year",)),
    "condition.type2_diabetes": RuleFactSpec(numeric=False),
    "observation.hba1c": RuleFactSpec(numeric=True, units=("%",)),
}


def test_rule_validator_rejects_misspelled_operator() -> None:
    issues = validate_rule(
        {"op": "presnet", "fact": "condition.type2_diabetes"},
        fact_specs=FACT_SPECS,
    )

    assert [(issue.code, issue.path) for issue in issues] == [
        ("RULE_OPERATOR_UNSUPPORTED", "$.op")
    ]
    assert '"presnet"' in issues[0].message


def test_rule_validator_rejects_misspelled_catalog_fact() -> None:
    issues = validate_rule(
        {"op": "present", "fact": "condition.diabtes"},
        fact_specs=FACT_SPECS,
    )

    assert [(issue.code, issue.path) for issue in issues] == [
        ("RULE_FACT_UNKNOWN", "$.fact")
    ]


def test_rule_validator_rejects_misspelled_concept() -> None:
    issues = validate_rule(
        {
            "op": "concept_is",
            "fact_type": "condition",
            "concept": "type2_diabtes",
        },
        fact_specs=FACT_SPECS,
    )

    assert [(issue.code, issue.path) for issue in issues] == [
        ("RULE_FACT_UNKNOWN", "$.concept")
    ]


def test_rule_validator_checks_nested_rules_and_units() -> None:
    issues = validate_rule(
        {
            "op": "and",
            "args": [
                {"op": "present", "fact": "condition.type2_diabetes"},
                {
                    "op": "between",
                    "fact": "observation.hba1c",
                    "min": 8,
                    "max": 6,
                    "unit": "mg/dL",
                },
            ],
        },
        fact_specs=FACT_SPECS,
    )

    assert {issue.code for issue in issues} == {
        "RULE_UNIT_INCOMPATIBLE",
        "RULE_RANGE_INVALID",
    }
    assert {issue.path for issue in issues} == {
        "$.args[1].unit",
        "$.args[1]",
    }


def test_rule_validator_accepts_supported_nested_rule() -> None:
    issues = validate_rule(
        {
            "op": "within_before",
            "days": 30,
            "arg": {
                "op": "gte",
                "fact": "observation.hba1c",
                "value": 7,
                "unit": "%",
                "selection": "latest",
            },
        },
        fact_specs=FACT_SPECS,
    )

    assert issues == ()
