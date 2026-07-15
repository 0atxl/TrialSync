from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from trialsync.db.base import Base


class FactType(str, enum.Enum):
    condition = "condition"
    medication = "medication"
    observation = "observation"
    demographic = "demographic"


class Assertion(str, enum.Enum):
    present = "present"
    absent = "absent"
    unknown = "unknown"


class VersionStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"


class CriterionKind(str, enum.Enum):
    inclusion = "inclusion"
    exclusion = "exclusion"


class OverallState(str, enum.Enum):
    potentially_eligible = "potentially_eligible"
    likely_ineligible = "likely_ineligible"
    needs_review = "needs_review"


class EvaluationResult(str, enum.Enum):
    pass_ = "pass"
    fail = "fail"
    unknown = "unknown"


class DocumentKind(str, enum.Enum):
    patient = "patient"
    trial = "trial"


class DocumentSourceType(str, enum.Enum):
    text = "text"
    pdf = "pdf"


class DocumentStatus(str, enum.Enum):
    needs_review = "needs_review"
    approved = "approved"
    rejected = "rejected"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))


class Patient(TimestampMixin, Base):
    __tablename__ = "patients"
    __table_args__ = (UniqueConstraint("owner_id", "external_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(120))
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(32), nullable=True)
    facts: Mapped[list[PatientFact]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", order_by="PatientFact.created_at"
    )
    snapshots: Mapped[list[PatientSnapshot]] = relationship(
        back_populates="patient", passive_deletes=True
    )


class PatientFact(TimestampMixin, Base):
    __tablename__ = "patient_facts"
    __table_args__ = (Index("ix_patient_facts_patient_type", "patient_id", "fact_type"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    fact_type: Mapped[FactType] = mapped_column(Enum(FactType, name="fact_type"))
    concept: Mapped[str] = mapped_column(String(160))
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    assertion: Mapped[Assertion] = mapped_column(
        Enum(Assertion, name="fact_assertion"), default=Assertion.present
    )
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_label: Mapped[str] = mapped_column(String(120), default="Manual entry")
    patient: Mapped[Patient] = relationship(back_populates="facts")


class Trial(TimestampMixin, Base):
    __tablename__ = "trials"
    __table_args__ = (UniqueConstraint("owner_id", "registry_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    registry_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(240))
    condition: Mapped[str] = mapped_column(String(160))
    phase: Mapped[str | None] = mapped_column(String(40), nullable=True)
    versions: Mapped[list[TrialVersion]] = relationship(
        back_populates="trial", cascade="all, delete-orphan", order_by="TrialVersion.version"
    )


class TrialVersion(TimestampMixin, Base):
    __tablename__ = "trial_versions"
    __table_args__ = (UniqueConstraint("trial_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trial_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trials.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, name="version_status"), default=VersionStatus.draft
    )
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    trial: Mapped[Trial] = relationship(back_populates="versions")
    criteria: Mapped[list[Criterion]] = relationship(
        back_populates="trial_version", cascade="all, delete-orphan", order_by="Criterion.order"
    )


class Criterion(TimestampMixin, Base):
    __tablename__ = "criteria"
    __table_args__ = (UniqueConstraint("trial_version_id", "order"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trial_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trial_versions.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[CriterionKind] = mapped_column(Enum(CriterionKind, name="criterion_kind"))
    order: Mapped[int] = mapped_column(Integer)
    source_text: Mapped[str] = mapped_column(Text)
    normalized_rule: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    trial_version: Mapped[TrialVersion] = relationship(back_populates="criteria")


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_owner_status", "owner_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[DocumentKind] = mapped_column(Enum(DocumentKind, name="document_kind"))
    source_type: Mapped[DocumentSourceType] = mapped_column(
        Enum(DocumentSourceType, name="document_source_type")
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"), default=DocumentStatus.needs_review
    )
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    original_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    source_text: Mapped[str] = mapped_column(Text)
    pages_json: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    candidates_json: Mapped[dict[str, object]] = mapped_column(JSON)
    warnings_json: Mapped[list[str]] = mapped_column(JSON)
    quality_json: Mapped[dict[str, object]] = mapped_column(JSON)
    approved_resource_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    spans: Mapped[list[DocumentSpan]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentSpan.page"
    )


class DocumentSpan(Base):
    __tablename__ = "document_spans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page: Mapped[int] = mapped_column(Integer)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    exact_text: Mapped[str] = mapped_column(Text)
    document: Mapped[Document] = relationship(back_populates="spans")


class PatientSnapshot(TimestampMixin, Base):
    """An immutable, canonical copy of a patient's screening inputs."""

    __tablename__ = "patient_snapshots"
    __table_args__ = (UniqueConstraint("patient_id", "content_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    content_hash: Mapped[str] = mapped_column(String(64))
    snapshot_version: Mapped[str] = mapped_column(String(64))
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    facts_json: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    source_summary: Mapped[dict[str, object]] = mapped_column(JSON)
    patient: Mapped[Patient | None] = relationship(back_populates="snapshots")
    screenings: Mapped[list[Screening]] = relationship(back_populates="patient_snapshot")


class ScreeningBatch(TimestampMixin, Base):
    __tablename__ = "screening_batches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pair_count: Mapped[int] = mapped_column(Integer)
    screenings: Mapped[list[Screening]] = relationship(back_populates="batch")


class Screening(TimestampMixin, Base):
    __tablename__ = "screenings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("screening_batches.id", ondelete="CASCADE"), nullable=True, index=True
    )
    patient_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patient_snapshots.id", ondelete="CASCADE"), index=True
    )
    trial_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trial_versions.id", ondelete="RESTRICT"), index=True
    )
    trial_registry_id: Mapped[str] = mapped_column(String(64))
    trial_title: Mapped[str] = mapped_column(String(240))
    trial_version_number: Mapped[int] = mapped_column(Integer)
    overall_state: Mapped[OverallState] = mapped_column(
        Enum(OverallState, name="overall_state")
    )
    screening_date: Mapped[date] = mapped_column(Date)
    engine_version: Mapped[str] = mapped_column(String(40))
    dsl_version: Mapped[str] = mapped_column(String(20))
    terminology_version: Mapped[str] = mapped_column(String(40))
    unit_version: Mapped[str] = mapped_column(String(40))
    patient_snapshot: Mapped[PatientSnapshot] = relationship(back_populates="screenings")
    batch: Mapped[ScreeningBatch | None] = relationship(back_populates="screenings")
    evaluations: Mapped[list[CriterionEvaluation]] = relationship(
        back_populates="screening",
        cascade="all, delete-orphan",
        order_by="CriterionEvaluation.criterion_order",
    )


class CriterionEvaluation(TimestampMixin, Base):
    __tablename__ = "criterion_evaluations"
    __table_args__ = (UniqueConstraint("screening_id", "criterion_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    screening_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("screenings.id", ondelete="CASCADE"), index=True
    )
    criterion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("criteria.id", ondelete="RESTRICT"), index=True
    )
    criterion_order: Mapped[int] = mapped_column(Integer)
    criterion_kind: Mapped[CriterionKind] = mapped_column(
        Enum(CriterionKind, name="criterion_kind")
    )
    criterion_source_text: Mapped[str] = mapped_column(Text)
    result: Mapped[EvaluationResult] = mapped_column(
        Enum(
            EvaluationResult,
            name="evaluation_result",
            values_callable=lambda members: [member.value for member in members],
        )
    )
    truth: Mapped[str] = mapped_column(String(16))
    reason_code: Mapped[str] = mapped_column(String(64))
    canonical_explanation: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    rejected_evidence_json: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    missing_information_json: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    screening: Mapped[Screening] = relationship(back_populates="evaluations")
