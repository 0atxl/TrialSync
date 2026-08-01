from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trialsync.db.models import Assertion, FactType

INITIAL_CATALOG_CONCEPTS: frozenset[tuple[FactType, str]] = frozenset(
    {
        (FactType.condition, "type1_diabetes"),
        (FactType.condition, "type2_diabetes"),
        (FactType.condition, "hypertension"),
        (FactType.condition, "asthma"),
        (FactType.condition, "pregnancy"),
        (FactType.medication, "metformin"),
        (FactType.medication, "atorvastatin"),
        (FactType.medication, "insulin"),
        (FactType.medication, "semaglutide"),
        (FactType.observation, "hba1c"),
        (FactType.observation, "fasting_glucose"),
        (FactType.observation, "egfr"),
        (FactType.observation, "creatinine"),
        (FactType.observation, "alt"),
        (FactType.observation, "ast"),
        (FactType.observation, "hemoglobin"),
        (FactType.observation, "wbc"),
        (FactType.observation, "platelets"),
        (FactType.observation, "ldl"),
        (FactType.observation, "triglycerides"),
        (FactType.observation, "bmi"),
        (FactType.observation, "systolic_bp"),
        (FactType.observation, "diastolic_bp"),
        (FactType.observation, "potassium"),
        (FactType.observation, "albumin"),
    }
)

INITIAL_OBSERVATION_UNITS: dict[str, str] = {
    "hba1c": "%",
    "fasting_glucose": "mg/dL",
    "egfr": "mL/min/1.73m2",
    "creatinine": "mg/dL",
    "alt": "U/L",
    "ast": "U/L",
    "hemoglobin": "g/dL",
    "wbc": "10^9/L",
    "platelets": "10^9/L",
    "ldl": "mg/dL",
    "triglycerides": "mg/dL",
    "bmi": "kg/m2",
    "systolic_bp": "mmHg",
    "diastolic_bp": "mmHg",
    "potassium": "mmol/L",
    "albumin": "g/dL",
}


class BiologicalSex(StrEnum):
    male = "male"
    female = "female"


class PatientDataErrorCode(StrEnum):
    """Stable API error identifiers reserved by the PD0 contract."""

    sex_invalid = "PATIENT_SEX_INVALID"
    date_of_birth_in_future = "PATIENT_DOB_IN_FUTURE"
    pregnancy_sex_conflict = "PATIENT_PREGNANCY_SEX_CONFLICT"
    fact_duplicate = "PATIENT_FACT_DUPLICATE"
    fact_conflict = "PATIENT_FACT_CONFLICT"
    fact_unsupported = "PATIENT_FACT_UNSUPPORTED"
    fact_value_invalid = "PATIENT_FACT_VALUE_INVALID"
    record_stale = "PATIENT_RECORD_STALE"
    removal_reason_required = "PATIENT_FACT_REMOVAL_REASON_REQUIRED"
    fact_already_removed = "PATIENT_FACT_ALREADY_REMOVED"
    fact_restore_conflict = "PATIENT_FACT_RESTORE_CONFLICT"


class PatientDataWarningCode(StrEnum):
    sex_not_recorded_for_pregnancy = "PATIENT_SEX_NOT_RECORDED_FOR_PREGNANCY"


class PatientFactGroup(StrEnum):
    conditions = "conditions"
    medications = "medications"
    observations = "observations"


class PatientFactInputKind(StrEnum):
    status = "status"
    pregnancy_status = "pregnancy_status"
    numeric = "numeric"


class PatientFactCatalogEntry(BaseModel):
    """Read contract for one backend-owned clinical-detail definition."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(pattern=r"^[a-z0-9_]+$", min_length=1, max_length=80)
    fact_type: FactType
    concept: str = Field(pattern=r"^[a-z0-9_]+$", min_length=1, max_length=160)
    display_label: str = Field(min_length=1, max_length=120)
    group: PatientFactGroup
    input_kind: PatientFactInputKind
    allowed_assertions: tuple[Assertion, ...] = Field(min_length=1)
    fixed_unit: str | None = Field(default=None, max_length=40)
    allowed_units: tuple[str, ...] = ()
    effective_date_required: bool
    screening_supported: bool
    help_text: str = Field(min_length=1, max_length=300)
    display_order: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_catalog_shape(self) -> PatientFactCatalogEntry:
        if self.input_kind is PatientFactInputKind.numeric:
            if self.fact_type is not FactType.observation:
                raise ValueError("Numeric catalog entries must be observations.")
            if not self.fixed_unit and not self.allowed_units:
                raise ValueError("Numeric catalog entries require a fixed or allowed unit.")
        elif self.fixed_unit or self.allowed_units:
            raise ValueError("Status catalog entries cannot define numeric units.")
        if self.input_kind is PatientFactInputKind.pregnancy_status:
            if self.fact_type is not FactType.condition or self.concept != "pregnancy":
                raise ValueError("Pregnancy status must use condition.pregnancy.")
            if not self.effective_date_required:
                raise ValueError("Pregnancy status requires an assessed date.")
        return self


class PatientFactCatalogResponse(BaseModel):
    version: Literal["pd0-contract-v1"] = "pd0-contract-v1"
    entries: tuple[PatientFactCatalogEntry, ...]


class ConditionMedicationValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_kind: Literal["status"] = "status"
    assertion: Assertion
    effective_date: date | None = None


class PregnancyStatusValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_kind: Literal["pregnancy_status"] = "pregnancy_status"
    assertion: Assertion
    effective_date: date


class NumericObservationValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_kind: Literal["numeric"] = "numeric"
    assertion: Literal[Assertion.present, Assertion.unknown] = Assertion.present
    value_numeric: Decimal | None = None
    effective_date: date

    @model_validator(mode="after")
    def validate_value_matches_assertion(self) -> NumericObservationValue:
        if self.assertion is Assertion.present and self.value_numeric is None:
            raise ValueError("A present numeric observation requires a value.")
        if self.assertion is Assertion.unknown and self.value_numeric is not None:
            raise ValueError("An unknown numeric observation cannot supply a value.")
        return self


PatientFactValue = Annotated[
    ConditionMedicationValue | PregnancyStatusValue | NumericObservationValue,
    Field(discriminator="input_kind"),
]


class PatientFactCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_key: str = Field(pattern=r"^[a-z0-9_]+$", min_length=1, max_length=80)
    value: PatientFactValue
    source_label: str = Field(default="Manual entry", min_length=1, max_length=120)
    expected_patient_updated_at: datetime


class PatientFactUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: PatientFactValue
    source_label: str = Field(default="Manual entry", min_length=1, max_length=120)
    expected_fact_updated_at: datetime


class PatientFactVoidRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)
    expected_fact_updated_at: datetime

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return " ".join(value.split())
