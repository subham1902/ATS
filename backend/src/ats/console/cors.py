"""Credentialed-CORS origin policy for the operator console.

``allow_origins=["*"]`` together with ``allow_credentials=True`` lets any web
page act as the operator's browser against this API. Origins are therefore an
explicit allowlist: local control-center defaults, or ``ATS_CORS_ORIGINS`` (a
comma-separated list). A wildcard or malformed entry is a startup error, never
silently accepted.
"""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit

ENV_VAR = "ATS_CORS_ORIGINS"

DEFAULT_LOCAL_ORIGINS: tuple[str, ...] = (
    "http://127.0.0.1:3001",
    "http://localhost:3001",
)


class InvalidCorsConfiguration(ValueError):
    """Raised when the configured origin list is unsafe or malformed."""


def _validate_origin(origin: str) -> str:
    if origin == "*" or "*" in origin:
        raise InvalidCorsConfiguration(
            f"{ENV_VAR}: wildcard origins are not allowed with credentials ({origin!r})"
        )
    parts = urlsplit(origin)
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
        or parts.username
    ):
        raise InvalidCorsConfiguration(
            f"{ENV_VAR}: {origin!r} is not a bare http(s) origin like https://host[:port]"
        )
    port = f":{parts.port}" if parts.port else ""
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    return f"{parts.scheme}://{host}{port}"


def resolve_cors_origins(env: Mapping[str, str]) -> list[str]:
    """Return the allowed origins, or raise :class:`InvalidCorsConfiguration`."""

    raw = env.get(ENV_VAR)
    if raw is None or not raw.strip():
        return list(DEFAULT_LOCAL_ORIGINS)
    origins = [_validate_origin(item.strip()) for item in raw.split(",") if item.strip()]
    if not origins:
        raise InvalidCorsConfiguration(f"{ENV_VAR} is set but contains no origins")
    return list(dict.fromkeys(origins))


__all__ = [
    "DEFAULT_LOCAL_ORIGINS",
    "ENV_VAR",
    "InvalidCorsConfiguration",
    "resolve_cors_origins",
]
