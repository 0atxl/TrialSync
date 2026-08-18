from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from research.build_r6_cohort import materialize, write_artifacts
from research.configs.r6_cohort import R6CohortConfig

from trialsync.api.deps import get_current_user
from trialsync.api.errors import ApplicationError
from trialsync.research.artifacts import CohortArtifactService

pytestmark = pytest.mark.anyio


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _attach_json(
    run_directory: Path, manifest: dict[str, Any], logical_name: str, relative: str, value: object
) -> None:
    path = run_directory / relative
    _write_json(path, value)
    manifest["files"][logical_name] = {
        "path": relative,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _run_with_cluster_artifacts(tmp_path: Path) -> tuple[CohortArtifactService, str]:
    cohort = materialize(R6CohortConfig(patient_count=3, trial_count=2, seed=91))
    root = tmp_path / "r6"
    run_directory = root / cohort.run_id
    manifest = write_artifacts(cohort, run_directory)
    member_ids = [str(record["patient_snapshot_id"]) for record in cohort.patient_records]
    members = [
        {
            "member_id": member_id,
            "label": f"Participant {index:04d}",
            "date_of_birth": "1980-01-01",
            "sex": None,
            "conditions": [],
        }
        for index, member_id in enumerate(member_ids, start=1)
    ]
    for representation in ("patient_fact", "screening_profile"):
        feature_checksum = f"{representation}-features"
        _attach_json(run_directory, manifest, "members", "members.json", members)
        _attach_json(
            run_directory,
            manifest,
            f"{representation}_clusters",
            f"clusters/{representation}.json",
            {
                "representation": representation,
                "representation_version": f"r6.{representation}.v1",
                "cohort_checksum": manifest["semantic_checksums"]["cohort"],
                "feature_order_checksum": feature_checksum,
                "member_ids": member_ids,
                "distance_distribution": {
                    "nearest_neighbor_min": 0.2,
                    "nearest_neighbor_p25": 0.3,
                    "nearest_neighbor_median": 0.4,
                    "nearest_neighbor_p75": 0.5,
                    "nearest_neighbor_max": 0.6,
                },
                "selected": {
                    "eps": 0.6,
                    "min_samples": 2,
                    "labels": [0, 0, -1],
                    "cluster_count": 1,
                    "cluster_sizes": [[0, 2]],
                    "noise_fraction": 1 / 3,
                },
                "selection_reason": "Stable evaluated result.",
                "condition_composition": [],
            },
        )
        _attach_json(
            run_directory,
            manifest,
            f"{representation}_projection",
            f"projections/{representation}.json",
            {
                "representation": representation,
                "representation_version": f"r6.{representation}.v1",
                "member_ids": member_ids,
                "coordinates": [[0.0, 0.1], [0.2, 0.3], [0.4, 0.5]],
                "display_only": True,
            },
        )
        manifest.setdefault("representations", {})[representation] = {
            "version": f"r6.{representation}.v1",
            "feature_order_checksum": feature_checksum,
        }
    manifest["analysis_status"] = "ready"
    _write_json(run_directory / "manifest.json", manifest)
    return CohortArtifactService(root, cohort.run_id), cohort.run_id


def test_artifact_service_reports_unconfigured_and_incomplete_runs(tmp_path: Path) -> None:
    empty = CohortArtifactService(tmp_path / "missing", None).list_runs()
    assert empty == {
        "status": "degraded",
        "active_run_id": None,
        "message": "No active cohort run is configured.",
        "runs": [],
    }

    cohort = materialize(R6CohortConfig(patient_count=2, trial_count=2, seed=12))
    root = tmp_path / "runs"
    write_artifacts(cohort, root / cohort.run_id)
    result = CohortArtifactService(root, cohort.run_id).list_runs()
    assert result["status"] == "degraded"
    assert result["runs"][0]["member_count"] == 2


def test_malformed_manifest_is_reported_as_degraded_not_an_internal_error(
    tmp_path: Path,
) -> None:
    run_id = "r6-broken"
    run_directory = tmp_path / run_id
    run_directory.mkdir()
    _write_json(run_directory / "manifest.json", {"run_id": run_id, "files": {}})
    service = CohortArtifactService(tmp_path, run_id)

    with pytest.raises(ApplicationError) as raised:
        service.get_run(run_id)

    assert raised.value.code == "RESEARCH_COHORT_DEGRADED"
    assert service.list_runs()["status"] == "degraded"


def test_cluster_service_returns_neutral_labels_and_noise(tmp_path: Path) -> None:
    service, run_id = _run_with_cluster_artifacts(tmp_path)

    result = service.clusters(run_id, "patient_fact")

    assert result["cluster_count"] == 1
    assert result["clusters"] == [{"label": "fact_cluster_0", "size": 2}]
    assert result["points"][2]["cluster_label"] is None
    assert result["points"][2]["is_noise"] is True
    assert result["display_projection_only"] is True


def test_artifact_symlink_cannot_escape_the_run_directory(tmp_path: Path) -> None:
    service, run_id = _run_with_cluster_artifacts(tmp_path)
    run_directory = service.root / run_id
    outside = tmp_path / "outside.json"
    _write_json(outside, [])
    members = run_directory / "members.json"
    members.unlink()
    members.symlink_to(outside)
    manifest = json.loads((run_directory / "manifest.json").read_text())
    manifest["files"]["members"]["sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()
    _write_json(run_directory / "manifest.json", manifest)

    with pytest.raises(ApplicationError) as raised:
        service.clusters(run_id, "patient_fact")

    assert raised.value.code == "RESEARCH_COHORT_DEGRADED"


def test_similarity_missing_dependency_or_index_is_degraded(tmp_path: Path) -> None:
    service, run_id = _run_with_cluster_artifacts(tmp_path)

    with pytest.raises(ApplicationError) as raised:
        service.similarity(run_id, "patient_fact", "member", 5)

    assert raised.value.code == "RESEARCH_COHORT_DEGRADED"
    assert raised.value.status_code == 503


class StubCohortService:
    def list_runs(self) -> dict[str, Any]:
        return {"status": "ready", "active_run_id": "r6-a", "message": None, "runs": []}

    def get_run(self, run_id: str) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "active": True,
            "status": "ready",
            "contract_version": "r6-cohort-v1",
            "generated_at": "2026-08-16T00:00:00+00:00",
            "screening_date": "2026-08-16",
            "member_count": 750,
            "trial_count": 20,
            "pair_count": 15000,
            "engine_version": "0.1.0",
            "representations": {},
            "message": None,
        }

    def similarity(self, *args: object) -> dict[str, Any]:
        return {
            "run_id": "r6-a",
            "representation": "patient_fact",
            "query_member_id": "member-a",
            "index_metadata": {"index_type": "IndexFlatIP"},
            "neighbors": [],
        }


async def test_research_routes_require_auth_and_validate_similarity_payload(app: FastAPI) -> None:
    app.state.research_cohorts = StubCohortService()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        unauthenticated = await client.get("/api/v1/research/cohorts/runs")
        assert unauthenticated.status_code == 401

        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user")
        runs = await client.get("/api/v1/research/cohorts/runs")
        assert runs.status_code == 200
        invalid = await client.post(
            "/api/v1/research/similarity/queries",
            json={
                "run_id": "r6-a",
                "representation": "patient_fact",
                "member_id": "member-a",
                "neighbor_count": 21,
            },
        )
        assert invalid.status_code == 422
        valid = await client.post(
            "/api/v1/research/similarity/queries",
            json={
                "run_id": "r6-a",
                "representation": "patient_fact",
                "member_id": "member-a",
                "neighbor_count": 5,
            },
        )
        assert valid.status_code == 200
        assert valid.json()["index_metadata"]["index_type"] == "IndexFlatIP"
