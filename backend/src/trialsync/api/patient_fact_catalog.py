from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from trialsync.api.deps import CurrentUser, SessionDep
from trialsync.db.models import FactType
from trialsync.patient_data import PatientFactCatalogResponse
from trialsync.patient_data.catalog import active_catalog_entries
from trialsync.schemas import PatientFactCatalogSuggestionResponse
from trialsync.terminology.suggestions import TerminologySuggestionService

router = APIRouter(prefix="/api/v1/patient-fact-catalog", tags=["patient facts"])


@router.get("", response_model=PatientFactCatalogResponse)
async def get_patient_fact_catalog(
    session: SessionDep,
    user: CurrentUser,
) -> PatientFactCatalogResponse:
    del user
    return PatientFactCatalogResponse(entries=tuple(await active_catalog_entries(session)))


@router.get("/suggestions", response_model=PatientFactCatalogSuggestionResponse)
async def get_patient_fact_catalog_suggestions(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    query: Annotated[str, Query(min_length=2, max_length=100)],
    fact_type: Annotated[FactType | None, Query()] = None,
) -> PatientFactCatalogSuggestionResponse:
    del user
    normalized_query = " ".join(query.split())
    if len(normalized_query) < 2:
        raise HTTPException(status_code=422, detail="Enter at least two non-space characters.")
    term = normalized_query.casefold()
    entries = await active_catalog_entries(session)
    local_matches = [
        entry
        for entry in entries
        if (fact_type is None or entry.fact_type == fact_type)
        and term in f"{entry.display_label} {entry.concept} {entry.help_text}".casefold()
    ][:8]
    if fact_type not in {FactType.medication, FactType.observation}:
        return PatientFactCatalogSuggestionResponse(
            query=normalized_query,
            local_matches=local_matches,
        )
    service: TerminologySuggestionService = request.app.state.terminology_suggestions
    result = await service.suggest(query=normalized_query, fact_type=fact_type)
    return PatientFactCatalogSuggestionResponse(
        query=normalized_query,
        local_matches=local_matches,
        suggestions=result.suggestions,
        unavailable_sources=result.unavailable_sources,
    )
