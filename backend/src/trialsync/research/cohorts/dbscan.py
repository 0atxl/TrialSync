"""Bounded DBSCAN evaluation and display-only seeded PCA for R6."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Any, Literal

import numpy as np

from trialsync.research.cohort_profiles.contracts import (
    FeatureContractError,
    RepresentationArtifact,
)


class ResearchDependencyError(RuntimeError):
    """An optional R6 analysis dependency is not installed in this runtime."""


def _require_sklearn() -> tuple[Any, Any, Any, Any]:
    try:
        from sklearn.cluster import DBSCAN
        from sklearn.decomposition import PCA
        from sklearn.metrics import (
            adjusted_rand_score,
            silhouette_score,
        )
    except ImportError as exc:  # pragma: no cover - depends on environment extras
        raise ResearchDependencyError(
            "R6 clustering requires the optional scikit-learn dependency; install the approved "
            "research dependency set before running DBSCAN or PCA."
        ) from exc
    return DBSCAN, PCA, adjusted_rand_score, silhouette_score


@dataclass(frozen=True, slots=True)
class DBSCANConfig:
    """Small, explicit parameter grid. The limits prevent accidental search expansion."""

    eps_values: tuple[float, ...]
    min_samples_values: tuple[int, ...]
    random_state: int = 20260816
    stability_repeats: int = 3
    sample_fraction: float = 0.8

    def __post_init__(self) -> None:
        if not self.eps_values or not self.min_samples_values:
            raise FeatureContractError("DBSCAN grid must contain eps and min_samples values")
        if len(self.eps_values) > 12 or len(self.min_samples_values) > 8:
            raise FeatureContractError("DBSCAN parameter grid exceeds the bounded R6 limits")
        if any(not 0.0 < value <= 10.0 for value in self.eps_values):
            raise FeatureContractError("R6 eps values must be in (0, 10]")
        if any(value < 2 or value > 100 for value in self.min_samples_values):
            raise FeatureContractError("R6 min_samples values must be in [2, 100]")
        if self.stability_repeats < 1 or self.stability_repeats > 10:
            raise FeatureContractError("R6 stability repeats must be in [1, 10]")
        if not 0.5 <= self.sample_fraction < 1.0:
            raise FeatureContractError("R6 stability sample_fraction must be in [0.5, 1)")


@dataclass(frozen=True, slots=True)
class DistanceDistribution:
    nearest_neighbor_min: float
    nearest_neighbor_p25: float
    nearest_neighbor_median: float
    nearest_neighbor_p75: float
    nearest_neighbor_max: float


@dataclass(frozen=True, slots=True)
class StabilitySummary:
    bootstrap_adjusted_rand_mean: float | None
    bootstrap_adjusted_rand_values: tuple[float, ...]
    nearby_parameter_adjusted_rand_mean: float | None
    nearby_parameter_adjusted_rand_values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class DBSCANCandidate:
    eps: float
    min_samples: int
    labels: tuple[int, ...]
    core_indices: tuple[int, ...]
    cluster_count: int
    cluster_sizes: tuple[tuple[int, int], ...]
    noise_fraction: float
    silhouette_score: float | None
    stability: StabilitySummary


@dataclass(frozen=True, slots=True)
class ConditionComposition:
    cluster_label: int
    condition: str
    cluster_member_count: int
    condition_member_count: int
    cluster_prevalence: float
    cohort_prevalence: float
    prevalence_lift: float | None


@dataclass(frozen=True, slots=True)
class DBSCANReport:
    representation: Literal["patient_fact", "screening_profile"]
    representation_version: str
    cohort_checksum: str
    feature_order_checksum: str
    member_ids: tuple[str, ...]
    distance_distribution: DistanceDistribution
    candidates: tuple[DBSCANCandidate, ...]
    selected: DBSCANCandidate
    selection_reason: str
    condition_composition: tuple[ConditionComposition, ...]


@dataclass(frozen=True, slots=True)
class PCAProjection:
    representation: Literal["patient_fact", "screening_profile"]
    representation_version: str
    member_ids: tuple[str, ...]
    coordinates: np.ndarray
    mean: np.ndarray
    components: np.ndarray
    explained_variance_ratio: tuple[float, float]
    random_state: int
    display_only: bool = True


def _check_vectors(artifact: RepresentationArtifact) -> np.ndarray:
    vectors = artifact.normalized_matrix
    if not vectors.ndim == 2 or not len(vectors):
        raise FeatureContractError("DBSCAN requires a non-empty two-dimensional vector matrix")
    if not np.isfinite(vectors).all():
        raise FeatureContractError("DBSCAN vectors must be finite")
    return vectors.astype(np.float32, copy=False)


def _distance_distribution(vectors: np.ndarray) -> DistanceDistribution:
    if len(vectors) == 1:
        values = np.array([0.0], dtype=np.float64)
    else:
        similarities = np.clip(vectors @ vectors.T, -1.0, 1.0)
        # DBSCAN operates on Euclidean distance in the normalized space.  For unit vectors this
        # is sqrt(2 - 2 * cosine_similarity), so the diagnostic must use the same scale as eps.
        distances = np.sqrt(np.maximum(0.0, 2.0 - (2.0 * similarities)))
        np.fill_diagonal(distances, np.inf)
        values = distances.min(axis=1)
    return DistanceDistribution(
        nearest_neighbor_min=float(np.min(values)),
        nearest_neighbor_p25=float(np.quantile(values, 0.25)),
        nearest_neighbor_median=float(np.quantile(values, 0.5)),
        nearest_neighbor_p75=float(np.quantile(values, 0.75)),
        nearest_neighbor_max=float(np.max(values)),
    )


def _cluster_metrics(labels: np.ndarray) -> tuple[int, tuple[tuple[int, int], ...], float]:
    non_noise = labels[labels >= 0]
    clusters = tuple(sorted((int(label), int((labels == label).sum())) for label in set(non_noise)))
    return len(clusters), clusters, float((labels == -1).mean())


def _silhouette(vectors: np.ndarray, labels: np.ndarray, silhouette_score: Any) -> float | None:
    non_noise_mask = labels >= 0
    subset_labels = labels[non_noise_mask]
    cluster_count = len(set(subset_labels))
    if cluster_count < 2 or len(subset_labels) <= cluster_count:
        return None
    return float(silhouette_score(vectors[non_noise_mask], subset_labels, metric="euclidean"))


def _fit_labels(DBSCAN: Any, vectors: np.ndarray, eps: float, min_samples: int) -> np.ndarray:
    return np.asarray(
        DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean").fit_predict(vectors)
    )


def _stability(
    *,
    DBSCAN: Any,
    adjusted_rand_score: Any,
    vectors: np.ndarray,
    labels: np.ndarray,
    eps: float,
    min_samples: int,
    config: DBSCANConfig,
) -> StabilitySummary:
    sample_size = min(len(vectors), max(2, round(len(vectors) * config.sample_fraction)))
    bootstrap: list[float] = []
    for offset in range(config.stability_repeats):
        rng = np.random.default_rng(config.random_state + offset)
        indices = np.sort(rng.choice(len(vectors), size=sample_size, replace=False))
        sampled_labels = _fit_labels(DBSCAN, vectors[indices], eps, min_samples)
        bootstrap.append(float(adjusted_rand_score(labels[indices], sampled_labels)))
    nearby: list[float] = []
    neighbor_parameters = (
        (round(eps * 0.95, 12), min_samples),
        (round(eps * 1.05, 12), min_samples),
        (eps, max(2, min_samples - 1)),
        (eps, min(100, min_samples + 1)),
    )
    for nearby_eps, nearby_min_samples in neighbor_parameters:
        nearby_labels = _fit_labels(DBSCAN, vectors, nearby_eps, nearby_min_samples)
        nearby.append(float(adjusted_rand_score(labels, nearby_labels)))
    return StabilitySummary(
        bootstrap_adjusted_rand_mean=fmean(bootstrap) if bootstrap else None,
        bootstrap_adjusted_rand_values=tuple(bootstrap),
        nearby_parameter_adjusted_rand_mean=fmean(nearby) if nearby else None,
        nearby_parameter_adjusted_rand_values=tuple(nearby),
    )


def _condition_composition(
    member_ids: tuple[str, ...],
    labels: tuple[int, ...],
    conditions: dict[str, frozenset[str]] | None,
) -> tuple[ConditionComposition, ...]:
    if not conditions:
        return ()
    unknown = set(conditions).difference(member_ids)
    if unknown:
        raise FeatureContractError("condition composition includes an unknown R6 member")
    all_conditions = sorted({condition for values in conditions.values() for condition in values})
    output: list[ConditionComposition] = []
    for label in sorted(set(labels).difference({-1})):
        cluster_members = [
            member_id for member_id, value in zip(member_ids, labels, strict=True) if value == label
        ]
        for condition in all_conditions:
            cohort_count = sum(
                condition in conditions.get(member_id, frozenset()) for member_id in member_ids
            )
            cluster_count = sum(
                condition in conditions.get(member_id, frozenset()) for member_id in cluster_members
            )
            cohort_prevalence = cohort_count / len(member_ids)
            cluster_prevalence = cluster_count / len(cluster_members)
            output.append(
                ConditionComposition(
                    cluster_label=label,
                    condition=condition,
                    cluster_member_count=len(cluster_members),
                    condition_member_count=cluster_count,
                    cluster_prevalence=cluster_prevalence,
                    cohort_prevalence=cohort_prevalence,
                    prevalence_lift=(
                        cluster_prevalence / cohort_prevalence if cohort_prevalence else None
                    ),
                )
            )
    return tuple(output)


def _select(candidates: list[DBSCANCandidate]) -> tuple[DBSCANCandidate, str]:
    clustered = [candidate for candidate in candidates if candidate.cluster_count > 0]
    if not clustered:
        selected = min(
            candidates, key=lambda item: (item.noise_fraction, item.eps, item.min_samples)
        )
        return (
            selected,
            "No candidate formed a cluster; selected the lowest-noise evaluated outcome.",
        )

    # All-noise and single-cluster partitions can receive perfect adjusted-rand stability simply
    # because they are trivial.  They are useful boundary outcomes to report, but must not outrank
    # a genuine cohort partition on that basis.  Prefer multi-cluster candidates, and first bound
    # the noise fraction when the evaluated grid offers such a result.
    non_trivial = [candidate for candidate in clustered if candidate.cluster_count >= 2]
    if not non_trivial:
        selected = min(
            clustered,
            key=lambda item: (item.noise_fraction, item.eps, item.min_samples),
        )
        return (
            selected,
            "No evaluated candidate formed multiple clusters; selected the lowest-noise "
            "single-cluster outcome and retained it as a negative cohort-discovery result.",
        )

    bounded_noise = [candidate for candidate in non_trivial if candidate.noise_fraction <= 0.5]
    selection_pool = bounded_noise or non_trivial

    def score(candidate: DBSCANCandidate) -> tuple[float, float, float, float, float]:
        return (
            candidate.stability.bootstrap_adjusted_rand_mean or -1.0,
            candidate.stability.nearby_parameter_adjusted_rand_mean or -1.0,
            candidate.silhouette_score or -1.0,
            -candidate.noise_fraction,
            -candidate.eps,
        )

    selected = max(selection_pool, key=score)
    noise_reason = (
        "with at most 50% noise"
        if bounded_noise
        else "after no multi-cluster candidate met the 50% noise bound"
    )
    return (
        selected,
        f"Selected a non-trivial multi-cluster candidate {noise_reason}, ranked by bootstrap "
        "stability, nearby-parameter stability, silhouette, and noise fraction.",
    )


def run_dbscan_analysis(
    artifact: RepresentationArtifact,
    config: DBSCANConfig,
    *,
    condition_memberships: dict[str, frozenset[str]] | None = None,
) -> DBSCANReport:
    """Evaluate the full bounded grid; vectors are always full-dimensional normalized vectors."""

    if artifact.name not in {"patient_fact", "screening_profile"}:
        raise FeatureContractError("unknown R6 representation")
    vectors = _check_vectors(artifact)
    DBSCAN, _PCA, adjusted_rand_score, silhouette_score = _require_sklearn()
    candidates: list[DBSCANCandidate] = []
    for eps in sorted(set(config.eps_values)):
        for min_samples in sorted(set(config.min_samples_values)):
            fitted = DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean").fit(vectors)
            labels_array = np.asarray(fitted.labels_)
            cluster_count, cluster_sizes, noise_fraction = _cluster_metrics(labels_array)
            candidates.append(
                DBSCANCandidate(
                    eps=eps,
                    min_samples=min_samples,
                    labels=tuple(int(value) for value in labels_array),
                    core_indices=tuple(int(value) for value in fitted.core_sample_indices_),
                    cluster_count=cluster_count,
                    cluster_sizes=cluster_sizes,
                    noise_fraction=noise_fraction,
                    silhouette_score=_silhouette(vectors, labels_array, silhouette_score),
                    stability=_stability(
                        DBSCAN=DBSCAN,
                        adjusted_rand_score=adjusted_rand_score,
                        vectors=vectors,
                        labels=labels_array,
                        eps=eps,
                        min_samples=min_samples,
                        config=config,
                    ),
                )
            )
    selected, reason = _select(candidates)
    return DBSCANReport(
        representation=artifact.name,
        representation_version=artifact.version,
        cohort_checksum=artifact.cohort_checksum,
        feature_order_checksum=artifact.feature_order_checksum,
        member_ids=artifact.member_ids,
        distance_distribution=_distance_distribution(vectors),
        candidates=tuple(candidates),
        selected=selected,
        selection_reason=reason,
        condition_composition=_condition_composition(
            artifact.member_ids,
            selected.labels,
            condition_memberships if artifact.name == "patient_fact" else None,
        ),
    )


def build_pca_projection(
    artifact: RepresentationArtifact, *, random_state: int = 20260816
) -> PCAProjection:
    """Build a deterministic 2D display projection. It is never used by DBSCAN or FAISS."""

    vectors = _check_vectors(artifact)
    _DBSCAN, PCA, _adjusted_rand_score, _silhouette_score = _require_sklearn()
    components = min(2, vectors.shape[0], vectors.shape[1])
    if components == 0:
        raise FeatureContractError("PCA requires at least one member and one feature")
    model = PCA(n_components=components, random_state=random_state)
    coordinates = np.asarray(model.fit_transform(vectors), dtype=np.float32)
    # PCA signs are arbitrary. Fix them by the largest absolute loading, which keeps repeated runs
    # stable across otherwise equivalent LAPACK sign choices.
    for component in range(components):
        loading = np.asarray(model.components_[component])
        pivot = int(np.argmax(np.abs(loading)))
        if loading[pivot] < 0:
            coordinates[:, component] *= -1
            model.components_[component] *= -1
    if components == 1:
        coordinates = np.column_stack(
            (coordinates[:, 0], np.zeros(len(coordinates), dtype=np.float32))
        )
        explained = (float(model.explained_variance_ratio_[0]), 0.0)
    else:
        explained = (
            float(model.explained_variance_ratio_[0]),
            float(model.explained_variance_ratio_[1]),
        )
    return PCAProjection(
        representation=artifact.name,
        representation_version=artifact.version,
        member_ids=artifact.member_ids,
        coordinates=coordinates,
        mean=np.asarray(model.mean_, dtype=np.float32),
        components=np.asarray(model.components_, dtype=np.float32),
        explained_variance_ratio=explained,
        random_state=random_state,
    )
