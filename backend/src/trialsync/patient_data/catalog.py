from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trialsync.db.models import Assertion, ClinicalConcept, FactType
from trialsync.patient_data.contracts import (
    PatientFactCatalogEntry,
    PatientFactGroup,
    PatientFactInputKind,
)


def catalog_entry_from_record(record: ClinicalConcept) -> PatientFactCatalogEntry:
    """Adapt a database concept to the stable entry contract used by both forms."""

    return PatientFactCatalogEntry(
        key=record.key,
        fact_type=record.fact_type,
        concept=record.concept,
        display_label=record.display_label,
        group=PatientFactGroup(record.concept_group),
        input_kind=PatientFactInputKind(record.input_kind),
        allowed_assertions=tuple(Assertion(value) for value in record.allowed_assertions_json),
        fixed_unit=record.fixed_unit,
        effective_date_required=record.effective_date_required,
        screening_supported=record.screening_supported,
        help_text=record.help_text,
        display_order=record.display_order,
    )


async def active_catalog_entries(session: AsyncSession) -> list[PatientFactCatalogEntry]:
    records = await session.scalars(
        select(ClinicalConcept)
        .where(ClinicalConcept.active.is_(True))
        .order_by(ClinicalConcept.concept_group, ClinicalConcept.display_order)
    )
    return [catalog_entry_from_record(record) for record in records]


async def active_catalog_entry_by_key(
    session: AsyncSession,
    key: str,
) -> PatientFactCatalogEntry | None:
    record = await session.scalar(
        select(ClinicalConcept).where(ClinicalConcept.key == key, ClinicalConcept.active.is_(True))
    )
    return catalog_entry_from_record(record) if record is not None else None


async def active_catalog_entry_by_fact(
    session: AsyncSession,
    fact_type: FactType,
    concept: str,
) -> PatientFactCatalogEntry | None:
    record = await session.scalar(
        select(ClinicalConcept).where(
            ClinicalConcept.fact_type == fact_type,
            ClinicalConcept.concept == concept,
            ClinicalConcept.active.is_(True),
        )
    )
    return catalog_entry_from_record(record) if record is not None else None
