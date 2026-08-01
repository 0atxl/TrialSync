from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from trialsync.db.models import Screening

REPORT_SCHEMA_VERSION = "r1-report-v1"
REPORT_TEMPLATE_VERSION = "r1-pdf-template-v1"


class ScreeningReportPatientSnapshot(BaseModel):
    id: str
    external_id: str
    display_name: str
    date_of_birth: str | None
    sex: str | None
    snapshot_version: str
    content_hash: str
    as_of_date: str


class ScreeningReportTrial(BaseModel):
    id: str
    registry_id: str
    title: str
    version: int


class ScreeningReportEvidence(BaseModel):
    """One evidence record preserved from an immutable criterion evaluation."""

    fact_id: str
    source_label: str
    value: Any = None
    unit: str | None = None
    effective_date: str | None = None


class ScreeningReportMissingInformation(BaseModel):
    """A complete requirement that prevented a deterministic conclusion."""

    fact: str
    reason: str
    detail: str


class ScreeningReportCounts(BaseModel):
    pass_count: int
    fail_count: int
    unknown_count: int


class ScreeningReportCriterion(BaseModel):
    id: str
    criterion_id: str
    order: int
    kind: str
    source_text: str
    result: str
    truth: str
    reason_code: str
    canonical_explanation: str
    evidence: list[ScreeningReportEvidence] = Field(default_factory=list)
    rejected_evidence: list[ScreeningReportEvidence] = Field(default_factory=list)
    missing_information: list[ScreeningReportMissingInformation] = Field(default_factory=list)


class ScreeningReportDocument(BaseModel):
    schema_version: str
    template_version: str
    generated_at: datetime
    screening_id: str
    created_at: datetime
    screening_date: str
    overall_state: str
    patient_snapshot: ScreeningReportPatientSnapshot
    trial: ScreeningReportTrial
    engine_version: str
    dsl_version: str
    terminology_version: str
    unit_version: str
    counts: ScreeningReportCounts
    criteria: list[ScreeningReportCriterion] = Field(default_factory=list)


def _iso(value: object) -> str:
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def assemble_screening_report(
    screening: Screening,
    *,
    generated_at: datetime | None = None,
) -> ScreeningReportDocument:
    """Build a report document from immutable screening rows only.

    This function never evaluates criteria, reads providers, or loads mutable patient
    records. The screening and snapshot relationships must already be authorized and
    loaded by the caller.
    """

    snapshot = screening.patient_snapshot
    source = snapshot.source_summary
    results = [evaluation.result.value for evaluation in screening.evaluations]
    return ScreeningReportDocument(
        schema_version=REPORT_SCHEMA_VERSION,
        template_version=REPORT_TEMPLATE_VERSION,
        generated_at=_as_utc(generated_at or datetime.now(UTC)),
        screening_id=str(screening.id),
        created_at=_as_utc(screening.created_at),
        screening_date=_iso(screening.screening_date),
        overall_state=screening.overall_state.value,
        patient_snapshot=ScreeningReportPatientSnapshot(
            id=str(snapshot.id),
            external_id=str(source.get("external_id", "Synthetic patient")),
            display_name=str(source.get("display_name", "Synthetic patient")),
            date_of_birth=_iso(snapshot.date_of_birth) if snapshot.date_of_birth else None,
            sex=str(source["sex"]) if source.get("sex") is not None else None,
            snapshot_version=snapshot.snapshot_version,
            content_hash=snapshot.content_hash,
            as_of_date=_iso(screening.screening_date),
        ),
        trial=ScreeningReportTrial(
            id=str(screening.trial_version_id),
            registry_id=screening.trial_registry_id,
            title=screening.trial_title,
            version=screening.trial_version_number,
        ),
        engine_version=screening.engine_version,
        dsl_version=screening.dsl_version,
        terminology_version=screening.terminology_version,
        unit_version=screening.unit_version,
        counts=ScreeningReportCounts(
            pass_count=results.count("pass"),
            fail_count=results.count("fail"),
            unknown_count=results.count("unknown"),
        ),
        criteria=[
            ScreeningReportCriterion(
                id=str(item.id),
                criterion_id=str(item.criterion_id),
                order=item.criterion_order,
                kind=item.criterion_kind.value,
                source_text=item.criterion_source_text,
                result=item.result.value,
                truth=item.truth,
                reason_code=item.reason_code,
                canonical_explanation=item.canonical_explanation,
                evidence=[
                    ScreeningReportEvidence.model_validate(value) for value in item.evidence_json
                ],
                rejected_evidence=[
                    ScreeningReportEvidence.model_validate(value)
                    for value in item.rejected_evidence_json
                ],
                missing_information=[
                    ScreeningReportMissingInformation.model_validate(value)
                    for value in item.missing_information_json
                ],
            )
            for item in screening.evaluations
        ],
    )
