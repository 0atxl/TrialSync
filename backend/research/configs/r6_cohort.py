"""Frozen configuration for the R6 screening-derived cohort.

The configuration deliberately contains only the inputs to deterministic cohort
materialization.  It is not a product seed, and it never opens a database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

R6_CONTRACT_VERSION = "r6-cohort-v1"
R6_GENERATOR_VERSION = "r6-materializer-v1"
R6_SCREENING_DATE = date(2026, 8, 16)
R6_SEED = 60816
R6_ENGINE_VERSION = "0.1.0"
R6_TERMINOLOGY_VERSION = "local-1"
R6_UNIT_VERSION = "units-1"


@dataclass(frozen=True, slots=True)
class R6CohortConfig:
    """Complete, serializable input boundary for one materialization run."""

    patient_count: int = 750
    trial_count: int = 20
    seed: int = R6_SEED
    screening_date: date = R6_SCREENING_DATE
    contract_version: str = R6_CONTRACT_VERSION
    generator_version: str = R6_GENERATOR_VERSION
    engine_version: str = R6_ENGINE_VERSION
    terminology_version: str = R6_TERMINOLOGY_VERSION
    unit_version: str = R6_UNIT_VERSION
    dsl_version: str = "1.0"

    def __post_init__(self) -> None:
        if self.patient_count <= 0:
            raise ValueError("patient_count must be positive")
        if self.patient_count > 750:
            raise ValueError("patient_count exceeds the frozen R6 cohort limit")
        if self.trial_count <= 0:
            raise ValueError("trial_count must be positive")
        if self.trial_count > 20:
            raise ValueError("trial_count exceeds the frozen R6 reference-panel limit")
        if not self.contract_version or not self.generator_version:
            raise ValueError("R6 configuration versions must be non-empty")
        if self.dsl_version != "1.0":
            raise ValueError("R6 reference trials require the supported DSL version 1.0")


DEFAULT_CONFIG = R6CohortConfig()
