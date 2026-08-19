"""Version-checked exact FAISS IndexFlatIP queries over L2-normalized R6 vectors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import numpy as np

from trialsync.research.cohort_profiles.contracts import (
    FeatureContractError,
    RepresentationArtifact,
)


class ResearchDependencyError(RuntimeError):
    """The optional FAISS CPU package is not available in this runtime."""


class IndexMetadataMismatchError(ValueError):
    """The caller tried to use an index for a different frozen feature space."""


_SCORE_RTOL = 1e-5
_SCORE_ATOL = 1e-6


def _require_faiss() -> Any:
    try:
        import faiss
    except ImportError as exc:  # pragma: no cover - depends on optional dependency
        raise ResearchDependencyError(
            "R6 similarity requires the optional faiss-cpu dependency; the core application can "
            "remain available without an R6 index."
        ) from exc
    return faiss


@dataclass(frozen=True, slots=True)
class SimilarityIndexMetadata:
    representation: Literal["patient_fact", "screening_profile"]
    representation_version: str
    embedding_version: str
    preprocessing_version: str
    cohort_checksum: str
    reference_panel_checksum: str
    criterion_order_checksum: str
    feature_order_checksum: str
    subject_order_checksum: str
    index_type: str
    dimension: int
    vector_count: int
    built_at: str


@dataclass(frozen=True, slots=True)
class ExactSimilarityIndex:
    """The in-memory index plus enough immutable metadata to reject stale use."""

    index: Any
    metadata: SimilarityIndexMetadata
    member_ids: tuple[str, ...]
    vectors: np.ndarray
    feature_names: tuple[str, ...]
    raw_matrix: np.ndarray


@dataclass(frozen=True, slots=True)
class SimilarityNeighbor:
    member_id: str
    cosine_similarity: float


@dataclass(frozen=True, slots=True)
class FeatureDifference:
    feature_name: str
    query_value: float | None
    neighbor_value: float | None
    absolute_difference: float | None


@dataclass(frozen=True, slots=True)
class SimilarityQueryResult:
    query_member_id: str
    neighbors: tuple[SimilarityNeighbor, ...]
    metadata: SimilarityIndexMetadata


@dataclass(frozen=True, slots=True)
class SimilarityVerification:
    checked_member_count: int
    passed: bool
    mismatches: tuple[str, ...]


def _metadata(artifact: RepresentationArtifact) -> SimilarityIndexMetadata:
    return SimilarityIndexMetadata(
        representation=artifact.name,
        representation_version=artifact.version,
        embedding_version=artifact.version,
        preprocessing_version=artifact.preprocessing.version,
        cohort_checksum=artifact.cohort_checksum,
        reference_panel_checksum=artifact.reference_panel_checksum,
        criterion_order_checksum=artifact.criterion_order_checksum,
        feature_order_checksum=artifact.feature_order_checksum,
        subject_order_checksum=artifact.subject_order_checksum,
        index_type="IndexFlatIP",
        dimension=len(artifact.feature_names),
        vector_count=len(artifact.member_ids),
        built_at=datetime.now(UTC).isoformat(),
    )


def build_exact_faiss_index(artifact: RepresentationArtifact) -> ExactSimilarityIndex:
    """Build an exact CPU inner-product index; normalized IP equals cosine similarity."""

    if not artifact.member_ids or len(set(artifact.member_ids)) != len(artifact.member_ids):
        raise FeatureContractError("R6 FAISS index requires unique non-empty subject identifiers")
    vectors = np.ascontiguousarray(artifact.normalized_matrix.astype(np.float32, copy=False))
    if not np.isfinite(vectors).all():
        raise FeatureContractError("R6 FAISS vectors must be finite")
    if vectors.shape != (len(artifact.member_ids), len(artifact.feature_names)):
        raise FeatureContractError("R6 FAISS vectors do not match representation metadata")
    norms = np.linalg.norm(vectors, axis=1)
    if not np.all(np.isclose(norms, 1.0, atol=1e-5) | np.isclose(norms, 0.0, atol=1e-7)):
        raise FeatureContractError("R6 FAISS vectors must be L2-normalized")
    faiss = _require_faiss()
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    return ExactSimilarityIndex(
        index=index,
        metadata=_metadata(artifact),
        member_ids=artifact.member_ids,
        vectors=vectors,
        feature_names=artifact.feature_names,
        raw_matrix=artifact.raw_matrix,
    )


def validate_index_metadata(index: ExactSimilarityIndex, expected: SimilarityIndexMetadata) -> None:
    """Reject a candidate index unless every frozen space/version property agrees."""

    if index.metadata != expected:
        differences = [
            field
            for field in index.metadata.__dataclass_fields__
            if getattr(index.metadata, field) != getattr(expected, field)
        ]
        raise IndexMetadataMismatchError(
            "R6 similarity index metadata mismatch for: " + ", ".join(differences)
        )


def _member_index(index: ExactSimilarityIndex, member_id: str) -> int:
    try:
        return index.member_ids.index(member_id)
    except ValueError as exc:
        raise KeyError(f"member {member_id!r} is not in this R6 similarity index") from exc


def _ordered_neighbors(
    member_ids: tuple[str, ...], scores: np.ndarray, *, query_index: int, limit: int
) -> tuple[SimilarityNeighbor, ...]:
    candidates = [
        SimilarityNeighbor(member_id=member_id, cosine_similarity=float(scores[position]))
        for position, member_id in enumerate(member_ids)
        if position != query_index
    ]
    # Exact float32 dot products can differ by a few ULPs between FAISS and NumPy.  First order by
    # score, then treat values within the verification tolerance as one numerical tie group and
    # order that group by identifier.  This keeps the public order deterministic across both exact
    # implementations, including when a tie crosses the requested-neighbor boundary.
    score_ordered = sorted(candidates, key=lambda item: -item.cosine_similarity)
    deterministic: list[SimilarityNeighbor] = []
    start = 0
    while start < len(score_ordered):
        anchor = score_ordered[start].cosine_similarity
        end = start + 1
        while end < len(score_ordered) and np.isclose(
            score_ordered[end].cosine_similarity,
            anchor,
            rtol=_SCORE_RTOL,
            atol=_SCORE_ATOL,
        ):
            end += 1
        deterministic.extend(sorted(score_ordered[start:end], key=lambda item: item.member_id))
        start = end
    return tuple(deterministic[:limit])


def query_neighbors(
    index: ExactSimilarityIndex,
    member_id: str,
    neighbor_count: int,
    *,
    expected_metadata: SimilarityIndexMetadata | None = None,
) -> SimilarityQueryResult:
    """Return exact cosine neighbors, excluding self and ordering score ties by identifier."""

    if neighbor_count < 1:
        raise ValueError("neighbor_count must be at least one")
    if expected_metadata is not None:
        validate_index_metadata(index, expected_metadata)
    query_index = _member_index(index, member_id)
    # Search every member so deterministic secondary tie ordering cannot truncate valid ties.
    scores, positions = index.index.search(
        index.vectors[query_index : query_index + 1], len(index.member_ids)
    )
    dense_scores = np.full(len(index.member_ids), -np.inf, dtype=np.float32)
    for score, position in zip(scores[0], positions[0], strict=True):
        if position >= 0:
            dense_scores[int(position)] = score
    return SimilarityQueryResult(
        query_member_id=member_id,
        neighbors=_ordered_neighbors(
            index.member_ids,
            dense_scores,
            query_index=query_index,
            limit=min(neighbor_count, len(index.member_ids) - 1),
        ),
        metadata=index.metadata,
    )


def brute_force_neighbors(
    index: ExactSimilarityIndex, member_id: str, neighbor_count: int
) -> tuple[SimilarityNeighbor, ...]:
    """Reference implementation used to audit exact FAISS retrieval."""

    query_index = _member_index(index, member_id)
    scores = index.vectors @ index.vectors[query_index]
    return _ordered_neighbors(
        index.member_ids,
        scores,
        query_index=query_index,
        limit=min(neighbor_count, len(index.member_ids) - 1),
    )


def verify_exact_neighbors(
    index: ExactSimilarityIndex, *, neighbor_count: int = 10
) -> SimilarityVerification:
    """Compare FAISS with brute force, accepting only score-equivalent boundary ties."""

    mismatches: list[str] = []
    for member_id in index.member_ids:
        observed = query_neighbors(index, member_id, neighbor_count).neighbors
        query_index = _member_index(index, member_id)
        limit = min(neighbor_count, len(index.member_ids) - 1)
        if limit == 0:
            if observed:
                mismatches.append(f"{member_id}: neighbor count differs")
            continue
        reference_scores = index.vectors @ index.vectors[query_index]
        reference_scores[query_index] = -np.inf
        finite_scores = reference_scores[np.isfinite(reference_scores)]
        if len(observed) != limit or finite_scores.size != len(index.member_ids) - 1:
            mismatches.append(f"{member_id}: neighbor count differs")
            continue
        threshold = float(np.sort(finite_scores)[::-1][limit - 1])
        observed_ids = [neighbor.member_id for neighbor in observed]
        if len(set(observed_ids)) != len(observed_ids) or member_id in observed_ids:
            mismatches.append(f"{member_id}: duplicate or self neighbor")
            continue
        invalid_score = False
        for found in observed:
            found_index = _member_index(index, found.member_id)
            reference_score = float(reference_scores[found_index])
            if not np.isclose(
                found.cosine_similarity,
                reference_score,
                rtol=_SCORE_RTOL,
                atol=_SCORE_ATOL,
            ) or (
                reference_score < threshold
                and not np.isclose(
                    reference_score,
                    threshold,
                    rtol=_SCORE_RTOL,
                    atol=_SCORE_ATOL,
                )
            ):
                invalid_score = True
                break
        if invalid_score:
            mismatches.append(f"{member_id}: FAISS score differs from brute force")
            continue
        mandatory_ids = {
            candidate_id
            for candidate_index, candidate_id in enumerate(index.member_ids)
            if candidate_index != query_index
            and reference_scores[candidate_index] > threshold
            and not np.isclose(
                reference_scores[candidate_index],
                threshold,
                rtol=_SCORE_RTOL,
                atol=_SCORE_ATOL,
            )
        }
        if not mandatory_ids.issubset(observed_ids):
            mismatches.append(f"{member_id}: FAISS omitted a higher-scoring neighbor")
    return SimilarityVerification(
        checked_member_count=len(index.member_ids),
        passed=not mismatches,
        mismatches=tuple(mismatches),
    )


def transparent_feature_differences(
    index: ExactSimilarityIndex, query_member_id: str, neighbor_member_id: str
) -> tuple[FeatureDifference, ...]:
    """Expose raw-space differences; missing values stay explicit rather than becoming zeros."""

    query_index = _member_index(index, query_member_id)
    neighbor_index = _member_index(index, neighbor_member_id)
    differences: list[FeatureDifference] = []
    for feature_name, left, right in zip(
        index.feature_names,
        index.raw_matrix[query_index],
        index.raw_matrix[neighbor_index],
        strict=True,
    ):
        left_value = float(left) if np.isfinite(left) else None
        right_value = float(right) if np.isfinite(right) else None
        difference = (
            abs(left_value - right_value)
            if left_value is not None and right_value is not None
            else None
        )
        if left_value != right_value:
            differences.append(
                FeatureDifference(
                    feature_name=feature_name,
                    query_value=left_value,
                    neighbor_value=right_value,
                    absolute_difference=difference,
                )
            )
    return tuple(
        sorted(
            differences,
            key=lambda item: (
                item.absolute_difference is None,
                -(item.absolute_difference or 0.0),
                item.feature_name,
            ),
        )
    )
