from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trialsync.db.models import Assertion, FactType
from trialsync.demo import _admin_patients, _patients
from trialsync.imports.parser import extract_patient_candidates, extract_text_input
from trialsync.patient_data import (
    INITIAL_CATALOG_CONCEPTS,
    INITIAL_OBSERVATION_UNITS,
    BiologicalSex,
    NumericObservationValue,
    PatientDataErrorCode,
    PatientDataWarningCode,
    PatientFactCatalogEntry,
    PatientFactCatalogResponse,
    PatientFactCreateRequest,
)


def test_pd0_reserves_canonical_sex_and_error_contracts() -> None:
    assert [value.value for value in BiologicalSex] == ["male", "female"]
    assert {value.value for value in PatientDataErrorCode} == {
        "PATIENT_SEX_INVALID",
        "PATIENT_DOB_IN_FUTURE",
        "PATIENT_PREGNANCY_SEX_CONFLICT",
        "PATIENT_FACT_DUPLICATE",
        "PATIENT_FACT_CONFLICT",
        "PATIENT_FACT_UNSUPPORTED",
        "PATIENT_FACT_VALUE_INVALID",
        "PATIENT_RECORD_STALE",
        "PATIENT_FACT_REMOVAL_REASON_REQUIRED",
        "PATIENT_FACT_ALREADY_REMOVED",
        "PATIENT_FACT_RESTORE_CONFLICT",
    }
    assert [value.value for value in PatientDataWarningCode] == [
        "PATIENT_SEX_NOT_RECORDED_FOR_PREGNANCY"
    ]


def test_catalog_response_contract_validates_semantic_shape() -> None:
    entry = PatientFactCatalogEntry(
        key="hba1c",
        fact_type=FactType.observation,
        concept="hba1c",
        display_label="HbA1c",
        group="observations",
        input_kind="numeric",
        allowed_assertions=(Assertion.present, Assertion.unknown),
        fixed_unit="%",
        effective_date_required=True,
        screening_supported=True,
        help_text="Most recent synthetic HbA1c result.",
        display_order=1,
    )
    response = PatientFactCatalogResponse(entries=(entry,))

    assert response.version == "pd0-contract-v1"
    assert response.model_dump(mode="json")["entries"][0] == {
        "key": "hba1c",
        "fact_type": "observation",
        "concept": "hba1c",
        "display_label": "HbA1c",
        "group": "observations",
        "input_kind": "numeric",
        "allowed_assertions": ["present", "unknown"],
        "fixed_unit": "%",
        "allowed_units": [],
        "effective_date_required": True,
        "screening_supported": True,
        "help_text": "Most recent synthetic HbA1c result.",
        "display_order": 1,
    }

    with pytest.raises(ValidationError, match="Numeric catalog entries require"):
        PatientFactCatalogEntry(
            key="hba1c",
            fact_type=FactType.observation,
            concept="hba1c",
            display_label="HbA1c",
            group="observations",
            input_kind="numeric",
            allowed_assertions=(Assertion.present,),
            effective_date_required=True,
            screening_supported=True,
            help_text="Synthetic observation.",
            display_order=1,
        )


def test_typed_mutation_contract_discriminates_values() -> None:
    expected_revision = datetime(2026, 7, 29, 10, 0, tzinfo=UTC)
    request = PatientFactCreateRequest.model_validate(
        {
            "catalog_key": "hba1c",
            "value": {
                "input_kind": "numeric",
                "assertion": "present",
                "value_numeric": "7.8",
                "effective_date": "2026-07-29",
            },
            "expected_patient_updated_at": expected_revision.isoformat(),
        }
    )

    assert isinstance(request.value, NumericObservationValue)
    assert request.value.value_numeric == Decimal("7.8")
    assert request.value.effective_date == date(2026, 7, 29)
    assert request.expected_patient_updated_at == expected_revision

    with pytest.raises(ValidationError, match="requires a value"):
        PatientFactCreateRequest.model_validate(
            {
                "catalog_key": "hba1c",
                "value": {
                    "input_kind": "numeric",
                    "assertion": "present",
                    "effective_date": "2026-07-29",
                },
                "expected_patient_updated_at": expected_revision.isoformat(),
            }
        )


def test_all_seed_facts_are_covered_by_the_initial_catalog_inventory() -> None:
    owner_id = uuid.uuid4()
    seed_facts = [
        fact
        for patient in [*_patients(owner_id), *_admin_patients(owner_id)]
        for fact in patient.facts
    ]

    uncovered = {
        (fact.fact_type, fact.concept)
        for fact in seed_facts
        if (fact.fact_type, fact.concept) not in INITIAL_CATALOG_CONCEPTS
    }
    mismatched_units = {
        (fact.concept, fact.unit)
        for fact in seed_facts
        if fact.fact_type is FactType.observation
        and fact.unit != INITIAL_OBSERVATION_UNITS[fact.concept]
    }

    assert uncovered == set()
    assert mismatched_units == set()


def test_pasted_text_inventory_distinguishes_known_and_unrestricted_concepts() -> None:
    extracted = extract_text_input(
        "\n".join(
            [
                "Patient name: Synthetic Inventory Rowan",
                "HbA1c: 7.8 %",
                "eGFR: 72 mL/min/1.73m2",
                "BMI: 24 kg/m2",
                "creatinine: 1.0 mg/dL",
                "condition: custom_condition",
                "medication: custom_medication",
            ]
        )
    )
    candidates, _ = extract_patient_candidates(extracted)
    facts = list(candidates["facts"])
    observation_concepts = {
        str(fact["concept"]).lower()
        for fact in facts
        if fact["fact_type"] == FactType.observation.value
    }
    unrestricted = {
        (FactType(str(fact["fact_type"])), str(fact["concept"]))
        for fact in facts
        if str(fact["concept"]).startswith("custom_")
    }

    assert observation_concepts == {"hba1c", "egfr", "bmi", "creatinine"}
    assert unrestricted == {
        (FactType.condition, "custom_condition"),
        (FactType.medication, "custom_medication"),
    }
    assert unrestricted.isdisjoint(INITIAL_CATALOG_CONCEPTS)
