"""Strict, deterministic primitives shared by all ATS contracts.

Aware timestamps supplied with a non-UTC offset are normalized to UTC. Naive
timestamps are rejected. Decimal fields accept :class:`~decimal.Decimal` values
only during Python validation; callers converting text must do so explicitly via
``decimal_from_string``. JSON validation accepts Decimal values only as strings
in that same grammar. Binary floating-point input is never accepted.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Protocol, runtime_checkable

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    StringConstraints,
    ValidationInfo,
)

_SCHEMA_VERSION_PATTERN = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
_DECIMAL_TEXT_PATTERN = re.compile(r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$")


class ATSBaseModel(BaseModel):
    """Immutable strict model base for durable ATS contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        allow_inf_nan=False,
    )


SchemaVersion = Annotated[
    str,
    StringConstraints(strict=True, pattern=_SCHEMA_VERSION_PATTERN),
]


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


UTCDateTime = Annotated[datetime, AfterValidator(_normalize_utc)]


def _prepare_decimal(value: object, info: ValidationInfo) -> object:
    if info.mode == "json":
        if not isinstance(value, str):
            raise ValueError("JSON Decimal values must be encoded as strings")
        return decimal_from_string(value)
    if isinstance(value, float):
        raise ValueError("binary floating-point input is not permitted")
    return value


def _require_finite(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("Decimal value must be finite")
    return value


FiniteDecimal = Annotated[
    Decimal,
    BeforeValidator(_prepare_decimal),
    AfterValidator(_require_finite),
]


def _require_probability(value: Decimal) -> Decimal:
    value = _require_finite(value)
    if not Decimal(0) <= value <= Decimal(1):
        raise ValueError("probability must be between 0 and 1 inclusive")
    return value


Probability = Annotated[
    Decimal,
    BeforeValidator(_prepare_decimal),
    AfterValidator(_require_probability),
]


def decimal_from_string(value: str) -> Decimal:
    """Explicitly parse a finite decimal from the documented numeric grammar."""

    if not isinstance(value, str) or _DECIMAL_TEXT_PATTERN.fullmatch(value) is None:
        raise ValueError("invalid decimal text")
    try:
        return _require_finite(Decimal(value))
    except InvalidOperation as exc:
        raise ValueError("invalid decimal text") from exc


@runtime_checkable
class ClockProtocol(Protocol):
    """Minimal injectable source of timezone-aware UTC timestamps."""

    def now(self) -> UTCDateTime:
        """Return the current timezone-aware UTC timestamp."""
        ...


class SystemClock:
    """The common layer's sole adapter to the ambient wall clock."""

    def now(self) -> UTCDateTime:
        """Return the current system time as an aware UTC datetime."""

        return datetime.now(UTC)


__all__ = [
    "ATSBaseModel",
    "ClockProtocol",
    "FiniteDecimal",
    "Probability",
    "SchemaVersion",
    "SystemClock",
    "UTCDateTime",
    "decimal_from_string",
]
