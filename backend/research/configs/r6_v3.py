"""Configuration for the R6 V3 controlled-group cohort."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Final
from uuid import NAMESPACE_URL, uuid5

from .r6_cohort import (
    R6_ENGINE_VERSION,
    R6_SCREENING_DATE,
    R6_TERMINOLOGY_VERSION,
    R6_UNIT_VERSION,
)

V3_CONTRACT_VERSION: Final = "r6-cohort-v3"
V3_GENERATOR_VERSION: Final = "r6-controlled-groups-v3.1"
V3_SEED: Final = 60818
V3_UUID_NAMESPACE: Final = uuid5(NAMESPACE_URL, "trialsync:r6:controlled-groups:v3")
V3_BACKGROUND_GROUP: Final = "healthy_borderline"

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

OBSERVATION_BOUNDS: Final[dict[str, tuple[str, float, float]]] = {
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


@dataclass(frozen=True, slots=True)
class PatientGroup:
    name: str
    target_count: int
    age_min: int
    age_max: int
    condition_probabilities: dict[str, float]
    medication_probabilities: dict[str, float]
    observation_centers: dict[str, float]
    observation_spreads: dict[str, float]


PATIENT_GROUPS: Final[tuple[PatientGroup, ...]] = (
    PatientGroup(
        name="young_t1d",
        target_count=160,
        age_min=18,
        age_max=32,
        condition_probabilities={
            "type1_diabetes": 1.0,
            "type2_diabetes": 0.0,
            "hypertension": 0.0,
            "asthma": 0.0,
        },
        medication_probabilities={
            "metformin": 0.0,
            "atorvastatin": 0.0,
            "insulin": 1.0,
            "semaglutide": 0.0,
        },
        observation_centers={
            "hba1c": 8.8,
            "fasting_glucose": 165.0,
            "egfr": 118.0,
            "creatinine": 0.65,
            "hemoglobin": 14.8,
            "platelets": 260.0,
            "bmi": 19.5,
            "systolic_bp": 112.0,
            "diastolic_bp": 70.0,
            "potassium": 4.6,
        },
        observation_spreads={
            "hba1c": 0.2,
            "fasting_glucose": 5.0,
            "egfr": 3.0,
            "creatinine": 0.03,
            "hemoglobin": 0.3,
            "platelets": 15.0,
            "bmi": 0.7,
            "systolic_bp": 3.0,
            "diastolic_bp": 2.0,
            "potassium": 0.12,
        },
    ),
    PatientGroup(
        name="elderly_t2d",
        target_count=160,
        age_min=55,
        age_max=78,
        condition_probabilities={
            "type1_diabetes": 0.0,
            "type2_diabetes": 1.0,
            "hypertension": 0.0,
            "asthma": 0.0,
        },
        medication_probabilities={
            "metformin": 1.0,
            "atorvastatin": 0.95,
            "insulin": 0.0,
            "semaglutide": 0.85,
        },
        observation_centers={
            "hba1c": 9.8,
            "fasting_glucose": 215.0,
            "egfr": 78.0,
            "creatinine": 1.05,
            "hemoglobin": 13.2,
            "platelets": 240.0,
            "bmi": 36.0,
            "systolic_bp": 138.0,
            "diastolic_bp": 84.0,
            "potassium": 4.3,
        },
        observation_spreads={
            "hba1c": 0.25,
            "fasting_glucose": 6.0,
            "egfr": 3.0,
            "creatinine": 0.04,
            "hemoglobin": 0.3,
            "platelets": 15.0,
            "bmi": 0.9,
            "systolic_bp": 3.0,
            "diastolic_bp": 2.0,
            "potassium": 0.12,
        },
    ),
    PatientGroup(
        name="hypertensive_renal",
        target_count=160,
        age_min=50,
        age_max=74,
        condition_probabilities={
            "type1_diabetes": 0.0,
            "type2_diabetes": 0.0,
            "hypertension": 1.0,
            "asthma": 0.0,
        },
        medication_probabilities={
            "metformin": 0.0,
            "atorvastatin": 0.85,
            "insulin": 0.0,
            "semaglutide": 0.0,
        },
        observation_centers={
            "hba1c": 5.1,
            "fasting_glucose": 90.0,
            "egfr": 25.0,
            "creatinine": 2.50,
            "hemoglobin": 11.2,
            "platelets": 200.0,
            "bmi": 27.5,
            "systolic_bp": 178.0,
            "diastolic_bp": 102.0,
            "potassium": 5.2,
        },
        observation_spreads={
            "hba1c": 0.15,
            "fasting_glucose": 4.0,
            "egfr": 2.5,
            "creatinine": 0.06,
            "hemoglobin": 0.3,
            "platelets": 15.0,
            "bmi": 0.8,
            "systolic_bp": 3.5,
            "diastolic_bp": 2.0,
            "potassium": 0.12,
        },
    ),
    PatientGroup(
        name="respiratory_asthma",
        target_count=160,
        age_min=30,
        age_max=52,
        condition_probabilities={
            "type1_diabetes": 0.0,
            "type2_diabetes": 0.0,
            "hypertension": 0.0,
            "asthma": 1.0,
        },
        medication_probabilities={
            "metformin": 0.0,
            "atorvastatin": 0.0,
            "insulin": 0.0,
            "semaglutide": 0.0,
        },
        observation_centers={
            "hba1c": 5.1,
            "fasting_glucose": 88.0,
            "egfr": 110.0,
            "creatinine": 0.68,
            "hemoglobin": 14.5,
            "platelets": 360.0,
            "bmi": 24.5,
            "systolic_bp": 115.0,
            "diastolic_bp": 72.0,
            "potassium": 4.1,
        },
        observation_spreads={
            "hba1c": 0.15,
            "fasting_glucose": 4.0,
            "egfr": 2.5,
            "creatinine": 0.03,
            "hemoglobin": 0.3,
            "platelets": 15.0,
            "bmi": 0.8,
            "systolic_bp": 3.0,
            "diastolic_bp": 2.0,
            "potassium": 0.10,
        },
    ),
    PatientGroup(
        name="healthy_borderline",
        target_count=110,
        age_min=18,
        age_max=82,
        condition_probabilities={
            "type1_diabetes": 0.05,
            "type2_diabetes": 0.15,
            "hypertension": 0.20,
            "asthma": 0.15,
        },
        medication_probabilities={
            "metformin": 0.08,
            "atorvastatin": 0.15,
            "insulin": 0.03,
            "semaglutide": 0.03,
        },
        observation_centers={
            "hba1c": 5.4,
            "fasting_glucose": 95.0,
            "egfr": 92.0,
            "creatinine": 0.90,
            "hemoglobin": 13.8,
            "platelets": 240.0,
            "bmi": 26.0,
            "systolic_bp": 122.0,
            "diastolic_bp": 76.0,
            "potassium": 4.3,
        },
        observation_spreads={
            "hba1c": 1.2,
            "fasting_glucose": 25.0,
            "egfr": 18.0,
            "creatinine": 0.25,
            "hemoglobin": 1.5,
            "platelets": 60.0,
            "bmi": 4.5,
            "systolic_bp": 15.0,
            "diastolic_bp": 10.0,
            "potassium": 0.50,
        },
    ),
)


@dataclass(frozen=True, slots=True)
class R6V3Config:
    patient_count: int = 750
    trial_count: int = 20
    seed: int = V3_SEED
    screening_date: date = R6_SCREENING_DATE
    contract_version: str = V3_CONTRACT_VERSION
    generator_version: str = V3_GENERATOR_VERSION
    engine_version: str = R6_ENGINE_VERSION
    terminology_version: str = R6_TERMINOLOGY_VERSION
    unit_version: str = R6_UNIT_VERSION
    dsl_version: str = "1.0"
    patient_groups: tuple[PatientGroup, ...] = PATIENT_GROUPS

    def __post_init__(self) -> None:
        if self.patient_count <= 0:
            raise ValueError("patient_count must be positive")
        if self.patient_count > 750:
            raise ValueError("patient_count exceeds 750 limit")
        if self.trial_count <= 0:
            raise ValueError("trial_count must be positive")
        if self.trial_count > 20:
            raise ValueError("trial_count exceeds 20 limit")
        sum_target_counts = sum(group.target_count for group in self.patient_groups)
        if sum_target_counts != self.patient_count:
            raise ValueError(
                f"Sum of patient-group target_counts ({sum_target_counts}) "
                f"must equal patient_count ({self.patient_count})"
            )
        names = [item.name for item in self.patient_groups]
        if len(set(names)) != len(names):
            raise ValueError("patient-group names must be unique")
        expected_conditions = set(CONDITIONS)
        expected_medications = set(MEDICATIONS)
        expected_observations = set(OBSERVATIONS)
        for item in self.patient_groups:
            if item.target_count <= 0 or item.age_min < 18 or item.age_max < item.age_min:
                raise ValueError(f"invalid population bounds for {item.name}")
            if set(item.condition_probabilities) != expected_conditions:
                raise ValueError(f"condition contract mismatch for {item.name}")
            if set(item.medication_probabilities) != expected_medications:
                raise ValueError(f"medication contract mismatch for {item.name}")
            if set(item.observation_centers) != expected_observations:
                raise ValueError(f"observation-center contract mismatch for {item.name}")
            if set(item.observation_spreads) != expected_observations:
                raise ValueError(f"observation-spread contract mismatch for {item.name}")
            probabilities = (
                *item.condition_probabilities.values(),
                *item.medication_probabilities.values(),
            )
            if any(value < 0.0 or value > 1.0 for value in probabilities):
                raise ValueError(f"probability outside [0, 1] for {item.name}")
            if any(value <= 0.0 for value in item.observation_spreads.values()):
                raise ValueError(f"observation spread must be positive for {item.name}")

    def contract_payload(self) -> dict[str, object]:
        """Return the complete order-significant generation contract."""

        return {
            "patient_count": self.patient_count,
            "trial_count": self.trial_count,
            "seed": self.seed,
            "screening_date": self.screening_date.isoformat(),
            "contract_version": self.contract_version,
            "generator_version": self.generator_version,
            "engine_version": self.engine_version,
            "terminology_version": self.terminology_version,
            "unit_version": self.unit_version,
            "dsl_version": self.dsl_version,
            "uuid_namespace": str(V3_UUID_NAMESPACE),
            "patient_groups": [asdict(item) for item in self.patient_groups],
            "encounter_policy": {
                "offset_days_min": 14,
                "offset_days_max": 45,
                "fact_jitter_days_min": 0,
                "fact_jitter_days_max": 2,
            },
            "missingness_policy": {
                "structured_status_skip": 0.01,
                "structured_status_unknown": 0.01,
                "structured_observation_skip": 0.01,
                "structured_observation_unknown": 0.01,
                "background_status_skip": 0.08,
                "background_status_unknown": 0.06,
                "background_observation_skip": 0.10,
                "background_observation_unknown": 0.05,
            },
        }


DEFAULT_V3_CONFIG = R6V3Config()
