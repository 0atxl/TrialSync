from __future__ import annotations

from fastapi import APIRouter

from trialsync.api.deps import CurrentUser
from trialsync.patient_data import PatientFactCatalogResponse
from trialsync.patient_data.catalog import PATIENT_FACT_CATALOG_RESPONSE

router = APIRouter(prefix="/api/v1/patient-fact-catalog", tags=["patient facts"])


@router.get("", response_model=PatientFactCatalogResponse)
async def get_patient_fact_catalog(user: CurrentUser) -> PatientFactCatalogResponse:
    del user
    return PATIENT_FACT_CATALOG_RESPONSE

