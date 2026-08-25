"""Credential-safe rendering helpers for provider edges."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

_SENSITIVE_HEADER_NAMES = frozenset(
    {"authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization"}
)
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_REDACTED = "[REDACTED]"


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        name: _REDACTED if name.casefold() in _SENSITIVE_HEADER_NAMES else value
        for name, value in headers.items()
    }


def redact_text(text: str, secrets: Sequence[str] = ()) -> str:
    redacted = _BEARER_PATTERN.sub(f"Bearer {_REDACTED}", text)
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, _REDACTED)
    return redacted


__all__ = ["redact_headers", "redact_text"]
