"""Secret scrubbing for text that is persisted or shown (e.g. run errors).

Provider exceptions routinely echo request headers, URLs with credentials, or
the key itself. Anything stored from an untrusted error string goes through
:func:`scrub_secrets` first. This module never logs the values it removes.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping

REDACTED = "[REDACTED]"

_SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|DSN|CREDENTIAL|AUTH)", re.IGNORECASE)
_MIN_ENV_SECRET_LEN = 6  # shorter values would redact ordinary words

# (pattern, keep) -- ``keep`` lists capture groups that stay around [REDACTED].
_PATTERNS: tuple[tuple[re.Pattern[str], tuple[int, ...]], ...] = (
    # Authorization / Proxy-Authorization header values (scheme + credential)
    (
        re.compile(
            r"(?i)\b((?:proxy-)?authorization\s*[:=]\s*)(?:bearer|basic|token)?\s*[^\s,;'\"]+"
        ),
        (1,),
    ),
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"), (1,)),
    # user:password@ inside any URL / connection string
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^\s:/@]+:)[^\s@/]+(@)"), (1, 2)),
    # key=value / key: value for secret-looking names
    (
        re.compile(
            r"(?i)\b((?:[a-z0-9_.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)"
            r"[a-z0-9_.-]*)\s*[=:]\s*)[^\s,;'\"&]+"
        ),
        (1,),
    ),
    # well-known token shapes
    (re.compile(r"\bsk-[A-Za-z0-9_-]{6,}"), ()),
    (re.compile(r"\b(?:ghp|gho|ghs|ghu|github_pat)_[A-Za-z0-9_]{10,}"), ()),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), ()),
    (re.compile(r"\bAKIA[0-9A-Z]{12,}"), ()),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"), ()),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"), ()),  # JWT
)


def _env_secret_values(env: Mapping[str, str], extra_names: Iterable[str]) -> list[str]:
    names = {n for n in extra_names if n}
    values = [
        v
        for k, v in env.items()
        if (k in names or _SECRET_NAME.search(k)) and len(v) >= _MIN_ENV_SECRET_LEN
    ]
    # Longest first so a value containing another is removed whole.
    return sorted(set(values), key=len, reverse=True)


def scrub_secrets(
    text: str,
    *,
    credential_refs: Iterable[str | None] = (),
    env: Mapping[str, str] | None = None,
) -> str:
    """Return ``text`` with credentials removed.

    Removes the actual values of the named credential env vars and of any
    secret-looking env var, then pattern-matches common credential shapes.
    """

    out = text
    source = env if env is not None else os.environ
    for value in _env_secret_values(source, [r or "" for r in credential_refs]):
        out = out.replace(value, REDACTED)
    for pattern, keep in _PATTERNS:

        def _sub(m: re.Match[str], keep: tuple[int, ...] = keep) -> str:
            if not keep:
                return REDACTED
            if keep == (1, 2):
                return f"{m.group(1)}{REDACTED}{m.group(2)}"
            return f"{m.group(1)} {REDACTED}" if keep == (1,) and m.group(1).lower() in ("bearer", "basic") else f"{m.group(1)}{REDACTED}"

        out = pattern.sub(_sub, out)
    return out


__all__ = ["REDACTED", "scrub_secrets"]
