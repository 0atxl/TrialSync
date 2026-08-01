from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from trialsync.api.auth import router as auth_router
from trialsync.api.clinical_concepts import router as clinical_concepts_router
from trialsync.api.errors import install_error_handlers
from trialsync.api.health import router as health_router
from trialsync.api.imports import router as imports_router
from trialsync.api.middleware import TraceIdMiddleware
from trialsync.api.patient_fact_catalog import router as patient_fact_catalog_router
from trialsync.api.patients import router as patients_router
from trialsync.api.screenings import router as screenings_router
from trialsync.api.trials import router as trials_router
from trialsync.config import Settings, get_settings
from trialsync.nlp.chat import build_chat_provider
from trialsync.nlp.extraction import build_extractor
from trialsync.terminology.suggestions import build_terminology_suggestion_service


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_settings.require_auth_secret()
    app = FastAPI(
        title=resolved_settings.app_name,
        debug=resolved_settings.debug,
        version="0.1.0",
        description="Academic TrialSync foundation API using synthetic data only.",
    )
    app.state.settings = resolved_settings
    app.state.extractor = build_extractor(resolved_settings)
    app.state.chat_provider = build_chat_provider(resolved_settings)
    app.state.terminology_suggestions = build_terminology_suggestion_service(resolved_settings)

    if resolved_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved_settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Trace-ID"],
        )

    app.add_middleware(TraceIdMiddleware)
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(clinical_concepts_router)
    app.include_router(patient_fact_catalog_router)
    app.include_router(patients_router)
    app.include_router(trials_router)
    app.include_router(screenings_router)
    app.include_router(imports_router)
    return app
