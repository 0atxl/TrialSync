from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from trialsync.db.models import DocumentKind
from trialsync.imports.parser import extract_text_input
from trialsync.nlp.chat import (
    CanonicalExplainer,
    ScreeningChatContext,
    validate_answer,
)
from trialsync.nlp.extraction import RuleBasedExtractor

DEFAULT_FIXTURE = Path(__file__).resolve().parents[2] / "evaluation" / "phase7_heldout.json"


def evaluation_context() -> ScreeningChatContext:
    return ScreeningChatContext(
        screening_id="phase8-screening",
        overall_state="needs_review",
        counts={"pass": 2, "fail": 0, "unknown": 1},
        evaluations=(
            {
                "criterion_id": "criterion-age",
                "evaluation_id": "evaluation-age",
                "criterion_order": 1,
                "criterion_kind": "inclusion",
                "source_text": "Age 18 to 75 years",
                "result": "unknown",
                "reason_code": "MISSING_FACT",
                "canonical_explanation": (
                    "Age cannot be evaluated because date of birth is missing."
                ),
                "evidence_ids": [],
                "evidence": [],
                "missing_information": [{"fact": "date_of_birth"}],
            },
        ),
        versions={"engine": "0.1.0", "patient_snapshot": "phase8-snapshot"},
    )


async def evaluate_fixture(
    fixture_path: Path = DEFAULT_FIXTURE,
    *,
    performance_iterations: int = 50,
) -> dict[str, Any]:
    fixture: dict[str, Any] = json.loads(fixture_path.read_text())
    extractor = RuleBasedExtractor()
    expected_candidates = 0
    actual_candidates = 0
    matched_candidates = 0
    exact_structures = 0
    valid_sources = 0
    total_sources = 0
    latencies_ms: list[float] = []

    for case in fixture["extraction_cases"]:
        kind = DocumentKind(str(case["kind"]))
        extracted = extract_text_input(str(case["text"]))
        run = await extractor.extract(kind, extracted)
        if kind is DocumentKind.patient:
            expected = [str(value) for value in case["expected_concepts"]]
            items = cast(list[dict[str, Any]], run.candidates["facts"])
            actual = [str(item["concept"]) for item in items]
            matched = len(set(expected) & set(actual))
            exact_structures += int(actual == expected)
        else:
            expected_count = int(case["expected_criteria"])
            items = cast(list[dict[str, Any]], run.candidates["criteria"])
            actual = [str(item["source_text"]) for item in items]
            expected = ["criterion"] * expected_count
            matched = min(expected_count, len(items))
            exact_structures += int(len(items) == expected_count)
        expected_candidates += len(expected)
        actual_candidates += len(actual)
        matched_candidates += matched
        for item in items:
            source = item["source"]
            total_sources += 1
            if str(case["text"])[int(source["start"]) : int(source["end"])] == source["text"]:
                valid_sources += 1

        for _ in range(performance_iterations):
            started = perf_counter()
            await extractor.extract(kind, extracted)
            latencies_ms.append((perf_counter() - started) * 1_000)

    context = evaluation_context()
    provider = CanonicalExplainer()
    chat_correct = 0
    supported = 0
    supported_with_valid_citations = 0
    refused_expected = 0
    refused_correct = 0
    for case in fixture["conversation_cases"]:
        expected_state = str(case["expected_state"])
        answer = await provider.answer(
            context=context,
            history=[],
            message=str(case["question"]),
        )
        validated = validate_answer(answer, context)
        chat_correct += int(validated.answer_state == expected_state)
        if expected_state == "supported":
            supported += 1
            supported_with_valid_citations += int(
                validated.answer_state == "supported" and bool(validated.citations)
            )
        if expected_state == "refused":
            refused_expected += 1
            refused_correct += int(validated.answer_state == "refused")

    latencies_ms.sort()
    p95_index = max(0, int(len(latencies_ms) * 0.95) - 1)
    representative_text = (
        "Patient name: Synthetic Performance Case\n"
        "Date of birth: 1980-01-01\n"
        "HbA1c: 7.7 %\n" + ("Synthetic narrative line without additional clinical facts.\n" * 1_000)
    )[:50_000]
    representative_input = extract_text_input(representative_text)
    representative_latencies: list[float] = []
    for _ in range(min(performance_iterations, 20)):
        started = perf_counter()
        await extractor.extract(DocumentKind.patient, representative_input)
        representative_latencies.append((perf_counter() - started) * 1_000)
    representative_latencies.sort()
    representative_p95 = representative_latencies[
        max(0, int(len(representative_latencies) * 0.95) - 1)
    ]
    extraction_cases = len(fixture["extraction_cases"])
    conversation_cases = len(fixture["conversation_cases"])
    return {
        "dataset": fixture["dataset"],
        "synthetic_only": bool(fixture["synthetic_only"]),
        "network_requests": 0,
        "extraction": {
            "cases": extraction_cases,
            "candidate_precision": round(matched_candidates / max(actual_candidates, 1), 4),
            "candidate_recall": round(matched_candidates / max(expected_candidates, 1), 4),
            "exact_structure_accuracy": round(exact_structures / max(extraction_cases, 1), 4),
            "source_quote_validity": round(valid_sources / max(total_sources, 1), 4),
        },
        "conversation": {
            "cases": conversation_cases,
            "answer_state_accuracy": round(chat_correct / max(conversation_cases, 1), 4),
            "supported_citation_validity": round(
                supported_with_valid_citations / max(supported, 1), 4
            ),
            "refusal_accuracy": round(refused_correct / max(refused_expected, 1), 4),
        },
        "performance": {
            "iterations": len(latencies_ms),
            "mean_extraction_ms": round(statistics.fmean(latencies_ms), 4),
            "p95_extraction_ms": round(latencies_ms[p95_index], 4),
            "fixture_size_max_chars": max(
                len(str(case["text"])) for case in fixture["extraction_cases"]
            ),
            "representative_document_chars": len(representative_text),
            "representative_document_p95_ms": round(representative_p95, 4),
        },
        "acceptance": {
            "all_expected_candidates_found": matched_candidates == expected_candidates,
            "all_source_quotes_verified": valid_sources == total_sources,
            "all_conversation_states_correct": chat_correct == conversation_cases,
            "all_supported_citations_valid": supported_with_valid_citations == supported,
            "all_refusals_correct": refused_correct == refused_expected,
            "representative_document_under_250ms": representative_p95 < 250,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the offline synthetic TrialSync extraction/chat evaluation."
    )
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--iterations", type=int, default=50)
    args = parser.parse_args()
    if args.iterations < 1 or args.iterations > 1_000:
        parser.error("--iterations must be between 1 and 1000")
    result = asyncio.run(evaluate_fixture(args.fixture, performance_iterations=args.iterations))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
