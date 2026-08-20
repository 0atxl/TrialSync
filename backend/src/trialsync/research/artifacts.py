"""Validated, read-only access to versioned R6 runtime artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from trialsync.api.errors import ApplicationError
from trialsync.db.models import PatientSnapshot

if TYPE_CHECKING:
    from trialsync.research.projection import ProjectedScreening

RepresentationName = Literal["patient_fact", "screening_profile"]
_SAFE_RUN_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$")


def _degraded(message: str) -> ApplicationError:
    return ApplicationError(code="RESEARCH_COHORT_DEGRADED", message=message, status_code=503)


class CohortArtifactService:
    """Serve immutable cohort runs without making them ordinary application records."""

    def __init__(self, root: Path, active_run_id: str | None) -> None:
        self.root = root
        self.active_run_id = active_run_id

    def _run_directory(self, run_id: str) -> Path:
        if not _SAFE_RUN_ID.fullmatch(run_id):
            raise ApplicationError(
                code="RESEARCH_COHORT_RUN_NOT_FOUND",
                message="The requested cohort run was not found.",
                status_code=404,
            )
        root = self.root.resolve()
        candidate = self.root / run_id
        resolved = candidate.resolve()
        if candidate.is_symlink() or not resolved.is_relative_to(root):
            raise _degraded("The cohort run directory is not contained by the artifact root.")
        return resolved

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise _degraded(f"A required cohort artifact could not be read: {path.name}.") from exc

    def _manifest(self, run_id: str) -> dict[str, Any]:
        run_directory = self._run_directory(run_id)
        unresolved = run_directory / "manifest.json"
        try:
            path = unresolved.resolve(strict=True)
        except OSError as exc:
            raise ApplicationError(
                code="RESEARCH_COHORT_RUN_NOT_FOUND",
                message="The requested cohort run was not found.",
                status_code=404,
            ) from exc
        if unresolved.is_symlink() or not path.is_relative_to(run_directory) or not path.is_file():
            raise _degraded("The cohort manifest is not contained by its run directory.")
        manifest = self._read_json(path)
        if not isinstance(manifest, dict) or manifest.get("run_id") != run_id:
            raise _degraded("The cohort manifest does not match its run directory.")
        required = {
            "contract_version": str,
            "generator_version": str,
            "uuid_namespace": str,
            "artifact_format": str,
            "generated_at": str,
            "screening_date": str,
            "patient_count": int,
            "trial_count": int,
            "pair_count": int,
            "criterion_result_count": int,
            "engine_version": str,
            "semantic_checksums": dict,
            "files": dict,
        }
        if any(not isinstance(manifest.get(name), kind) for name, kind in required.items()):
            raise _degraded("The cohort manifest is missing required versioned metadata.")
        if "representations" in manifest and not isinstance(manifest["representations"], dict):
            raise _degraded("The cohort representation metadata is invalid.")
        return manifest

    def _artifact_path(self, run_id: str, manifest: dict[str, Any], logical_name: str) -> Path:
        record = manifest["files"].get(logical_name)
        if not isinstance(record, dict) or "path" not in record:
            raise _degraded(f"The cohort run is missing the {logical_name} artifact.")
        relative = Path(str(record["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise _degraded("The cohort manifest contains an unsafe artifact path.")
        run_directory = self._run_directory(run_id)
        unresolved = run_directory / relative
        try:
            path = unresolved.resolve(strict=True)
        except OSError as exc:
            raise _degraded(f"The cohort run is missing the {logical_name} artifact.") from exc
        if unresolved.is_symlink() or not path.is_relative_to(run_directory) or not path.is_file():
            raise _degraded(f"The cohort run is missing the {logical_name} artifact.")
        expected = record.get("sha256")
        if not isinstance(expected, str):
            raise _degraded(f"The {logical_name} artifact has no checksum.")
        try:
            observed = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise _degraded(f"The {logical_name} artifact could not be read.") from exc
        if observed != expected:
            raise _degraded(f"The {logical_name} artifact failed checksum validation.")
        return path

    @staticmethod
    def _run_summary(manifest: dict[str, Any], *, active: bool) -> dict[str, Any]:
        ready = manifest.get("analysis_status") == "ready"
        return {
            "run_id": manifest["run_id"],
            "active": active,
            "status": "ready" if ready else "degraded",
            "contract_version": manifest["contract_version"],
            "generated_at": manifest["generated_at"],
            "screening_date": manifest["screening_date"],
            "member_count": manifest["patient_count"],
            "trial_count": manifest["trial_count"],
            "pair_count": manifest["pair_count"],
            "engine_version": manifest["engine_version"],
            "representations": manifest.get("representations", {}),
            "message": None if ready else "Analysis artifacts are not complete for this run.",
        }

    def list_runs(self) -> dict[str, Any]:
        runs: list[dict[str, Any]] = []
        if self.root.is_dir():
            for path in sorted(self.root.iterdir(), key=lambda item: item.name):
                if not path.is_dir() or not _SAFE_RUN_ID.fullmatch(path.name):
                    continue
                try:
                    manifest = self._manifest(path.name)
                except ApplicationError:
                    continue
                runs.append(self._run_summary(manifest, active=path.name == self.active_run_id))
        if self.active_run_id is None:
            return {
                "status": "degraded",
                "active_run_id": None,
                "message": "No active cohort run is configured.",
                "runs": runs,
            }
        active = next((run for run in runs if run["run_id"] == self.active_run_id), None)
        if active is None:
            return {
                "status": "degraded",
                "active_run_id": self.active_run_id,
                "message": "The configured cohort run is unavailable.",
                "runs": runs,
            }
        return {
            "status": active["status"],
            "active_run_id": self.active_run_id,
            "message": active["message"],
            "runs": runs,
        }

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self._run_summary(self._manifest(run_id), active=run_id == self.active_run_id)

    def _active_manifest(self) -> tuple[str, dict[str, Any]]:
        if self.active_run_id is None:
            raise _degraded("No active cohort reference run is configured.")
        manifest = self._manifest(self.active_run_id)
        if manifest.get("analysis_status") != "ready":
            raise _degraded("The active cohort reference run is not ready.")
        return self.active_run_id, manifest

    def _project_saved_snapshot(
        self,
        snapshot: PatientSnapshot,
        *,
        screening_date: date,
        representation: RepresentationName,
    ) -> tuple[str, dict[str, Any], dict[str, Any], ProjectedScreening]:
        from trialsync.research.projection import (
            ProjectionError,
            project_patient_fact,
            project_screening_profile,
        )

        run_id, manifest = self._active_manifest()
        metadata = self._read_json(
            self._artifact_path(run_id, manifest, f"{representation}_representation_metadata")
        )
        if not isinstance(metadata, dict):
            raise _degraded("The active cohort representation metadata is invalid.")
        try:
            if representation == "patient_fact":
                projected = project_patient_fact(
                    snapshot,
                    screening_date=screening_date,
                    metadata=metadata,
                )
            else:
                panel = self._read_json(self._artifact_path(run_id, manifest, "reference_panel"))
                if not isinstance(panel, dict):
                    raise _degraded("The active cohort reference panel is invalid.")
                projected = project_screening_profile(
                    snapshot,
                    screening_date=screening_date,
                    metadata=metadata,
                    reference_panel=panel,
                    engine_version=str(manifest["engine_version"]),
                    terminology_version=str(manifest.get("terminology_version", "local-1")),
                    unit_version=str(manifest.get("unit_version", "units-1")),
                )
        except ProjectionError as exc:
            raise _degraded(str(exc)) from exc
        return run_id, manifest, metadata, projected

    def live_query_status(self) -> dict[str, Any]:
        try:
            run_id, manifest = self._active_manifest()
            for representation in ("patient_fact", "screening_profile"):
                metadata = self._read_json(
                    self._artifact_path(
                        run_id,
                        manifest,
                        f"{representation}_representation_metadata",
                    )
                )
                report = self._read_json(
                    self._artifact_path(run_id, manifest, f"{representation}_clusters")
                )
                projection = self._read_json(
                    self._artifact_path(run_id, manifest, f"{representation}_projection")
                )
                if not isinstance(metadata, dict) or not isinstance(report, dict):
                    raise _degraded("Live-query metadata is invalid.")
                selected = report.get("selected")
                if not isinstance(selected, dict) or not isinstance(
                    selected.get("core_indices"), list
                ):
                    raise _degraded("The active run predates out-of-sample DBSCAN metadata.")
                if not isinstance(projection, dict) or not all(
                    name in projection for name in ("mean", "components")
                ):
                    raise _degraded("The active run predates out-of-sample projection metadata.")
                if representation == "patient_fact" and not isinstance(
                    metadata.get("fact_units"), dict
                ):
                    raise _degraded("The active run predates patient-fact unit metadata.")
            return {"status": "ready", "run_id": run_id, "message": None}
        except ApplicationError as exc:
            return {
                "status": "degraded",
                "run_id": self.active_run_id,
                "message": exc.message,
            }

    def _members(self, run_id: str, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        value = self._read_json(self._artifact_path(run_id, manifest, "members"))
        if (
            not isinstance(value, list)
            or len(value) != manifest["patient_count"]
            or any(
                not isinstance(item, dict)
                or not isinstance(item.get("member_id"), str)
                or not isinstance(item.get("label"), str)
                for item in value
            )
            or len({item["member_id"] for item in value}) != len(value)
        ):
            raise _degraded("The cohort member artifact has an invalid structure.")
        return value

    def clusters(self, run_id: str, representation: RepresentationName) -> dict[str, Any]:
        manifest = self._manifest(run_id)
        report = self._read_json(
            self._artifact_path(run_id, manifest, f"{representation}_clusters")
        )
        projection = self._read_json(
            self._artifact_path(run_id, manifest, f"{representation}_projection")
        )
        members = self._members(run_id, manifest)
        if not isinstance(report, dict) or not isinstance(projection, dict):
            raise _degraded("The cluster artifacts have an invalid structure.")
        selected = report.get("selected")
        if not isinstance(selected, dict):
            raise _degraded("The selected cluster result is missing.")
        member_ids = report.get("member_ids")
        labels = selected.get("labels")
        coordinates = projection.get("coordinates")
        representations = manifest.get("representations")
        representation_metadata = (
            representations.get(representation, {}) if isinstance(representations, dict) else {}
        )
        if (
            report.get("representation") != representation
            or report.get("representation_version") != representation_metadata.get("version")
            or report.get("cohort_checksum") != manifest.get("semantic_checksums", {}).get("cohort")
            or report.get("feature_order_checksum")
            != representation_metadata.get("feature_order_checksum")
            or projection.get("representation") != representation
            or projection.get("representation_version") != representation_metadata.get("version")
            or projection.get("member_ids") != member_ids
            or projection.get("display_only") is not True
        ):
            raise _degraded("The cluster artifacts do not match the cohort run metadata.")
        if not (
            isinstance(member_ids, list)
            and isinstance(labels, list)
            and isinstance(coordinates, list)
            and len(member_ids) == len(labels) == len(coordinates) == len(members)
            and all(isinstance(member_id, str) for member_id in member_ids)
            and len(set(member_ids)) == len(member_ids)
            and all(isinstance(label, int) and not isinstance(label, bool) for label in labels)
        ):
            raise _degraded("The cluster, projection, and member artifacts do not align.")
        member_by_id = {str(member["member_id"]): member for member in members}
        prefix = "fact" if representation == "patient_fact" else "screening"
        points = []
        for member_id, label, coordinate in zip(member_ids, labels, coordinates, strict=True):
            member = member_by_id.get(str(member_id))
            if (
                member is None
                or not isinstance(coordinate, list)
                or len(coordinate) != 2
                or any(
                    not isinstance(value, (int, float)) or isinstance(value, bool)
                    for value in coordinate
                )
            ):
                raise _degraded("The cluster projection contains an unknown cohort member.")
            points.append(
                {
                    **member,
                    "cluster_label": None if label == -1 else f"{prefix}_cluster_{label}",
                    "is_noise": label == -1,
                    "x": coordinate[0],
                    "y": coordinate[1],
                }
            )
        cluster_sizes = selected.get("cluster_sizes", [])
        if not isinstance(cluster_sizes, list):
            raise _degraded("The selected cluster sizes are invalid.")
        try:
            selected_parameters = {
                "eps": selected["eps"],
                "min_samples": selected["min_samples"],
            }
            clusters = [
                {"label": f"{prefix}_cluster_{label}", "size": size}
                for label, size in cluster_sizes
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise _degraded("The selected cluster result is invalid.") from exc
        try:
            return {
                "run_id": run_id,
                "representation": representation,
                "representation_version": report["representation_version"],
                "display_projection_only": True,
                "distance_distribution": report["distance_distribution"],
                "selected_parameters": selected_parameters,
                "selection_reason": report["selection_reason"],
                "cluster_count": selected["cluster_count"],
                "noise_fraction": selected["noise_fraction"],
                "clusters": clusters,
                "points": points,
                "condition_composition": report.get("condition_composition", []),
            }
        except (KeyError, TypeError) as exc:
            raise _degraded("The selected cluster report is incomplete.") from exc

    def members(
        self,
        run_id: str,
        representation: RepresentationName,
        *,
        offset: int,
        limit: int,
        cluster_label: str | None,
        noise: bool | None,
    ) -> dict[str, Any]:
        cluster = self.clusters(run_id, representation)
        points = cluster["points"]
        if cluster_label is not None:
            points = [point for point in points if point["cluster_label"] == cluster_label]
        if noise is not None:
            points = [point for point in points if point["is_noise"] is noise]
        return {
            "run_id": run_id,
            "representation": representation,
            "total": len(points),
            "offset": offset,
            "limit": limit,
            "members": points[offset : offset + limit],
        }

    def member(self, run_id: str, member_id: str) -> dict[str, Any]:
        manifest = self._manifest(run_id)
        member = next(
            (
                item
                for item in self._members(run_id, manifest)
                if str(item.get("member_id")) == member_id
            ),
            None,
        )
        if member is None:
            raise ApplicationError(
                code="RESEARCH_COHORT_MEMBER_NOT_FOUND",
                message="The requested cohort member was not found.",
                status_code=404,
            )
        views = {}
        for representation in ("patient_fact", "screening_profile"):
            point = next(
                (
                    item
                    for item in self.clusters(run_id, representation)["points"]
                    if item["member_id"] == member_id
                ),
                None,
            )
            if point is None:
                raise _degraded("The cluster artifacts do not contain the requested member.")
            views[representation] = {
                key: point[key] for key in ("cluster_label", "is_noise", "x", "y")
            }
        return {"run_id": run_id, **member, "representations": views}

    def similarity(
        self,
        run_id: str,
        representation: RepresentationName,
        member_id: str,
        neighbor_count: int,
    ) -> dict[str, Any]:
        manifest = self._manifest(run_id)
        try:
            import faiss
            import numpy as np

            from trialsync.research.similarity.index import (
                ExactSimilarityIndex,
                SimilarityIndexMetadata,
                query_neighbors,
                transparent_feature_differences,
            )
        except ImportError as exc:
            raise _degraded("The exact similarity capability is not installed.") from exc
        metadata_value = self._read_json(
            self._artifact_path(run_id, manifest, f"{representation}_index_metadata")
        )
        representation_metadata = self._read_json(
            self._artifact_path(run_id, manifest, f"{representation}_representation_metadata")
        )
        try:
            metadata = SimilarityIndexMetadata(**metadata_value)
            vectors = np.load(
                self._artifact_path(run_id, manifest, f"{representation}_vectors"),
                allow_pickle=False,
            )
            raw_matrix = np.load(
                self._artifact_path(run_id, manifest, f"{representation}_raw"),
                allow_pickle=False,
            )
            index = faiss.read_index(
                str(self._artifact_path(run_id, manifest, f"{representation}_index"))
            )
            exact = ExactSimilarityIndex(
                index=index,
                metadata=metadata,
                member_ids=tuple(representation_metadata["member_ids"]),
                vectors=vectors,
                feature_names=tuple(representation_metadata["feature_names"]),
                raw_matrix=raw_matrix,
            )
        except (OSError, RuntimeError, TypeError, ValueError, KeyError) as exc:
            raise _degraded("The exact similarity artifacts are invalid.") from exc
        expected_metadata = {
            "representation": representation,
            "representation_version": representation_metadata.get("version"),
            "embedding_version": representation_metadata.get("version"),
            "preprocessing_version": representation_metadata.get("preprocessing", {}).get(
                "version"
            ),
            "cohort_checksum": manifest.get("semantic_checksums", {}).get("cohort"),
            "reference_panel_checksum": manifest.get("semantic_checksums", {}).get(
                "reference_panel"
            ),
            "criterion_order_checksum": manifest.get("semantic_checksums", {}).get(
                "criterion_order"
            ),
            "feature_order_checksum": representation_metadata.get("feature_order_checksum"),
            "subject_order_checksum": representation_metadata.get("subject_order_checksum"),
            "index_type": "IndexFlatIP",
            "dimension": representation_metadata.get("dimension"),
            "vector_count": representation_metadata.get("member_count"),
        }
        if any(getattr(metadata, name) != expected for name, expected in expected_metadata.items()):
            raise _degraded("The exact similarity metadata does not match the cohort run.")
        if not isinstance(metadata.built_at, str) or not metadata.built_at:
            raise _degraded("The exact similarity index has no build timestamp.")
        expected_shape = (metadata.vector_count, metadata.dimension)
        if (
            vectors.shape != expected_shape
            or raw_matrix.shape != expected_shape
            or len(exact.member_ids) != metadata.vector_count
            or len(set(exact.member_ids)) != metadata.vector_count
            or len(exact.feature_names) != metadata.dimension
            or not np.isfinite(vectors).all()
        ):
            raise _degraded("The exact similarity matrices do not match their metadata.")
        norms = np.linalg.norm(vectors, axis=1)
        if not np.all(np.isclose(norms, 1.0, atol=1e-5) | np.isclose(norms, 0.0, atol=1e-7)):
            raise _degraded("The exact similarity vectors are not L2-normalized.")
        if index.d != metadata.dimension or index.ntotal != metadata.vector_count:
            raise _degraded("The exact similarity index does not match its metadata.")
        canonical_members = tuple(
            str(item.get("member_id")) for item in self._members(run_id, manifest)
        )
        if exact.member_ids != canonical_members:
            raise _degraded("The exact similarity subject order does not match the cohort members.")
        try:
            result = query_neighbors(exact, member_id, neighbor_count, expected_metadata=metadata)
        except KeyError as exc:
            raise ApplicationError(
                code="RESEARCH_COHORT_MEMBER_NOT_FOUND",
                message="The requested cohort member was not found.",
                status_code=404,
            ) from exc
        members = {item["member_id"]: item for item in self._members(run_id, manifest)}
        return {
            "run_id": run_id,
            "representation": representation,
            "query_member_id": member_id,
            "index_metadata": asdict_metadata(metadata),
            "neighbors": [
                {
                    "rank": rank,
                    "member_id": neighbor.member_id,
                    "label": members[neighbor.member_id]["label"],
                    "cosine_similarity": neighbor.cosine_similarity,
                    "feature_differences": [
                        {
                            "feature": difference.feature_name,
                            "query_value": difference.query_value,
                            "neighbor_value": difference.neighbor_value,
                            "absolute_difference": difference.absolute_difference,
                        }
                        for difference in transparent_feature_differences(
                            exact, member_id, neighbor.member_id
                        )[:20]
                    ],
                }
                for rank, neighbor in enumerate(result.neighbors, start=1)
            ],
        }

    def screening_cohort_context(
        self,
        snapshot: PatientSnapshot,
        *,
        screening_date: date,
        representation: RepresentationName,
    ) -> dict[str, Any]:
        import numpy as np

        run_id, manifest, metadata, projected = self._project_saved_snapshot(
            snapshot,
            screening_date=screening_date,
            representation=representation,
        )
        report = self._read_json(
            self._artifact_path(run_id, manifest, f"{representation}_clusters")
        )
        display = self._read_json(
            self._artifact_path(run_id, manifest, f"{representation}_projection")
        )
        try:
            vectors = np.load(
                self._artifact_path(run_id, manifest, f"{representation}_vectors"),
                allow_pickle=False,
            )
            selected = report["selected"]
            labels = np.asarray(selected["labels"], dtype=np.int64)
            core_indices = np.asarray(selected["core_indices"], dtype=np.int64)
            eps = float(selected["eps"])
            member_ids = tuple(str(value) for value in metadata["member_ids"])
            mean = np.asarray(display["mean"], dtype=np.float32)
            components = np.asarray(display["components"], dtype=np.float32)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            raise _degraded("The out-of-sample cohort artifacts are invalid.") from exc
        expected_shape = (len(member_ids), len(projected.feature_names))
        if (
            vectors.shape != expected_shape
            or labels.shape != (len(member_ids),)
            or mean.shape != (expected_shape[1],)
            or components.ndim != 2
            or components.shape[1] != expected_shape[1]
            or np.any(core_indices < 0)
            or np.any(core_indices >= len(member_ids))
        ):
            raise _degraded("The out-of-sample cohort artifacts do not align.")
        assigned_label: int | None = None
        nearest_core_member_id: str | None = None
        nearest_core_distance: float | None = None
        competing_labels: list[dict[str, Any]] = []
        if len(core_indices):
            distances = np.linalg.norm(
                vectors[core_indices] - projected.normalized_vector,
                axis=1,
            )
            candidates = [
                (float(distance), member_ids[int(index)], int(labels[int(index)]))
                for distance, index in zip(distances, core_indices, strict=True)
                if int(labels[int(index)]) != -1 and float(distance) <= eps + 1e-7
            ]
            if candidates:
                nearest_core_distance, nearest_core_member_id, assigned_label = min(candidates)
                by_label: dict[int, float] = {}
                for distance, _member_id, label in candidates:
                    by_label[label] = min(distance, by_label.get(label, float("inf")))
                competing_labels = [
                    {
                        "cluster_label": (
                            f"{'fact' if representation == 'patient_fact' else 'screening'}"
                            f"_cluster_{label}"
                        ),
                        "nearest_core_distance": distance,
                    }
                    for label, distance in sorted(by_label.items())
                ]
        prefix = "fact" if representation == "patient_fact" else "screening"
        coordinates = (projected.normalized_vector - mean) @ components.T
        x = float(coordinates[0]) if len(coordinates) else 0.0
        y = float(coordinates[1]) if len(coordinates) > 1 else 0.0
        return {
            "run_id": run_id,
            "representation": representation,
            "representation_version": metadata["version"],
            "out_of_sample": True,
            "association": {
                "cluster_label": (
                    f"{prefix}_cluster_{assigned_label}" if assigned_label is not None else None
                ),
                "is_unassigned": assigned_label is None,
                "eps": eps,
                "nearest_core_member_id": nearest_core_member_id,
                "nearest_core_distance": nearest_core_distance,
                "competing_labels": competing_labels,
                "method": "dbscan_core_radius_v1",
            },
            "projection": {"x": x, "y": y, "display_only": True},
            "vector_checksum": projected.vector_checksum,
            "unsupported_concepts": list(projected.unsupported_concepts),
            "disclaimer": "Exploratory cohort context; not a diagnosis or eligibility result.",
        }

    def screening_similarity(
        self,
        snapshot: PatientSnapshot,
        *,
        screening_date: date,
        representation: RepresentationName,
        neighbor_count: int,
    ) -> dict[str, Any]:
        try:
            import faiss
            import numpy as np

            from trialsync.research.similarity.index import SimilarityIndexMetadata
        except ImportError as exc:
            raise _degraded("The exact similarity capability is not installed.") from exc
        run_id, manifest, metadata, projected = self._project_saved_snapshot(
            snapshot,
            screening_date=screening_date,
            representation=representation,
        )
        metadata_value = self._read_json(
            self._artifact_path(run_id, manifest, f"{representation}_index_metadata")
        )
        try:
            index_metadata = SimilarityIndexMetadata(**metadata_value)
            vectors = np.load(
                self._artifact_path(run_id, manifest, f"{representation}_vectors"),
                allow_pickle=False,
            )
            raw_matrix = np.load(
                self._artifact_path(run_id, manifest, f"{representation}_raw"),
                allow_pickle=False,
            )
            index = faiss.read_index(
                str(self._artifact_path(run_id, manifest, f"{representation}_index"))
            )
            member_ids = tuple(str(value) for value in metadata["member_ids"])
            feature_names = tuple(str(value) for value in metadata["feature_names"])
        except (OSError, RuntimeError, TypeError, ValueError, KeyError) as exc:
            raise _degraded("The exact similarity artifacts are invalid.") from exc
        expected_shape = (index_metadata.vector_count, index_metadata.dimension)
        if (
            index_metadata.representation != representation
            or index_metadata.representation_version != metadata.get("version")
            or index_metadata.feature_order_checksum != metadata.get("feature_order_checksum")
            or vectors.shape != expected_shape
            or raw_matrix.shape != expected_shape
            or len(member_ids) != expected_shape[0]
            or len(feature_names) != expected_shape[1]
            or index.d != expected_shape[1]
            or index.ntotal != expected_shape[0]
        ):
            raise _degraded("The exact similarity artifacts do not match the active run.")
        query = np.ascontiguousarray(projected.normalized_vector[None, :], dtype=np.float32)
        scores, positions = index.search(query, len(member_ids))
        candidates = sorted(
            (
                (float(score), member_ids[int(position)], int(position))
                for score, position in zip(scores[0], positions[0], strict=True)
                if int(position) >= 0
            ),
            key=lambda item: (-item[0], item[1]),
        )[: min(neighbor_count, len(member_ids))]
        members = {item["member_id"]: item for item in self._members(run_id, manifest)}
        neighbors: list[dict[str, Any]] = []
        for rank, (score, member_id, position) in enumerate(candidates, start=1):
            differences = []
            for feature, query_value, neighbor_value in zip(
                feature_names,
                projected.raw_vector,
                raw_matrix[position],
                strict=True,
            ):
                left = float(query_value) if np.isfinite(query_value) else None
                right = float(neighbor_value) if np.isfinite(neighbor_value) else None
                difference = abs(left - right) if left is not None and right is not None else None
                differences.append(
                    {
                        "feature": feature,
                        "query_value": left,
                        "neighbor_value": right,
                        "absolute_difference": difference,
                        "criterion_context": self._criterion_context(
                            feature, projected.criterion_details
                        ),
                    }
                )

            def difference_order(item: dict[str, Any]) -> tuple[bool, float, str]:
                difference = item.get("absolute_difference")
                numeric = float(difference) if isinstance(difference, (int, float)) else 0.0
                return difference is None, -numeric, str(item.get("feature", ""))

            differences.sort(key=difference_order)
            neighbors.append(
                {
                    "rank": rank,
                    "member_id": member_id,
                    "label": members[member_id]["label"],
                    "cosine_similarity": score,
                    "feature_differences": differences[:20],
                }
            )
        return {
            "run_id": run_id,
            "representation": representation,
            "representation_version": metadata["version"],
            "out_of_sample": True,
            "query_vector_checksum": projected.vector_checksum,
            "unsupported_concepts": list(projected.unsupported_concepts),
            "index_metadata": asdict_metadata(index_metadata),
            "neighbors": neighbors,
            "disclaimer": "Similarity is descriptive and is not screening evidence.",
        }

    @staticmethod
    def _criterion_context(
        feature_name: str,
        details: dict[tuple[str, str], dict[str, Any]],
    ) -> dict[str, Any] | None:
        parts = feature_name.split(":")
        if len(parts) < 5 or parts[0] != "criterion":
            return None
        detail = details.get((parts[1], parts[2]))
        if detail is None:
            return None
        return {
            "trial_label": detail["trial_label"],
            "criterion_text": detail["criterion_text"],
            "query_result": detail["result"],
            "query_evidence_fact_ids": detail["evidence"],
            "query_missing_categories": list(detail["missing_categories"]),
        }


def asdict_metadata(metadata: Any) -> dict[str, Any]:
    return {name: getattr(metadata, name) for name in metadata.__dataclass_fields__}
