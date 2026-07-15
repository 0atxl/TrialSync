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
    Criterion,
    Document,
    DocumentKind,
    DocumentSourceType,
    DocumentSpan,
    DocumentStatus,
    Patient,
    PatientFact,
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

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


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
            for fact in patient_candidates.facts:
                if fact.selected:
                    session.add(
                        PatientFact(
                            patient_id=patient.id,
                            fact_type=fact.fact_type,
                            concept=fact.concept,
                            value_numeric=fact.value_numeric,
                            value_text=fact.value_text,
                            unit=fact.unit,
                            assertion=fact.assertion,
                            effective_date=fact.effective_date,
                            source_label=f"Imported document p.{fact.source.page}",
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
