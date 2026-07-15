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


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
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
