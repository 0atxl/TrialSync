"""Generate the frozen controlled-recovery cohort and separately sealed answer key."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid5

import numpy as np

from research.build_r6_cohort import (
    ParquetArtifactSerializer,
    _fact_records,
    _patient_records,
    _reference_panel,
    _screening_records,
    _snapshot_version,
    build_reference_panel,
)
from research.configs.r6_cohort import DEFAULT_CONFIG as R6_V1_CONFIG
from research.configs.r6_recovery import (
    AGE_PARAMETERS,
    ALL_GROUPS,
    BACKGROUND_GROUP,
    CONDITION_PROBABILITIES,
    CONDITIONS,
    DEFAULT_RECOVERY_CONFIG,
    GROUP_RESIDUALS,
    MEDICATIONS,
    OBSERVATION_PARAMETERS,
    OBSERVATIONS,
    RECOVERY_UUID_NAMESPACE,
    STRUCTURED_GROUPS,
    R6RecoveryConfig,
)
from research.schemas.r6_dataset import (
    ARTIFACT_FILENAMES,
    CRITERION_RESULTS_FILENAME,
    MANIFEST_FILENAME,
    R6_ARTIFACT_FORMAT,
    REFERENCE_PANEL_FILENAME,
    canonical_json,
    semantic_checksum,
    validate_forbidden_feature_leakage,
)
from research.schemas.r6_recovery import (
    ANSWER_KEY_DIRECTORY,
    ANSWER_KEY_FILENAME,
    COHORT_DIRECTORY,
    GENERATION_AUDIT_FILENAME,
    GENERATION_CONFIG_FILENAME,
)
from trialsync.domain import Assertion, Fact, FactType, PatientSnapshot, Temporality

_SAFE_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SEXES = ("female", "male", "unspecified")
_SEX_PROBABILITIES = (0.45, 0.45, 0.10)
_FULL_REFERENCE_PANEL_CHECKSUM = "a9e0f6b06ce8c440f18f46d34217f0d642ecd4ea9b65a415111454963f1c686b"
_FULL_CRITERION_ORDER_CHECKSUM = "60825a8e975106d7a01558027a1407c57ebcc579db8b7c0c8f16f4bb00cab641"


@dataclass(frozen=True, slots=True)
class RecoveryMaterialization:
    config: R6RecoveryConfig
    run_id: str
    patients: tuple[PatientSnapshot, ...]
    patient_records: tuple[dict[str, object], ...]
    patient_fact_records: tuple[dict[str, object], ...]
    trials: tuple[Any, ...]
    reference_panel: dict[str, object]
    screening_pairs: tuple[dict[str, object], ...]
    criterion_results: tuple[dict[str, object], ...]
    answer_key: tuple[dict[str, object], ...]
    generation_audit: tuple[dict[str, object], ...]
    semantic_checksums: dict[str, str]


def _rng(
    config: R6RecoveryConfig, patient_ordinal: int, stream_name: str, instance: int = 0
) -> np.random.Generator:
    sequence = np.random.SeedSequence(
        [config.seed, patient_ordinal, config.stream_codes[stream_name], instance]
    )
    return np.random.Generator(np.random.PCG64(sequence))


def _field_instance_table() -> dict[str, dict[str, int]]:
    status_instances = {
        **{f"condition.{concept}": index for index, concept in enumerate(CONDITIONS, start=1)},
        **{f"medication.{concept}": index for index, concept in enumerate(MEDICATIONS, start=101)},
        **{
            f"observation.{concept}": index for index, concept in enumerate(OBSERVATIONS, start=201)
        },
    }
    return {
        "demographics": {"age": 1, "sex": 2, "birthday_offset": 3},
        "condition_truth": {concept: index for index, concept in enumerate(CONDITIONS, start=1)},
        "medication_truth": {concept: index for index, concept in enumerate(MEDICATIONS, start=1)},
        "observation_values": {
            concept: index for index, concept in enumerate(OBSERVATIONS, start=1)
        },
        "missing_unknown": status_instances,
        "evidence_dates": status_instances,
        "background_variation": {
            "condition_inversion": 1,
            **{
                f"observation_residual.{concept}": 100 + index
                for index, concept in enumerate(OBSERVATIONS, start=1)
            },
        },
        "crossover_secondary": {"secondary_group": 0},
    }


def _patient_stream_identifiers(config: R6RecoveryConfig, ordinal: int) -> dict[str, str]:
    return {
        f"{stream_name}.{field_name}": (
            f"{config.seed}:{ordinal}:{config.stream_codes[stream_name]}:{instance}"
        )
        for stream_name, fields in _field_instance_table().items()
        for field_name, instance in fields.items()
    }


def _stable_id(kind: str, value: object) -> str:
    return str(uuid5(RECOVERY_UUID_NAMESPACE, f"{kind}:{value}"))


def _make_fact(
    patient_id: str,
    ordinal: int,
    fact_type: FactType,
    concept: str,
    *,
    value: Decimal | str | None = None,
    unit: str | None = None,
    assertion: Assertion = Assertion.present,
    effective_date: date | None = None,
) -> Fact:
    return Fact(
        id=_stable_id("fact", f"{patient_id}:{ordinal}:{fact_type.value}:{concept}"),
        fact_type=fact_type,
        concept=concept,
        value=value,
        unit=unit,
        assertion=assertion,
        temporality=Temporality.current,
        effective_date=effective_date,
        source_label="Cohort record",
    )


def _assignment_schedule(config: R6RecoveryConfig) -> tuple[str, ...]:
    assignments = [
        group
        for group, count in zip(STRUCTURED_GROUPS, config.group_counts, strict=True)
        for _ in range(count)
    ]
    assignments.extend([BACKGROUND_GROUP] * config.background_count)
    permutation = _rng(config, 0, "assignment_shuffle").permutation(len(assignments))
    return tuple(assignments[int(index)] for index in permutation)


def _crossover_schedule(config: R6RecoveryConfig, assignments: Sequence[str]) -> frozenset[int]:
    selected: set[int] = set()
    for group_index, (group, count) in enumerate(
        zip(STRUCTURED_GROUPS, config.crossover_counts, strict=True), start=1
    ):
        candidates = np.asarray(
            [ordinal for ordinal, value in enumerate(assignments, start=1) if value == group],
            dtype=np.int64,
        )
        if count:
            chosen = _rng(config, 0, "crossover_selection", group_index).choice(
                candidates, size=count, replace=False
            )
            selected.update(int(value) for value in chosen)
    return frozenset(selected)


def _background_inversion_schedule(
    config: R6RecoveryConfig, assignments: Sequence[str]
) -> frozenset[int]:
    candidates = np.asarray(
        [
            ordinal
            for ordinal, value in enumerate(assignments, start=1)
            if value == BACKGROUND_GROUP
        ],
        dtype=np.int64,
    )
    count = config.background_count // 2
    chosen = _rng(config, 0, "background_variation", 99).choice(
        candidates, size=count, replace=False
    )
    return frozenset(int(value) for value in chosen)


def _draw_age(config: R6RecoveryConfig, ordinal: int, group: str) -> tuple[int, str, int]:
    parameters = AGE_PARAMETERS[group]
    age_rng = _rng(config, ordinal, "demographics", 1)
    if parameters["distribution"] == "discrete_uniform":
        age = int(age_rng.integers(int(parameters["min"]), int(parameters["max"]) + 1))
    else:
        age = -1
        while not int(parameters["min"]) <= age <= int(parameters["max"]):
            age = round(age_rng.normal(float(parameters["mean"]), float(parameters["sd"])))
    sex = str(_rng(config, ordinal, "demographics", 2).choice(_SEXES, p=_SEX_PROBABILITIES))
    birthday_offset = int(_rng(config, ordinal, "demographics", 3).integers(0, 365))
    return age, sex, birthday_offset


def _secondary_group(config: R6RecoveryConfig, ordinal: int, primary: str) -> str:
    candidates = tuple(group for group in STRUCTURED_GROUPS if group != primary)
    return str(_rng(config, ordinal, "crossover_secondary").choice(candidates))


def _condition_truth(
    config: R6RecoveryConfig,
    ordinal: int,
    primary: str,
    secondary: str | None,
    *,
    invert_background: bool,
) -> tuple[dict[str, bool], str | None]:
    primary_values = np.asarray(CONDITION_PROBABILITIES[primary], dtype=np.float64)
    if secondary is not None:
        secondary_values = np.asarray(CONDITION_PROBABILITIES[secondary], dtype=np.float64)
        probabilities = 0.75 * primary_values + 0.25 * secondary_values
    else:
        probabilities = primary_values
    truth = {
        concept: bool(_rng(config, ordinal, "condition_truth", index).random() < probability)
        for index, (concept, probability) in enumerate(
            zip(CONDITIONS, probabilities, strict=True), start=1
        )
    }
    if truth["type1_diabetes"]:
        truth["type2_diabetes"] = False
    inverted: str | None = None
    if primary == BACKGROUND_GROUP and invert_background:
        background_rng = _rng(config, ordinal, "background_variation", 1)
        inverted = CONDITIONS[int(background_rng.integers(0, len(CONDITIONS)))]
        truth[inverted] = not truth[inverted]
        if inverted == "type1_diabetes" and truth[inverted]:
            truth["type2_diabetes"] = False
        elif inverted == "type2_diabetes" and truth[inverted]:
            truth["type1_diabetes"] = False
    return truth, inverted


def _medication_probability(concept: str, truth: Mapping[str, bool], age: int) -> float:
    type1 = truth["type1_diabetes"]
    type2 = truth["type2_diabetes"]
    if concept == "metformin":
        return 0.75 if type2 else 0.05
    if concept == "insulin":
        return 0.88 if type1 else 0.22 if type2 else 0.03
    if concept == "semaglutide":
        return 0.38 if type2 else 0.04
    if concept == "atorvastatin":
        return 0.65 if truth["hypertension"] or type2 or age >= 55 else 0.08
    raise ValueError(f"unsupported medication concept: {concept}")


def _medication_truth(
    config: R6RecoveryConfig,
    ordinal: int,
    primary: str,
    condition_truth: Mapping[str, bool],
    age: int,
) -> dict[str, bool]:
    states: dict[str, bool] = {}
    for index, concept in enumerate(MEDICATIONS, start=1):
        rng = _rng(config, ordinal, "medication_truth", index)
        probability = _medication_probability(concept, condition_truth, age)
        if primary == BACKGROUND_GROUP:
            probability = 0.5 * probability + 0.5 * float(rng.uniform(0.05, 0.70))
        states[concept] = bool(rng.random() < probability)
    return states


def _observation_centers(age: int, truth: Mapping[str, bool]) -> dict[str, float]:
    type1 = float(truth["type1_diabetes"])
    type2 = float(truth["type2_diabetes"])
    hypertension = float(truth["hypertension"])
    diabetes = float(bool(type1 or type2))
    return {
        "hba1c": 5.4 + 2.7 * type1 + 2.3 * type2,
        "fasting_glucose": 92.0 + 72.0 * type1 + 62.0 * type2,
        "egfr": 105.0 - 0.65 * max(age - 30, 0) - 12.0 * diabetes,
        "creatinine": 0.78 + 0.008 * max(age - 40, 0) + 0.22 * diabetes,
        "hemoglobin": 13.8 - 0.45 * diabetes,
        "platelets": 245.0,
        "bmi": 24.0 + 5.0 * type2 + 1.8 * hypertension,
        "systolic_bp": 112.0 + 0.25 * max(age - 30, 0) + 22.0 * hypertension,
        "diastolic_bp": 72.0 + 12.0 * hypertension,
        "potassium": 4.2,
    }


def _residual(primary: str, secondary: str | None, concept: str) -> float:
    primary_value = GROUP_RESIDUALS.get(primary, {}).get(concept, 0.0)
    if secondary is None:
        return primary_value
    secondary_value = GROUP_RESIDUALS[secondary].get(concept, 0.0)
    return 0.75 * primary_value + 0.25 * secondary_value


def _draw_observations(
    config: R6RecoveryConfig,
    ordinal: int,
    primary: str,
    secondary: str | None,
    age: int,
    truth: Mapping[str, bool],
) -> tuple[dict[str, float], dict[str, float]]:
    centers = _observation_centers(age, truth)
    residual_factors: dict[str, float] = {}
    values: dict[str, float] = {}
    for index, concept in enumerate(OBSERVATIONS, start=1):
        parameters = OBSERVATION_PARAMETERS[concept]
        spread = float(parameters["spread"])
        if primary == BACKGROUND_GROUP:
            factor = float(
                _rng(config, ordinal, "background_variation", 100 + index).uniform(-1.5, 1.5)
            )
            center = centers[concept] + factor * spread
            used_spread = spread * 1.35
            residual_factors[concept] = factor
        else:
            center = centers[concept] + _residual(primary, secondary, concept)
            used_spread = spread
        sampled = float(
            _rng(config, ordinal, "observation_values", index).normal(center, used_spread)
        )
        values[concept] = round(
            min(max(sampled, float(parameters["min"])), float(parameters["max"])), 2
        )
    return values, residual_factors


def _record_status_fact(
    *,
    facts: list[Fact],
    patient_id: str,
    ordinal: int,
    fact_type: FactType,
    concept: str,
    present: bool,
    record_draw: float,
    date_offset: int,
    screening_date: date,
) -> int:
    if record_draw < 0.08:
        return ordinal
    assertion = (
        Assertion.unknown
        if record_draw < 0.14
        else Assertion.present
        if present
        else Assertion.absent
    )
    facts.append(
        _make_fact(
            patient_id,
            ordinal,
            fact_type,
            concept,
            assertion=assertion,
            effective_date=screening_date - timedelta(days=date_offset),
        )
    )
    return ordinal + 1


def _build_patient(
    config: R6RecoveryConfig,
    ordinal: int,
    primary: str,
    *,
    crossover: bool,
    invert_background: bool,
) -> tuple[PatientSnapshot, dict[str, object], dict[str, object]]:
    patient_id = _stable_id(
        "patient_snapshot", f"{config.contract_version}:{config.seed}:{ordinal}"
    )
    age, sex, birthday_offset = _draw_age(config, ordinal, primary)
    anchor = date(
        config.screening_date.year - age,
        config.screening_date.month,
        config.screening_date.day,
    )
    dob = anchor - timedelta(days=birthday_offset)
    secondary = _secondary_group(config, ordinal, primary) if crossover else None
    truths, inverted = _condition_truth(
        config,
        ordinal,
        primary,
        secondary,
        invert_background=invert_background,
    )
    medications = _medication_truth(config, ordinal, primary, truths, age)
    observations, background_residuals = _draw_observations(
        config, ordinal, primary, secondary, age, truths
    )
    facts: list[Fact] = []
    fact_ordinal = 1
    if sex != "unspecified":
        facts.append(
            _make_fact(
                patient_id,
                fact_ordinal,
                FactType.demographic,
                sex,
                value=sex,
                effective_date=config.screening_date,
            )
        )
        fact_ordinal += 1
    for index, concept in enumerate(CONDITIONS, start=1):
        fact_ordinal = _record_status_fact(
            facts=facts,
            patient_id=patient_id,
            ordinal=fact_ordinal,
            fact_type=FactType.condition,
            concept=concept,
            present=truths[concept],
            record_draw=float(_rng(config, ordinal, "missing_unknown", index).random()),
            date_offset=int(_rng(config, ordinal, "evidence_dates", index).integers(1, 91)),
            screening_date=config.screening_date,
        )
    for index, concept in enumerate(MEDICATIONS, start=101):
        fact_ordinal = _record_status_fact(
            facts=facts,
            patient_id=patient_id,
            ordinal=fact_ordinal,
            fact_type=FactType.medication,
            concept=concept,
            present=medications[concept],
            record_draw=float(_rng(config, ordinal, "missing_unknown", index).random()),
            date_offset=int(_rng(config, ordinal, "evidence_dates", index).integers(1, 91)),
            screening_date=config.screening_date,
        )
    for index, concept in enumerate(OBSERVATIONS, start=201):
        record_draw = float(_rng(config, ordinal, "missing_unknown", index).random())
        if record_draw < 0.12:
            continue
        parameters = OBSERVATION_PARAMETERS[concept]
        assertion = Assertion.unknown if record_draw < 0.17 else Assertion.present
        facts.append(
            _make_fact(
                patient_id,
                fact_ordinal,
                FactType.observation,
                concept,
                value=(
                    Decimal(str(observations[concept])) if assertion is Assertion.present else None
                ),
                unit=str(parameters["unit"]),
                assertion=assertion,
                effective_date=config.screening_date
                - timedelta(
                    days=int(_rng(config, ordinal, "evidence_dates", index).integers(1, 151))
                ),
            )
        )
        fact_ordinal += 1
    patient = PatientSnapshot(
        id=patient_id,
        version=_snapshot_version(dob, facts),
        date_of_birth=dob,
        facts=tuple(facts),
    )
    answer = {
        "patient_snapshot_id": patient_id,
        "latent_group_id": primary,
        "is_background": primary == BACKGROUND_GROUP,
        "answer_key_version": config.answer_key_version,
    }
    audit = {
        "patient_snapshot_id": patient_id,
        "patient_ordinal": ordinal,
        "primary_group_id": primary,
        "is_crossover": crossover,
        "secondary_group_id": secondary,
        "age": age,
        "sex": sex,
        "condition_truth": truths,
        "medication_truth": medications,
        "background_inverted_condition": inverted,
        "background_residual_factors": background_residuals,
        "rng_stream_ids": _patient_stream_identifiers(config, ordinal),
    }
    return patient, answer, audit


def _generation_config_record(config: R6RecoveryConfig) -> dict[str, object]:
    return {
        "contract_version": config.contract_version,
        "generator_version": config.generator_version,
        "answer_key_version": config.answer_key_version,
        "analysis_version": config.analysis_version,
        "evaluation_version": config.evaluation_version,
        "seed": config.seed,
        "screening_date": config.screening_date.isoformat(),
        "patient_count": config.patient_count,
        "structured_group_counts": dict(zip(STRUCTURED_GROUPS, config.group_counts, strict=True)),
        "background_count": config.background_count,
        "crossover_counts": dict(zip(STRUCTURED_GROUPS, config.crossover_counts, strict=True)),
        "trial_count": config.trial_count,
        "uuid_namespace": str(RECOVERY_UUID_NAMESPACE),
        "rng": {
            "algorithm": config.numpy_rng,
            "seed_sequence_inputs": ["seed", "patient_ordinal", "stream_code", "instance"],
            "stream_codes": dict(sorted(config.stream_codes.items())),
            "field_instance_table": _field_instance_table(),
        },
        "numpy_version": np.__version__,
        "sex_probabilities": dict(zip(_SEXES, _SEX_PROBABILITIES, strict=True)),
        "age_parameters": AGE_PARAMETERS,
        "condition_probabilities": {
            group: dict(zip(CONDITIONS, values, strict=True))
            for group, values in CONDITION_PROBABILITIES.items()
        },
        "crossover_blend": {"primary": 0.75, "secondary": 0.25},
        "medication_rules": {
            "metformin": {"type2": 0.75, "otherwise": 0.05},
            "insulin": {"type1": 0.88, "type2": 0.22, "otherwise": 0.03},
            "semaglutide": {"type2": 0.38, "otherwise": 0.04},
            "atorvastatin": {"qualifying": 0.65, "otherwise": 0.08},
            "background_blend": {"condition_weight": 0.5, "uniform_weight": 0.5},
        },
        "observation_parameters": OBSERVATION_PARAMETERS,
        "group_residuals": GROUP_RESIDUALS,
        "missingness": {
            "status": {"omitted": 0.08, "unknown": 0.06, "recorded": 0.86},
            "observation": {"omitted": 0.12, "unknown": 0.05, "numeric": 0.83},
        },
        "date_offsets_days": {"status": [1, 90], "observation": [1, 150]},
        "engine_version": config.engine_version,
        "dsl_version": config.dsl_version,
        "terminology_version": config.terminology_version,
        "unit_version": config.unit_version,
    }


def materialize_recovery(
    config: R6RecoveryConfig = DEFAULT_RECOVERY_CONFIG,
) -> RecoveryMaterialization:
    """Build one deterministic run in memory without opening a database or artifact path."""

    assignments = _assignment_schedule(config)
    crossovers = _crossover_schedule(config, assignments)
    inversions = _background_inversion_schedule(config, assignments)
    built = [
        _build_patient(
            config,
            ordinal,
            group,
            crossover=ordinal in crossovers,
            invert_background=ordinal in inversions,
        )
        for ordinal, group in enumerate(assignments, start=1)
    ]
    built.sort(key=lambda item: item[0].id)
    patients = tuple(item[0] for item in built)
    answer_key = tuple(item[1] for item in built)
    generation_audit = tuple(item[2] for item in built)
    trials = build_reference_panel(R6_V1_CONFIG)[: config.trial_count]
    reference_panel = _reference_panel(R6_V1_CONFIG, trials)
    patient_records = _patient_records(patients)
    patient_fact_records = _fact_records(patients)
    screening_pairs, criterion_results = _screening_records(patients, trials, R6_V1_CONFIG)
    expected_pairs = config.patient_count * config.trial_count
    if len(screening_pairs) != expected_pairs:
        raise ValueError("controlled-recovery screening matrix is incomplete")
    if len(criterion_results) != expected_pairs * 4:
        raise ValueError("controlled-recovery criterion matrix is incomplete")
    validate_forbidden_feature_leakage(
        (*patient_records, *patient_fact_records, *screening_pairs, *criterion_results)
    )
    checksums = {
        "patient_snapshots": semantic_checksum(patient_records),
        "patient_facts": semantic_checksum(patient_fact_records),
        "reference_panel": semantic_checksum(reference_panel),
        "criterion_order": semantic_checksum(
            [
                {
                    "trial_version_id": trial.id,
                    "criterion_id": criterion.id,
                    "order": criterion.order,
                }
                for trial in trials
                for criterion in trial.criteria
            ]
        ),
        "screening_pairs": semantic_checksum(screening_pairs),
        "criterion_results": semantic_checksum(criterion_results),
    }
    checksums["cohort"] = semantic_checksum(
        {
            "patient_snapshots": checksums["patient_snapshots"],
            "patient_facts": checksums["patient_facts"],
        }
    )
    if config == DEFAULT_RECOVERY_CONFIG:
        if checksums["reference_panel"] != _FULL_REFERENCE_PANEL_CHECKSUM:
            raise ValueError("controlled-recovery reference panel differs from frozen R6 V1")
        if checksums["criterion_order"] != _FULL_CRITERION_ORDER_CHECKSUM:
            raise ValueError("controlled-recovery criterion order differs from frozen R6 V1")
    run_payload = {
        "config": _generation_config_record(config),
        "semantic_checksums": checksums,
    }
    run_id = f"r6-recovery-{uuid5(RECOVERY_UUID_NAMESPACE, canonical_json(run_payload))}"
    if not _SAFE_RUN_ID.fullmatch(run_id):
        raise ValueError("controlled-recovery run_id is not path-safe")
    return RecoveryMaterialization(
        config=config,
        run_id=run_id,
        patients=patients,
        patient_records=patient_records,
        patient_fact_records=patient_fact_records,
        trials=trials,
        reference_panel=reference_panel,
        screening_pairs=screening_pairs,
        criterion_results=criterion_results,
        answer_key=answer_key,
        generation_audit=generation_audit,
        semantic_checksums=checksums,
    )


def _file_record(root: Path, path: Path, *, count: int | None = None) -> dict[str, object]:
    record: dict[str, object] = {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    if count is not None:
        record["record_count"] = count
    return record


def _write_answer_key(
    materialization: RecoveryMaterialization,
    directory: Path,
    serializer: ParquetArtifactSerializer,
    generated_at: str,
) -> dict[str, object]:
    directory.mkdir(parents=True)
    answer_path = directory / ANSWER_KEY_FILENAME
    audit_path = directory / GENERATION_AUDIT_FILENAME
    serializer.write_records(answer_path, materialization.answer_key)
    serializer.write_records(audit_path, materialization.generation_audit)
    group_counts = {
        group: sum(row["latent_group_id"] == group for row in materialization.answer_key)
        for group in ALL_GROUPS
    }
    manifest: dict[str, object] = {
        "run_id": materialization.run_id,
        "contract_version": materialization.config.answer_key_version,
        "generated_at": generated_at,
        "patient_count": len(materialization.answer_key),
        "group_counts": group_counts,
        "cohort_semantic_checksum": materialization.semantic_checksums["cohort"],
        "semantic_checksums": {
            "answer_key": semantic_checksum(materialization.answer_key),
            "generation_audit": semantic_checksum(materialization.generation_audit),
        },
        "files": {
            "answer_key": _file_record(
                directory, answer_path, count=len(materialization.answer_key)
            ),
            "generation_audit": _file_record(
                directory, audit_path, count=len(materialization.generation_audit)
            ),
        },
    }
    serializer.write_object(directory / MANIFEST_FILENAME, manifest)
    return manifest


def _write_cohort(
    materialization: RecoveryMaterialization,
    directory: Path,
    serializer: ParquetArtifactSerializer,
    generated_at: str,
    answer_key_manifest_sha256: str,
) -> dict[str, object]:
    directory.mkdir(parents=True)
    paths = {
        "patients": directory / ARTIFACT_FILENAMES["patients"],
        "patient_facts": directory / ARTIFACT_FILENAMES["patient_facts"],
        "reference_panel": directory / REFERENCE_PANEL_FILENAME,
        "screening_pairs": directory / ARTIFACT_FILENAMES["screening_pairs"],
        "criterion_results": directory / CRITERION_RESULTS_FILENAME,
        "generation_config": directory / GENERATION_CONFIG_FILENAME,
    }
    serializer.write_records(paths["patients"], materialization.patient_records)
    serializer.write_records(paths["patient_facts"], materialization.patient_fact_records)
    serializer.write_object(paths["reference_panel"], materialization.reference_panel)
    serializer.write_records(paths["screening_pairs"], materialization.screening_pairs)
    serializer.write_records(paths["criterion_results"], materialization.criterion_results)
    serializer.write_object(
        paths["generation_config"], _generation_config_record(materialization.config)
    )
    counts = {
        "patients": len(materialization.patient_records),
        "patient_facts": len(materialization.patient_fact_records),
        "reference_panel": len(materialization.trials),
        "screening_pairs": len(materialization.screening_pairs),
        "criterion_results": len(materialization.criterion_results),
    }
    files = {
        name: _file_record(directory, path, count=counts.get(name)) for name, path in paths.items()
    }
    manifest: dict[str, object] = {
        "run_id": materialization.run_id,
        # The base contract keeps the existing strict R6 loader reusable.
        "contract_version": R6_V1_CONFIG.contract_version,
        "recovery_contract_version": materialization.config.contract_version,
        "generated_at": generated_at,
        "generator_version": materialization.config.generator_version,
        "uuid_namespace": str(RECOVERY_UUID_NAMESPACE),
        "seed": materialization.config.seed,
        "screening_date": materialization.config.screening_date.isoformat(),
        "patient_count": len(materialization.patients),
        "trial_count": len(materialization.trials),
        "pair_count": len(materialization.screening_pairs),
        "criterion_result_count": len(materialization.criterion_results),
        "engine_version": materialization.config.engine_version,
        "dsl_version": materialization.config.dsl_version,
        "terminology_version": materialization.config.terminology_version,
        "unit_version": materialization.config.unit_version,
        "artifact_format": R6_ARTIFACT_FORMAT,
        "semantic_checksums": materialization.semantic_checksums,
        "answer_key_manifest_sha256": answer_key_manifest_sha256,
        "files": files,
    }
    serializer.write_object(directory / MANIFEST_FILENAME, manifest)
    return manifest


def write_recovery_artifacts(
    materialization: RecoveryMaterialization, output_root: Path
) -> tuple[Path, dict[str, object]]:
    """Atomically write one immutable benchmark run and refuse replacement."""

    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / materialization.run_id
    if target.exists():
        raise FileExistsError("controlled-recovery run already exists")
    serializer = ParquetArtifactSerializer()
    generated_at = datetime.now(UTC).isoformat()
    with tempfile.TemporaryDirectory(prefix=".recovery-building-", dir=output_root) as temporary:
        staging = Path(temporary)
        answer_directory = staging / ANSWER_KEY_DIRECTORY
        _write_answer_key(materialization, answer_directory, serializer, generated_at)
        answer_manifest_hash = hashlib.sha256(
            (answer_directory / MANIFEST_FILENAME).read_bytes()
        ).hexdigest()
        cohort_manifest = _write_cohort(
            materialization,
            staging / COHORT_DIRECTORY,
            serializer,
            generated_at,
            answer_manifest_hash,
        )
        staging.replace(target)
    return target, cohort_manifest


def run_generation(output_root: Path) -> dict[str, object]:
    materialization = materialize_recovery()
    run_directory, manifest = write_recovery_artifacts(materialization, output_root)
    return {
        "run_id": materialization.run_id,
        "run_directory": str(run_directory),
        "cohort_manifest": manifest,
        "next_command": (
            "backend/.venv/bin/python -m research.analyze_r6_recovery "
            f"--cohort-directory {run_directory / COHORT_DIRECTORY}"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the frozen R6 controlled-recovery benchmark."
    )
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_generation(args.output_root), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
