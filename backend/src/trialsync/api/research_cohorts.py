"""Authenticated read-only APIs for R6 cohort and exact-similarity artifacts."""

from __future__ import annotations

from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from trialsync.api.deps import CurrentUser
from trialsync.research.artifacts import CohortArtifactService

RepresentationName = Literal["patient_fact", "screening_profile"]

router = APIRouter(prefix="/api/v1/research", tags=["research cohorts"])


class CohortRunSummary(BaseModel):
    run_id: str
    active: bool
    status: Literal["ready", "degraded"]
    contract_version: str
    generated_at: str
    screening_date: str
    member_count: int
    trial_count: int
    pair_count: int
    engine_version: str
    representations: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class CohortRunsResponse(BaseModel):
    status: Literal["ready", "degraded"]
    active_run_id: str | None
    message: str | None
    runs: list[CohortRunSummary]


class CohortClustersResponse(BaseModel):
    run_id: str
    representation: RepresentationName
    representation_version: str
    display_projection_only: bool
    distance_distribution: dict[str, float]
    selected_parameters: dict[str, float | int]
    selection_reason: str
    cluster_count: int
    noise_fraction: float
    clusters: list[dict[str, Any]]
    points: list[dict[str, Any]]
    condition_composition: list[dict[str, Any]]


class CohortMembersResponse(BaseModel):
    run_id: str
    representation: RepresentationName
    total: int
    offset: int
    limit: int
    members: list[dict[str, Any]]


class SimilarityQueryCreate(BaseModel):
    model_config = {"extra": "forbid"}

    run_id: str = Field(min_length=1, max_length=80)
    representation: RepresentationName
    member_id: str = Field(min_length=1, max_length=80)
    neighbor_count: int = Field(default=10, ge=1, le=20)


class SimilarityQueryResponse(BaseModel):
    run_id: str
    representation: RepresentationName
    query_member_id: str
    index_metadata: dict[str, Any]
    neighbors: list[dict[str, Any]]


def get_cohort_service(request: Request) -> CohortArtifactService:
    return cast(CohortArtifactService, request.app.state.research_cohorts)


@router.get("/cohorts/runs", response_model=CohortRunsResponse)
def list_cohort_runs(
    _user: CurrentUser,
    request: Request,
) -> dict[str, Any]:
    return get_cohort_service(request).list_runs()


@router.get("/cohorts/runs/{run_id}", response_model=CohortRunSummary)
def get_cohort_run(
    run_id: str,
    _user: CurrentUser,
    request: Request,
) -> dict[str, Any]:
    return get_cohort_service(request).get_run(run_id)


@router.get(
    "/cohorts/runs/{run_id}/clusters",
    response_model=CohortClustersResponse,
)
def get_cohort_clusters(
    run_id: str,
    _user: CurrentUser,
    request: Request,
    representation: RepresentationName = "patient_fact",
) -> dict[str, Any]:
    return get_cohort_service(request).clusters(run_id, representation)


@router.get(
    "/cohorts/runs/{run_id}/members",
    response_model=CohortMembersResponse,
)
def list_cohort_members(
    run_id: str,
    _user: CurrentUser,
    request: Request,
    representation: RepresentationName = "patient_fact",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cluster_label: str | None = None,
    noise: bool | None = None,
) -> dict[str, Any]:
    return get_cohort_service(request).members(
        run_id,
        representation,
        offset=offset,
        limit=limit,
        cluster_label=cluster_label,
        noise=noise,
    )


@router.get("/cohorts/runs/{run_id}/members/{member_id}")
def get_cohort_member(
    run_id: str,
    member_id: str,
    _user: CurrentUser,
    request: Request,
) -> dict[str, Any]:
    return get_cohort_service(request).member(run_id, member_id)


@router.post("/similarity/queries", response_model=SimilarityQueryResponse)
def query_similarity(
    payload: SimilarityQueryCreate,
    _user: CurrentUser,
    request: Request,
) -> dict[str, Any]:
    return get_cohort_service(request).similarity(
        payload.run_id,
        payload.representation,
        payload.member_id,
        payload.neighbor_count,
    )
