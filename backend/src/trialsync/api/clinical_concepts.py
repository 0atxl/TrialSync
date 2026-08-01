from __future__ import annotations

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from trialsync.api.deps import CurrentUser, SessionDep
from trialsync.api.errors import ApplicationError
from trialsync.db.models import Assertion, ClinicalConcept, FactType, User
from trialsync.schemas import (
    ClinicalConceptCreate,
    ClinicalConceptRead,
    ClinicalConceptUpdate,
    TerminologySuggestionResponse,
)
from trialsync.terminology.suggestions import TerminologySuggestionService

router = APIRouter(prefix="/api/v1/clinical-concepts", tags=["clinical concepts"])


def require_catalog_admin(user: User) -> None:
    if not user.is_catalog_admin:
        raise ApplicationError(
            code="CATALOG_ADMIN_REQUIRED",
            message="Catalog management is available only to catalog administrators.",
            status_code=403,
        )


def catalog_key(label: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return key[:80]


def concept_metadata(payload: ClinicalConceptCreate) -> dict[str, object]:
    if payload.fact_type is FactType.observation:
        return {
            "concept_group": "observations",
            "input_kind": "numeric",
            "allowed_assertions_json": [Assertion.present.value, Assertion.unknown.value],
            "effective_date_required": True,
            "help_text": payload.help_text
            or f"Record the measured {payload.display_label} result.",
        }
    group = "conditions" if payload.fact_type is FactType.condition else "medications"
    return {
        "concept_group": group,
        "input_kind": "status",
        "allowed_assertions_json": [
            Assertion.present.value,
            Assertion.absent.value,
            Assertion.unknown.value,
        ],
        "effective_date_required": False,
        "help_text": payload.help_text
        or f"Record whether {payload.display_label} is present, absent, or unknown.",
    }


async def managed_concept(session: SessionDep, concept_id: uuid.UUID) -> ClinicalConcept:
    concept = await session.get(ClinicalConcept, concept_id)
    if concept is None:
        raise ApplicationError(
            code="CATALOG_CONCEPT_NOT_FOUND",
            message="The clinical concept was not found.",
            status_code=404,
        )
    return concept


@router.get("", response_model=list[ClinicalConceptRead])
async def list_clinical_concepts(
    session: SessionDep,
    user: CurrentUser,
) -> list[ClinicalConcept]:
    require_catalog_admin(user)
    records = await session.scalars(
        select(ClinicalConcept).order_by(
            ClinicalConcept.active.desc(),
            ClinicalConcept.concept_group,
            ClinicalConcept.display_order,
            ClinicalConcept.display_label,
        )
    )
    return list(records)


@router.get("/suggestions", response_model=TerminologySuggestionResponse)
async def terminology_suggestions(
    request: Request,
    user: CurrentUser,
    fact_type: Annotated[FactType, Query()],
    query: Annotated[str, Query(min_length=2, max_length=100)],
) -> TerminologySuggestionResponse:
    require_catalog_admin(user)
    service: TerminologySuggestionService = request.app.state.terminology_suggestions
    result = await service.suggest(query=query.strip(), fact_type=fact_type)
    return TerminologySuggestionResponse(
        query=query.strip(),
        suggestions=result.suggestions,
        unavailable_sources=result.unavailable_sources,
    )


@router.post("", response_model=ClinicalConceptRead, status_code=status.HTTP_201_CREATED)
async def create_clinical_concept(
    payload: ClinicalConceptCreate,
    session: SessionDep,
    user: CurrentUser,
) -> ClinicalConcept:
    require_catalog_admin(user)
    key = catalog_key(payload.display_label)
    if not key:
        raise ApplicationError(
            code="CATALOG_KEY_INVALID",
            message="Use a label containing letters or numbers.",
            status_code=422,
            field="display_label",
        )
    metadata = concept_metadata(payload)
    display_order = (
        await session.scalar(
            select(func.max(ClinicalConcept.display_order)).where(
                ClinicalConcept.concept_group == metadata["concept_group"]
            )
        )
        or 0
    ) + 10
    concept = ClinicalConcept(
        key=key,
        concept=key,
        fact_type=payload.fact_type,
        display_label=payload.display_label,
        fixed_unit=payload.fixed_unit,
        screening_supported=payload.screening_supported,
        terminology_system=payload.terminology_system,
        terminology_code=payload.terminology_code,
        display_order=display_order,
        active=True,
        **metadata,
    )
    session.add(concept)
    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="CATALOG_CONCEPT_EXISTS",
            message="A clinical concept with this label already exists.",
            status_code=409,
            field="display_label",
        ) from exception
    await session.refresh(concept)
    return concept


@router.patch("/{concept_id}", response_model=ClinicalConceptRead)
async def update_clinical_concept(
    concept_id: uuid.UUID,
    payload: ClinicalConceptUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> ClinicalConcept:
    require_catalog_admin(user)
    concept = await managed_concept(session, concept_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(concept, field, value)
    await session.commit()
    await session.refresh(concept)
    return concept


@router.post("/{concept_id}/retire", response_model=ClinicalConceptRead)
async def retire_clinical_concept(
    concept_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> ClinicalConcept:
    require_catalog_admin(user)
    concept = await managed_concept(session, concept_id)
    concept.active = False
    await session.commit()
    await session.refresh(concept)
    return concept


@router.post("/{concept_id}/restore", response_model=ClinicalConceptRead)
async def restore_clinical_concept(
    concept_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> ClinicalConcept:
    require_catalog_admin(user)
    concept = await managed_concept(session, concept_id)
    concept.active = True
    await session.commit()
    await session.refresh(concept)
    return concept
