from __future__ import annotations

import base64
import binascii
import hashlib
import uuid
from typing import Any

from fastapi import APIRouter, Request, Response, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from trialsync.api.deps import CurrentUser, SessionDep
from trialsync.api.errors import ApplicationError
from trialsync.db.models import (
    Assertion,
    Criterion,
    Document,
    DocumentKind,
    DocumentSourceType,
    DocumentSpan,
    DocumentStatus,
    Patient,
    PatientChangeEvent,
    PatientFact,
    PatientUnsupportedDetail,
    Trial,
    TrialVersion,
    VersionStatus,
)
from trialsync.imports.parser import (
    ImportParseError,
    extract_pdf_input,
    extract_text_input,
)
from trialsync.imports.schemas import (
    ImportAnalyzeRequest,
    ImportApprovalRead,
    ImportApproveRequest,
    ImportRead,
    ImportUpdateRequest,
    PatientImportCandidates,
    TrialImportCandidates,
)
from trialsync.nlp.extraction import GroqExtractor, RuleBasedExtractor
from trialsync.nlp.groq import ProviderCallError
from trialsync.patient_data import PatientFactCatalogEntry, PatientFactInputKind
from trialsync.patient_data.catalog import active_catalog_entries

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])

_IMPORT_CONCEPT_ALIASES: dict[tuple[str, str], str] = {
    ("condition", "type1diabetesmellitus"): "type1_diabetes",
    ("condition", "type1diabetes"): "type1_diabetes",
    ("condition", "typeidiabetes"): "type1_diabetes",
    ("condition", "type2diabetesmellitus"): "type2_diabetes",
    ("condition", "type2diabetes"): "type2_diabetes",
    ("condition", "typeiidiabetes"): "type2_diabetes",
    ("condition", "typeiidiabetesmellitus"): "type2_diabetes",
    ("condition", "highbloodpressure"): "hypertension",
    ("condition", "highbp"): "hypertension",
    ("condition", "reactiveairwaydisease"): "asthma",
    ("condition", "gestation"): "pregnancy",
    ("medication", "metforminhydrochloride"): "metformin",
    ("medication", "atorvastatincalcium"): "atorvastatin",
    ("medication", "insulintherapy"): "insulin",
    ("medication", "semaglutideinjection"): "semaglutide",
}


async def owned_import(session: SessionDep, user: CurrentUser, import_id: uuid.UUID) -> Document:
    document = await session.scalar(
        select(Document)
        .options(selectinload(Document.spans))
        .where(Document.id == import_id, Document.owner_id == user.id)
    )
    if document is None:
        raise ApplicationError(
            code="IMPORT_NOT_FOUND", message="Import was not found.", status_code=404
        )
    return document


def import_read(document: Document) -> ImportRead:
    return ImportRead(
        id=document.id,
        kind=document.kind,
        source_type=document.source_type,
        status=document.status.value,
        filename=document.filename,
        mime_type=document.mime_type,
        size_bytes=document.size_bytes,
        checksum=document.checksum,
        source_text=document.source_text,
        pages=document.pages_json,
        candidates=document.candidates_json,
        warnings=document.warnings_json,
        quality=document.quality_json,
        approved_resource_id=document.approved_resource_id,
        created_at=document.created_at,
    )


def _decode_pdf(payload: ImportAnalyzeRequest) -> bytes:
    if payload.mime_type not in {None, "application/pdf"}:
        raise ApplicationError(
            code="IMPORT_WRONG_TYPE",
            message="Only PDF files are accepted for PDF import.",
            status_code=422,
        )
    try:
        return base64.b64decode(payload.content_base64 or "", validate=True)
    except (binascii.Error, ValueError) as exception:
        raise ApplicationError(
            code="PDF_MALFORMED", message="The PDF payload is not valid base64.", status_code=422
        ) from exception


def _attach_spans(document: Document, candidates: dict[str, object]) -> None:
    key = "facts" if document.kind is DocumentKind.patient else "criteria"
    items = candidates.get(key, [])
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("source"), dict):
            continue
        source = item["source"]
        span_id = uuid.uuid4()
        DocumentSpan(
            id=span_id,
            document=document,
            page=int(source["page"]),
            start_offset=int(source["start"]),
            end_offset=int(source["end"]),
            exact_text=str(source["text"]),
        )
        source["span_id"] = str(span_id)


def _validate_candidates(kind: DocumentKind, candidates: dict[str, Any]) -> dict[str, object]:
    try:
        validated = (
            PatientImportCandidates.model_validate(candidates)
            if kind is DocumentKind.patient
            else TrialImportCandidates.model_validate(candidates)
        )
    except ValidationError as exception:
        raise ApplicationError(
            code="IMPORT_REVIEW_INVALID",
            message="The edited candidates could not be validated.",
            status_code=422,
            details=[dict(item) for item in exception.errors(include_url=False)],
        ) from exception
    return validated.model_dump(mode="json")


def _compact_concept(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _catalog_index(
    entries: list[PatientFactCatalogEntry],
) -> dict[tuple[str, str], PatientFactCatalogEntry]:
    index: dict[tuple[str, str], PatientFactCatalogEntry] = {}
    for entry in entries:
        for label in (entry.key, entry.concept, entry.display_label):
            index[(entry.fact_type.value, _compact_concept(label))] = entry
    return index


def _matched_catalog_entry(
    fact_type: str, concept: str, index: dict[tuple[str, str], PatientFactCatalogEntry]
) -> PatientFactCatalogEntry | None:
    compact = _compact_concept(concept)
    direct = index.get((fact_type, compact))
    if direct is not None:
        return direct
    alias = _IMPORT_CONCEPT_ALIASES.get((fact_type, compact))
    return index.get((fact_type, _compact_concept(alias))) if alias else None


def _unit_key(value: str) -> str:
    return "".join(value.casefold().split())


def _catalog_issues(
    fact: Any,
    entry: PatientFactCatalogEntry | None,
) -> list[str]:
    if entry is None:
        return [
            "This concept is not in the active clinical catalog; it will be retained "
            "as a review-only detail."
        ]
    issues: list[str] = []
    if entry.input_kind is PatientFactInputKind.numeric:
        if fact.assertion is Assertion.present and fact.value_numeric is None:
            issues.append("A present numeric observation needs a measured value.")
        if fact.unit and entry.fixed_unit and _unit_key(fact.unit) != _unit_key(entry.fixed_unit):
            issues.append(f"The catalog requires the unit {entry.fixed_unit}.")
        if entry.effective_date_required and fact.effective_date is None:
            issues.append("Add an effective date before approving this observation.")
    elif fact.value_numeric is not None:
        issues.append("Numeric values are not accepted for this status detail.")
    if fact.assertion not in entry.allowed_assertions:
        issues.append("The selected assertion is not supported by this catalog entry.")
    if entry.effective_date_required and fact.effective_date is None:
        issues.append("Add an effective date before approving this detail.")
    return list(dict.fromkeys(issues))


async def _annotate_patient_candidates(
    session: SessionDep,
    candidates: dict[str, object],
) -> tuple[dict[str, object], list[str]]:
    """Attach catalog review warnings without silently accepting free-text concepts."""

    parsed = PatientImportCandidates.model_validate(candidates)
    entries = await active_catalog_entries(session)
    index = _catalog_index(entries)
    normalized = parsed.model_dump(mode="json")
    warnings: list[str] = []
    for fact, raw_fact in zip(parsed.facts, normalized.get("facts", []), strict=True):
        entry = _matched_catalog_entry(fact.fact_type.value, fact.concept, index)
        issues = _catalog_issues(fact, entry)
        raw_warnings = list(raw_fact.get("warnings", []))
        for issue in issues:
            if issue not in raw_warnings:
                raw_warnings.append(issue)
            warning = f"Catalog review: {fact.concept} — {issue}"
            if warning not in warnings:
                warnings.append(warning)
        raw_fact["warnings"] = raw_warnings[:10]
    return normalized, warnings


def _unsupported_category(fact_type: str) -> str:
    return fact_type if fact_type in {"condition", "medication", "observation"} else "other"


def _unsupported_import_detail(
    patient_id: uuid.UUID,
    fact: Any,
    issues: list[str],
) -> PatientUnsupportedDetail:
    context = (
        f"Imported document p.{fact.source.page}: {fact.source.text}. "
        f"{' '.join(issues)}"
    )
    return PatientUnsupportedDetail(
        patient_id=patient_id,
        category=_unsupported_category(fact.fact_type.value),
        label=fact.concept,
        context=context[:500],
        source_label=f"Imported document p.{fact.source.page}",
    )


def _fact_event_payload(
    fact_id: uuid.UUID,
    fact_type: str,
    concept: str,
    assertion: Assertion,
    value_numeric: object,
    unit: str | None,
    effective_date: object,
    source_label: str,
) -> dict[str, object]:
    return {
        "id": str(fact_id),
        "fact_type": fact_type,
        "concept": concept,
        "assertion": assertion.value,
        "value_numeric": str(value_numeric) if value_numeric is not None else None,
        "unit": unit,
        "effective_date": (
            effective_date.isoformat() if hasattr(effective_date, "isoformat") else None
        ),
        "source_label": source_label,
    }


def _preserve_sources(document: Document, candidates: dict[str, object]) -> None:
    spans = {str(span.id): span for span in document.spans}
    key = "facts" if document.kind is DocumentKind.patient else "criteria"
    items = candidates.get(key, [])
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("source"), dict):
            continue
        source = item["source"]
        span = spans.get(str(source.get("span_id")))
        if span is None:
            raise ApplicationError(
                code="IMPORT_PROVENANCE_INVALID",
                message="Every extracted candidate must retain its original source span.",
                status_code=422,
            )
        item["source"] = {
            "span_id": str(span.id),
            "page": span.page,
            "start": span.start_offset,
            "end": span.end_offset,
            "text": span.exact_text,
        }


@router.post("", response_model=ImportRead, status_code=status.HTTP_201_CREATED)
async def analyze_import(
    payload: ImportAnalyzeRequest, request: Request, session: SessionDep, user: CurrentUser
) -> ImportRead:
    original: bytes | None = None
    try:
        if payload.source_type is DocumentSourceType.pdf:
            original = _decode_pdf(payload)
            extracted = extract_pdf_input(original)
            mime_type = "application/pdf"
            size_bytes = len(original)
            checksum_content = original
        else:
            extracted = extract_text_input(payload.text or "")
            mime_type = "text/plain"
            checksum_content = extracted.text.encode("utf-8")
            size_bytes = len(checksum_content)
    except ImportParseError as exception:
        raise ApplicationError(
            code=exception.code, message=exception.message, status_code=422
        ) from exception

    extractor = request.app.state.extractor
    try:
        if (
            isinstance(extractor, GroqExtractor)
            and len(extracted.text) > request.app.state.settings.provider_max_input_chars
        ):
            raise ProviderCallError(
                "PROVIDER_INPUT_TOO_LARGE", "The source exceeds the external provider limit."
            )
        extraction = await extractor.extract(payload.kind, extracted)
    except ProviderCallError as exception:
        extraction = await RuleBasedExtractor().extract(payload.kind, extracted)
        extraction = type(extraction)(
            candidates=extraction.candidates,
            warnings=[
                "External extraction was unavailable; deterministic candidates are shown.",
                *extraction.warnings,
            ],
            metadata={
                **extraction.metadata,
                "requested_provider": "groq",
                "provider_error": exception.code,
                "validation_outcome": "fallback",
            },
        )
    candidates, warnings = extraction.candidates, extraction.warnings
    if payload.kind is DocumentKind.patient:
        candidates, catalog_warnings = await _annotate_patient_candidates(session, candidates)
        warnings = [*warnings, *catalog_warnings]

    document = Document(
        owner_id=user.id,
        kind=payload.kind,
        source_type=payload.source_type,
        status=DocumentStatus.needs_review,
        filename=payload.filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        checksum=hashlib.sha256(checksum_content).hexdigest(),
        original_content=original,
        source_text=extracted.text,
        pages_json=extracted.pages,
        candidates_json=candidates,
        warnings_json=warnings,
        quality_json={**extracted.quality, "nlp": extraction.metadata},
    )
    _attach_spans(document, candidates)
    document.candidates_json = candidates
    session.add(document)
    await session.commit()
    return import_read(await owned_import(session, user, document.id))


@router.get("/{import_id}", response_model=ImportRead)
async def get_import(import_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> ImportRead:
    return import_read(await owned_import(session, user, import_id))


@router.put("/{import_id}", response_model=ImportRead)
async def update_import(
    import_id: uuid.UUID,
    payload: ImportUpdateRequest,
    session: SessionDep,
    user: CurrentUser,
) -> ImportRead:
    document = await owned_import(session, user, import_id)
    if document.status is not DocumentStatus.needs_review:
        raise ApplicationError(
            code="IMPORT_IMMUTABLE",
            message="Only imports awaiting review can be edited.",
            status_code=409,
        )
    candidates = _validate_candidates(document.kind, payload.candidates)
    _preserve_sources(document, candidates)
    if document.kind is DocumentKind.patient:
        candidates, catalog_warnings = await _annotate_patient_candidates(session, candidates)
        document.warnings_json = [
            warning
            for warning in document.warnings_json
            if not warning.startswith("Catalog review:")
        ] + catalog_warnings
    document.candidates_json = candidates
    await session.commit()
    return import_read(await owned_import(session, user, import_id))


@router.post("/{import_id}/approve", response_model=ImportApprovalRead)
async def approve_import(
    import_id: uuid.UUID,
    payload: ImportApproveRequest,
    session: SessionDep,
    user: CurrentUser,
) -> ImportApprovalRead:
    document = await owned_import(session, user, import_id)
    if document.status is not DocumentStatus.needs_review:
        raise ApplicationError(
            code="IMPORT_ALREADY_REVIEWED",
            message="This import has already been reviewed.",
            status_code=409,
        )
    candidates = _validate_candidates(document.kind, document.candidates_json)
    if document.kind is DocumentKind.patient:
        candidates, catalog_warnings = await _annotate_patient_candidates(session, candidates)
        document.candidates_json = candidates
        document.warnings_json = [
            warning
            for warning in document.warnings_json
            if not warning.startswith("Catalog review:")
        ] + catalog_warnings
    try:
        if document.kind is DocumentKind.patient:
            patient_candidates = PatientImportCandidates.model_validate(candidates)
            duplicate = await session.scalar(
                select(Patient).where(
                    Patient.owner_id == user.id,
                    func.lower(Patient.display_name)
                    == patient_candidates.profile.display_name.strip().lower(),
                )
            )
            if duplicate is not None and not payload.confirm_duplicate_name:
                raise ApplicationError(
                    code="PATIENT_NAME_REVIEW_REQUIRED",
                    message=(
                        "A patient with this name already exists. Review it or confirm a "
                        "distinct synthetic person."
                    ),
                    status_code=409,
                    details=[
                        {"patient_id": str(duplicate.id), "display_name": duplicate.display_name}
                    ],
                )
            patient = Patient(
                owner_id=user.id,
                external_id=f"SYN-{uuid.uuid4().hex[:10].upper()}",
                display_name=patient_candidates.profile.display_name,
                date_of_birth=patient_candidates.profile.date_of_birth,
                sex=patient_candidates.profile.sex,
            )
            session.add(patient)
            await session.flush()
            catalog_index = _catalog_index(await active_catalog_entries(session))
            session.add(
                PatientChangeEvent(
                    patient_id=patient.id,
                    actor_id=user.id,
                    event_type="patient_created",
                    entity_type="patient",
                    entity_id=patient.id,
                    after_json={
                        "display_name": patient.display_name,
                        "date_of_birth": (
                            patient.date_of_birth.isoformat() if patient.date_of_birth else None
                        ),
                        "sex": patient.sex,
                    },
                )
            )
            for fact in patient_candidates.facts:
                if not fact.selected:
                    continue
                entry = _matched_catalog_entry(
                    fact.fact_type.value,
                    fact.concept,
                    catalog_index,
                )
                issues = _catalog_issues(fact, entry)
                source_label = f"Imported document p.{fact.source.page}"
                if entry is None or issues:
                    session.add(_unsupported_import_detail(patient.id, fact, issues))
                    continue
                canonical_unit = (
                    entry.fixed_unit if entry.input_kind is PatientFactInputKind.numeric else None
                )
                saved_fact = PatientFact(
                    patient_id=patient.id,
                    fact_type=entry.fact_type,
                    concept=entry.concept,
                    value_numeric=fact.value_numeric,
                    value_text=None,
                    unit=canonical_unit,
                    assertion=fact.assertion,
                    effective_date=fact.effective_date,
                    source_label=source_label,
                )
                session.add(saved_fact)
                await session.flush()
                session.add(
                    PatientChangeEvent(
                        patient_id=patient.id,
                        actor_id=user.id,
                        event_type="fact_created",
                        entity_type="fact",
                        entity_id=saved_fact.id,
                        after_json=_fact_event_payload(
                            saved_fact.id,
                            entry.fact_type.value,
                            entry.concept,
                            fact.assertion,
                            fact.value_numeric,
                            canonical_unit,
                            fact.effective_date,
                            source_label,
                        ),
                    )
                )
            resource_id = patient.id
        else:
            trial_candidates = TrialImportCandidates.model_validate(candidates)
            selected = [criterion for criterion in trial_candidates.criteria if criterion.selected]
            if any(
                criterion.parse_state != "parsed" or criterion.normalized_rule is None
                for criterion in selected
            ):
                raise ApplicationError(
                    code="IMPORT_REVIEW_INCOMPLETE",
                    message="Selected criteria need valid manual rules before approval.",
                    status_code=422,
                )
            trial = Trial(
                owner_id=user.id,
                registry_id=f"SYN-TRIAL-{uuid.uuid4().hex[:10].upper()}",
                title=trial_candidates.profile.title,
                condition=trial_candidates.profile.condition,
                phase=trial_candidates.profile.phase,
            )
            session.add(trial)
            await session.flush()
            version = TrialVersion(
                trial_id=trial.id,
                version=1,
                status=VersionStatus.draft,
                source_text=document.source_text,
            )
            session.add(version)
            await session.flush()
            for order, criterion in enumerate(selected, 1):
                session.add(
                    Criterion(
                        trial_version_id=version.id,
                        kind=criterion.kind,
                        order=order,
                        source_text=criterion.source_text,
                        normalized_rule=criterion.normalized_rule,
                        required=True,
                    )
                )
            resource_id = trial.id
        document.status = DocumentStatus.approved
        document.approved_resource_id = resource_id
        await session.commit()
    except ApplicationError:
        await session.rollback()
        raise
    except Exception:
        await session.rollback()
        raise
    return ImportApprovalRead(kind=document.kind, resource_id=resource_id, review_id=document.id)


@router.delete("/{import_id}", status_code=status.HTTP_204_NO_CONTENT)
async def reject_import(import_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    document = await owned_import(session, user, import_id)
    if document.status is not DocumentStatus.needs_review:
        raise ApplicationError(
            code="IMPORT_ALREADY_REVIEWED",
            message="This import has already been reviewed.",
            status_code=409,
        )
    document.status = DocumentStatus.rejected
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
