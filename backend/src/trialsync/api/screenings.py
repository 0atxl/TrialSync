from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from trialsync.api.deps import CurrentUser, SessionDep
from trialsync.api.errors import ApplicationError
from trialsync.db.models import (
    PatientSnapshot,
    Screening,
    ScreeningBatch,
    ScreeningChatMessage,
    TrialVersion,
)
from trialsync.nlp.chat import (
    CHAT_PROMPT_VERSION,
    CanonicalExplainer,
    ScreeningChatContext,
    ScreeningChatProvider,
    contextual_suggestions,
    is_criterion_state_question,
    is_screening_assistant_capability_question,
    validate_answer,
)
from trialsync.nlp.groq import ProviderCallError
from trialsync.reports import assemble_screening_report, render_screening_report_pdf
from trialsync.schemas import (
    BatchCreate,
    BatchPairRead,
    BatchStateCounts,
    CriterionEvaluationRead,
    PatientSnapshotSummary,
    ScreeningBatchRead,
    ScreeningChatCitationRead,
    ScreeningChatMessageCreate,
    ScreeningChatMessageRead,
    ScreeningChatProviderRead,
    ScreeningConversationRead,
    ScreeningCounts,
    ScreeningCreate,
    ScreeningRead,
    TrialVersionSummary,
)
from trialsync.screening.service import (
    owned_approved_version,
    owned_patient,
    owned_snapshot,
    run_and_store,
    snapshot_for_patient,
)

router = APIRouter(tags=["screenings"])
chat_metrics = logging.getLogger("trialsync.chat.metrics")


def _counts(screening: Screening) -> ScreeningCounts:
    results = [item.result.value for item in screening.evaluations]
    return ScreeningCounts(
        pass_count=results.count("pass"),
        fail_count=results.count("fail"),
        unknown_count=results.count("unknown"),
    )


def _snapshot_summary(screening: Screening) -> PatientSnapshotSummary:
    snapshot = screening.patient_snapshot
    source = snapshot.source_summary
    return PatientSnapshotSummary(
        id=snapshot.id,
        external_id=str(source.get("external_id", "Synthetic patient")),
        display_name=str(source.get("display_name", "Synthetic patient")),
        date_of_birth=snapshot.date_of_birth,
        sex=str(source["sex"]) if source.get("sex") is not None else None,
        facts=snapshot.facts_json,
    )


def _screening_read(screening: Screening) -> ScreeningRead:
    return ScreeningRead(
        id=screening.id,
        batch_id=screening.batch_id,
        patient_snapshot_id=screening.patient_snapshot_id,
        patient_snapshot=_snapshot_summary(screening),
        trial_version_id=screening.trial_version_id,
        trial_version=TrialVersionSummary(
            registry_id=screening.trial_registry_id,
            title=screening.trial_title,
            version=screening.trial_version_number,
        ),
        overall_state=screening.overall_state.value,
        screening_date=screening.screening_date,
        engine_version=screening.engine_version,
        dsl_version=screening.dsl_version,
        terminology_version=screening.terminology_version,
        unit_version=screening.unit_version,
        created_at=screening.created_at,
        counts=_counts(screening),
        evaluations=[
            CriterionEvaluationRead(
                id=item.id,
                criterion_id=item.criterion_id,
                criterion_order=item.criterion_order,
                criterion_kind=item.criterion_kind,
                result=item.result.value,
                truth=item.truth,
                reason_code=item.reason_code,
                criterion_source_text=item.criterion_source_text,
                canonical_explanation=item.canonical_explanation,
                evidence=item.evidence_json,
                rejected_evidence=item.rejected_evidence_json,
                missing_information=item.missing_information_json,
            )
            for item in screening.evaluations
        ],
    )


def _batch_read(batch: ScreeningBatch) -> ScreeningBatchRead:
    states = [item.overall_state.value for item in batch.screenings]
    unknown_criterion_count = sum(_counts(item).unknown_count for item in batch.screenings)
    return ScreeningBatchRead(
        id=batch.id,
        label=batch.label,
        pair_count=batch.pair_count,
        created_at=batch.created_at,
        state_counts=BatchStateCounts(
            potentially_eligible=states.count("potentially_eligible"),
            likely_ineligible=states.count("likely_ineligible"),
            needs_review=states.count("needs_review"),
        ),
        unknown_criterion_count=unknown_criterion_count,
        screenings=[
            BatchPairRead(
                patient_snapshot_id=item.patient_snapshot_id,
                patient_snapshot=_snapshot_summary(item),
                trial_version_id=item.trial_version_id,
                trial_version=TrialVersionSummary(
                    registry_id=item.trial_registry_id,
                    title=item.trial_title,
                    version=item.trial_version_number,
                ),
                screening_id=item.id,
                overall_state=item.overall_state.value,
                counts=_counts(item),
            )
            for item in batch.screenings
        ],
    )


async def _owned_screening(
    session: SessionDep, owner_id: uuid.UUID, screening_id: uuid.UUID
) -> Screening:
    screening = await session.scalar(
        select(Screening)
        .options(
            selectinload(Screening.patient_snapshot),
            selectinload(Screening.evaluations),
        )
        .where(Screening.id == screening_id, Screening.owner_id == owner_id)
    )
    if screening is None:
        raise ApplicationError(
            code="SCREENING_NOT_FOUND", message="Screening was not found.", status_code=404
        )
    return screening


async def _owned_batch(
    session: SessionDep, owner_id: uuid.UUID, batch_id: uuid.UUID
) -> ScreeningBatch:
    batch = await session.scalar(
        select(ScreeningBatch)
        .options(
            selectinload(ScreeningBatch.screenings).selectinload(Screening.evaluations),
            selectinload(ScreeningBatch.screenings).selectinload(Screening.patient_snapshot),
        )
        .where(ScreeningBatch.id == batch_id, ScreeningBatch.owner_id == owner_id)
    )
    if batch is None:
        raise ApplicationError(
            code="SCREENING_BATCH_NOT_FOUND",
            message="Screening batch was not found.",
            status_code=404,
        )
    return batch


@router.post(
    "/api/v1/screenings",
    response_model=ScreeningRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_screening(
    payload: ScreeningCreate, session: SessionDep, user: CurrentUser
) -> ScreeningRead:
    try:
        patient = await owned_patient(session, user.id, payload.patient_id)
        version = await owned_approved_version(session, user.id, payload.trial_version_id)
        snapshot = await snapshot_for_patient(session, patient)
        screening = await run_and_store(
            session,
            owner_id=user.id,
            snapshot=snapshot,
            version=version,
            screening_date=payload.screening_date or date.today(),
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return _screening_read(await _owned_screening(session, user.id, screening.id))


@router.get("/api/v1/screenings", response_model=list[ScreeningRead])
async def list_screenings(
    session: SessionDep,
    user: CurrentUser,
    patient_id: uuid.UUID | None = None,
    trial_id: uuid.UUID | None = None,
) -> list[ScreeningRead]:
    statement = (
        select(Screening)
        .options(
            selectinload(Screening.patient_snapshot),
            selectinload(Screening.evaluations),
        )
        .where(Screening.owner_id == user.id)
    )
    if patient_id is not None:
        statement = statement.join(Screening.patient_snapshot).where(
            PatientSnapshot.patient_id == patient_id
        )
    if trial_id is not None:
        statement = statement.join(
            TrialVersion,
            Screening.trial_version_id == TrialVersion.id,
        ).where(TrialVersion.trial_id == trial_id)
    results = await session.scalars(
        statement.order_by(Screening.created_at.desc()).limit(100)
    )
    return [_screening_read(item) for item in results.unique()]


@router.get("/api/v1/screenings/{screening_id}", response_model=ScreeningRead)
async def get_screening(
    screening_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> ScreeningRead:
    return _screening_read(await _owned_screening(session, user.id, screening_id))


@router.get("/api/v1/screenings/{screening_id}/report.pdf")
async def download_screening_report(
    screening_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Response:
    screening = await _owned_screening(session, user.id, screening_id)
    report = assemble_screening_report(screening, generated_at=datetime.now(UTC))
    content = render_screening_report_pdf(report)
    filename = f"trialsync-screening-{screening.id}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _chat_context(screening: Screening) -> ScreeningChatContext:
    evaluations: list[dict[str, object]] = []
    for item in screening.evaluations:
        evaluations.append(
            {
                "criterion_id": str(item.criterion_id),
                "evaluation_id": str(item.id),
                "criterion_order": item.criterion_order,
                "criterion_kind": item.criterion_kind.value,
                "source_text": item.criterion_source_text,
                "result": item.result.value,
                "reason_code": item.reason_code,
                "canonical_explanation": item.canonical_explanation,
                "evidence_ids": [
                    str(value["fact_id"])
                    for value in item.evidence_json
                    if isinstance(value, dict) and value.get("fact_id") is not None
                ],
                "evidence": item.evidence_json,
                "missing_information": item.missing_information_json,
            }
        )
    counts = _counts(screening)
    return ScreeningChatContext(
        screening_id=str(screening.id),
        overall_state=screening.overall_state.value,
        counts={
            "pass": counts.pass_count,
            "fail": counts.fail_count,
            "unknown": counts.unknown_count,
        },
        evaluations=tuple(evaluations),
        versions={
            "engine": screening.engine_version,
            "dsl": screening.dsl_version,
            "patient_snapshot": str(screening.patient_snapshot_id),
            "trial_version": str(screening.trial_version_id),
        },
    )


def _provider_read(provider: ScreeningChatProvider) -> ScreeningChatProviderRead:
    return ScreeningChatProviderRead(
        enabled=provider.enabled,
        provider=provider.provider_name,
        model=provider.model_id,
        prompt_version=CHAT_PROMPT_VERSION,
    )


async def _recent_chat(
    session: SessionDep, screening_id: uuid.UUID, limit: int
) -> list[ScreeningChatMessage]:
    rows = list(
        await session.scalars(
            select(ScreeningChatMessage)
            .where(ScreeningChatMessage.screening_id == screening_id)
            .order_by(ScreeningChatMessage.created_at.desc(), ScreeningChatMessage.id.desc())
            .limit(limit)
        )
    )
    rows.reverse()
    return rows


def _message_read(
    message: ScreeningChatMessage,
    suggested_questions: list[str] | None = None,
    citation_labels: dict[str, str] | None = None,
) -> ScreeningChatMessageRead:
    provider = None
    if message.role == "assistant":
        provider = ScreeningChatProviderRead(
            enabled=True,
            provider=message.provider or "unknown",
            model=message.model_id,
            prompt_version=message.prompt_version or CHAT_PROMPT_VERSION,
        )
    return ScreeningChatMessageRead(
        id=message.id,
        role=message.role,
        content=message.content,
        answer_state=message.answer_state,
        citations=[
            ScreeningChatCitationRead.model_validate(
                {
                    **item,
                    "label": (citation_labels or {}).get(
                        str(item.get("evaluation_id")), str(item.get("label", "Criterion"))
                    ),
                }
            )
            for item in message.citations_json
        ],
        provider=provider,
        created_at=message.created_at,
        suggested_questions=suggested_questions or [],
    )


@router.get(
    "/api/v1/screenings/{screening_id}/conversation",
    response_model=ScreeningConversationRead,
)
async def get_screening_conversation(
    screening_id: uuid.UUID, request: Request, session: SessionDep, user: CurrentUser
) -> ScreeningConversationRead:
    screening = await _owned_screening(session, user.id, screening_id)
    limit = request.app.state.settings.screening_chat_max_messages
    messages = await _recent_chat(session, screening.id, limit)
    context = _chat_context(screening)
    citation_labels = {
        str(item["evaluation_id"]): str(item["source_text"])
        for item in context.evaluations
    }
    return ScreeningConversationRead(
        screening_id=screening.id,
        messages=[_message_read(message, citation_labels=citation_labels) for message in messages],
        provider=_provider_read(request.app.state.chat_provider),
        suggested_questions=contextual_suggestions(context),
        max_messages=limit,
        max_message_chars=request.app.state.settings.screening_chat_message_max_chars,
    )


@router.post(
    "/api/v1/screenings/{screening_id}/conversation/messages",
    response_model=ScreeningChatMessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_screening_chat_message(
    screening_id: uuid.UUID,
    payload: ScreeningChatMessageCreate,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> ScreeningChatMessageRead:
    screening = await _owned_screening(session, user.id, screening_id)
    settings = request.app.state.settings
    message = payload.message.strip()
    if not message or len(message) > settings.screening_chat_message_max_chars:
        raise ApplicationError(
            code="ASSISTANT_MESSAGE_TOO_LONG",
            message=(
                "Messages must contain at most "
                f"{settings.screening_chat_message_max_chars} characters."
            ),
            status_code=422,
            field="message",
        )
    history_rows = await _recent_chat(session, screening.id, settings.screening_chat_max_messages)
    history = [{"role": item.role, "content": item.content} for item in history_rows]
    context = _chat_context(screening)
    provider = request.app.state.chat_provider
    provider_used = provider
    fallback_used = False
    started = time.perf_counter()
    if (
        is_screening_assistant_capability_question(message.casefold())
        or is_criterion_state_question(message.casefold())
    ):
        provider_used = CanonicalExplainer()
        raw_answer = await provider_used.answer(context=context, history=history, message=message)
        answer = validate_answer(raw_answer, context)
    else:
        try:
            raw_answer = await provider.answer(context=context, history=history, message=message)
            answer = validate_answer(raw_answer, context)
        except ProviderCallError as exception:
            code_map = {
                "PROVIDER_TIMEOUT": ("ASSISTANT_TIMEOUT", 504),
                "PROVIDER_RATE_LIMITED": ("ASSISTANT_RATE_LIMITED", 429),
                "PROVIDER_RESPONSE_INVALID": ("ASSISTANT_RESPONSE_INVALID", 502),
                "PROVIDER_ERROR": ("ASSISTANT_PROVIDER_ERROR", 502),
                "ASSISTANT_DISABLED": ("ASSISTANT_DISABLED", 503),
            }
            code, status_code = code_map.get(exception.code, ("ASSISTANT_PROVIDER_ERROR", 502))
            chat_metrics.warning(
                "screening_chat_provider_failed",
                extra={
                    "provider": provider.provider_name,
                    "model_id": provider.model_id,
                    "prompt_version": CHAT_PROMPT_VERSION,
                    "latency_ms": round((time.perf_counter() - started) * 1_000, 2),
                    "validation_outcome": exception.code,
                    "answer_state": None,
                },
            )
            if provider.provider_name != "groq":
                raise ApplicationError(
                    code=code, message=exception.message, status_code=status_code
                ) from exception
            provider_used = CanonicalExplainer()
            raw_answer = await provider_used.answer(
                context=context, history=history, message=message
            )
            answer = validate_answer(raw_answer, context)
            fallback_used = True
    now = datetime.now(UTC)
    user_message = ScreeningChatMessage(
        screening_id=screening.id,
        role="user",
        content=message,
        answer_state=None,
        citations_json=[],
        created_at=now,
    )
    assistant_message = ScreeningChatMessage(
        screening_id=screening.id,
        role="assistant",
        content=answer.answer[: settings.screening_chat_max_answer_chars],
        answer_state=answer.answer_state,
        citations_json=[item.model_dump(mode="json") for item in answer.citations],
        provider=provider_used.provider_name,
        model_id=provider_used.model_id,
        prompt_version=CHAT_PROMPT_VERSION,
        created_at=now + timedelta(microseconds=1),
    )
    try:
        session.add_all([user_message, assistant_message])
        await session.flush()
        keep_ids = list(
            await session.scalars(
                select(ScreeningChatMessage.id)
                .where(ScreeningChatMessage.screening_id == screening.id)
                .order_by(
                    ScreeningChatMessage.created_at.desc(), ScreeningChatMessage.id.desc()
                )
                .limit(settings.screening_chat_max_messages)
            )
        )
        await session.execute(
            delete(ScreeningChatMessage).where(
                ScreeningChatMessage.screening_id == screening.id,
                ScreeningChatMessage.id.not_in(keep_ids),
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    validation_outcome = (
        "provider_fallback"
        if fallback_used
        else "safe_downgrade"
        if raw_answer.answer_state == "supported"
        and answer.answer_state == "insufficient_evidence"
        else "valid"
    )
    chat_metrics.info(
        "screening_chat_completed",
        extra={
            "provider": provider_used.provider_name,
            "model_id": provider_used.model_id,
            "prompt_version": CHAT_PROMPT_VERSION,
            "latency_ms": round((time.perf_counter() - started) * 1_000, 2),
            "validation_outcome": validation_outcome,
            "answer_state": answer.answer_state,
            "citation_count": len(answer.citations),
        },
    )
    return _message_read(assistant_message, answer.suggested_questions)


@router.delete(
    "/api/v1/screenings/{screening_id}/conversation",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_screening_conversation(
    screening_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Response:
    screening = await _owned_screening(session, user.id, screening_id)
    await session.execute(
        delete(ScreeningChatMessage).where(ScreeningChatMessage.screening_id == screening.id)
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/api/v1/screening-batches",
    response_model=ScreeningBatchRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_batch(
    payload: BatchCreate, request: Request, session: SessionDep, user: CurrentUser
) -> ScreeningBatchRead:
    patient_ids = list(dict.fromkeys(payload.patient_ids))
    snapshot_ids = list(dict.fromkeys(payload.patient_snapshot_ids))
    patient_count = len(patient_ids) or len(snapshot_ids)
    version_ids = list(dict.fromkeys(payload.trial_version_ids))
    max_patients = request.app.state.settings.screening_batch_max_patients
    max_trials = request.app.state.settings.screening_batch_max_trials
    max_pairs = request.app.state.settings.screening_batch_max_pairs
    if patient_count > max_patients or len(version_ids) > max_trials:
        raise ApplicationError(
            code="BATCH_LIMIT_EXCEEDED",
            message="Batch selection exceeds configured limits.",
            status_code=422,
        )
    pair_count = patient_count * len(version_ids)
    if pair_count > max_pairs:
        raise ApplicationError(
            code="BATCH_LIMIT_EXCEEDED",
            message="Batch pair count exceeds configured limit.",
            status_code=422,
        )
    try:
        if patient_ids:
            patients = [await owned_patient(session, user.id, item) for item in patient_ids]
            snapshots = [await snapshot_for_patient(session, patient) for patient in patients]
        else:
            snapshots = [await owned_snapshot(session, user.id, item) for item in snapshot_ids]
        versions = [await owned_approved_version(session, user.id, item) for item in version_ids]
        batch = ScreeningBatch(owner_id=user.id, label=payload.label, pair_count=pair_count)
        session.add(batch)
        await session.flush()
        screening_date = payload.screening_date or date.today()
        for snapshot in snapshots:
            for version in versions:
                await run_and_store(
                    session,
                    owner_id=user.id,
                    snapshot=snapshot,
                    version=version,
                    screening_date=screening_date,
                    batch=batch,
                )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return _batch_read(await _owned_batch(session, user.id, batch.id))


@router.get("/api/v1/screening-batches", response_model=list[ScreeningBatchRead])
async def list_batches(session: SessionDep, user: CurrentUser) -> list[ScreeningBatchRead]:
    results = await session.scalars(
        select(ScreeningBatch)
        .options(
            selectinload(ScreeningBatch.screenings).selectinload(Screening.evaluations),
            selectinload(ScreeningBatch.screenings).selectinload(Screening.patient_snapshot),
        )
        .where(ScreeningBatch.owner_id == user.id)
        .order_by(ScreeningBatch.created_at.desc())
        .limit(100)
    )
    return [_batch_read(item) for item in results.unique()]


@router.get("/api/v1/screening-batches/{batch_id}", response_model=ScreeningBatchRead)
async def get_batch(
    batch_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> ScreeningBatchRead:
    return _batch_read(await _owned_batch(session, user.id, batch_id))
