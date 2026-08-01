from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from trialsync.config import Settings
from trialsync.db.models import FactType
from trialsync.schemas import TerminologySuggestionRead

RXNAV_APPROXIMATE_URL = "https://rxnav.nlm.nih.gov/REST/approximateTerm.json"
LOINC_SEARCH_URL = "https://loinc.regenstrief.org/searchapi/loincs"


@dataclass(frozen=True)
class TerminologySuggestionResult:
    suggestions: list[TerminologySuggestionRead]
    unavailable_sources: list[str]


class TerminologySuggestionService:
    def __init__(
        self,
        *,
        enabled: bool,
        timeout_seconds: float,
        max_results: int,
        loinc_username: str,
        loinc_password: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.max_results = max_results
        self.loinc_username = loinc_username
        self.loinc_password = loinc_password
        self._client = client

    async def suggest(
        self,
        *,
        query: str,
        fact_type: FactType,
    ) -> TerminologySuggestionResult:
        if not self.enabled:
            return TerminologySuggestionResult([], ["Terminology suggestions are disabled."])
        if fact_type is FactType.medication:
            return await self._rxnorm(query)
        if fact_type is FactType.observation:
            return await self._loinc(query)
        return TerminologySuggestionResult(
            [],
            ["External suggestions are available for medications and observations only."],
        )

    async def _rxnorm(self, query: str) -> TerminologySuggestionResult:
        try:
            payload = await self._get_json(
                RXNAV_APPROXIMATE_URL,
                params={"term": query, "maxEntries": self.max_results, "option": 1},
            )
        except httpx.HTTPError:
            return TerminologySuggestionResult(
                [],
                ["RxNorm could not be reached. Try again later."],
            )
        group = payload.get("approximateGroup", {}) if isinstance(payload, dict) else {}
        candidates = group.get("candidate", []) if isinstance(group, dict) else []
        if isinstance(candidates, dict):
            candidates = [candidates]
        suggestions = [
            TerminologySuggestionRead(
                source="rxnorm",
                code=str(candidate["rxcui"]),
                display_label=str(candidate["name"]),
                detail=(str(candidate["source"]) if candidate.get("source") else None),
                score=float(candidate["score"]) if candidate.get("score") is not None else None,
            )
            for candidate in candidates
            if isinstance(candidate, dict) and candidate.get("rxcui") and candidate.get("name")
        ]
        return TerminologySuggestionResult(suggestions[: self.max_results], [])

    async def _loinc(self, query: str) -> TerminologySuggestionResult:
        if not self.loinc_username or not self.loinc_password:
            return TerminologySuggestionResult(
                [],
                ["LOINC search needs TRIALSYNC_LOINC_USERNAME and TRIALSYNC_LOINC_PASSWORD."],
            )
        try:
            payload = await self._get_json(
                LOINC_SEARCH_URL,
                params={"query": query, "rows": self.max_results, "offset": 0},
                auth=(self.loinc_username, self.loinc_password),
            )
        except httpx.HTTPError:
            return TerminologySuggestionResult([], ["LOINC could not be reached. Try again later."])
        rows = _loinc_rows(payload)
        suggestions = [suggestion for row in rows if (suggestion := _loinc_suggestion(row))]
        return TerminologySuggestionResult(suggestions[: self.max_results], [])

    async def _get_json(
        self,
        url: str,
        *,
        params: dict[str, str | int],
        auth: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        client = self._client or httpx.AsyncClient(timeout=self.timeout_seconds)
        try:
            response = await client.get(url, params=params, auth=auth)
            response.raise_for_status()
            payload = response.json()
        finally:
            if self._client is None:
                await client.aclose()
        return payload if isinstance(payload, dict) else {}


def _loinc_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("results", "items", "data"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _loinc_suggestion(row: dict[str, Any]) -> TerminologySuggestionRead | None:
    code = row.get("LOINC_NUM") or row.get("loinc_num") or row.get("code")
    label = (
        row.get("LONG_COMMON_NAME")
        or row.get("long_common_name")
        or row.get("display")
        or row.get("COMPONENT")
    )
    if not code or not label:
        return None
    unit = row.get("EXAMPLE_UCUM_UNITS") or row.get("example_ucum_units")
    detail = row.get("SHORTNAME") or row.get("shortname") or row.get("CLASS")
    return TerminologySuggestionRead(
        source="loinc",
        code=str(code),
        display_label=str(label),
        detail=str(detail) if detail else None,
        fixed_unit=str(unit) if unit else None,
    )


def build_terminology_suggestion_service(settings: Settings) -> TerminologySuggestionService:
    return TerminologySuggestionService(
        enabled=settings.terminology_suggestions_enabled,
        timeout_seconds=settings.terminology_timeout_seconds,
        max_results=settings.terminology_max_results,
        loinc_username=settings.loinc_username.get_secret_value(),
        loinc_password=settings.loinc_password.get_secret_value(),
    )
