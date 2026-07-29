from __future__ import annotations

from trialsync.db.models import Assertion, FactType
from trialsync.patient_data.contracts import (
    INITIAL_OBSERVATION_UNITS,
    PatientFactCatalogEntry,
    PatientFactCatalogResponse,
    PatientFactGroup,
    PatientFactInputKind,
)

_ALL_ASSERTIONS = (Assertion.present, Assertion.absent, Assertion.unknown)
_OBSERVATION_ASSERTIONS = (Assertion.present, Assertion.unknown)


def _status(
    concept: str,
    label: str,
    fact_type: FactType,
    group: PatientFactGroup,
    order: int,
    help_text: str,
) -> PatientFactCatalogEntry:
    return PatientFactCatalogEntry(
        key=concept,
        fact_type=fact_type,
        concept=concept,
        display_label=label,
        group=group,
        input_kind=PatientFactInputKind.status,
        allowed_assertions=_ALL_ASSERTIONS,
        effective_date_required=False,
        screening_supported=True,
        help_text=help_text,
        display_order=order,
    )


def _observation(
    concept: str,
    label: str,
    order: int,
    help_text: str,
) -> PatientFactCatalogEntry:
    return PatientFactCatalogEntry(
        key=concept,
        fact_type=FactType.observation,
        concept=concept,
        display_label=label,
        group=PatientFactGroup.observations,
        input_kind=PatientFactInputKind.numeric,
        allowed_assertions=_OBSERVATION_ASSERTIONS,
        fixed_unit=INITIAL_OBSERVATION_UNITS[concept],
        effective_date_required=True,
        screening_supported=True,
        help_text=help_text,
        display_order=order,
    )


PATIENT_FACT_CATALOG: tuple[PatientFactCatalogEntry, ...] = (
    _status(
        "type1_diabetes",
        "Type 1 diabetes",
        FactType.condition,
        PatientFactGroup.conditions,
        10,
        "Record whether Type 1 diabetes is present, absent, or unknown.",
    ),
    _status(
        "type2_diabetes",
        "Type 2 diabetes",
        FactType.condition,
        PatientFactGroup.conditions,
        20,
        "Record whether Type 2 diabetes is present, absent, or unknown.",
    ),
    _status(
        "hypertension",
        "Hypertension",
        FactType.condition,
        PatientFactGroup.conditions,
        30,
        "Record whether hypertension is present, absent, or unknown.",
    ),
    _status(
        "asthma",
        "Asthma",
        FactType.condition,
        PatientFactGroup.conditions,
        40,
        "Record whether asthma is present, absent, or unknown.",
    ),
    PatientFactCatalogEntry(
        key="pregnancy",
        fact_type=FactType.condition,
        concept="pregnancy",
        display_label="Pregnancy status",
        group=PatientFactGroup.conditions,
        input_kind=PatientFactInputKind.pregnancy_status,
        allowed_assertions=_ALL_ASSERTIONS,
        effective_date_required=True,
        screening_supported=True,
        help_text="Record the assessed pregnancy status and assessment date.",
        display_order=50,
    ),
    _status(
        "metformin",
        "Metformin",
        FactType.medication,
        PatientFactGroup.medications,
        10,
        "Record whether metformin use is present, absent, or unknown.",
    ),
    _status(
        "atorvastatin",
        "Atorvastatin",
        FactType.medication,
        PatientFactGroup.medications,
        20,
        "Record whether atorvastatin use is present, absent, or unknown.",
    ),
    _status(
        "insulin",
        "Insulin",
        FactType.medication,
        PatientFactGroup.medications,
        30,
        "Record whether insulin use is present, absent, or unknown.",
    ),
    _status(
        "semaglutide",
        "Semaglutide",
        FactType.medication,
        PatientFactGroup.medications,
        40,
        "Record whether semaglutide use is present, absent, or unknown.",
    ),
    _observation("hba1c", "HbA1c", 10, "Record the measured HbA1c result."),
    _observation(
        "fasting_glucose",
        "Fasting glucose",
        20,
        "Record the measured fasting glucose result.",
    ),
    _observation("egfr", "eGFR", 30, "Record the measured estimated filtration rate."),
    _observation("creatinine", "Creatinine", 40, "Record the measured creatinine result."),
    _observation("alt", "ALT", 50, "Record the measured alanine transaminase result."),
    _observation("ast", "AST", 60, "Record the measured aspartate transaminase result."),
    _observation("hemoglobin", "Hemoglobin", 70, "Record the measured hemoglobin result."),
    _observation(
        "wbc",
        "White blood cell count",
        80,
        "Record the measured white blood cell count.",
    ),
    _observation("platelets", "Platelets", 90, "Record the measured platelet count."),
    _observation("ldl", "LDL cholesterol", 100, "Record the measured LDL result."),
    _observation(
        "triglycerides",
        "Triglycerides",
        110,
        "Record the measured triglyceride result.",
    ),
    _observation("bmi", "BMI", 120, "Record the measured body mass index."),
    _observation(
        "systolic_bp",
        "Systolic blood pressure",
        130,
        "Record the measured systolic blood pressure.",
    ),
    _observation(
        "diastolic_bp",
        "Diastolic blood pressure",
        140,
        "Record the measured diastolic blood pressure.",
    ),
    _observation("potassium", "Potassium", 150, "Record the measured potassium result."),
    _observation("albumin", "Albumin", 160, "Record the measured albumin result."),
)

PATIENT_FACT_CATALOG_BY_KEY = {entry.key: entry for entry in PATIENT_FACT_CATALOG}
PATIENT_FACT_CATALOG_BY_CONCEPT = {
    (entry.fact_type, entry.concept): entry for entry in PATIENT_FACT_CATALOG
}
PATIENT_FACT_CATALOG_RESPONSE = PatientFactCatalogResponse(entries=PATIENT_FACT_CATALOG)

