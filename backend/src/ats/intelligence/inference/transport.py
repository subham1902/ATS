"""Secret-safe OpenRouter HTTP transport."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Protocol

from pydantic import SecretStr

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain.types import NonNegativeInt


class InferenceHttpResponse(ATSBaseModel):
    status_code: NonNegativeInt
    body: bytes


class InferenceTransport(Protocol):
    def post(
        self,
        *,
        payload: dict[str, object],
        api_key: SecretStr,
        timeout_ms: int,
    ) -> InferenceHttpResponse: ...


class OpenRouterHttpTransport:
    ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

    def post(
        self,
        *,
        payload: dict[str, object],
        api_key: SecretStr,
        timeout_ms: int,
    ) -> InferenceHttpResponse:
        request = urllib.request.Request(
            self.ENDPOINT,
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers={
                "Authorization": f"Bearer {api_key.get_secret_value()}",
                "Content-Type": "application/json",
                "User-Agent": "ATS-Harness-Inference/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_ms / 1000) as response:
                return InferenceHttpResponse(status_code=response.status, body=response.read())
        except urllib.error.HTTPError as error:
            return InferenceHttpResponse(status_code=error.code, body=error.read())
        except OSError as error:
            raise TimeoutError("OpenRouter transport failed") from error


__all__ = ["InferenceHttpResponse", "InferenceTransport", "OpenRouterHttpTransport"]
