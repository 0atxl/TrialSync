"""Schema and leakage contract for R6 materialization artifacts."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from hashlib import sha256
from typing import Any

R6_ARTIFACT_FORMAT = "parquet-v1"
MANIFEST_FILENAME = "manifest.json"
PATIENTS_FILENAME = "patients.parquet"
PATIENT_FACTS_FILENAME = "patient_facts.parquet"
REFERENCE_PANEL_FILENAME = "reference_panel.json"
SCREENING_PAIRS_FILENAME = "screening_pairs.parquet"
CRITERION_RESULTS_FILENAME = "criterion_results.parquet"

ARTIFACT_FILENAMES = {
    "patients": PATIENTS_FILENAME,
    "patient_facts": PATIENT_FACTS_FILENAME,
    "reference_panel": REFERENCE_PANEL_FILENAME,
    "screening_pairs": SCREENING_PAIRS_FILENAME,
    "criterion_results": CRITERION_RESULTS_FILENAME,
}

PATIENT_COLUMNS = ("patient_snapshot_id", "patient_snapshot_version", "label", "date_of_birth")
PATIENT_FACT_COLUMNS = (
    "patient_snapshot_id",
    "fact_id",
    "fact_type",
    "concept",
    "value",
    "unit",
    "assertion",
    "temporality",
    "effective_date",
    "source_label",
    "experiencer",
)
SCREENING_PAIR_COLUMNS = (
    "pair_id",
    "patient_snapshot_id",
    "patient_snapshot_version",
    "trial_version_id",
    "trial_version",
    "screening_date",
    "overall_state",
    "pass_count",
    "fail_count",
    "unknown_count",
    "engine_version",
    "dsl_version",
    "terminology_version",
    "unit_version",
)
CRITERION_RESULT_COLUMNS = (
    "criterion_result_id",
    "pair_id",
    "patient_snapshot_id",
    "trial_version_id",
    "trial_order",
    "criterion_id",
    "criterion_kind",
    "criterion_family",
    "criterion_order",
    "required",
    "truth",
    "result",
    "reason_code",
    "evidence",
    "rejected_evidence",
    "missing",
)

# These names are prohibited anywhere in a materialized R6 record.  The
# guard applies to field names rather than natural-language criterion text.
FORBIDDEN_FEATURE_TOKENS = (
    "dropout",
    "outcome",
    "risk",
    "shap",
    "hidden_generator",
    "chat",
    "rag",
    "llm",
    "prediction",
)


def canonical_json(value: object) -> str:
    """Canonical semantic encoding independent of JSON whitespace or file order."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def semantic_checksum(records: Iterable[Mapping[str, Any]] | Mapping[str, Any]) -> str:
    """Checksum canonical sorted records, not a serializer's bytes or metadata."""

    if isinstance(records, Mapping):
        payload: object = records
    else:
        payload = sorted((dict(record) for record in records), key=canonical_json)
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def validate_forbidden_feature_leakage(records: Iterable[Mapping[str, Any]]) -> None:
    """Fail closed if a prohibited R6 feature/provenance field is introduced."""

    def visit(value: object, path: str) -> None:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if not isinstance(key, str):
                    raise ValueError(f"R6 record field at {path} is not text")
                key_lower = key.lower()
                if any(token in key_lower for token in FORBIDDEN_FEATURE_TOKENS):
                    raise ValueError(f"Forbidden R6 feature leakage at {path}.{key}")
                visit(nested, f"{path}.{key}")
        elif isinstance(value, (list, tuple)):
            for index, nested in enumerate(value):
                visit(nested, f"{path}[{index}]")

    for index, record in enumerate(records):
        visit(record, f"records[{index}]")
