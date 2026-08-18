"""Frozen feature-balancing experiment for the two R6 V2 representations."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence

import numpy as np

from .contracts import (
    BalancedPreprocessingParameters,
    FeatureContractError,
    R6CriterionResultRecord,
    R6PatientRecord,
    RepresentationArtifact,
    RepresentationContext,
)
from .features import (
    build_patient_fact_representation,
    build_screening_profile_representation,
    canonical_checksum,
)

PATIENT_FACT_V2_VERSION = "r6.patient_fact.v2"
SCREENING_PROFILE_V2_VERSION = "r6.screening_profile.v2"
V2_PREPROCESSING_VERSION = "r6.robust-block-balanced-l2.v2"


def _normalized(
    processed: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    standardized = processed.astype(np.float32)
    norms = np.linalg.norm(standardized, axis=1, keepdims=True)
    if np.any(norms <= 0.0):
        raise FeatureContractError("R6 V2 preprocessing produced a zero-length member vector")
    normalized = (standardized / norms).astype(np.float32)
    return standardized, normalized


def _is_zero_variance(values: np.ndarray) -> bool:
    finite = values[np.isfinite(values)]
    return not len(finite) or bool(np.all(finite == finite[0]))


def _patient_block(feature_name: str) -> str:
    prefix = feature_name.split(":", 1)[0]
    if prefix in {"age_band", "sex"}:
        return "demographic"
    if prefix in {"condition", "medication", "observation"}:
        return prefix
    raise FeatureContractError(f"R6 V2 patient feature has no semantic block: {feature_name!r}")


def _screening_block(feature_name: str) -> str:
    prefix = feature_name.split(":", 1)[0]
    blocks = {
        "criterion": "criterion_state",
        "trial": "trial_rate",
        "family": "criterion_family_rate",
        "missing_category": "missing_category",
    }
    try:
        return blocks[prefix]
    except KeyError as exc:
        raise FeatureContractError(
            f"R6 V2 screening feature has no semantic block: {feature_name!r}"
        ) from exc


def _block_weights(blocks: tuple[str, ...]) -> dict[str, float]:
    counts = Counter(blocks)
    return {name: 1.0 / math.sqrt(count) for name, count in sorted(counts.items())}


def _artifact(
    *,
    source: RepresentationArtifact,
    version: str,
    feature_names: tuple[str, ...],
    raw_matrix: np.ndarray,
    processed: np.ndarray,
    preprocessing: BalancedPreprocessingParameters,
) -> RepresentationArtifact:
    standardized, normalized = _normalized(processed)
    return RepresentationArtifact(
        name=source.name,
        version=version,
        member_ids=source.member_ids,
        feature_names=feature_names,
        raw_matrix=raw_matrix.astype(np.float32),
        standardized_matrix=standardized,
        normalized_matrix=normalized,
        preprocessing=preprocessing,
        cohort_checksum=source.cohort_checksum,
        reference_panel_checksum=source.reference_panel_checksum,
        criterion_order_checksum=source.criterion_order_checksum,
        subject_order_checksum=source.subject_order_checksum,
        feature_order_checksum=canonical_checksum(feature_names),
    )


def build_patient_fact_representation_v2(
    patients: Sequence[R6PatientRecord], context: RepresentationContext
) -> RepresentationArtifact:
    """Apply the one-shot robust and block-balanced V2 patient-fact transformation."""

    source = build_patient_fact_representation(patients, context)
    numeric = set(source.preprocessing.numeric_feature_names)
    required_explicit = tuple(
        name.startswith(("age_band:", "sex:"))
        or ":state:" in name
        or name.endswith(("value_missing", "evidence_age_missing"))
        for name in source.feature_names
    )
    keep = tuple(
        explicit or not _is_zero_variance(source.raw_matrix[:, index])
        for index, explicit in enumerate(required_explicit)
    )
    feature_names = tuple(
        name for name, active in zip(source.feature_names, keep, strict=True) if active
    )
    removed = tuple(
        name for name, active in zip(source.feature_names, keep, strict=True) if not active
    )
    raw = source.raw_matrix[:, np.asarray(keep, dtype=bool)].astype(np.float64, copy=True)
    processed = raw.copy()
    active_numeric = tuple(name for name in feature_names if name in numeric)
    medians: list[float] = []
    lowers: list[float] = []
    uppers: list[float] = []
    centers: list[float] = []
    scales: list[float] = []
    for name in active_numeric:
        index = feature_names.index(name)
        present = processed[:, index][np.isfinite(processed[:, index])]
        if not len(present):
            raise FeatureContractError(f"R6 V2 numeric feature is completely missing: {name!r}")
        median = float(np.median(present))
        lower = float(np.quantile(present, 0.01))
        upper = float(np.quantile(present, 0.99))
        clipped = np.clip(present, lower, upper)
        center = float(np.median(clipped))
        q25, q75 = np.quantile(clipped, (0.25, 0.75))
        scale = float(q75 - q25)
        if not math.isfinite(scale) or scale <= 0.0:
            scale = 1.0
        values = processed[:, index]
        values[~np.isfinite(values)] = median
        processed[:, index] = (np.clip(values, lower, upper) - center) / scale
        medians.append(median)
        lowers.append(lower)
        uppers.append(upper)
        centers.append(center)
        scales.append(scale)
    if not np.isfinite(processed).all():
        raise FeatureContractError("R6 V2 patient preprocessing left a non-finite value")
    blocks = tuple(_patient_block(name) for name in feature_names)
    block_weights = _block_weights(blocks)
    feature_weights = tuple(block_weights[block] for block in blocks)
    processed *= np.asarray(feature_weights, dtype=np.float64)
    preprocessing = BalancedPreprocessingParameters(
        version=V2_PREPROCESSING_VERSION,
        source_version=source.version,
        numeric_feature_names=active_numeric,
        medians=tuple(medians),
        clip_lower=tuple(lowers),
        clip_upper=tuple(uppers),
        centers=tuple(centers),
        scales=tuple(scales),
        removed_feature_names=removed,
        feature_blocks=blocks,
        block_weights=tuple(block_weights.items()),
        feature_weights=feature_weights,
    )
    return _artifact(
        source=source,
        version=PATIENT_FACT_V2_VERSION,
        feature_names=feature_names,
        raw_matrix=raw,
        processed=processed,
        preprocessing=preprocessing,
    )


def _criterion_key(feature_name: str) -> tuple[str, str] | None:
    parts = feature_name.split(":")
    if len(parts) == 5 and parts[0] == "criterion" and parts[3] == "result":
        return parts[1], parts[2]
    return None


def build_screening_profile_representation_v2(
    patients: Sequence[R6PatientRecord],
    criterion_results: Sequence[R6CriterionResultRecord],
    context: RepresentationContext,
    *,
    rule_signatures: Mapping[tuple[str, str], str],
) -> RepresentationArtifact:
    """Apply the one-shot repeated-rule and block-balanced V2 screening transformation."""

    source = build_screening_profile_representation(patients, criterion_results, context)
    criterion_keys = {
        key for feature_name in source.feature_names if (key := _criterion_key(feature_name))
    }
    if criterion_keys != set(rule_signatures):
        raise FeatureContractError("R6 V2 rule signatures do not match the frozen criterion panel")
    required_explicit = tuple(name.startswith("criterion:") for name in source.feature_names)
    keep = tuple(
        explicit or not _is_zero_variance(source.raw_matrix[:, index])
        for index, explicit in enumerate(required_explicit)
    )
    feature_names = tuple(
        name for name, active in zip(source.feature_names, keep, strict=True) if active
    )
    removed = tuple(
        name for name, active in zip(source.feature_names, keep, strict=True) if not active
    )
    raw = source.raw_matrix[:, np.asarray(keep, dtype=bool)].astype(np.float64, copy=True)
    if not np.isfinite(raw).all():
        raise FeatureContractError("R6 V2 screening preprocessing received a non-finite value")
    signature_counts = Counter(rule_signatures.values())
    repetition_weights: list[float] = []
    for name in feature_names:
        key = _criterion_key(name)
        repetition_weights.append(
            1.0 / math.sqrt(signature_counts[rule_signatures[key]]) if key is not None else 1.0
        )
    blocks = tuple(_screening_block(name) for name in feature_names)
    block_weights = _block_weights(blocks)
    feature_weights = tuple(
        repetition * block_weights[block]
        for repetition, block in zip(repetition_weights, blocks, strict=True)
    )
    processed = raw * np.asarray(feature_weights, dtype=np.float64)
    preprocessing = BalancedPreprocessingParameters(
        version=V2_PREPROCESSING_VERSION,
        source_version=source.version,
        numeric_feature_names=(),
        medians=(),
        clip_lower=(),
        clip_upper=(),
        centers=(),
        scales=(),
        removed_feature_names=removed,
        feature_blocks=blocks,
        block_weights=tuple(block_weights.items()),
        feature_weights=feature_weights,
        rule_signature_checksum=canonical_checksum(
            [(key, rule_signatures[key]) for key in sorted(rule_signatures)]
        ),
    )
    return _artifact(
        source=source,
        version=SCREENING_PROFILE_V2_VERSION,
        feature_names=feature_names,
        raw_matrix=raw,
        processed=processed,
        preprocessing=preprocessing,
    )
