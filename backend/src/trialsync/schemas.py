from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from trialsync.db.models import Assertion, CriterionKind, FactType, VersionStatus


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
    external_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=120)
    date_of_birth: date | None = None
    sex: str | None = Field(default=None, max_length=32)


class PatientUpdate(BaseModel):
    external_id: str | None = Field(default=None, min_length=1, max_length=64)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_birth: date | None = None
    sex: str | None = Field(default=None, max_length=32)


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
        if self.unit and self.value_numeric is None:
            raise ValueError("value_numeric is required when unit is supplied")
        if self.value_numeric is not None and self.value_text is not None:
            raise ValueError("provide either value_numeric or value_text, not both")
        return self


class FactRead(FactCreate, ORMModel):
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


class TrialCreate(BaseModel):
    registry_id: str = Field(min_length=1, max_length=64)
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
