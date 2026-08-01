from __future__ import annotations

from fastapi import APIRouter

from trialsync.api.deps import CurrentUser, SessionDep
from trialsync.patient_data import PatientFactCatalogResponse
from trialsync.patient_data.catalog import active_catalog_entries

router = APIRouter(prefix="/api/v1/patient-fact-catalog", tags=["patient facts"])


@router.get("", response_model=PatientFactCatalogResponse)
async def get_patient_fact_catalog(
    session: SessionDep,
    user: CurrentUser,
) -> PatientFactCatalogResponse:
    del user
    return PatientFactCatalogResponse(entries=tuple(await active_catalog_entries(session)))
