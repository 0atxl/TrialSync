"""Artifact names and fail-closed validation for controlled recovery."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

COHORT_DIRECTORY = "cohort"
ANSWER_KEY_DIRECTORY = "answer-key"
ANALYSIS_DIRECTORY = "analysis"
EVALUATION_DIRECTORY = "evaluation"

GENERATION_CONFIG_FILENAME = "generation_config.json"
ANSWER_KEY_FILENAME = "answer_key.parquet"
GENERATION_AUDIT_FILENAME = "generation_audit.parquet"

BENCHMARK_REPRESENTATIONS = (
    "patient_fact_v1",
    "patient_fact_v2",
    "screening_profile_v1",
    "screening_profile_v2",
)

# Answer-key and generator-internal names may exist only inside answer-key artifacts and the
# post-seal evaluator. They are forbidden in every serialized analysis object.
SEALED_SOURCE_TOKENS = (
    "latent_group",
    "primary_group",
    "secondary_group",
    "is_background",
    "crossover",
    "assignment_order",
    "answer_key",
    "generator_stream",
    "random_draw",
    "residual_identifier",
    "dropout",
    "risk_prediction",
    "shap",
    "chat",
    "rag",
)


def validate_label_free_payload(value: object, *, location: str = "payload") -> None:
    """Reject sealed-source names recursively from analysis-bound data."""

    def visit(item: object, path: str) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                if not isinstance(key, str):
                    raise ValueError(f"controlled-recovery field at {path} is not text")
                normalized = key.casefold().replace("-", "_").replace(" ", "_")
                if any(token in normalized for token in SEALED_SOURCE_TOKENS):
                    raise ValueError(f"sealed controlled-recovery source at {path}.{key}")
                visit(nested, f"{path}.{key}")
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for index, nested in enumerate(item):
                visit(nested, f"{path}[{index}]")
        elif isinstance(item, str):
            normalized = item.casefold().replace("-", "_").replace(" ", "_")
            if any(token in normalized for token in SEALED_SOURCE_TOKENS):
                raise ValueError(f"sealed controlled-recovery value at {path}")

    visit(value, location)
