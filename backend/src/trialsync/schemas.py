from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from trialsync.db.models import Assertion, CriterionKind, FactType, VersionStatus
from trialsync.patient_data import BiologicalSex


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserRead(ORMModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class PatientCreate(BaseModel):
    external_id: str | None = Field(default=None, min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=120)
    date_of_birth: date | None = None
    sex: BiologicalSex | None = None
    confirm_duplicate_name: bool = False

    @field_validator("date_of_birth")
    @classmethod
    def reject_future_date_of_birth(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise PydanticCustomError(
                "patient_date_of_birth_in_future",
                "Date of birth cannot be in the future.",
            )
        return value


class PatientUpdate(BaseModel):
    external_id: str | None = Field(default=None, min_length=1, max_length=64)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_birth: date | None = None
    sex: BiologicalSex | None = None
    expected_updated_at: datetime

    @field_validator("date_of_birth")
    @classmethod
    def reject_future_date_of_birth(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise PydanticCustomError(
                "patient_date_of_birth_in_future",
                "Date of birth cannot be in the future.",
            )
        return value


class FactCreate(BaseModel):
    fact_type: FactType
    concept: str = Field(min_length=1, max_length=160)
    value_numeric: Decimal | None = None
    value_text: str | None = Field(default=None, max_length=500)
    unit: str | None = Field(default=None, max_length=40)
    assertion: Assertion = Assertion.present
    effective_date: date | None = None
    source_label: str = Field(default="Manual entry", min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_value_and_unit(self) -> FactCreate:
        if self.value_numeric is not None and not self.unit:
            raise ValueError("unit is required when value_numeric is supplied")
        if self.unit and self.value_numeric is None and self.assertion is not Assertion.unknown:
            raise ValueError("value_numeric is required when unit is supplied")
        if self.value_numeric is not None and self.value_text is not None:
            raise ValueError("provide either value_numeric or value_text, not both")
        return self


class FactRead(FactCreate, ORMModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


UnsupportedDetailCategory = Literal["condition", "medication", "observation", "other"]


class UnsupportedDetailCreate(BaseModel):
    category: UnsupportedDetailCategory
    label: str = Field(min_length=1, max_length=160)
    context: str | None = Field(default=None, max_length=500)
    source_label: str = Field(default="Manual review item", min_length=1, max_length=120)

    @field_validator("label", "context", "source_label", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = " ".join(value.split())
        return normalized or None


class UnsupportedDetailUpdate(BaseModel):
    category: UnsupportedDetailCategory | None = None
    label: str | None = Field(default=None, min_length=1, max_length=160)
    context: str | None = Field(default=None, max_length=500)
    expected_updated_at: datetime

    @field_validator("label", "context", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = " ".join(value.split())
        return normalized or None


class UnsupportedDetailRead(UnsupportedDetailCreate, ORMModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PatientRead(ORMModel):
    id: uuid.UUID
    external_id: str
    display_name: str
    date_of_birth: date | None
    sex: str | None
    created_at: datetime
    updated_at: datetime
    facts: list[FactRead] = Field(default_factory=list)
    unsupported_details: list[UnsupportedDetailRead] = Field(default_factory=list)


class TrialCreate(BaseModel):
    registry_id: str | None = Field(default=None, min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=240)
    condition: str = Field(min_length=1, max_length=160)
    phase: str | None = Field(default=None, max_length=40)


class TrialUpdate(BaseModel):
    registry_id: str | None = Field(default=None, min_length=1, max_length=64)
    title: str | None = Field(default=None, min_length=1, max_length=240)
    condition: str | None = Field(default=None, min_length=1, max_length=160)
    phase: str | None = Field(default=None, max_length=40)


class VersionCreate(BaseModel):
    version: int = Field(ge=1)
    status: VersionStatus = VersionStatus.draft
    source_text: str | None = Field(default=None, max_length=100_000)


class CriterionCreate(BaseModel):
    kind: CriterionKind
    order: int = Field(ge=1)
    source_text: str = Field(min_length=1, max_length=10_000)
    normalized_rule: dict[str, Any] | None = None
    required: bool = True


class GuidedCriterionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: CriterionKind
    subject_key: str = Field(pattern=r"^[a-z0-9_]+$", min_length=1, max_length=80)
    operator: Literal["present", "absent", "gte", "lte", "between", "is"]
    value: Decimal | None = None
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    biological_sex: BiologicalSex | None = None


class UnsupportedCriterionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: CriterionKind
    category: Literal[
        "demographic",
        "condition",
        "medication",
        "observation",
        "other",
    ]
    source_text: str = Field(min_length=1, max_length=10_000)

    @field_validator("source_text", mode="before")
    @classmethod
    def normalize_source_text(cls, value: object) -> object:
        return " ".join(value.split()) if isinstance(value, str) else value


class CriterionRead(CriterionCreate, ORMModel):
    id: uuid.UUID
    trial_version_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class VersionRead(ORMModel):
    id: uuid.UUID
    trial_id: uuid.UUID
    version: int
    status: VersionStatus
    source_text: str | None
    created_at: datetime
    updated_at: datetime
    criteria: list[CriterionRead] = Field(default_factory=list)


class TrialRead(ORMModel):
    id: uuid.UUID
    registry_id: str
    title: str
    condition: str
    phase: str | None
    created_at: datetime
    updated_at: datetime
    versions: list[VersionRead] = Field(default_factory=list)


class ScreeningCreate(BaseModel):
    patient_id: uuid.UUID
    trial_version_id: uuid.UUID
    screening_date: date | None = None


class ScreeningCounts(BaseModel):
    pass_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)


class PatientSnapshotSummary(BaseModel):
    id: uuid.UUID
    external_id: str
    display_name: str
    date_of_birth: date | None
    sex: str | None
    facts: list[dict[str, Any]] = Field(default_factory=list)


class TrialVersionSummary(BaseModel):
    registry_id: str
    title: str
    version: int


class CriterionEvaluationRead(BaseModel):
    id: uuid.UUID
    criterion_id: uuid.UUID
    criterion_order: int
    criterion_kind: CriterionKind
    result: str
    truth: str
    reason_code: str
    criterion_source_text: str
    canonical_explanation: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    rejected_evidence: list[dict[str, Any]] = Field(default_factory=list)
    missing_information: list[dict[str, Any]] = Field(default_factory=list)


class ScreeningRead(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID | None
    patient_snapshot_id: uuid.UUID
    trial_version_id: uuid.UUID
    patient_snapshot: PatientSnapshotSummary
    trial_version: TrialVersionSummary
    overall_state: str
    screening_date: date
    engine_version: str
    dsl_version: str
    terminology_version: str
    unit_version: str
    created_at: datetime
    counts: ScreeningCounts
    evaluations: list[CriterionEvaluationRead] = Field(default_factory=list)


class BatchCreate(BaseModel):
    patient_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    patient_snapshot_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    trial_version_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    label: str | None = Field(default=None, min_length=1, max_length=120)
    screening_date: date | None = None

    @model_validator(mode="after")
    def require_one_patient_source(self) -> BatchCreate:
        if bool(self.patient_ids) == bool(self.patient_snapshot_ids):
            raise ValueError("Provide exactly one of patient_ids or patient_snapshot_ids.")
        return self


class BatchPairRead(BaseModel):
    patient_snapshot_id: uuid.UUID
    trial_version_id: uuid.UUID
    patient_snapshot: PatientSnapshotSummary
    trial_version: TrialVersionSummary
    screening_id: uuid.UUID
    overall_state: str
    counts: ScreeningCounts


class BatchStateCounts(BaseModel):
    potentially_eligible: int = Field(ge=0)
    likely_ineligible: int = Field(ge=0)
    needs_review: int = Field(ge=0)


class ScreeningBatchRead(BaseModel):
    id: uuid.UUID
    label: str | None
    pair_count: int
    created_at: datetime
    state_counts: BatchStateCounts
    unknown_criterion_count: int = Field(ge=0)
    screenings: list[BatchPairRead] = Field(default_factory=list)


class ScreeningChatMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=4_000)


class ScreeningChatCitationRead(BaseModel):
    criterion_id: uuid.UUID
    evaluation_id: uuid.UUID
    evidence_ids: list[str] = Field(default_factory=list)
    label: str


class ScreeningChatProviderRead(BaseModel):
    enabled: bool
    provider: str
    model: str | None
    prompt_version: str


class ScreeningChatMessageRead(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    answer_state: Literal["supported", "insufficient_evidence", "refused"] | None
    citations: list[ScreeningChatCitationRead] = Field(default_factory=list)
    provider: ScreeningChatProviderRead | None
    created_at: datetime
    suggested_questions: list[str] = Field(default_factory=list)


class ScreeningConversationRead(BaseModel):
    screening_id: uuid.UUID
    messages: list[ScreeningChatMessageRead] = Field(default_factory=list)
    provider: ScreeningChatProviderRead
    suggested_questions: list[str] = Field(default_factory=list)
    max_messages: int
    max_message_chars: int
