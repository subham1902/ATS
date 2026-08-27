"""HTTP transport for local Ollama — mirrors OpenRouterHttpTransport shape."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from pydantic import SecretStr

from .transport import InferenceHttpResponse


class OllamaHttpTransport:
    def __init__(self, *, endpoint: str = "http://127.0.0.1:11434") -> None:
        self._endpoint = endpoint.rstrip("/")

    @property
    def endpoint(self) -> str:
        return self._endpoint

    def post(
        self,
        *,
        payload: dict[str, object],
        api_key: SecretStr,
        timeout_ms: int,
    ) -> InferenceHttpResponse:
        _ = api_key
        path = str(payload.get("_ollama_path") or "/api/chat")
        body_payload = {k: v for k, v in payload.items() if not k.startswith("_")}
        url = f"{self._endpoint}{path}"
        data = json.dumps(body_payload, separators=(",", ":")).encode()
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ATS-Ollama-Inference/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_ms / 1000) as response:
                return InferenceHttpResponse(status_code=response.status, body=response.read())
        except urllib.error.HTTPError as error:
            return InferenceHttpResponse(status_code=error.code, body=error.read())
        except OSError as error:
            raise TimeoutError("Ollama transport failed") from error


__all__ = ["OllamaHttpTransport"]
