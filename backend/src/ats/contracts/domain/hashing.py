"""Explicit A02 payload-hash preimage convention.

The hash field itself is excluded from its preimage. Every other authoritative
field is included and serialized by the A01/A01.1 canonical JSON convention.
No model construction mutates or automatically generates a hash.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias

from pydantic import BaseModel

from ats.contracts.hashing import JSONValue, canonical_sha256, canonicalize

HashablePayload: TypeAlias = BaseModel | Mapping[str, object]


def payload_preimage(
    value: HashablePayload,
    *,
    hash_field: str = "payload_hash",
) -> dict[str, JSONValue]:
    """Return canonicalizable authoritative fields with the hash field removed."""

    if isinstance(value, BaseModel):
        raw = value.model_dump(mode="python", by_alias=True, exclude_none=False, round_trip=True)
    else:
        raw = dict(value)
    if hash_field not in raw:
        raise ValueError(f"hash field {hash_field!r} is absent")
    del raw[hash_field]
    normalized = canonicalize(raw)
    if not isinstance(normalized, dict):
        raise TypeError("payload preimage must be a mapping")
    return normalized


def compute_payload_hash(
    value: HashablePayload,
    *,
    hash_field: str = "payload_hash",
) -> str:
    """Compute SHA-256 over all authoritative fields except the hash field itself."""

    return canonical_sha256(payload_preimage(value, hash_field=hash_field))


__all__ = ["compute_payload_hash", "payload_preimage"]
