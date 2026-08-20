"""Project one immutable platform screening into a sealed R6 reference space."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from trialsync.db.models import PatientSnapshot as StoredPatientSnapshot
from trialsync.domain import (
    ApprovedTrialVersion,
    Assertion,
    Criterion,
    CriterionKind,
    Fact,
    FactType,
    PatientSnapshot,
    ScreeningContext,
    Temporality,
    screen,
)

RepresentationName = Literal["patient_fact", "screening_profile"]


class ProjectionError(ValueError):
    """Raised when a saved screening cannot use a frozen R6 transform."""


@dataclass(frozen=True, slots=True)
class ProjectedScreening:
    representation: RepresentationName
    raw_vector: np.ndarray
    normalized_vector: np.ndarray
    feature_names: tuple[str, ...]
    vector_checksum: str
    unsupported_concepts: tuple[str, ...]
    criterion_details: dict[tuple[str, str], dict[str, Any]]


def _checksum(vector: np.ndarray) -> str:
    return hashlib.sha256(vector.astype(np.float32, copy=False).tobytes()).hexdigest()


def _domain_snapshot(snapshot: StoredPatientSnapshot) -> PatientSnapshot:
    facts: list[Fact] = []
    for raw in snapshot.facts_json:
        numeric = raw.get("value_numeric")
        value: Decimal | str | None = (
            Decimal(str(numeric))
            if numeric is not None
            else str(raw["value_text"])
            if raw.get("value_text") is not None
            else None
        )
        effective = raw.get("effective_date")
        facts.append(
            Fact(
                id=str(raw["id"]),
                fact_type=FactType(str(raw["fact_type"])),
                concept=str(raw["concept"]),
                value=value,
                unit=str(raw["unit"]) if raw.get("unit") is not None else None,
                assertion=Assertion(str(raw["assertion"])),
                effective_date=date.fromisoformat(str(effective)) if effective else None,
                source_label=str(raw["source_label"]),
                temporality=Temporality.current,
            )
        )
    return PatientSnapshot(
        id=str(snapshot.id),
        version=snapshot.snapshot_version,
        date_of_birth=snapshot.date_of_birth,
        facts=tuple(facts),
    )


def _transform(raw: np.ndarray, metadata: dict[str, Any]) -> np.ndarray:
    preprocessing = metadata.get("preprocessing")
    feature_names = metadata.get("feature_names")
    if not isinstance(preprocessing, dict) or not isinstance(feature_names, list):
        raise ProjectionError("R6 representation preprocessing metadata is missing")
    try:
        means = np.asarray(preprocessing["means"], dtype=np.float64)
        scales = np.asarray(preprocessing["scales"], dtype=np.float64)
        numeric_names = tuple(str(name) for name in preprocessing["numeric_feature_names"])
        medians = tuple(float(value) for value in preprocessing["medians"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectionError("R6 representation preprocessing metadata is invalid") from exc
    if raw.shape != means.shape or means.shape != scales.shape or len(feature_names) != len(raw):
        raise ProjectionError("R6 query vector does not match the frozen feature order")
    transformed = raw.astype(np.float64, copy=True)
    if len(numeric_names) != len(medians):
        raise ProjectionError("R6 numeric imputation metadata is invalid")
    for name, median in zip(numeric_names, medians, strict=True):
        try:
            index = feature_names.index(name)
        except ValueError as exc:
            raise ProjectionError("R6 numeric feature is absent from its frozen order") from exc
        if not math.isfinite(float(transformed[index])):
            transformed[index] = median
    if not np.isfinite(transformed).all() or np.any(scales == 0):
        raise ProjectionError("R6 query contains unsupported non-finite values")
    standardized = ((transformed - means) / scales).astype(np.float32)
    norm = float(np.linalg.norm(standardized))
    return standardized / norm if norm > 0 else np.zeros_like(standardized)


def _age_band(born: date | None, as_of: date) -> str:
    if born is None:
        return "unknown"
    age = as_of.year - born.year - ((as_of.month, as_of.day) < (born.month, born.day))
    if age < 0:
        raise ProjectionError("Patient date of birth is after the screening date")
    if age < 18:
        return "0_17"
    if age < 35:
        return "18_34"
    if age < 50:
        return "35_49"
    if age < 65:
        return "50_64"
    return "65_plus"


def project_patient_fact(
    snapshot: StoredPatientSnapshot,
    *,
    screening_date: date,
    metadata: dict[str, Any],
) -> ProjectedScreening:
    feature_names = tuple(str(name) for name in metadata.get("feature_names", ()))
    fact_units = metadata.get("fact_units")
    if not feature_names or not isinstance(fact_units, dict):
        raise ProjectionError("R6 patient-fact query metadata is incomplete; rebuild the run")
    domain = _domain_snapshot(snapshot)
    latest: dict[tuple[str, str], Fact] = {}
    for fact in domain.facts:
        if fact.fact_type is FactType.demographic:
            continue
        key = (fact.fact_type.value, fact.concept)
        previous = latest.get(key)
        if previous is None or (fact.effective_date or date.min, fact.id) > (
            previous.effective_date or date.min,
            previous.id,
        ):
            latest[key] = fact
    supported = {
        (parts[0], parts[1])
        for name in feature_names
        if len(parts := name.split(":")) >= 3
        and parts[0] in {"condition", "medication", "observation"}
    }
    unsupported = tuple(sorted(f"{kind}:{concept}" for kind, concept in set(latest) - supported))
    sex = snapshot.source_summary.get("sex")
    normalized_sex = str(sex).casefold() if isinstance(sex, str) else "missing"
    if normalized_sex not in {"female", "male"}:
        normalized_sex = "missing"
    band = _age_band(snapshot.date_of_birth, screening_date)
    values: list[float] = []
    for name in feature_names:
        parts = name.split(":")
        if parts[0] == "age_band":
            values.append(float(parts[1] == band))
            continue
        if parts[0] == "sex":
            values.append(float(parts[1] == normalized_sex))
            continue
        current_fact = latest.get((parts[0], parts[1]))
        suffix = ":".join(parts[2:])
        if suffix.startswith("state:"):
            state = current_fact.assertion.value if current_fact is not None else "missing"
            values.append(float(suffix == f"state:{state}"))
        elif suffix == "value":
            expected_unit = fact_units.get(parts[1])
            if (
                current_fact is None
                or current_fact.assertion is not Assertion.present
                or current_fact.value is None
                or (expected_unit is not None and current_fact.unit != expected_unit)
            ):
                values.append(math.nan)
            else:
                try:
                    values.append(float(current_fact.value))
                except (TypeError, ValueError) as exc:
                    raise ProjectionError(f"Observation {parts[1]!r} is not numeric") from exc
        elif suffix == "value_missing":
            expected_unit = fact_units.get(parts[1])
            missing = (
                current_fact is None
                or current_fact.assertion is not Assertion.present
                or current_fact.value is None
                or (expected_unit is not None and current_fact.unit != expected_unit)
            )
            values.append(float(missing))
        elif suffix == "evidence_age_days":
            values.append(
                float(max(0, (screening_date - current_fact.effective_date).days))
                if current_fact is not None and current_fact.effective_date is not None
                else math.nan
            )
        elif suffix == "evidence_age_missing":
            values.append(float(current_fact is None or current_fact.effective_date is None))
        else:
            raise ProjectionError(f"Unsupported frozen patient-fact feature: {name}")
    raw = np.asarray(values, dtype=np.float32)
    normalized = _transform(raw, metadata)
    return ProjectedScreening(
        representation="patient_fact",
        raw_vector=raw,
        normalized_vector=normalized,
        feature_names=feature_names,
        vector_checksum=_checksum(normalized),
        unsupported_concepts=unsupported,
        criterion_details={},
    )


def project_screening_profile(
    snapshot: StoredPatientSnapshot,
    *,
    screening_date: date,
    metadata: dict[str, Any],
    reference_panel: dict[str, Any],
    engine_version: str,
    terminology_version: str,
    unit_version: str,
) -> ProjectedScreening:
    feature_names = tuple(str(name) for name in metadata.get("feature_names", ()))
    trials = reference_panel.get("trials")
    if not feature_names or not isinstance(trials, list):
        raise ProjectionError("R6 screening-profile query metadata is incomplete")
    patient = _domain_snapshot(snapshot)
    records: dict[tuple[str, str], dict[str, Any]] = {}
    trial_records: dict[str, list[dict[str, Any]]] = {}
    family_records: dict[str, list[dict[str, Any]]] = {}
    for trial in trials:
        criteria = tuple(
            Criterion(
                id=str(item["criterion_id"]),
                kind=CriterionKind(str(item["kind"])),
                order=int(item["order"]),
                source_text=str(item["source_text"]),
                expression=item["expression"],
                required=bool(item["required"]),
            )
            for item in trial["criteria"]
        )
        approved = ApprovedTrialVersion(
            id=str(trial["trial_version_id"]),
            version=str(trial["trial_version"]),
            criteria=criteria,
        )
        result = screen(
            patient,
            approved,
            ScreeningContext(
                screening_date=screening_date,
                engine_version=engine_version,
                terminology_version=terminology_version,
                unit_version=unit_version,
            ),
        )
        criterion_by_id = {str(item["criterion_id"]): item for item in trial["criteria"]}
        for evaluation in result.evaluations:
            definition = criterion_by_id[evaluation.criterion_id]
            record: dict[str, Any] = {
                "trial_version_id": approved.id,
                "criterion_id": evaluation.criterion_id,
                "family": str(definition["criterion_family"]),
                "result": evaluation.result.value,
                "missing_categories": tuple(
                    sorted({item.reason.value for item in evaluation.missing})
                ),
                "trial_label": str(trial["label"]),
                "criterion_text": evaluation.source_text,
                "evidence": [item.fact_id for item in evaluation.evidence],
            }
            records[(approved.id, evaluation.criterion_id)] = record
            trial_records.setdefault(approved.id, []).append(record)
            family_records.setdefault(record["family"], []).append(record)

    values: list[float] = []
    for name in feature_names:
        parts = name.split(":")
        if parts[0] == "criterion":
            current_record = records.get((parts[1], parts[2]))
            if current_record is None:
                raise ProjectionError("R6 reference panel does not match the frozen feature order")
            values.append(float(current_record["result"] == parts[-1]))
        elif parts[0] == "trial":
            candidates = trial_records.get(parts[1], [])
            if not candidates:
                raise ProjectionError("R6 reference trial is absent from the frozen panel")
            values.append(sum(item["result"] == parts[-1] for item in candidates) / len(candidates))
        elif parts[0] == "family":
            candidates = family_records.get(parts[1], [])
            if not candidates:
                raise ProjectionError("R6 criterion family is absent from the frozen panel")
            values.append(sum(item["result"] == parts[-1] for item in candidates) / len(candidates))
        elif parts[0] == "missing_category":
            all_records = list(records.values())
            values.append(
                sum(parts[1] in item["missing_categories"] for item in all_records)
                / len(all_records)
            )
        else:
            raise ProjectionError(f"Unsupported frozen screening-profile feature: {name}")
    raw = np.asarray(values, dtype=np.float32)
    normalized = _transform(raw, metadata)
    return ProjectedScreening(
        representation="screening_profile",
        raw_vector=raw,
        normalized_vector=normalized,
        feature_names=feature_names,
        vector_checksum=_checksum(normalized),
        unsupported_concepts=(),
        criterion_details=records,
    )
