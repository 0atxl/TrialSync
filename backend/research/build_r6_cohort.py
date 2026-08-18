"""Materialize the isolated R6 screening cohort without database writes.

The module calls only the pure ``trialsync.domain.screen`` engine. Parquet stores
the tabular records while canonical semantic checksums remain serializer-independent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from trialsync.domain import (
    ApprovedTrialVersion,
    Assertion,
    Criterion,
    CriterionKind,
    CriterionResult,
    EvidenceReference,
    Fact,
    FactType,
    MissingRequirement,
    PatientSnapshot,
    ScreeningContext,
    Temporality,
    screen,
)

from .configs.r6_cohort import DEFAULT_CONFIG, R6CohortConfig
from .schemas.r6_dataset import (
    ARTIFACT_FILENAMES,
    CRITERION_RESULTS_FILENAME,
    MANIFEST_FILENAME,
    R6_ARTIFACT_FORMAT,
    REFERENCE_PANEL_FILENAME,
    semantic_checksum,
    validate_forbidden_feature_leakage,
)

_NAMESPACE = uuid5(NAMESPACE_URL, "trialsync:r6:cohort")
_CONDITIONS = ("type1_diabetes", "type2_diabetes", "hypertension", "asthma")
_MEDICATIONS = ("metformin", "atorvastatin", "insulin", "semaglutide")
_OBSERVATIONS: dict[str, tuple[str, float, float]] = {
    "hba1c": ("%", 4.5, 12.5),
    "fasting_glucose": ("mg/dL", 65.0, 280.0),
    "egfr": ("mL/min/1.73m2", 25.0, 125.0),
    "creatinine": ("mg/dL", 0.5, 2.8),
    "hemoglobin": ("g/dL", 8.5, 17.5),
    "platelets": ("10^9/L", 90.0, 520.0),
    "bmi": ("kg/m2", 16.0, 48.0),
    "systolic_bp": ("mmHg", 85.0, 210.0),
    "diastolic_bp": ("mmHg", 50.0, 125.0),
    "potassium": ("mmol/L", 2.8, 6.2),
}
_SEXES = ("female", "male", "unspecified")
_SAFE_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True, slots=True)
class MaterializedCohort:
    config: R6CohortConfig
    run_id: str
    patients: tuple[PatientSnapshot, ...]
    trials: tuple[ApprovedTrialVersion, ...]
    patient_records: tuple[dict[str, object], ...]
    patient_fact_records: tuple[dict[str, object], ...]
    reference_panel: dict[str, object]
    screening_pairs: tuple[dict[str, object], ...]
    criterion_results: tuple[dict[str, object], ...]
    semantic_checksums: dict[str, str]


class ArtifactSerializer(Protocol):
    format_name: str

    def write_records(self, path: Path, records: Sequence[Mapping[str, object]]) -> None: ...

    def write_object(self, path: Path, value: Mapping[str, object]) -> None: ...


class ParquetArtifactSerializer:
    """Deterministic columnar serialization for the versioned tabular artifacts."""

    format_name = R6_ARTIFACT_FORMAT

    def write_records(self, path: Path, records: Sequence[Mapping[str, object]]) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.Table.from_pylist([dict(record) for record in records])
        pq.write_table(  # type: ignore[no-untyped-call]
            table, path, compression="zstd", write_statistics=True
        )

    def write_object(self, path: Path, value: Mapping[str, object]) -> None:
        path.write_text(f"{_canonical_json(value)}\n", encoding="utf-8", newline="\n")


def _stable_id(kind: str, value: object) -> str:
    return str(uuid5(_NAMESPACE, f"{kind}:{value}"))


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fact(
    patient_key: str,
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
        id=_stable_id("fact", f"{patient_key}:{ordinal}:{fact_type.value}:{concept}"),
        fact_type=fact_type,
        concept=concept,
        value=value,
        unit=unit,
        assertion=assertion,
        temporality=Temporality.current,
        effective_date=effective_date,
        source_label="Cohort record",
    )


def _append_status_fact(
    *,
    rng: random.Random,
    facts: list[Fact],
    patient_key: str,
    ordinal: int,
    fact_type: FactType,
    concept: str,
    present: bool,
    screening_date: date,
) -> int:
    record_draw = rng.random()
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
        _fact(
            patient_key,
            ordinal,
            fact_type,
            concept,
            assertion=assertion,
            effective_date=screening_date - timedelta(days=rng.randint(1, 90)),
        )
    )
    return ordinal + 1


def _snapshot_version(date_of_birth: date, facts: Sequence[Fact]) -> str:
    payload = {
        "date_of_birth": date_of_birth.isoformat(),
        "facts": [
            {
                "id": fact.id,
                "fact_type": fact.fact_type.value,
                "concept": fact.concept,
                "value": str(fact.value) if fact.value is not None else None,
                "unit": fact.unit,
                "assertion": fact.assertion.value,
                "temporality": fact.temporality.value,
                "effective_date": fact.effective_date.isoformat()
                if fact.effective_date
                else None,
            }
            for fact in sorted(facts, key=lambda item: item.id)
        ],
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def build_patients(config: R6CohortConfig) -> tuple[PatientSnapshot, ...]:
    """Build sorted unique snapshots from a local seeded pseudo-random stream."""

    rng = random.Random(config.seed)
    patients: list[PatientSnapshot] = []
    cohort_key = (
        f"{config.contract_version}:{config.generator_version}:"
        f"{config.seed}:{config.screening_date.isoformat()}"
    )
    for index in range(1, config.patient_count + 1):
        patient_id = _stable_id("patient_snapshot", f"{cohort_key}:{index}")
        age = rng.randint(18, 82)
        birthday_offset = rng.randint(0, 364)
        dob = date(config.screening_date.year - age, 1, 1) - timedelta(days=birthday_offset)
        facts: list[Fact] = []
        sex = rng.choice(_SEXES)
        ordinal = 1
        if sex != "unspecified":
            facts.append(
                _fact(
                    patient_id,
                    ordinal,
                    FactType.demographic,
                    sex,
                    value=sex,
                    effective_date=config.screening_date,
                )
            )
            ordinal += 1

        type1 = rng.random() < 0.11
        type2_probability = min(0.48, 0.10 + max(age - 25, 0) * 0.006)
        type2 = not type1 and rng.random() < type2_probability
        hypertension_probability = min(0.68, 0.12 + max(age - 25, 0) * 0.009)
        condition_states = {
            "type1_diabetes": type1,
            "type2_diabetes": type2,
            "hypertension": rng.random() < hypertension_probability,
            "asthma": rng.random() < 0.21,
        }

        for condition in _CONDITIONS:
            ordinal = _append_status_fact(
                rng=rng,
                facts=facts,
                patient_key=patient_id,
                ordinal=ordinal,
                fact_type=FactType.condition,
                concept=condition,
                present=condition_states[condition],
                screening_date=config.screening_date,
            )

        medication_states = {
            "metformin": type2 and rng.random() < 0.72,
            "atorvastatin": (
                condition_states["hypertension"] or type2 or age >= 55
            ) and rng.random() < 0.58,
            "insulin": (type1 and rng.random() < 0.88) or (type2 and rng.random() < 0.22),
            "semaglutide": type2 and rng.random() < 0.31,
        }
        for medication in _MEDICATIONS:
            ordinal = _append_status_fact(
                rng=rng,
                facts=facts,
                patient_key=patient_id,
                ordinal=ordinal,
                fact_type=FactType.medication,
                concept=medication,
                present=medication_states[medication],
                screening_date=config.screening_date,
            )

        diabetic = type1 or type2
        observation_centers = {
            "hba1c": 7.8 if diabetic else 5.4,
            "fasting_glucose": 155.0 if diabetic else 92.0,
            "egfr": 104.0 - max(age - 30, 0) * 0.65 - (13.0 if diabetic else 0.0),
            "creatinine": 0.78 + max(age - 40, 0) * 0.008 + (0.24 if diabetic else 0.0),
            "hemoglobin": 13.8 - (0.5 if diabetic else 0.0),
            "platelets": 245.0,
            "bmi": 24.0 + (5.2 if type2 else 0.0) + (
                2.0 if condition_states["hypertension"] else 0.0
            ),
            "systolic_bp": 112.0 + max(age - 30, 0) * 0.28 + (
                23.0 if condition_states["hypertension"] else 0.0
            ),
            "diastolic_bp": 72.0 + (13.0 if condition_states["hypertension"] else 0.0),
            "potassium": 4.2,
        }
        observation_spreads = {
            "hba1c": 1.15,
            "fasting_glucose": 28.0,
            "egfr": 14.0,
            "creatinine": 0.25,
            "hemoglobin": 1.4,
            "platelets": 62.0,
            "bmi": 4.1,
            "systolic_bp": 14.0,
            "diastolic_bp": 9.0,
            "potassium": 0.45,
        }
        for concept, (unit, minimum, maximum) in _OBSERVATIONS.items():
            record_draw = rng.random()
            if record_draw < 0.12:
                continue
            if record_draw < 0.17:
                facts.append(
                    _fact(
                        patient_id,
                        ordinal,
                        FactType.observation,
                        concept,
                        unit=unit,
                        assertion=Assertion.unknown,
                        effective_date=config.screening_date
                        - timedelta(days=rng.randint(1, 150)),
                    )
                )
                ordinal += 1
                continue
            sampled = rng.gauss(observation_centers[concept], observation_spreads[concept])
            value = Decimal(str(round(min(max(sampled, minimum), maximum), 2)))
            facts.append(
                _fact(
                    patient_id,
                    ordinal,
                    FactType.observation,
                    concept,
                    value=value,
                    unit=unit,
                    effective_date=config.screening_date - timedelta(days=rng.randint(1, 150)),
                )
            )
            ordinal += 1
        patients.append(
            PatientSnapshot(
                id=patient_id,
                version=_snapshot_version(dob, facts),
                date_of_birth=dob,
                facts=tuple(facts),
            )
        )
    return tuple(sorted(patients, key=lambda patient: patient.id))


def build_reference_panel(config: R6CohortConfig) -> tuple[ApprovedTrialVersion, ...]:
    """Build a frozen panel of domain-compatible approved trial versions."""

    trials: list[ApprovedTrialVersion] = []
    panel_key = f"{config.contract_version}:{config.generator_version}"
    observation_by_condition = {
        "type1_diabetes": ("hba1c", "%", Decimal("5.5"), Decimal("11.5")),
        "type2_diabetes": ("fasting_glucose", "mg/dL", Decimal("80"), Decimal("240")),
        "hypertension": ("systolic_bp", "mmHg", Decimal("105"), Decimal("190")),
        "asthma": ("hemoglobin", "g/dL", Decimal("9.5"), Decimal("17.0")),
    }
    for index in range(1, config.trial_count + 1):
        condition_index = (index - 1) % len(_CONDITIONS)
        condition = _CONDITIONS[condition_index]
        lower_age = 18 + ((index - 1) % 5) * 4
        upper_age = 80 - ((index - 1) % 4) * 3
        observation, unit, base_minimum, base_maximum = observation_by_condition[condition]
        observation_minimum = base_minimum + Decimal((index - 1) % 3)
        observation_maximum = base_maximum - Decimal((index - 1) % 2)
        excluded_medication = _MEDICATIONS[(index + condition_index) % len(_MEDICATIONS)]
        trial_id = _stable_id("reference_trial", f"{panel_key}:{index}")
        criteria = (
            Criterion(
                id=_stable_id("criterion", f"{panel_key}:{index}:1"),
                kind=CriterionKind.inclusion,
                order=1,
                source_text=f"Age is between {lower_age} and {upper_age} years.",
                expression={
                    "op": "between",
                    "fact": "demographic.age",
                    "min": lower_age,
                    "max": upper_age,
                    "unit": "year",
                },
            ),
            Criterion(
                id=_stable_id("criterion", f"{panel_key}:{index}:2"),
                kind=CriterionKind.inclusion,
                order=2,
                source_text=f"Documented {condition.replace('_', ' ')} is required.",
                expression={"op": "present", "fact": f"condition.{condition}"},
            ),
            Criterion(
                id=_stable_id("criterion", f"{panel_key}:{index}:3"),
                kind=CriterionKind.inclusion,
                order=3,
                source_text=(
                    f"{observation.replace('_', ' ')} must be between "
                    f"{observation_minimum} and {observation_maximum} {unit}."
                ),
                expression={
                    "op": "between",
                    "fact": f"observation.{observation}",
                    "min": str(observation_minimum),
                    "max": str(observation_maximum),
                    "unit": unit,
                    "selection": "latest",
                },
            ),
            Criterion(
                id=_stable_id("criterion", f"{panel_key}:{index}:4"),
                kind=CriterionKind.exclusion,
                order=4,
                source_text=(
                    f"Current {excluded_medication.replace('_', ' ')} use is excluded."
                ),
                expression={"op": "present", "fact": f"medication.{excluded_medication}"},
            ),
        )
        trials.append(
            ApprovedTrialVersion(
                id=trial_id,
                version="1",
                criteria=criteria,
                dsl_version=config.dsl_version,
            )
        )
    return tuple(sorted(trials, key=lambda trial: trial.id))


def _patient_records(patients: Sequence[PatientSnapshot]) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for index, patient in enumerate(patients, start=1):
        records.append(
            {
                "patient_snapshot_id": patient.id,
                "patient_snapshot_version": patient.version,
                "label": f"Participant {index:04d}",
                "date_of_birth": (
                    patient.date_of_birth.isoformat() if patient.date_of_birth else None
                ),
            }
        )
    return tuple(records)


def _fact_records(patients: Sequence[PatientSnapshot]) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for patient in patients:
        for fact in sorted(patient.facts, key=lambda item: item.id):
            records.append(
                {
                    "patient_snapshot_id": patient.id,
                    "fact_id": fact.id,
                    "fact_type": fact.fact_type.value,
                    "concept": fact.concept,
                    "value": str(fact.value) if fact.value is not None else None,
                    "unit": fact.unit,
                    "assertion": fact.assertion.value,
                    "temporality": fact.temporality.value,
                    "effective_date": (
                        fact.effective_date.isoformat() if fact.effective_date else None
                    ),
                    "source_label": fact.source_label,
                    "experiencer": fact.experiencer,
                }
            )
    return tuple(records)


def _reference_panel(
    config: R6CohortConfig, trials: Sequence[ApprovedTrialVersion]
) -> dict[str, object]:
    return {
        "contract_version": config.contract_version,
        "dsl_version": config.dsl_version,
        "trials": [
            {
                "trial_version_id": trial.id,
                "trial_version": trial.version,
                "order": index,
                "label": f"Reference Trial {index:02d}",
                "criteria": [
                    {
                        "criterion_id": criterion.id,
                        "kind": criterion.kind.value,
                        "order": criterion.order,
                        "required": criterion.required,
                        "criterion_family": _criterion_family(criterion),
                        "source_text": criterion.source_text,
                        "expression": dict(criterion.expression),
                    }
                    for criterion in sorted(trial.criteria, key=lambda item: (item.order, item.id))
                ],
            }
            for index, trial in enumerate(trials, start=1)
        ],
    }


def _criterion_family(criterion: Criterion) -> str:
    fact = criterion.expression.get("fact")
    if isinstance(fact, str) and "." in fact:
        family = fact.split(".", 1)[0]
        if family in {"demographic", "condition", "medication", "observation"}:
            return family
    return "compound"


def _evidence_records(items: Sequence[EvidenceReference]) -> list[dict[str, object]]:
    return [
        {
            "fact_id": item.fact_id,
            "source_label": item.source_label,
            "value": item.value,
            "unit": item.unit,
            "effective_date": item.effective_date.isoformat() if item.effective_date else None,
        }
        for item in items
    ]


def _missing_records(items: Sequence[MissingRequirement]) -> list[dict[str, object]]:
    return [
        {"fact": item.fact, "reason": item.reason.value, "detail": item.detail} for item in items
    ]


def _screening_records(
    patients: Sequence[PatientSnapshot],
    trials: Sequence[ApprovedTrialVersion],
    config: R6CohortConfig,
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    context = ScreeningContext(
        screening_date=config.screening_date,
        engine_version=config.engine_version,
        terminology_version=config.terminology_version,
        unit_version=config.unit_version,
    )
    pairs: list[dict[str, object]] = []
    criteria: list[dict[str, object]] = []
    trial_orders = {trial.id: order for order, trial in enumerate(trials, start=1)}
    criterion_families = {
        criterion.id: _criterion_family(criterion)
        for trial in trials
        for criterion in trial.criteria
    }
    for patient in patients:
        for trial in trials:
            result = screen(patient, trial, context)
            pair_id = _stable_id("screening_pair", f"{patient.id}:{trial.id}")
            pairs.append(
                {
                    "pair_id": pair_id,
                    "patient_snapshot_id": result.patient_snapshot_id,
                    "patient_snapshot_version": result.patient_snapshot_version,
                    "trial_version_id": result.trial_version_id,
                    "trial_version": result.trial_version,
                    "screening_date": result.screening_date.isoformat(),
                    "overall_state": result.overall_state.value,
                    "pass_count": result.counts[CriterionResult.pass_],
                    "fail_count": result.counts[CriterionResult.fail],
                    "unknown_count": result.counts[CriterionResult.unknown],
                    "engine_version": result.engine_version,
                    "dsl_version": result.dsl_version,
                    "terminology_version": result.terminology_version,
                    "unit_version": result.unit_version,
                }
            )
            for evaluation in result.evaluations:
                criteria.append(
                    {
                        "criterion_result_id": _stable_id(
                            "criterion_result", f"{pair_id}:{evaluation.criterion_id}"
                        ),
                        "pair_id": pair_id,
                        "patient_snapshot_id": patient.id,
                        "trial_version_id": trial.id,
                        "trial_order": trial_orders[trial.id],
                        "criterion_id": evaluation.criterion_id,
                        "criterion_kind": evaluation.criterion_kind.value,
                        "criterion_family": criterion_families[evaluation.criterion_id],
                        "criterion_order": evaluation.criterion_order,
                        "required": evaluation.required,
                        "truth": evaluation.truth.value,
                        "result": evaluation.result.value,
                        "reason_code": evaluation.reason_code.value,
                        "evidence": _evidence_records(evaluation.evidence),
                        "rejected_evidence": _evidence_records(evaluation.rejected_evidence),
                        "missing": _missing_records(evaluation.missing),
                    }
                )
    return tuple(pairs), tuple(criteria)


def materialize(config: R6CohortConfig = DEFAULT_CONFIG) -> MaterializedCohort:
    """Materialize one in-memory R6 run.  This function has no I/O or DB effects."""

    patients = build_patients(config)
    trials = build_reference_panel(config)
    patient_records = _patient_records(patients)
    patient_fact_records = _fact_records(patients)
    reference_panel = _reference_panel(config, trials)
    pairs, criterion_results = _screening_records(patients, trials, config)
    if len(pairs) != config.patient_count * config.trial_count:
        raise ValueError("R6 materialization did not evaluate every patient/trial pair")
    if len({record["patient_snapshot_id"] for record in pairs}) != config.patient_count:
        raise ValueError("R6 pair matrix did not collapse to one unique sample per patient")
    all_records = (*patient_records, *patient_fact_records, *pairs, *criterion_results)
    validate_forbidden_feature_leakage(all_records)
    checksums = {
        "patient_snapshots": semantic_checksum(patient_records),
        "patient_facts": semantic_checksum(patient_fact_records),
        "reference_panel": semantic_checksum(reference_panel),
        "criterion_order": semantic_checksum(
            [
                {"trial_version_id": trial.id, "criterion_id": item.id, "order": item.order}
                for trial in trials
                for item in trial.criteria
            ]
        ),
        "screening_pairs": semantic_checksum(pairs),
        "criterion_results": semantic_checksum(criterion_results),
    }
    checksums["cohort"] = semantic_checksum(
        {
            "patient_snapshots": checksums["patient_snapshots"],
            "patient_facts": checksums["patient_facts"],
        }
    )
    run_payload = {"config": _config_record(config), "checksums": checksums}
    run_id = f"r6-{uuid5(_NAMESPACE, _canonical_json(run_payload))}"
    if not _SAFE_RUN_ID.fullmatch(run_id):
        raise ValueError("R6 run_id must be path-safe")
    return MaterializedCohort(
        config=config,
        run_id=run_id,
        patients=patients,
        trials=trials,
        patient_records=patient_records,
        patient_fact_records=patient_fact_records,
        reference_panel=reference_panel,
        screening_pairs=pairs,
        criterion_results=criterion_results,
        semantic_checksums=checksums,
    )


def _config_record(config: R6CohortConfig) -> dict[str, object]:
    return {
        "contract_version": config.contract_version,
        "generator_version": config.generator_version,
        "seed": config.seed,
        "screening_date": config.screening_date.isoformat(),
        "patient_count": config.patient_count,
        "trial_count": config.trial_count,
        "engine_version": config.engine_version,
        "dsl_version": config.dsl_version,
        "terminology_version": config.terminology_version,
        "unit_version": config.unit_version,
    }


def write_artifacts(
    cohort: MaterializedCohort,
    output_directory: Path,
    *,
    serializer: ArtifactSerializer | None = None,
) -> dict[str, object]:
    """Write immutable R6 JSON/JSONL artifacts and return their manifest object."""

    serializer = serializer or ParquetArtifactSerializer()
    output_directory.mkdir(parents=True, exist_ok=True)
    serializer.write_records(
        output_directory / ARTIFACT_FILENAMES["patients"], cohort.patient_records
    )
    serializer.write_records(
        output_directory / ARTIFACT_FILENAMES["patient_facts"], cohort.patient_fact_records
    )
    serializer.write_object(output_directory / REFERENCE_PANEL_FILENAME, cohort.reference_panel)
    serializer.write_records(
        output_directory / ARTIFACT_FILENAMES["screening_pairs"], cohort.screening_pairs
    )
    serializer.write_records(
        output_directory / CRITERION_RESULTS_FILENAME, cohort.criterion_results
    )
    file_records = {
        "patients": {
            "path": ARTIFACT_FILENAMES["patients"],
            "record_count": len(cohort.patient_records),
        },
        "patient_facts": {
            "path": ARTIFACT_FILENAMES["patient_facts"],
            "record_count": len(cohort.patient_fact_records),
        },
        "reference_panel": {"path": REFERENCE_PANEL_FILENAME, "record_count": len(cohort.trials)},
        "screening_pairs": {
            "path": ARTIFACT_FILENAMES["screening_pairs"],
            "record_count": len(cohort.screening_pairs),
        },
        "criterion_results": {
            "path": CRITERION_RESULTS_FILENAME,
            "record_count": len(cohort.criterion_results),
        },
    }
    for record in file_records.values():
        path = output_directory / str(record["path"])
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest: dict[str, object] = {
        "run_id": cohort.run_id,
        "contract_version": cohort.config.contract_version,
        "generated_at": datetime.now(UTC).isoformat(),
        "generator_version": cohort.config.generator_version,
        "uuid_namespace": str(_NAMESPACE),
        "seed": cohort.config.seed,
        "screening_date": cohort.config.screening_date.isoformat(),
        "patient_count": len(cohort.patients),
        "trial_count": len(cohort.trials),
        "pair_count": len(cohort.screening_pairs),
        "criterion_result_count": len(cohort.criterion_results),
        "engine_version": cohort.config.engine_version,
        "dsl_version": cohort.config.dsl_version,
        "terminology_version": cohort.config.terminology_version,
        "unit_version": cohort.config.unit_version,
        "artifact_format": serializer.format_name,
        "semantic_checksums": cohort.semantic_checksums,
        "files": file_records,
    }
    serializer.write_object(output_directory / MANIFEST_FILENAME, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize the deterministic R6 cohort.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--patients", type=int, default=DEFAULT_CONFIG.patient_count)
    parser.add_argument("--trials", type=int, default=DEFAULT_CONFIG.trial_count)
    args = parser.parse_args()
    config = R6CohortConfig(patient_count=args.patients, trial_count=args.trials)
    cohort = materialize(config)
    manifest = write_artifacts(cohort, args.output)
    print(_canonical_json(manifest))


if __name__ == "__main__":
    main()
