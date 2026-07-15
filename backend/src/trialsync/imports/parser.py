from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_TEXT_BYTES = 1_000_000
MAX_PDF_BYTES = 5_000_000


class ImportParseError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ExtractedInput:
    text: str
    pages: list[dict[str, Any]]
    quality: dict[str, Any]


def extract_text_input(text: str) -> ExtractedInput:
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_TEXT_BYTES:
        raise ImportParseError("IMPORT_TOO_LARGE", "Pasted text exceeds the 1 MB limit.")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ImportParseError("IMPORT_EMPTY", "The pasted text is empty.")
    return ExtractedInput(
        text=normalized,
        pages=[{"page": 1, "start_offset": 0, "end_offset": len(normalized), "text": normalized}],
        quality=_quality(normalized, 1),
    )


def extract_pdf_input(content: bytes) -> ExtractedInput:
    if not content:
        raise ImportParseError("IMPORT_EMPTY", "The uploaded PDF is empty.")
    if len(content) > MAX_PDF_BYTES:
        raise ImportParseError("IMPORT_TOO_LARGE", "The PDF exceeds the 5 MB limit.")
    if not content.startswith(b"%PDF-"):
        raise ImportParseError("IMPORT_WRONG_TYPE", "The uploaded file is not a valid PDF.")
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise ImportParseError("PDF_ENCRYPTED", "Encrypted PDFs are not supported.")
        raw_pages = [page.extract_text() or "" for page in reader.pages]
    except ImportParseError:
        raise
    except (PdfReadError, OSError, ValueError, TypeError) as exception:
        raise ImportParseError(
            "PDF_MALFORMED", "The PDF is malformed and could not be read."
        ) from exception
    if not raw_pages:
        raise ImportParseError("PDF_EMPTY", "The PDF does not contain any pages.")

    parts: list[str] = []
    pages: list[dict[str, object]] = []
    offset = 0
    for number, raw in enumerate(raw_pages, 1):
        page_text = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
        if parts:
            parts.append("\n\n")
            offset += 2
        start = offset
        parts.append(page_text)
        offset += len(page_text)
        pages.append(
            {"page": number, "start_offset": start, "end_offset": offset, "text": page_text}
        )
    text = "".join(parts)
    quality = _quality(text, len(pages))
    quality["extractor"] = "pypdf-6.14.2"
    if len(re.sub(r"\s+", "", text)) < 40 or float(str(quality["characters_per_page"])) < 20:
        raise ImportParseError(
            "PDF_OCR_NOT_ENABLED",
            "No machine-readable text was found. Upload a text-based PDF; OCR is not enabled.",
        )
    return ExtractedInput(text=text, pages=pages, quality=quality)


def _quality(text: str, page_count: int) -> dict[str, Any]:
    printable = sum(character.isprintable() or character in "\n\t" for character in text)
    return {
        "page_count": page_count,
        "character_count": len(text),
        "characters_per_page": round(len(text) / max(page_count, 1), 2),
        "printable_ratio": round(printable / max(len(text), 1), 4),
        "extractor": "deterministic-text-1",
    }


def _source(pages: list[dict[str, Any]], start: int, end: int, text: str) -> dict[str, object]:
    page = next(
        (item for item in pages if int(item["start_offset"]) <= start <= int(item["end_offset"])),
        pages[0],
    )
    page_start = int(page["start_offset"])
    return {
        "page": int(page["page"]),
        "start": start - page_start,
        "end": end - page_start,
        "text": text.strip(),
    }


def _match_value(pattern: str, text: str) -> re.Match[str] | None:
    return re.search(pattern, text, re.IGNORECASE | re.MULTILINE)


def extract_patient_candidates(extracted: ExtractedInput) -> tuple[dict[str, object], list[str]]:
    text, pages = extracted.text, extracted.pages
    warnings: list[str] = []
    name = _match_value(r"^(?:patient\s+name|name)\s*:\s*(?P<value>[^\n]+)", text)
    dob = _match_value(r"^(?:date\s+of\s+birth|dob)\s*:\s*(?P<value>\d{4}-\d{2}-\d{2})", text)
    sex = _match_value(r"^sex\s*:\s*(?P<value>[^\n]+)", text)
    profile: dict[str, object] = {
        "display_name": name.group("value").strip() if name else "Imported synthetic patient",
        "date_of_birth": dob.group("value") if dob else None,
        "sex": sex.group("value").strip() if sex else None,
    }
    facts: list[dict[str, object]] = []

    observation_pattern = re.compile(
        r"(?P<concept>HbA1c|eGFR|BMI|creatinine)\s*[:=]?\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>%|mg/dL|mL/min/1\.73m2|kg/m2)",
        re.IGNORECASE,
    )
    seen_values: dict[str, set[str]] = {}
    for match in observation_pattern.finditer(text):
        concept = match.group("concept")
        value = match.group("value")
        seen_values.setdefault(concept.lower(), set()).add(value)
        facts.append(
            _patient_fact(
                "observation", concept, match, pages, value_numeric=value, unit=match.group("unit")
            )
        )

    simple_pattern = re.compile(
        r"^(?P<label>condition|diagnosis|medication)\s*:\s*(?P<value>[^\n]+)",
        re.IGNORECASE | re.MULTILINE,
    )
    for match in simple_pattern.finditer(text):
        label = match.group("label").lower()
        value = match.group("value").strip()
        facts.append(
            _patient_fact(
                "medication" if label == "medication" else "condition",
                value,
                match,
                pages,
                value_text="Present",
            )
        )

    for concept, values in seen_values.items():
        if len(values) > 1:
            warning = f"Conflicting extracted values for {concept}; choose the accepted candidate."
            warnings.append(warning)
            for fact in facts:
                if str(fact["concept"]).lower() == concept:
                    fact["warnings"] = [warning]
    if not facts:
        warnings.append("No structured facts were recognized; add or edit facts during review.")
    return {"profile": profile, "facts": facts}, warnings


def _patient_fact(
    fact_type: str,
    concept: str,
    match: re.Match[str],
    pages: list[dict[str, Any]],
    *,
    value_numeric: str | None = None,
    value_text: str | None = None,
    unit: str | None = None,
) -> dict[str, object]:
    return {
        "candidate_id": str(uuid.uuid4()),
        "selected": True,
        "fact_type": fact_type,
        "concept": concept.strip(),
        "value_numeric": value_numeric,
        "value_text": value_text,
        "unit": unit,
        "assertion": "present",
        "effective_date": None,
        "source": _source(pages, match.start(), match.end(), match.group(0)),
        "warnings": [],
    }


def extract_trial_candidates(extracted: ExtractedInput) -> tuple[dict[str, object], list[str]]:
    text, pages = extracted.text, extracted.pages
    warnings: list[str] = []
    title = _match_value(r"^(?:trial\s+title|title)\s*:\s*(?P<value>[^\n]+)", text)
    condition = _match_value(r"^condition\s*:\s*(?P<value>[^\n]+)", text)
    phase = _match_value(r"^phase\s*:\s*(?P<value>[^\n]+)", text)
    profile = {
        "title": title.group("value").strip() if title else "Imported synthetic trial",
        "condition": condition.group("value").strip() if condition else "Synthetic condition",
        "phase": phase.group("value").strip() if phase else None,
    }
    criteria: list[dict[str, object]] = []
    kind: str | None = None
    cursor = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        lower = stripped.lower().rstrip(":")
        if lower in {"inclusion", "inclusion criteria", "eligibility criteria - inclusion"}:
            kind = "inclusion"
        elif lower in {"exclusion", "exclusion criteria", "eligibility criteria - exclusion"}:
            kind = "exclusion"
        elif kind and stripped:
            criterion_text = re.sub(r"^(?:[-*•]|\d+[.)])\s*", "", stripped).strip()
            if (
                criterion_text
                and criterion_text == stripped
                and not re.match(r"^(?:[-*•]|\d+[.)])", stripped)
            ):
                cursor += len(line)
                continue
            start = cursor + line.find(criterion_text)
            rule = _trial_rule(criterion_text)
            parse_state = "parsed" if rule else "needs_manual_rule"
            criterion_warnings = (
                [] if rule else ["This criterion needs manual rule entry before approval."]
            )
            criteria.append(
                {
                    "candidate_id": str(uuid.uuid4()),
                    "selected": True,
                    "kind": kind,
                    "order": len(criteria) + 1,
                    "source_text": criterion_text,
                    "normalized_rule": rule,
                    "parse_state": parse_state,
                    "source": _source(pages, start, start + len(criterion_text), criterion_text),
                    "warnings": criterion_warnings,
                }
            )
        cursor += len(line)
    if not criteria:
        warnings.append("No inclusion or exclusion list items were recognized.")
    elif any(item["parse_state"] == "needs_manual_rule" for item in criteria):
        warnings.append("Some criteria require manual rule entry and cannot be approved as-is.")
    return {"profile": profile, "criteria": criteria}, warnings


def _trial_rule(text: str) -> dict[str, Any] | None:
    age_between = re.search(
        r"age\s+(?:between\s+)?(\d+)\s*(?:to|-|\u2013)\s*(\d+)\s*(?:years?)?",
        text,
        re.IGNORECASE,
    )
    if age_between:
        return {
            "op": "between",
            "fact": "demographic.age",
            "min": int(age_between.group(1)),
            "max": int(age_between.group(2)),
            "unit": "year",
        }
    age_min = re.search(
        r"age\s+(\d+)\s*(?:years?)?\s*(?:or older|and older|minimum)", text, re.IGNORECASE
    )
    if age_min:
        return {
            "op": "gte",
            "fact": "demographic.age",
            "value": int(age_min.group(1)),
            "unit": "year",
        }
    numeric = re.search(
        r"(HbA1c|eGFR|BMI|creatinine)\s*(?:is\s+)?"
        r"(less than or equal to|greater than or equal to|no more than|no less than|"
        r"at most|at least|less than|greater than|<=|>=|<|>|≤|≥)\s*"
        r"(\d+(?:\.\d+)?)\s*([^\s,;]+)?",
        text,
        re.IGNORECASE,
    )
    if numeric:
        operations = {
            "<": "lt",
            "less than": "lt",
            "<=": "lte",
            "≤": "lte",
            "less than or equal to": "lte",
            "no more than": "lte",
            "at most": "lte",
            ">": "gt",
            "greater than": "gt",
            ">=": "gte",
            "≥": "gte",
            "greater than or equal to": "gte",
            "no less than": "gte",
            "at least": "gte",
        }
        concept = numeric.group(1).lower()
        unit = numeric.group(4) or ("%" if concept == "hba1c" else None)
        if unit:
            return {
                "op": operations[numeric.group(2).lower()],
                "fact": f"observation.{concept}",
                "value": float(numeric.group(3)),
                "unit": unit,
            }
    return None
