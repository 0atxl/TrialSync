"""Sealed artifact contract for the R6 V3 cohort transfer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

GENERATION_CONFIG_FILENAME = "generation_config.json"
PRIVATE_DIRECTORY = "private"
ANSWER_KEY_FILENAME = "answer_key.json"
PRIVATE_MANIFEST_FILENAME = "manifest.json"
EVALUATION_DIRECTORY = "evaluation"
EVALUATION_REPORT_FILENAME = "report.json"
EVALUATION_MANIFEST_FILENAME = "manifest.json"

V3_ANSWER_KEY_VERSION = "r6-v3-answer-key-v1"
V3_EVALUATION_VERSION = "r6-v3-evaluation-v1"

# These names may exist in the generator configuration, private answer key, and post-analysis
# evaluator. They must never enter patient records, screening records, representations, indexes,
# runtime member payloads, or cluster reports.
PRIVATE_SOURCE_TOKENS = (
    "patient_group",
    "cohort_group",
    "answer_key",
    "generator_assignment",
)


def validate_private_source_absent(value: object, *, location: str = "payload") -> None:
    """Reject private V3 source names recursively from analysis-bound values."""

    def visit(item: object, path: str) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                if not isinstance(key, str):
                    raise ValueError(f"R6 V3 field at {path} is not text")
                normalized = key.casefold().replace("-", "_").replace(" ", "_")
                if any(token in normalized for token in PRIVATE_SOURCE_TOKENS):
                    raise ValueError(f"private R6 V3 source at {path}.{key}")
                visit(nested, f"{path}.{key}")
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for index, nested in enumerate(item):
                visit(nested, f"{path}[{index}]")
        elif isinstance(item, str):
            normalized = item.casefold().replace("-", "_").replace(" ", "_")
            if any(token in normalized for token in PRIVATE_SOURCE_TOKENS):
                raise ValueError(f"private R6 V3 value at {path}")

    visit(value, location)
