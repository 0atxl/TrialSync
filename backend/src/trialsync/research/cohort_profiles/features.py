"""Feature construction for the two intentionally distinct R6 cohort spaces."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import date

import numpy as np

from .contracts import (
    FORBIDDEN_FEATURE_TOKENS,
    PATIENT_FACT_REPRESENTATION_VERSION,
    PREPROCESSING_VERSION,
    SCREENING_PROFILE_REPRESENTATION_VERSION,
    FeatureContractError,
    PreprocessingParameters,
    R6CriterionResultRecord,
    R6FactRecord,
    R6PatientRecord,
    RepresentationArtifact,
    RepresentationContext,
)

_FACT_STATES = ("present", "absent", "unknown", "missing")
_RESULT_STATES = ("pass", "fail", "unknown")


def canonical_checksum(values: Iterable[object]) -> str:
    """Return a stable checksum for an already order-significant sequence."""

    payload = json.dumps(list(values), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_identifier(value: str, *, field: str) -> None:
    normalized = value.casefold().replace("-", "_").replace(" ", "_")
    if any(token in normalized for token in FORBIDDEN_FEATURE_TOKENS):
        raise FeatureContractError(f"{field} contains a forbidden R6 source token: {value!r}")


def _validate_context(context: RepresentationContext) -> None:
    for field in ("cohort_checksum", "reference_panel_checksum", "criterion_order_checksum"):
        if not getattr(context, field):
            raise FeatureContractError(f"{field} is required for a versioned R6 representation")


def _ordered_members(patients: Sequence[R6PatientRecord]) -> tuple[R6PatientRecord, ...]:
    by_id: dict[str, R6PatientRecord] = {}
    for patient in patients:
        if not patient.member_id:
            raise FeatureContractError("member_id is required")
        if patient.member_id in by_id:
            raise FeatureContractError(f"duplicate cohort member {patient.member_id!r}")
        by_id[patient.member_id] = patient
    if not by_id:
        raise FeatureContractError("R6 representation requires at least one patient")
    return tuple(by_id[member_id] for member_id in sorted(by_id))


def _fact_key(fact: R6FactRecord) -> tuple[str, str]:
    _validate_identifier(fact.concept, field="fact concept")
    if fact.fact_type not in {"condition", "medication", "observation", "demographic"}:
        raise FeatureContractError(f"unsupported fact type {fact.fact_type!r}")
    if fact.assertion not in _FACT_STATES[:-1]:
        raise FeatureContractError(f"unsupported fact assertion {fact.assertion!r}")
    return fact.fact_type, fact.concept


def _latest_facts(patient: R6PatientRecord) -> Mapping[tuple[str, str], R6FactRecord]:
    """Choose one deterministic current value per concept without relying on input order."""

    selected: dict[tuple[str, str], R6FactRecord] = {}
    for fact in patient.facts:
        key = _fact_key(fact)
        previous = selected.get(key)
        rank = (fact.effective_date or date.min, fact.fact_id)
        previous_rank = (
            (previous.effective_date or date.min, previous.fact_id)
            if previous is not None
            else None
        )
        if previous_rank is None or rank > previous_rank:
            selected[key] = fact
    return selected


def _age_band(patient: R6PatientRecord, as_of_date: date) -> str:
    if patient.date_of_birth is None:
        return "unknown"
    age = (
        as_of_date.year
        - patient.date_of_birth.year
        - (
            (as_of_date.month, as_of_date.day)
            < (patient.date_of_birth.month, patient.date_of_birth.day)
        )
    )
    if age < 0:
        raise FeatureContractError(f"member {patient.member_id!r} has a future date of birth")
    if age < 18:
        return "0_17"
    if age < 35:
        return "18_34"
    if age < 50:
        return "35_49"
    if age < 65:
        return "50_64"
    return "65_plus"


def _evidence_age(fact: R6FactRecord | None, as_of_date: date) -> float:
    if fact is None or fact.effective_date is None:
        return math.nan
    return float(max(0, (as_of_date - fact.effective_date).days))


def _numeric_value(fact: R6FactRecord | None) -> float:
    if fact is None or fact.assertion != "present" or fact.value is None:
        return math.nan
    if isinstance(fact.value, bool):
        raise FeatureContractError(f"observation {fact.concept!r} has a boolean numeric value")
    try:
        value = float(fact.value)
    except (TypeError, ValueError) as exc:
        raise FeatureContractError(
            f"observation {fact.concept!r} requires a finite numeric value when present"
        ) from exc
    if not math.isfinite(value):
        raise FeatureContractError(f"observation {fact.concept!r} has a non-finite numeric value")
    return value


def _preprocess(
    raw_matrix: np.ndarray, feature_names: tuple[str, ...], numeric_feature_names: tuple[str, ...]
) -> tuple[np.ndarray, np.ndarray, PreprocessingParameters]:
    """Median-impute only declared numeric columns, then standardize and L2 normalize."""

    matrix = raw_matrix.astype(np.float64, copy=True)
    numeric_indices = tuple(feature_names.index(name) for name in numeric_feature_names)
    medians: list[float] = []
    for index in numeric_indices:
        present = matrix[:, index][np.isfinite(matrix[:, index])]
        if not len(present):
            raise FeatureContractError(
                f"numeric feature {feature_names[index]!r} is completely missing; "
                "cannot median-impute"
            )
        median = float(np.median(present))
        matrix[~np.isfinite(matrix[:, index]), index] = median
        medians.append(median)
    if not np.isfinite(matrix).all():
        raise FeatureContractError("only declared numeric columns may contain missing values")
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0)
    scales[scales == 0.0] = 1.0
    standardized = ((matrix - means) / scales).astype(np.float32)
    norms = np.linalg.norm(standardized, axis=1, keepdims=True)
    # A single completely invariant row has no direction. Keep it a valid zero vector rather than
    # inventing information; FAISS then reports tied zero cosine scores deterministically.
    normalized = np.divide(
        standardized,
        norms,
        out=np.zeros_like(standardized, dtype=np.float32),
        where=norms > 0,
    ).astype(np.float32)
    return (
        standardized,
        normalized,
        PreprocessingParameters(
            version=PREPROCESSING_VERSION,
            numeric_feature_names=numeric_feature_names,
            medians=tuple(medians),
            means=tuple(float(value) for value in means),
            scales=tuple(float(value) for value in scales),
        ),
    )


def _artifact(
    *,
    name: str,
    version: str,
    member_ids: tuple[str, ...],
    feature_names: tuple[str, ...],
    raw_matrix: np.ndarray,
    numeric_feature_names: tuple[str, ...],
    context: RepresentationContext,
) -> RepresentationArtifact:
    if len(set(feature_names)) != len(feature_names):
        raise FeatureContractError("feature names must be unique")
    for feature_name in feature_names:
        _validate_identifier(feature_name, field="feature name")
    standardized, normalized, preprocessing = _preprocess(
        raw_matrix, feature_names, numeric_feature_names
    )
    subject_checksum = context.subject_order_checksum or canonical_checksum(member_ids)
    return RepresentationArtifact(
        name=name,  # type: ignore[arg-type]
        version=version,
        member_ids=member_ids,
        feature_names=feature_names,
        raw_matrix=raw_matrix.astype(np.float32),
        standardized_matrix=standardized,
        normalized_matrix=normalized,
        preprocessing=preprocessing,
        cohort_checksum=context.cohort_checksum,
        reference_panel_checksum=context.reference_panel_checksum,
        criterion_order_checksum=context.criterion_order_checksum,
        subject_order_checksum=subject_checksum,
        feature_order_checksum=canonical_checksum(feature_names),
    )


def build_patient_fact_representation(
    patients: Sequence[R6PatientRecord], context: RepresentationContext
) -> RepresentationArtifact:
    """Build the fact-recording space; no screening result fields are accepted here."""

    _validate_context(context)
    ordered = _ordered_members(patients)
    latest = {patient.member_id: _latest_facts(patient) for patient in ordered}
    concepts = sorted(
        {
            key
            for facts in latest.values()
            for key in facts
            if key[0] in {"condition", "medication", "observation"}
        }
    )
    feature_names: list[str] = [
        f"age_band:{band}" for band in ("0_17", "18_34", "35_49", "50_64", "65_plus", "unknown")
    ]
    sexes = ("female", "male", "missing")
    feature_names.extend(f"sex:{sex}" for sex in sexes)
    numeric_feature_names: list[str] = []
    for fact_type, concept in concepts:
        prefix = f"{fact_type}:{concept}"
        if fact_type in {"condition", "medication"}:
            feature_names.extend(f"{prefix}:state:{state}" for state in _FACT_STATES)
        else:
            value_name = f"{prefix}:value"
            missing_name = f"{prefix}:value_missing"
            feature_names.extend((value_name, missing_name))
            numeric_feature_names.append(value_name)
        age_name = f"{prefix}:evidence_age_days"
        age_missing_name = f"{prefix}:evidence_age_missing"
        feature_names.extend((age_name, age_missing_name))
        numeric_feature_names.append(age_name)
    rows: list[list[float]] = []
    for patient in ordered:
        member_facts = latest[patient.member_id]
        row: list[float] = []
        patient_band = _age_band(patient, context.as_of_date)
        row.extend(
            float(patient_band == band)
            for band in ("0_17", "18_34", "35_49", "50_64", "65_plus", "unknown")
        )
        normalized_sex = patient.sex.casefold() if patient.sex else "missing"
        if normalized_sex not in {"female", "male"}:
            normalized_sex = "missing"
        row.extend(float(normalized_sex == sex) for sex in sexes)
        for fact_type, concept in concepts:
            fact = member_facts.get((fact_type, concept))
            if fact_type in {"condition", "medication"}:
                state = fact.assertion if fact is not None else "missing"
                row.extend(float(state == candidate) for candidate in _FACT_STATES)
            else:
                value = _numeric_value(fact)
                row.extend((value, float(not math.isfinite(value))))
            evidence_age = _evidence_age(fact, context.as_of_date)
            row.extend((evidence_age, float(not math.isfinite(evidence_age))))
        rows.append(row)
    return _artifact(
        name="patient_fact",
        version=PATIENT_FACT_REPRESENTATION_VERSION,
        member_ids=tuple(patient.member_id for patient in ordered),
        feature_names=tuple(feature_names),
        raw_matrix=np.asarray(rows, dtype=np.float64),
        numeric_feature_names=tuple(numeric_feature_names),
        context=context,
    )


def build_screening_profile_representation(
    patients: Sequence[R6PatientRecord],
    criterion_results: Sequence[R6CriterionResultRecord],
    context: RepresentationContext,
) -> RepresentationArtifact:
    """Build the deterministic-screening evidence space over one complete frozen panel."""

    _validate_context(context)
    ordered = _ordered_members(patients)
    member_ids = tuple(patient.member_id for patient in ordered)
    known_members = set(member_ids)
    records: dict[tuple[str, str, str], R6CriterionResultRecord] = {}
    panel: dict[tuple[str, str], tuple[int, int, str]] = {}
    missing_categories: set[str] = set()
    for record in criterion_results:
        if record.member_id not in known_members:
            raise FeatureContractError(f"criterion result has unknown member {record.member_id!r}")
        if record.result not in _RESULT_STATES:
            raise FeatureContractError(f"unsupported criterion result {record.result!r}")
        _validate_identifier(record.trial_version_id, field="trial version id")
        _validate_identifier(record.criterion_id, field="criterion id")
        _validate_identifier(record.criterion_family, field="criterion family")
        panel_key = (record.trial_version_id, record.criterion_id)
        panel_value = (record.trial_order, record.criterion_order, record.criterion_family)
        existing_panel = panel.get(panel_key)
        if existing_panel is not None and existing_panel != panel_value:
            raise FeatureContractError(f"criterion order/family changed for {panel_key!r}")
        panel[panel_key] = panel_value
        record_key = (record.member_id, *panel_key)
        if record_key in records:
            raise FeatureContractError(f"duplicate criterion result {record_key!r}")
        records[record_key] = record
        for category in record.missing_categories:
            _validate_identifier(category, field="missing-information category")
            missing_categories.add(category)
    if not panel:
        raise FeatureContractError("screening-profile representation requires criterion results")
    ordered_panel = tuple(sorted(panel, key=lambda item: (*panel[item][:2], item[0], item[1])))
    for member_id in member_ids:
        for trial_id, criterion_id in ordered_panel:
            if (member_id, trial_id, criterion_id) not in records:
                raise FeatureContractError(
                    "screening-profile matrix is incomplete for "
                    f"member={member_id!r}, trial={trial_id!r}, criterion={criterion_id!r}"
                )
    trial_ids = tuple(
        sorted(
            {trial_id for trial_id, _ in ordered_panel},
            key=lambda item: (
                min(panel[(item, cid)][0] for tid, cid in ordered_panel if tid == item),
                item,
            ),
        )
    )
    families = tuple(sorted({panel[key][2] for key in ordered_panel}))
    feature_names: list[str] = []
    for trial_id, criterion_id in ordered_panel:
        feature_names.extend(
            f"criterion:{trial_id}:{criterion_id}:result:{state}" for state in _RESULT_STATES
        )
    for trial_id in trial_ids:
        feature_names.extend(
            f"trial:{trial_id}:criterion_result_rate:{state}" for state in _RESULT_STATES
        )
    for family in families:
        feature_names.extend(
            f"family:{family}:criterion_result_rate:{state}" for state in _RESULT_STATES
        )
    categories = tuple(sorted(missing_categories))
    feature_names.extend(f"missing_category:{category}:rate" for category in categories)
    rows: list[list[float]] = []
    for member_id in member_ids:
        row: list[float] = []
        member_records = [records[(member_id, *panel_key)] for panel_key in ordered_panel]
        for record in member_records:
            row.extend(float(record.result == state) for state in _RESULT_STATES)
        for trial_id in trial_ids:
            trial_records = [
                record for record in member_records if record.trial_version_id == trial_id
            ]
            row.extend(
                sum(record.result == state for record in trial_records) / len(trial_records)
                for state in _RESULT_STATES
            )
        for family in families:
            family_records = [
                record for record in member_records if record.criterion_family == family
            ]
            row.extend(
                sum(record.result == state for record in family_records) / len(family_records)
                for state in _RESULT_STATES
            )
        row.extend(
            sum(category in record.missing_categories for record in member_records)
            / len(member_records)
            for category in categories
        )
        rows.append(row)
    return _artifact(
        name="screening_profile",
        version=SCREENING_PROFILE_REPRESENTATION_VERSION,
        member_ids=member_ids,
        feature_names=tuple(feature_names),
        raw_matrix=np.asarray(rows, dtype=np.float64),
        numeric_feature_names=(),
        context=context,
    )
