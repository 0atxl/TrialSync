"""Frozen configuration for the one-run R6 controlled-recovery benchmark."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Final
from uuid import NAMESPACE_URL, uuid5

from .r6_cohort import (
    R6_ENGINE_VERSION,
    R6_SCREENING_DATE,
    R6_TERMINOLOGY_VERSION,
    R6_UNIT_VERSION,
)

RECOVERY_CONTRACT_VERSION: Final = "r6-controlled-recovery-v1"
RECOVERY_GENERATOR_VERSION: Final = "r6-controlled-recovery-generator-v1"
RECOVERY_ANSWER_KEY_VERSION: Final = "r6-controlled-recovery-answer-key-v1"
RECOVERY_EVALUATION_VERSION: Final = "r6-controlled-recovery-evaluation-v1"
RECOVERY_ANALYSIS_VERSION: Final = "r6-controlled-recovery-analysis-v1"
RECOVERY_SEED: Final = 60817
RECOVERY_UUID_NAMESPACE: Final = uuid5(NAMESPACE_URL, "trialsync:r6:controlled-recovery:v1")

STRUCTURED_GROUPS: Final = (
    "latent_group_01",
    "latent_group_02",
    "latent_group_03",
    "latent_group_04",
)
BACKGROUND_GROUP: Final = "background"
ALL_GROUPS: Final = (*STRUCTURED_GROUPS, BACKGROUND_GROUP)

CONDITIONS: Final = (
    "type1_diabetes",
    "type2_diabetes",
    "hypertension",
    "asthma",
)
MEDICATIONS: Final = ("metformin", "atorvastatin", "insulin", "semaglutide")
OBSERVATIONS: Final = (
    "hba1c",
    "fasting_glucose",
    "egfr",
    "creatinine",
    "hemoglobin",
    "platelets",
    "bmi",
    "systolic_bp",
    "diastolic_bp",
    "potassium",
)

RNG_STREAM_CODES: Final = {
    "assignment_shuffle": 101,
    "demographics": 201,
    "condition_truth": 301,
    "medication_truth": 401,
    "observation_values": 501,
    "missing_unknown": 601,
    "evidence_dates": 701,
    "background_variation": 801,
    "crossover_selection": 901,
    "crossover_secondary": 902,
}

AGE_PARAMETERS: Final[dict[str, dict[str, str | int]]] = {
    "latent_group_01": {
        "distribution": "truncated_normal",
        "mean": 58,
        "sd": 11,
        "min": 32,
        "max": 82,
    },
    "latent_group_02": {
        "distribution": "truncated_normal",
        "mean": 64,
        "sd": 10,
        "min": 38,
        "max": 82,
    },
    "latent_group_03": {
        "distribution": "truncated_normal",
        "mean": 38,
        "sd": 13,
        "min": 18,
        "max": 70,
    },
    "latent_group_04": {
        "distribution": "truncated_normal",
        "mean": 31,
        "sd": 10,
        "min": 18,
        "max": 58,
    },
    "background": {"distribution": "discrete_uniform", "min": 18, "max": 82},
}

CONDITION_PROBABILITIES: Final[dict[str, tuple[float, float, float, float]]] = {
    "latent_group_01": (0.02, 0.82, 0.48, 0.14),
    "latent_group_02": (0.03, 0.28, 0.86, 0.12),
    "latent_group_03": (0.04, 0.12, 0.18, 0.84),
    "latent_group_04": (0.84, 0.02, 0.18, 0.14),
    "background": (0.12, 0.25, 0.38, 0.24),
}

OBSERVATION_PARAMETERS: Final[dict[str, dict[str, str | float]]] = {
    "hba1c": {"unit": "%", "spread": 1.0, "min": 4.5, "max": 12.5},
    "fasting_glucose": {
        "unit": "mg/dL",
        "spread": 26.0,
        "min": 65.0,
        "max": 280.0,
    },
    "egfr": {
        "unit": "mL/min/1.73m2",
        "spread": 13.0,
        "min": 25.0,
        "max": 125.0,
    },
    "creatinine": {
        "unit": "mg/dL",
        "spread": 0.22,
        "min": 0.5,
        "max": 2.8,
    },
    "hemoglobin": {
        "unit": "g/dL",
        "spread": 1.25,
        "min": 8.5,
        "max": 17.5,
    },
    "platelets": {
        "unit": "10^9/L",
        "spread": 58.0,
        "min": 90.0,
        "max": 520.0,
    },
    "bmi": {"unit": "kg/m2", "spread": 3.8, "min": 16.0, "max": 48.0},
    "systolic_bp": {
        "unit": "mmHg",
        "spread": 13.0,
        "min": 85.0,
        "max": 210.0,
    },
    "diastolic_bp": {
        "unit": "mmHg",
        "spread": 8.5,
        "min": 50.0,
        "max": 125.0,
    },
    "potassium": {
        "unit": "mmol/L",
        "spread": 0.42,
        "min": 2.8,
        "max": 6.2,
    },
}

GROUP_RESIDUALS: Final[dict[str, dict[str, float]]] = {
    "latent_group_01": {"hba1c": 0.4, "fasting_glucose": 15.0, "bmi": 2.0, "egfr": -5.0},
    "latent_group_02": {
        "systolic_bp": 10.0,
        "diastolic_bp": 6.0,
        "egfr": -12.0,
        "creatinine": 0.20,
    },
    "latent_group_03": {},
    "latent_group_04": {"hba1c": 0.5, "fasting_glucose": 18.0, "bmi": -1.5},
}


@dataclass(frozen=True, slots=True)
class R6RecoveryConfig:
    """Complete predeclared generation boundary; overrides exist only for small tests."""

    seed: int = RECOVERY_SEED
    screening_date: date = R6_SCREENING_DATE
    group_counts: tuple[int, int, int, int] = (210, 180, 150, 120)
    background_count: int = 90
    crossover_counts: tuple[int, int, int, int] = (25, 22, 18, 14)
    trial_count: int = 20
    contract_version: str = RECOVERY_CONTRACT_VERSION
    generator_version: str = RECOVERY_GENERATOR_VERSION
    answer_key_version: str = RECOVERY_ANSWER_KEY_VERSION
    analysis_version: str = RECOVERY_ANALYSIS_VERSION
    evaluation_version: str = RECOVERY_EVALUATION_VERSION
    engine_version: str = R6_ENGINE_VERSION
    dsl_version: str = "1.0"
    terminology_version: str = R6_TERMINOLOGY_VERSION
    unit_version: str = R6_UNIT_VERSION
    numpy_rng: str = "Generator(PCG64)"
    stream_codes: dict[str, int] = field(default_factory=lambda: dict(RNG_STREAM_CODES))

    def __post_init__(self) -> None:
        if any(count <= 0 for count in self.group_counts) or self.background_count <= 0:
            raise ValueError("controlled-recovery group counts must be positive")
        if len(self.group_counts) != 4 or len(self.crossover_counts) != 4:
            raise ValueError("controlled-recovery requires exactly four structured groups")
        if any(value < 0 for value in self.crossover_counts):
            raise ValueError("crossover counts cannot be negative")
        if any(
            crossovers > members
            for crossovers, members in zip(self.crossover_counts, self.group_counts, strict=True)
        ):
            raise ValueError("crossover count exceeds its structured group")
        if not 1 <= self.trial_count <= 20:
            raise ValueError("trial_count must be in [1, 20]")
        if set(self.stream_codes) != set(RNG_STREAM_CODES):
            raise ValueError("controlled-recovery RNG stream table is incomplete")
        if len(set(self.stream_codes.values())) != len(self.stream_codes):
            raise ValueError("controlled-recovery RNG stream codes must be unique")

    @property
    def patient_count(self) -> int:
        return sum(self.group_counts) + self.background_count


DEFAULT_RECOVERY_CONFIG = R6RecoveryConfig()
