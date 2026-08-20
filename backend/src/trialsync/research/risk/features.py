from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

FeatureGroup = Literal["baseline", "day30_follow_up"]
FeatureValue = str | int | float

BASELINE_FEATURES = (
    "condition_category",
    "site_region",
    "treatment_arm",
    "age",
    "sex",
    "baseline_functional_severity",
    "patient_reported_burden",
    "baseline_comorbidity_burden",
    "baseline_treatment_burden",
    "travel_access_burden",
    "support_availability",
    "medication_count",
)
FOLLOW_UP_FEATURES = (
    "latest_functional_severity",
    "functional_severity_slope",
    "functional_observation_count",
    "missed_dose_rate",
    "delayed_visit_count",
    "missed_visit_rate",
    "mean_visit_delay_days",
    "measurement_missingness_rate",
    "adverse_event_count",
    "adverse_event_burden",
)
FEATURE_NAMES = BASELINE_FEATURES + FOLLOW_UP_FEATURES

_CATEGORIES: dict[str, frozenset[str]] = {
    "condition_category": frozenset(
        {"metabolic", "cardiovascular", "renal", "oncology", "respiratory"}
    ),
    "site_region": frozenset({"central", "north", "south", "east", "west"}),
    "treatment_arm": frozenset({"active", "control"}),
    "sex": frozenset({"female", "intersex_or_other", "male", "not_recorded"}),
}
_INTEGER_RANGES: dict[str, tuple[int, int]] = {
    "age": (18, 100),
    "baseline_comorbidity_burden": (0, 20),
    "baseline_treatment_burden": (0, 20),
    "travel_access_burden": (0, 4),
    "support_availability": (0, 4),
    "medication_count": (0, 50),
    "functional_observation_count": (0, 100),
    "delayed_visit_count": (0, 100),
    "adverse_event_count": (0, 100),
    "adverse_event_burden": (0, 500),
}
_FLOAT_RANGES: dict[str, tuple[float, float]] = {
    "baseline_functional_severity": (0.0, 1.0),
    "patient_reported_burden": (0.0, 1.0),
    "latest_functional_severity": (0.0, 1.0),
    "functional_severity_slope": (-1.0, 1.0),
    "missed_dose_rate": (0.0, 1.0),
    "missed_visit_rate": (0.0, 1.0),
    "mean_visit_delay_days": (0.0, 30.0),
    "measurement_missingness_rate": (0.0, 1.0),
}


class FeatureSnapshotError(ValueError):
    """Raised when a day-30 model feature snapshot is incomplete or invalid."""


@dataclass(frozen=True)
class SourcedFeatureValue:
    value: FeatureValue
    source: str


@dataclass(frozen=True)
class FeatureSnapshot:
    values: dict[str, FeatureValue]
    sources: dict[str, str]
    checksum: str


def feature_group(name: str) -> FeatureGroup:
    if name in BASELINE_FEATURES:
        return "baseline"
    if name in FOLLOW_UP_FEATURES:
        return "day30_follow_up"
    raise FeatureSnapshotError(f"unknown R5 feature: {name}")


def _validate_value(name: str, value: FeatureValue) -> FeatureValue:
    if name in _CATEGORIES:
        if not isinstance(value, str) or value not in _CATEGORIES[name]:
            allowed = ", ".join(sorted(_CATEGORIES[name]))
            raise FeatureSnapshotError(f"{name} must be one of: {allowed}")
        return value

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FeatureSnapshotError(f"{name} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise FeatureSnapshotError(f"{name} must be finite")
    if name in _INTEGER_RANGES:
        if numeric != int(numeric):
            raise FeatureSnapshotError(f"{name} must be an integer")
        lower, upper = _INTEGER_RANGES[name]
        if not lower <= int(numeric) <= upper:
            raise FeatureSnapshotError(f"{name} must be between {lower} and {upper}")
        return int(numeric)
    lower_float, upper_float = _FLOAT_RANGES[name]
    if not lower_float <= numeric <= upper_float:
        raise FeatureSnapshotError(f"{name} must be between {lower_float} and {upper_float}")
    return numeric


def build_feature_snapshot(
    values: Mapping[str, SourcedFeatureValue],
) -> FeatureSnapshot:
    unknown = sorted(set(values) - set(FEATURE_NAMES))
    if unknown:
        raise FeatureSnapshotError("unknown R5 features: " + ", ".join(unknown))
    missing = [name for name in FEATURE_NAMES if name not in values]
    if missing:
        raise FeatureSnapshotError("missing R5 features: " + ", ".join(missing))

    validated_values: dict[str, FeatureValue] = {}
    validated_sources: dict[str, str] = {}
    for name in FEATURE_NAMES:
        sourced = values[name]
        source = sourced.source.strip()
        if not source:
            raise FeatureSnapshotError(f"{name} requires an explicit source")
        validated_values[name] = _validate_value(name, sourced.value)
        validated_sources[name] = source

    canonical = json.dumps(
        {"values": validated_values, "sources": validated_sources},
        sort_keys=True,
        separators=(",", ":"),
    )
    return FeatureSnapshot(
        values=validated_values,
        sources=validated_sources,
        checksum=hashlib.sha256(canonical.encode()).hexdigest(),
    )


def validate_partial_features(
    values: Mapping[str, SourcedFeatureValue],
    *,
    allowed: tuple[str, ...] = FEATURE_NAMES,
) -> dict[str, SourcedFeatureValue]:
    """Validate sourced values without inventing values for absent fields."""

    unknown = sorted(set(values) - set(allowed))
    if unknown:
        raise FeatureSnapshotError("unknown R5 features: " + ", ".join(unknown))
    validated: dict[str, SourcedFeatureValue] = {}
    for name in allowed:
        sourced = values.get(name)
        if sourced is None:
            continue
        source = sourced.source.strip()
        if not source:
            raise FeatureSnapshotError(f"{name} requires an explicit source")
        validated[name] = SourcedFeatureValue(_validate_value(name, sourced.value), source)
    return validated
