from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import httpx


class ProviderCallError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class GroqCompletion:
    payload: dict[str, Any]
    input_tokens: int | None
    output_tokens: int | None


class GroqStructuredClient:
    """Small OpenAI-compatible Groq client with no tool support or payload logging."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._client = client

    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
        max_tokens: int,
    ) -> GroqCompletion:
        request = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_completion_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
        }
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.timeout_seconds)
        try:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=request,
                    )
                except httpx.TimeoutException as exception:
                    if attempt < self.max_retries:
                        continue
                    raise ProviderCallError(
                        "PROVIDER_TIMEOUT", "The provider timed out."
                    ) from exception
                except httpx.HTTPError as exception:
                    if attempt < self.max_retries:
                        continue
                    raise ProviderCallError(
                        "PROVIDER_ERROR", "The provider could not be reached."
                    ) from exception
                if response.status_code == 429:
                    if attempt < self.max_retries:
                        await asyncio.sleep(_retry_delay(response))
                        continue
                    raise ProviderCallError(
                        "PROVIDER_RATE_LIMITED", "The provider rate limit was reached."
                    )
                if response.status_code >= 500 and attempt < self.max_retries:
                    await asyncio.sleep(_retry_delay(response))
                    continue
                if response.status_code >= 400:
                    raise ProviderCallError("PROVIDER_ERROR", "The provider rejected the request.")
                try:
                    body = response.json()
                    content = body["choices"][0]["message"]["content"]
                    payload = json.loads(content)
                    if not isinstance(payload, dict):
                        raise TypeError
                    usage = body.get("usage", {})
                except (
                    KeyError,
                    IndexError,
                    TypeError,
                    ValueError,
                    json.JSONDecodeError,
                ) as exception:
                    raise ProviderCallError(
                        "PROVIDER_RESPONSE_INVALID", "The provider returned an invalid response."
                    ) from exception
                return GroqCompletion(
                    payload=payload,
                    input_tokens=_optional_int(usage.get("prompt_tokens")),
                    output_tokens=_optional_int(usage.get("completion_tokens")),
                )
        finally:
            if own_client:
                await client.aclose()
        raise ProviderCallError("PROVIDER_ERROR", "The provider request did not complete.")


def _retry_delay(response: httpx.Response) -> float:
    value = response.headers.get("retry-after", "0.1")
    try:
        return min(max(float(value), 0.0), 1.0)
    except ValueError:
        return 0.1


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int) else None
