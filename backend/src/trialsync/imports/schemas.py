from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from trialsync.db.models import Assertion, CriterionKind, DocumentKind, DocumentSourceType, FactType


class ImportAnalyzeRequest(BaseModel):
    kind: DocumentKind
    source_type: DocumentSourceType
    text: str | None = Field(default=None, max_length=1_000_000)
    content_base64: str | None = Field(default=None, max_length=8_000_000)
    filename: str | None = Field(default=None, max_length=255)
    mime_type: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_source(self) -> ImportAnalyzeRequest:
        if self.source_type is DocumentSourceType.text and self.text is None:
            raise ValueError("Pasted text is required for a text import.")
        if self.source_type is DocumentSourceType.pdf and self.content_base64 is None:
            raise ValueError("PDF content is required for a PDF import.")
        return self


class SourceReference(BaseModel):
    span_id: uuid.UUID | None = None
    page: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=2_000)


class PatientProfileCandidate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    date_of_birth: date | None = None
    sex: str | None = Field(default=None, max_length=32)


class PatientFactCandidate(BaseModel):
    candidate_id: uuid.UUID
    selected: bool = True
    fact_type: FactType
    concept: str = Field(min_length=1, max_length=160)
    value_numeric: Decimal | None = None
    value_text: str | None = Field(default=None, max_length=500)
    unit: str | None = Field(default=None, max_length=40)
    assertion: Assertion = Assertion.present
    effective_date: date | None = None
    source: SourceReference
    warnings: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def numeric_requires_unit(self) -> PatientFactCandidate:
        if self.value_numeric is not None and not self.unit:
            raise ValueError("Numeric fact candidates require a unit.")
        return self


class PatientImportCandidates(BaseModel):
    profile: PatientProfileCandidate
    facts: list[PatientFactCandidate] = Field(default_factory=list, max_length=100)


class TrialProfileCandidate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    condition: str = Field(min_length=1, max_length=160)
    phase: str | None = Field(default=None, max_length=40)


class TrialCriterionCandidate(BaseModel):
    candidate_id: uuid.UUID
    selected: bool = True
    kind: CriterionKind
    order: int = Field(ge=1)
    source_text: str = Field(min_length=1, max_length=10_000)
    normalized_rule: dict[str, Any] | None = None
    parse_state: Literal["parsed", "needs_manual_rule"]
    source: SourceReference
    warnings: list[str] = Field(default_factory=list, max_length=10)


class TrialImportCandidates(BaseModel):
    profile: TrialProfileCandidate
    criteria: list[TrialCriterionCandidate] = Field(default_factory=list, max_length=200)


class ImportUpdateRequest(BaseModel):
    candidates: dict[str, Any]


class ImportApproveRequest(BaseModel):
    confirm_duplicate_name: bool = False


class ImportRead(BaseModel):
    id: uuid.UUID
    kind: DocumentKind
    source_type: DocumentSourceType
    status: str
    filename: str | None
    mime_type: str
    size_bytes: int
    checksum: str
    source_text: str
    pages: list[dict[str, Any]]
    candidates: dict[str, Any]
    warnings: list[str]
    quality: dict[str, Any]
    approved_resource_id: uuid.UUID | None
    created_at: datetime


class ImportApprovalRead(BaseModel):
    kind: DocumentKind
    resource_id: uuid.UUID
    review_id: uuid.UUID
