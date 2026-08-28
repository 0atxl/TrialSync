from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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
    and_,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from trialsync.db.base import Base


class FactType(StrEnum):
    condition = "condition"
    medication = "medication"
    observation = "observation"
    demographic = "demographic"


class Assertion(StrEnum):
    present = "present"
    absent = "absent"
    unknown = "unknown"


class VersionStatus(StrEnum):
    draft = "draft"
    approved = "approved"


class CriterionKind(StrEnum):
    inclusion = "inclusion"
    exclusion = "exclusion"


class OverallState(StrEnum):
    potentially_eligible = "potentially_eligible"
    likely_ineligible = "likely_ineligible"
    needs_review = "needs_review"


class EvaluationResult(StrEnum):
    pass_ = "pass"
    fail = "fail"
    unknown = "unknown"


class DocumentKind(StrEnum):
    patient = "patient"
    trial = "trial"


class DocumentSourceType(StrEnum):
    text = "text"
    pdf = "pdf"


class DocumentStatus(StrEnum):
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
    is_catalog_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class Patient(TimestampMixin, Base):
    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint(
            "sex IS NULL OR sex IN ('male', 'female')",
            name="ck_patients_biological_sex",
        ),
        UniqueConstraint("owner_id", "external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(120))
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(32), nullable=True)
    facts: Mapped[list[PatientFact]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="PatientFact.created_at",
        primaryjoin=lambda: and_(
            PatientFact.patient_id == Patient.id,
            PatientFact.voided_at.is_(None),
        ),
    )
    unsupported_details: Mapped[list[PatientUnsupportedDetail]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="PatientUnsupportedDetail.created_at",
    )
    snapshots: Mapped[list[PatientSnapshot]] = relationship(
        back_populates="patient", passive_deletes=True
    )
    activity: Mapped[list[PatientChangeEvent]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="PatientChangeEvent.created_at.desc()",
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
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    voided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    patient: Mapped[Patient] = relationship(back_populates="facts")


class PatientUnsupportedDetail(TimestampMixin, Base):
    __tablename__ = "patient_unsupported_details"
    __table_args__ = (
        CheckConstraint(
            "category IN ('condition', 'medication', 'observation', 'other')",
            name="ck_patient_unsupported_detail_category",
        ),
        Index(
            "ix_patient_unsupported_details_patient_category",
            "patient_id",
            "category",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(24))
    label: Mapped[str] = mapped_column(String(160))
    context: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_label: Mapped[str] = mapped_column(String(120), default="Manual review item")
    patient: Mapped[Patient] = relationship(back_populates="unsupported_details")


class PatientChangeEvent(Base):
    """Immutable, owner-scoped activity for a patient's mutable record."""

    __tablename__ = "patient_change_events"
    __table_args__ = (
        Index("ix_patient_change_events_patient_created", "patient_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(32))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    before_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    patient: Mapped[Patient] = relationship(back_populates="activity")


class ClinicalConcept(TimestampMixin, Base):
    """A database-owned concept available to patient and protocol entry."""

    __tablename__ = "clinical_concepts"
    __table_args__ = (
        CheckConstraint(
            "concept_group IN ('conditions', 'medications', 'observations')",
            name="ck_clinical_concepts_group",
        ),
        CheckConstraint(
            "input_kind IN ('status', 'pregnancy_status', 'numeric')",
            name="ck_clinical_concepts_input_kind",
        ),
        UniqueConstraint("key"),
        UniqueConstraint("fact_type", "concept"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(80), index=True)
    fact_type: Mapped[FactType] = mapped_column(Enum(FactType, name="fact_type"))
    concept: Mapped[str] = mapped_column(String(160))
    display_label: Mapped[str] = mapped_column(String(120))
    concept_group: Mapped[str] = mapped_column(String(24))
    input_kind: Mapped[str] = mapped_column(String(24))
    allowed_assertions_json: Mapped[list[str]] = mapped_column(JSON)
    fixed_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    effective_date_required: Mapped[bool] = mapped_column(Boolean, default=False)
    screening_supported: Mapped[bool] = mapped_column(Boolean, default=True)
    help_text: Mapped[str] = mapped_column(String(300))
    terminology_system: Mapped[str | None] = mapped_column(String(32), nullable=True)
    terminology_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


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
    overall_state: Mapped[OverallState] = mapped_column(Enum(OverallState, name="overall_state"))
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
    chat_messages: Mapped[list[ScreeningChatMessage]] = relationship(
        back_populates="screening",
        cascade="all, delete-orphan",
        order_by="ScreeningChatMessage.created_at",
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


class ScreeningChatMessage(Base):
    __tablename__ = "screening_chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_message_role"),
        CheckConstraint(
            "answer_state IS NULL OR answer_state IN "
            "('supported', 'insufficient_evidence', 'refused')",
            name="ck_chat_message_answer_state",
        ),
        CheckConstraint(
            "(role = 'user' AND answer_state IS NULL) OR "
            "(role = 'assistant' AND answer_state IS NOT NULL)",
            name="ck_chat_message_role_state",
        ),
        Index("ix_screening_chat_messages_screening_created", "screening_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    screening_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("screenings.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    answer_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    citations_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=False
    )
    screening: Mapped[Screening] = relationship(back_populates="chat_messages")


class ResearchModelVersion(Base):
    """Immutable metadata for an explicitly approved local research model package."""

    __tablename__ = "research_model_versions"
    __table_args__ = (
        CheckConstraint("threshold > 0 AND threshold < 1", name="ck_research_model_threshold"),
        CheckConstraint("horizon_day > 0", name="ck_research_model_horizon"),
        UniqueConstraint("model_name", "version"),
        UniqueConstraint("candidate_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(40))
    alias: Mapped[str] = mapped_column(String(40))
    candidate_id: Mapped[str] = mapped_column(String(80))
    training_dataset_version: Mapped[str] = mapped_column(String(80))
    training_dataset_checksum: Mapped[str] = mapped_column(String(64))
    feature_schema_version: Mapped[str] = mapped_column(String(80))
    feature_schema_checksum: Mapped[str] = mapped_column(String(64))
    threshold: Mapped[Decimal] = mapped_column(Numeric(18, 16))
    horizon_day: Mapped[int] = mapped_column(Integer)
    validation_status: Mapped[str] = mapped_column(String(80))
    metrics_json: Mapped[dict[str, object]] = mapped_column(JSON)
    artifact_locator: Mapped[str] = mapped_column(String(240))
    artifact_checksum: Mapped[str] = mapped_column(String(64))
    band_policy_version: Mapped[str] = mapped_column(String(80))
    disclaimer_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchEnrollment(Base):
    """Platform-owned participant/trial episode rooted in one saved screening."""

    __tablename__ = "research_enrollments"
    __table_args__ = (
        UniqueConstraint("owner_id", "screening_id"),
        UniqueConstraint("owner_id", "patient_snapshot_id", "trial_version_id"),
        CheckConstraint("observation_cutoff_day > 0", name="ck_research_enrollment_cutoff"),
        CheckConstraint(
            "prediction_horizon_day > observation_cutoff_day",
            name="ck_research_enrollment_horizon",
        ),
        CheckConstraint(
            "tracking_status IN ('active', 'closed')",
            name="ck_research_enrollment_tracking_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    patient_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patient_snapshots.id", ondelete="RESTRICT"), index=True
    )
    trial_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trial_versions.id", ondelete="RESTRICT"), index=True
    )
    screening_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("screenings.id", ondelete="RESTRICT"), index=True
    )
    research_context_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    enrollment_date: Mapped[date] = mapped_column(Date)
    observation_cutoff_day: Mapped[int] = mapped_column(Integer, default=30)
    prediction_horizon_day: Mapped[int] = mapped_column(Integer, default=90)
    baseline_values_json: Mapped[dict[str, object]] = mapped_column(JSON)
    baseline_sources_json: Mapped[dict[str, object]] = mapped_column(JSON)
    baseline_snapshot_hash: Mapped[str] = mapped_column(String(64))
    feature_contract_version: Mapped[str] = mapped_column(String(80))
    tracking_status: Mapped[str] = mapped_column(String(16), default="active")
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchEnrollmentBaselineRevision(Base):
    """Append-only enrollment baseline used to build future feature snapshots."""

    __tablename__ = "research_enrollment_baseline_revisions"
    __table_args__ = (
        UniqueConstraint("supersedes_revision_id"),
        Index("ix_research_baseline_revisions_owner", "owner_id"),
        Index("ix_research_baseline_revisions_enrollment", "research_enrollment_id"),
        Index("ix_research_baseline_revisions_creator", "created_by_id"),
        Index(
            "ix_research_baseline_revisions_enrollment_created",
            "research_enrollment_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    research_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_enrollments.id", ondelete="CASCADE")
    )
    enrollment_date: Mapped[date] = mapped_column(Date)
    baseline_values_json: Mapped[dict[str, object]] = mapped_column(JSON)
    baseline_sources_json: Mapped[dict[str, object]] = mapped_column(JSON)
    baseline_snapshot_hash: Mapped[str] = mapped_column(String(64))
    feature_contract_version: Mapped[str] = mapped_column(String(80))
    supersedes_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_enrollment_baseline_revisions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    correction_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchDoseEvent(Base):
    __tablename__ = "research_dose_events"
    __table_args__ = (
        CheckConstraint("event_day >= 0", name="ck_research_dose_event_day"),
        CheckConstraint("scheduled_count >= 1", name="ck_research_dose_scheduled"),
        CheckConstraint(
            "administered_count >= 0 AND administered_count <= scheduled_count",
            name="ck_research_dose_administered",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'administered', 'partially_administered', 'missed', 'held')",
            name="ck_research_dose_status",
        ),
        UniqueConstraint("supersedes_event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    research_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_enrollments.id", ondelete="CASCADE"), index=True
    )
    event_day: Mapped[int] = mapped_column(Integer)
    medication_concept: Mapped[str] = mapped_column(String(160))
    scheduled_date: Mapped[date] = mapped_column(Date)
    scheduled_count: Mapped[int] = mapped_column(Integer)
    administered_count: Mapped[int] = mapped_column(Integer)
    dose_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    dose_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    route: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_label: Mapped[str] = mapped_column(String(120))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    supersedes_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_dose_events.id", ondelete="RESTRICT"), nullable=True
    )
    correction_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResearchVisitEvent(Base):
    __tablename__ = "research_visit_events"
    __table_args__ = (
        CheckConstraint("event_day >= 0", name="ck_research_visit_event_day"),
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'delayed', 'missed')",
            name="ck_research_visit_status",
        ),
        CheckConstraint("delay_days IS NULL OR delay_days >= 0", name="ck_research_visit_delay"),
        UniqueConstraint("supersedes_event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    research_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_enrollments.id", ondelete="CASCADE"), index=True
    )
    event_day: Mapped[int] = mapped_column(Integer)
    visit_type: Mapped[str] = mapped_column(String(120))
    scheduled_date: Mapped[date] = mapped_column(Date)
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    delay_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_label: Mapped[str] = mapped_column(String(120))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    supersedes_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_visit_events.id", ondelete="RESTRICT"), nullable=True
    )
    correction_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResearchMeasurement(Base):
    __tablename__ = "research_measurements"
    __table_args__ = (
        CheckConstraint("event_day >= 0", name="ck_research_measurement_event_day"),
        CheckConstraint(
            "(observed AND value_numeric IS NOT NULL AND unit IS NOT NULL) OR "
            "(NOT observed AND value_numeric IS NULL)",
            name="ck_research_measurement_observed_value",
        ),
        UniqueConstraint("supersedes_event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    research_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_enrollments.id", ondelete="CASCADE"), index=True
    )
    event_day: Mapped[int] = mapped_column(Integer)
    concept: Mapped[str] = mapped_column(String(160))
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    observed: Mapped[bool] = mapped_column(Boolean, default=True)
    observed_date: Mapped[date] = mapped_column(Date)
    method: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reference_range_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    source_label: Mapped[str] = mapped_column(String(120))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    supersedes_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_measurements.id", ondelete="RESTRICT"), nullable=True
    )
    correction_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResearchAdverseEvent(Base):
    __tablename__ = "research_adverse_events"
    __table_args__ = (
        CheckConstraint("event_day >= 0", name="ck_research_adverse_event_day"),
        CheckConstraint("severity_grade BETWEEN 1 AND 4", name="ck_research_adverse_severity"),
        CheckConstraint(
            "relatedness IN ('unrelated', 'unlikely', 'possible', 'probable', "
            "'definite', 'unknown')",
            name="ck_research_adverse_relatedness",
        ),
        CheckConstraint(
            "outcome IN ('ongoing', 'resolved', 'resolved_with_sequelae', 'unknown')",
            name="ck_research_adverse_outcome",
        ),
        UniqueConstraint("supersedes_event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    research_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_enrollments.id", ondelete="CASCADE"), index=True
    )
    event_day: Mapped[int] = mapped_column(Integer)
    event_concept: Mapped[str] = mapped_column(String(160))
    onset_date: Mapped[date] = mapped_column(Date)
    severity_grade: Mapped[int] = mapped_column(Integer)
    resolved_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    serious: Mapped[bool] = mapped_column(Boolean, default=False)
    relatedness: Mapped[str] = mapped_column(String(16))
    action_taken: Mapped[str | None] = mapped_column(String(120), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32))
    source_label: Mapped[str] = mapped_column(String(120))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    supersedes_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_adverse_events.id", ondelete="RESTRICT"), nullable=True
    )
    correction_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResearchFollowUpSnapshot(Base):
    __tablename__ = "research_follow_up_snapshots"
    __table_args__ = (
        CheckConstraint("cutoff_day > 0", name="ck_research_follow_up_cutoff"),
        CheckConstraint("status IN ('incomplete', 'ready')", name="ck_research_follow_up_status"),
        UniqueConstraint("research_enrollment_id", "cutoff_day", "event_set_checksum"),
        Index("ix_research_follow_ups_baseline_revision", "baseline_revision_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    research_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_enrollments.id", ondelete="CASCADE"), index=True
    )
    baseline_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_enrollment_baseline_revisions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    cutoff_day: Mapped[int] = mapped_column(Integer)
    feature_schema_version: Mapped[str] = mapped_column(String(80))
    feature_values_json: Mapped[dict[str, object]] = mapped_column(JSON)
    feature_sources_json: Mapped[dict[str, object]] = mapped_column(JSON)
    feature_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_summary_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    event_set_checksum: Mapped[str] = mapped_column(String(64))
    missing_features_json: Mapped[list[str]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchPrediction(Base):
    """Immutable, versioned R5 output; never part of deterministic screening state."""

    __tablename__ = "research_predictions"
    __table_args__ = (
        CheckConstraint(
            "probability >= 0 AND probability <= 1", name="ck_research_prediction_probability"
        ),
        CheckConstraint(
            "research_label IN ('lower', 'near_threshold', 'higher')",
            name="ck_research_prediction_label",
        ),
        UniqueConstraint(
            "owner_id", "research_enrollment_id", "model_version_id", "feature_snapshot_hash"
        ),
        Index("ix_research_predictions_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    research_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_enrollments.id", ondelete="RESTRICT"), index=True
    )
    follow_up_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_follow_up_snapshots.id", ondelete="RESTRICT"), index=True
    )
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_model_versions.id", ondelete="RESTRICT"), index=True
    )
    feature_snapshot_json: Mapped[dict[str, object]] = mapped_column(JSON)
    feature_snapshot_hash: Mapped[str] = mapped_column(String(64))
    probability: Mapped[Decimal] = mapped_column(Numeric(18, 16))
    research_label: Mapped[str] = mapped_column(String(32))
    top_contributions_json: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
