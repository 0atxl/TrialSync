from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from trialsync.api.errors import ApplicationError
from trialsync.db.models import (
    CriterionEvaluation as StoredCriterionEvaluation,
)
from trialsync.db.models import (
    EvaluationResult,
    Patient,
    PatientFact,
    Screening,
    ScreeningBatch,
    Trial,
    TrialVersion,
    VersionStatus,
)
from trialsync.db.models import (
    OverallState as StoredOverallState,
)
from trialsync.db.models import (
    PatientSnapshot as StoredPatientSnapshot,
)
from trialsync.domain import (
    ApprovedTrialVersion,
    Assertion,
    CriterionKind,
    Fact,
    FactType,
    PatientSnapshot,
    ScreeningContext,
    Temporality,
    screen,
)
from trialsync.domain import (
    Criterion as DomainCriterion,
)

ENGINE_VERSION = "0.1.0"


def _fact_payload(fact: PatientFact) -> dict[str, object]:
    return {
        "id": str(fact.id),
        "fact_type": fact.fact_type.value,
        "concept": fact.concept,
        "value_numeric": str(fact.value_numeric) if fact.value_numeric is not None else None,
        "value_text": fact.value_text,
        "unit": fact.unit,
        "assertion": fact.assertion.value,
        "effective_date": fact.effective_date.isoformat() if fact.effective_date else None,
        "source_label": fact.source_label,
    }


def _snapshot_payload(patient: Patient) -> tuple[str, list[dict[str, object]], dict[str, object]]:
    facts = [_fact_payload(fact) for fact in patient.facts]
    facts.sort(key=lambda value: str(value["id"]))
    source: dict[str, object] = {
        "patient_id": str(patient.id),
        "external_id": patient.external_id,
        "display_name": patient.display_name,
        "sex": patient.sex,
    }
    canonical = json.dumps(
        {
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            "sex": patient.sex,
            "facts": facts,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest(), facts, source


async def snapshot_for_patient(session: AsyncSession, patient: Patient) -> StoredPatientSnapshot:
    content_hash, facts, source = _snapshot_payload(patient)
    existing = await session.scalar(
        select(StoredPatientSnapshot).where(
            StoredPatientSnapshot.patient_id == patient.id,
            StoredPatientSnapshot.content_hash == content_hash,
        )
    )
    if existing is not None:
        return existing
    snapshot = StoredPatientSnapshot(
        owner_id=patient.owner_id,
        patient_id=patient.id,
        content_hash=content_hash,
        snapshot_version=content_hash,
        date_of_birth=patient.date_of_birth,
        facts_json=facts,
        source_summary=source,
    )
    session.add(snapshot)
    await session.flush()
    return snapshot


def _domain_snapshot(snapshot: StoredPatientSnapshot) -> PatientSnapshot:
    facts: list[Fact] = []
    for raw in snapshot.facts_json:
        numeric = raw.get("value_numeric")
        value: Decimal | str | None
        if numeric is not None:
            value = Decimal(str(numeric))
        else:
            value_text = raw.get("value_text")
            value = str(value_text) if value_text is not None else None
        effective = raw.get("effective_date")
        facts.append(
            Fact(
                id=str(raw["id"]),
                fact_type=FactType(str(raw["fact_type"])),
                concept=str(raw["concept"]),
                value=value,
                unit=str(raw["unit"]) if raw.get("unit") is not None else None,
                assertion=Assertion(str(raw["assertion"])),
                effective_date=date.fromisoformat(str(effective)) if effective else None,
                source_label=str(raw["source_label"]),
                temporality=Temporality.current,
            )
        )
    sex = snapshot.source_summary.get("sex")
    if isinstance(sex, str) and sex.strip():
        normalized_sex = sex.strip().lower()
        facts.append(
            Fact(
                id="demographic.sex",
                fact_type=FactType.demographic,
                concept=normalized_sex,
                value=normalized_sex,
                assertion=Assertion.present,
                source_label="Patient profile",
                temporality=Temporality.current,
            )
        )
    return PatientSnapshot(
        id=str(snapshot.id),
        version=snapshot.snapshot_version,
        date_of_birth=snapshot.date_of_birth,
        facts=tuple(facts),
    )


def _domain_trial(version: TrialVersion) -> ApprovedTrialVersion:
    criteria = tuple(
        DomainCriterion(
            id=str(criterion.id),
            kind=CriterionKind(criterion.kind.value),
            order=criterion.order,
            source_text=criterion.source_text,
            expression=criterion.normalized_rule or {"op": "unsupported"},
            required=criterion.required,
        )
        for criterion in version.criteria
    )
    return ApprovedTrialVersion(id=str(version.id), version=str(version.version), criteria=criteria)


def _evidence_payload(items: Any) -> list[dict[str, object]]:
    return [
        {
            "fact_id": item.fact_id,
            "source_label": item.source_label,
            "value": item.value,
            "unit": item.unit,
            "effective_date": item.effective_date.isoformat() if item.effective_date else None,
        }
        for item in items
    ]


def _missing_payload(items: Any) -> list[dict[str, object]]:
    return [
        {"fact": item.fact, "reason": item.reason.value, "detail": item.detail} for item in items
    ]


async def run_and_store(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    snapshot: StoredPatientSnapshot,
    version: TrialVersion,
    screening_date: date,
    batch: ScreeningBatch | None = None,
) -> Screening:
    result = screen(
        _domain_snapshot(snapshot),
        _domain_trial(version),
        ScreeningContext(screening_date=screening_date, engine_version=ENGINE_VERSION),
    )
    screening = Screening(
        owner_id=owner_id,
        batch=batch,
        patient_snapshot_id=snapshot.id,
        trial_version_id=version.id,
        overall_state=StoredOverallState(result.overall_state.value),
        screening_date=result.screening_date,
        engine_version=result.engine_version,
        dsl_version=result.dsl_version,
        terminology_version=result.terminology_version,
        unit_version=result.unit_version,
    )
    session.add(screening)
    await session.flush()
    for evaluation in result.evaluations:
        session.add(
            StoredCriterionEvaluation(
                screening_id=screening.id,
                criterion_id=uuid.UUID(evaluation.criterion_id),
                criterion_order=evaluation.criterion_order,
                criterion_kind=evaluation.criterion_kind.value,
                result=EvaluationResult(evaluation.result.value),
                truth=evaluation.truth.value,
                reason_code=evaluation.reason_code.value,
                canonical_explanation=evaluation.explanation,
                evidence_json=_evidence_payload(evaluation.evidence),
                rejected_evidence_json=_evidence_payload(evaluation.rejected_evidence),
                missing_information_json=_missing_payload(evaluation.missing),
            )
        )
    await session.flush()
    return screening


async def owned_patient(
    session: AsyncSession, owner_id: uuid.UUID, patient_id: uuid.UUID
) -> Patient:
    patient = await session.scalar(
        select(Patient)
        .options(selectinload(Patient.facts))
        .where(Patient.id == patient_id, Patient.owner_id == owner_id)
    )
    if patient is None:
        raise ApplicationError(
            code="PATIENT_NOT_FOUND", message="Patient was not found.", status_code=404
        )
    return patient


async def owned_snapshot(
    session: AsyncSession, owner_id: uuid.UUID, snapshot_id: uuid.UUID
) -> StoredPatientSnapshot:
    snapshot = await session.scalar(
        select(StoredPatientSnapshot).where(
            StoredPatientSnapshot.id == snapshot_id,
            StoredPatientSnapshot.owner_id == owner_id,
        )
    )
    if snapshot is None:
        raise ApplicationError(
            code="PATIENT_SNAPSHOT_NOT_FOUND",
            message="Patient snapshot was not found.",
            status_code=404,
        )
    return snapshot


async def owned_approved_version(
    session: AsyncSession, owner_id: uuid.UUID, version_id: uuid.UUID
) -> TrialVersion:
    version = await session.scalar(
        select(TrialVersion)
        .join(Trial)
        .options(selectinload(TrialVersion.criteria), selectinload(TrialVersion.trial))
        .where(
            TrialVersion.id == version_id,
            Trial.owner_id == owner_id,
            TrialVersion.status == VersionStatus.approved,
        )
    )
    if version is None:
        raise ApplicationError(
            code="APPROVED_TRIAL_VERSION_NOT_FOUND",
            message="Approved trial version was not found.",
            status_code=404,
        )
    return version
