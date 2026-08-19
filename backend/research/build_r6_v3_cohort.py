"""Materialize the controlled-group R6 V3 cohort."""

from __future__ import annotations

import argparse
import hashlib
import random
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid5

from research.build_r6_cohort import (
    ParquetArtifactSerializer,
    _fact_records,
    _patient_records,
    _reference_panel,
    _screening_records,
    _snapshot_version,
    build_reference_panel,
)
from research.configs.r6_cohort import R6CohortConfig
from research.configs.r6_v3 import (
    CONDITIONS,
    DEFAULT_V3_CONFIG,
    MEDICATIONS,
    OBSERVATION_BOUNDS,
    OBSERVATIONS,
    V3_BACKGROUND_GROUP,
    V3_UUID_NAMESPACE,
    R6V3Config,
)
from research.schemas.r6_dataset import (
    ARTIFACT_FILENAMES,
    CRITERION_RESULTS_FILENAME,
    MANIFEST_FILENAME,
    REFERENCE_PANEL_FILENAME,
    canonical_json,
    semantic_checksum,
    validate_forbidden_feature_leakage,
)
from research.schemas.r6_v3 import (
    ANSWER_KEY_FILENAME,
    GENERATION_CONFIG_FILENAME,
    PRIVATE_DIRECTORY,
    PRIVATE_MANIFEST_FILENAME,
    V3_ANSWER_KEY_VERSION,
    validate_private_source_absent,
)
from trialsync.domain import (
    ApprovedTrialVersion,
    Assertion,
    Fact,
    FactType,
    PatientSnapshot,
    Temporality,
)

_SAFE_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True, slots=True)
class MaterializedV3Cohort:
    config: R6V3Config
    run_id: str
    patients: tuple[PatientSnapshot, ...]
    trials: tuple[ApprovedTrialVersion, ...]
    patient_records: tuple[dict[str, object], ...]
    patient_fact_records: tuple[dict[str, object], ...]
    reference_panel: dict[str, object]
    screening_pairs: tuple[dict[str, object], ...]
    criterion_results: tuple[dict[str, object], ...]
    semantic_checksums: dict[str, str]
    implementation_checksums: dict[str, str]


def _stable_id(kind: str, value: object) -> str:
    return str(uuid5(V3_UUID_NAMESPACE, f"{kind}:{value}"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _implementation_checksums() -> dict[str, str]:
    research_directory = Path(__file__).resolve().parent
    source_root = research_directory.parent / "src" / "trialsync" / "research"
    paths = {
        "v3_generator": Path(__file__).resolve(),
        "v3_config": research_directory / "configs" / "r6_v3.py",
        "materializer": research_directory / "build_r6_cohort.py",
        "analysis": research_directory / "analyze_r6_cohort.py",
        "feature_builder": source_root / "cohort_profiles" / "features.py",
        "dbscan": source_root / "cohorts" / "dbscan.py",
        "similarity": source_root / "similarity" / "index.py",
    }
    return {name: _sha256(path) for name, path in paths.items()}


def _sealed_timestamp(screening_date: date) -> str:
    return datetime.combine(screening_date, time.min, tzinfo=UTC).isoformat()


def _answer_key_payload(
    assignments: dict[str, str],
) -> dict[str, object]:
    return {
        "answer_key_version": V3_ANSWER_KEY_VERSION,
        "members": [
            {"patient_snapshot_id": patient_id, "cohort_group": group}
            for patient_id, group in sorted(assignments.items())
        ],
    }


def _make_fact(
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


def build_patients_v3(
    config: R6V3Config,
) -> tuple[tuple[PatientSnapshot, ...], dict[str, str]]:
    rng = random.Random(config.seed)

    assignment_list = []
    for group in config.patient_groups:
        assignment_list.extend([group] * group.target_count)

    rng.shuffle(assignment_list)

    patients = []
    group_assignments = {}

    cohort_key = (
        f"{config.contract_version}:{config.generator_version}:"
        f"{config.seed}:{config.screening_date.isoformat()}"
    )

    for index, group in enumerate(assignment_list, start=1):
        patient_id = _stable_id("patient_snapshot", f"{cohort_key}:{index}")
        group_assignments[patient_id] = group.name

        age = rng.randint(group.age_min, group.age_max)
        # V3 uses binary sex (no "unspecified") to ensure every patient has a
        # demographic fact, reducing within-group feature variance for this
        # controlled recovery case.
        sex = rng.choice(("female", "male"))

        birthday_offset = rng.randint(0, 364)
        dob = config.screening_date.replace(
            year=config.screening_date.year - age, month=1, day=1
        ) - timedelta(days=birthday_offset)

        # Encounter cohesion: clinically realistic encounter date for patient facts
        encounter_offset = rng.randint(14, 45)
        base_date = config.screening_date - timedelta(days=encounter_offset)

        facts = []
        ordinal = 1

        facts.append(
            _make_fact(
                patient_id,
                ordinal,
                FactType.demographic,
                sex,
                value=sex,
                effective_date=config.screening_date,
            )
        )
        ordinal += 1

        is_noise = group.name == V3_BACKGROUND_GROUP

        # Missingness rates: structured groups use 1% skip / 1% unknown to
        # maintain near-complete clinical panels. The background group uses
        # 8% skip / 6% unknown, matching V1 rates, so
        # DBSCAN correctly classifies it as density-sparse background.
        for condition in CONDITIONS:
            prob = group.condition_probabilities[condition]
            skip_prob = 0.08 if is_noise else 0.01
            unk_prob = 0.06 if is_noise else 0.01

            draw = rng.random()
            if draw < skip_prob:
                continue

            assertion = (
                Assertion.unknown
                if draw < (skip_prob + unk_prob)
                else (Assertion.present if rng.random() < prob else Assertion.absent)
            )
            eff_date = base_date - timedelta(days=rng.randint(0, 2))

            facts.append(
                _make_fact(
                    patient_id,
                    ordinal,
                    FactType.condition,
                    condition,
                    assertion=assertion,
                    effective_date=eff_date,
                )
            )
            ordinal += 1

        for medication in MEDICATIONS:
            prob = group.medication_probabilities[medication]
            skip_prob = 0.08 if is_noise else 0.01
            unk_prob = 0.06 if is_noise else 0.01

            draw = rng.random()
            if draw < skip_prob:
                continue

            assertion = (
                Assertion.unknown
                if draw < (skip_prob + unk_prob)
                else (Assertion.present if rng.random() < prob else Assertion.absent)
            )
            eff_date = base_date - timedelta(days=rng.randint(0, 2))

            facts.append(
                _make_fact(
                    patient_id,
                    ordinal,
                    FactType.medication,
                    medication,
                    assertion=assertion,
                    effective_date=eff_date,
                )
            )
            ordinal += 1

        for obs in OBSERVATIONS:
            skip_prob = 0.10 if is_noise else 0.01
            unk_prob = 0.05 if is_noise else 0.01

            draw = rng.random()
            if draw < skip_prob:
                continue

            unit, minimum, maximum = OBSERVATION_BOUNDS[obs]
            eff_date = base_date - timedelta(days=rng.randint(0, 2))

            if draw < (skip_prob + unk_prob):
                facts.append(
                    _make_fact(
                        patient_id,
                        ordinal,
                        FactType.observation,
                        obs,
                        unit=unit,
                        assertion=Assertion.unknown,
                        effective_date=eff_date,
                    )
                )
                ordinal += 1
                continue

            sampled = rng.gauss(
                group.observation_centers[obs], group.observation_spreads[obs]
            )
            clamped = min(max(sampled, minimum), maximum)
            value = Decimal(str(round(clamped, 2)))

            facts.append(
                _make_fact(
                    patient_id,
                    ordinal,
                    FactType.observation,
                    obs,
                    value=value,
                    unit=unit,
                    assertion=Assertion.present,
                    effective_date=eff_date,
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

    patients.sort(key=lambda p: p.id)
    return tuple(patients), group_assignments


def materialize_v3(
    config: R6V3Config = DEFAULT_V3_CONFIG,
) -> tuple[MaterializedV3Cohort, dict[str, str]]:
    patients, group_assignments = build_patients_v3(config)

    r6_config = R6CohortConfig(
        trial_count=config.trial_count,
        screening_date=config.screening_date,
        engine_version=config.engine_version,
        terminology_version=config.terminology_version,
        unit_version=config.unit_version,
        dsl_version=config.dsl_version,
    )

    trials = build_reference_panel(r6_config)
    patient_records = _patient_records(patients)
    patient_fact_records = _fact_records(patients)
    reference_panel = _reference_panel(r6_config, trials)

    pairs, criterion_results = _screening_records(patients, trials, r6_config)

    if len(pairs) != config.patient_count * config.trial_count:
        raise ValueError("R6 V3 materialization did not evaluate every patient/trial pair")
    if len({record["patient_snapshot_id"] for record in pairs}) != config.patient_count:
        raise ValueError("R6 V3 pair matrix did not collapse to one unique sample per patient")

    all_records = (*patient_records, *patient_fact_records, *pairs, *criterion_results)
    validate_forbidden_feature_leakage(all_records)
    validate_private_source_absent(all_records)

    generation_config = config.contract_payload()
    answer_key = _answer_key_payload(group_assignments)

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
        "generation_config": semantic_checksum(generation_config),
        "answer_key": semantic_checksum(answer_key),
    }
    checksums["cohort"] = semantic_checksum(
        {
            "patient_snapshots": checksums["patient_snapshots"],
            "patient_facts": checksums["patient_facts"],
        }
    )

    run_payload = {
        "config": generation_config,
        "checksums": checksums,
    }
    run_id = f"r6-v3-{uuid5(V3_UUID_NAMESPACE, canonical_json(run_payload))}"
    if not _SAFE_RUN_ID.fullmatch(run_id):
        raise ValueError("R6 V3 run_id must be path-safe")

    cohort = MaterializedV3Cohort(
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
        implementation_checksums=_implementation_checksums(),
    )

    return cohort, group_assignments


def write_artifacts_v3(
    cohort: MaterializedV3Cohort,
    output_directory: Path,
    group_assignments: dict[str, str],
    *,
    serializer: ParquetArtifactSerializer | None = None,
) -> dict[str, object]:
    serializer = serializer or ParquetArtifactSerializer()
    if output_directory.exists():
        raise FileExistsError(f"R6 V3 run directory already exists: {output_directory}")
    output_directory.mkdir(parents=True)
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
    generation_config = cohort.config.contract_payload()
    serializer.write_object(
        output_directory / GENERATION_CONFIG_FILENAME,
        generation_config,
    )

    private_directory = output_directory / PRIVATE_DIRECTORY
    private_directory.mkdir()
    answer_key = _answer_key_payload(group_assignments)
    answer_key_path = private_directory / ANSWER_KEY_FILENAME
    serializer.write_object(answer_key_path, answer_key)
    private_manifest: dict[str, object] = {
        "run_id": cohort.run_id,
        "contract_version": V3_ANSWER_KEY_VERSION,
        "sealed_at": _sealed_timestamp(cohort.config.screening_date),
        "cohort_semantic_checksum": cohort.semantic_checksums["cohort"],
        "generation_config_semantic_checksum": cohort.semantic_checksums[
            "generation_config"
        ],
        "answer_key_semantic_checksum": cohort.semantic_checksums["answer_key"],
        "member_count": len(group_assignments),
        "group_counts": dict(sorted(Counter(group_assignments.values()).items())),
        "files": {
            "answer_key": {
                "path": ANSWER_KEY_FILENAME,
                "sha256": _sha256(answer_key_path),
            }
        },
    }
    private_manifest_path = private_directory / PRIVATE_MANIFEST_FILENAME
    serializer.write_object(private_manifest_path, private_manifest)

    file_records: dict[str, dict[str, object]] = {
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
        "generation_config": {
            "path": GENERATION_CONFIG_FILENAME,
        },
    }
    for record in file_records.values():
        path = output_directory / str(record["path"])
        record["sha256"] = _sha256(path)

    manifest: dict[str, object] = {
        "run_id": cohort.run_id,
        "contract_version": cohort.config.contract_version,
        "generated_at": _sealed_timestamp(cohort.config.screening_date),
        "generator_version": cohort.config.generator_version,
        "uuid_namespace": str(V3_UUID_NAMESPACE),
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
        "implementation_checksums": cohort.implementation_checksums,
        "answer_key_manifest_sha256": _sha256(private_manifest_path),
        "files": file_records,
    }
    serializer.write_object(output_directory / MANIFEST_FILENAME, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize the controlled-group R6 V3 cohort.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--patients", type=int, default=DEFAULT_V3_CONFIG.patient_count)
    parser.add_argument("--trials", type=int, default=DEFAULT_V3_CONFIG.trial_count)
    args = parser.parse_args()
    config = R6V3Config(patient_count=args.patients, trial_count=args.trials)
    cohort, assignments = materialize_v3(config)
    manifest = write_artifacts_v3(cohort, args.output, assignments)
    print(canonical_json(manifest))


if __name__ == "__main__":
    main()
