"""Canonical UTF-8 JSON serialization and SHA-256 integrity hashing.

Rules:

* mapping keys are strings and are sorted by Unicode code point;
* list and tuple order is preserved and both serialize as JSON arrays;
* UUIDs use lowercase hyphenated text;
* aware datetimes normalize to UTC and use six fractional digits plus ``Z``;
* finite Decimals use normalized, non-exponent decimal text;
* finite floats remain JSON numbers and use pinned Python 3.11's shortest
  correctly-round-trippable binary64 representation as emitted by ``json``;
* float exponent notation follows that representation and negative zero is
  normalized to ``0.0``;
* Decimal and float remain distinct: Decimal is a JSON string while float is a
  JSON number, with contract field typing providing the authority boundary;
* string enums use their declared values;
* ``None`` is retained as JSON ``null``;
* nested Pydantic models use aliases and include null fields;
* non-finite floats, naive datetimes, sets, callables, and unknown objects are rejected.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, TypeAlias
from uuid import UUID

from pydantic import BaseModel

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


def _canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("Decimal value must be finite")
    if value.is_zero():
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _canonical_datetime(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    normalized = value.astimezone(UTC)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonicalize(value: Any) -> JSONValue:
    """Convert supported values into the canonical JSON value domain."""

    if isinstance(value, BaseModel):
        return canonicalize(
            value.model_dump(mode="python", by_alias=True, exclude_none=False, round_trip=True)
        )
    if isinstance(value, Enum):
        if not isinstance(value.value, str):
            raise TypeError("canonical enums must have string values")
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return _canonical_datetime(value)
    if isinstance(value, Decimal):
        return _canonical_decimal(value)
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("float value must be finite")
        return 0.0 if value == 0.0 else value
    if isinstance(value, Mapping):
        result: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical mapping keys must be strings")
            result[key] = canonicalize(item)
        return result
    if isinstance(value, list | tuple):
        return [canonicalize(item) for item in value]
    raise TypeError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a supported value as compact canonical UTF-8 JSON bytes."""

    normalized = canonicalize(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Return the lowercase SHA-256 hex digest of canonical JSON bytes."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


__all__ = ["JSONValue", "canonical_json_bytes", "canonical_sha256", "canonicalize"]
