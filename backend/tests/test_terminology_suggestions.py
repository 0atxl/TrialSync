from __future__ import annotations

import httpx
import pytest

from trialsync.db.models import FactType
from trialsync.terminology.suggestions import TerminologySuggestionService

pytestmark = pytest.mark.anyio


async def test_rxnorm_suggestions_are_bounded_and_preserve_the_rxcui() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/approximateTerm.json")
        assert request.url.params["term"] == "metformin"
        return httpx.Response(
            200,
            json={
                "approximateGroup": {
                    "candidate": [
                        {
                            "rxcui": "6809",
                            "name": "metformin",
                            "source": "RXNORM",
                            "score": "100",
                        }
                    ]
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = TerminologySuggestionService(
            enabled=True,
            timeout_seconds=1,
            max_results=5,
            loinc_username="",
            loinc_password="",
            client=client,
        )
        result = await service.suggest(query="metformin", fact_type=FactType.medication)

    assert result.unavailable_sources == []
    assert result.suggestions[0].model_dump() == {
        "source": "rxnorm",
        "code": "6809",
        "display_label": "metformin",
        "detail": "RXNORM",
        "fixed_unit": None,
        "score": 100.0,
    }


async def test_loinc_suggestions_require_credentials_and_preserve_units() -> None:
    no_credentials = TerminologySuggestionService(
        enabled=True,
        timeout_seconds=1,
        max_results=5,
        loinc_username="",
        loinc_password="",
    )
    unavailable = await no_credentials.suggest(query="glucose", fact_type=FactType.observation)
    assert unavailable.suggestions == []
    assert "TRIALSYNC_LOINC_USERNAME" in unavailable.unavailable_sources[0]

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/searchapi/loincs")
        assert request.url.params["query"] == "glucose"
        return httpx.Response(
            200,
            json={
                "Results": [
                    {
                        "LOINC_NUM": "2345-7",
                        "LONG_COMMON_NAME": "Glucose [Mass/volume] in Serum or Plasma",
                        "EXAMPLE_UCUM_UNITS": "mg/dL",
                        "SHORTNAME": "Glucose SerPl-mCnc",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = TerminologySuggestionService(
            enabled=True,
            timeout_seconds=1,
            max_results=5,
            loinc_username="loinc-user",
            loinc_password="loinc-password",
            client=client,
        )
        result = await service.suggest(query="glucose", fact_type=FactType.observation)

    assert result.unavailable_sources == []
    assert result.suggestions[0].source == "loinc"
    assert result.suggestions[0].code == "2345-7"
    assert result.suggestions[0].fixed_unit == "mg/dL"
