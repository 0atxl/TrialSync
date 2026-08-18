"""Versioned R6 patient-fact and screening-profile representations."""

from .contracts import (
    R6CriterionResultRecord,
    R6FactRecord,
    R6PatientRecord,
    RepresentationArtifact,
    RepresentationContext,
)
from .features import build_patient_fact_representation, build_screening_profile_representation
from .v2 import (
    build_patient_fact_representation_v2,
    build_screening_profile_representation_v2,
)

__all__ = [
    "R6CriterionResultRecord",
    "R6FactRecord",
    "R6PatientRecord",
    "RepresentationArtifact",
    "RepresentationContext",
    "build_patient_fact_representation",
    "build_patient_fact_representation_v2",
    "build_screening_profile_representation",
    "build_screening_profile_representation_v2",
]
