"""Unit tests for A01 common deterministic primitives."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from enum import auto
from uuid import UUID

import pytest
from pydantic import ValidationError

from ats.contracts import (
    ATSBaseModel,
    ATSStringEnum,
    ClockProtocol,
    FiniteDecimal,
    FiniteFloat,
    OpaqueId,
    Probability,
    SchemaVersion,
    SystemClock,
    UTCDateTime,
    decimal_from_string,
    fixture_id,
    new_opaque_id,
)


class CommonFixture(ATSBaseModel):
    schema_version: SchemaVersion
    timestamp: UTCDateTime
    amount: FiniteDecimal
    probability: Probability
    identity: OpaqueId


class ExampleState(ATSStringEnum):
    READY = auto()


class NumericBoundaryFixture(ATSBaseModel):
    financial_value: FiniteDecimal
    analytical_value: FiniteFloat


def valid_fixture() -> CommonFixture:
    return CommonFixture(
        schema_version="1.0",
        timestamp=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        amount=Decimal("12.50"),
        probability=Decimal("0.5"),
        identity=UUID("12345678-1234-5678-9234-567812345678"),
    )


def test_strict_model_rejects_extra_fields_and_coercion() -> None:
    payload = valid_fixture().model_dump()
    with pytest.raises(ValidationError):
        CommonFixture(**payload, unexpected=True)
    payload["amount"] = "12.50"
    with pytest.raises(ValidationError):
        CommonFixture.model_validate(payload)


def test_model_is_frozen() -> None:
    fixture = valid_fixture()
    with pytest.raises(ValidationError):
        fixture.amount = Decimal("13")  # type: ignore[misc]


@pytest.mark.parametrize("version", ["1", "1.0.0", "01.0", "1.00", "v1.0", ""])
def test_schema_version_rejects_invalid_format(version: str) -> None:
    payload = valid_fixture().model_dump()
    payload["schema_version"] = version
    with pytest.raises(ValidationError):
        CommonFixture.model_validate(payload)


def test_utc_datetime_accepts_utc_and_normalizes_aware_offset() -> None:
    fixture = valid_fixture()
    assert fixture.timestamp.tzinfo is UTC

    payload = fixture.model_dump()
    payload["timestamp"] = datetime(2026, 1, 2, 8, 34, 5, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    normalized = CommonFixture.model_validate(payload)
    assert normalized.timestamp == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert normalized.timestamp.tzinfo is UTC


def test_naive_datetime_is_rejected() -> None:
    payload = valid_fixture().model_dump()
    payload["timestamp"] = datetime(2026, 1, 2, 3, 4, 5)
    with pytest.raises(ValidationError):
        CommonFixture.model_validate(payload)


def test_decimal_rules_are_explicit_and_finite() -> None:
    assert decimal_from_string("123.4500") == Decimal("123.4500")
    for text in ("NaN", "Infinity", "-Infinity", " 1", "+1"):
        with pytest.raises(ValueError):
            decimal_from_string(text)

    payload = valid_fixture().model_dump()
    for value in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), 0.1):
        payload["amount"] = value
        with pytest.raises(ValidationError):
            CommonFixture.model_validate(payload)


@pytest.mark.parametrize("value", [0.0, -2.5, 1.0, 0.1, 1.2345678901234567])
def test_finite_float_accepts_explicit_finite_binary64(value: float) -> None:
    fixture = NumericBoundaryFixture(
        financial_value=Decimal("10.25"),
        analytical_value=value,
    )
    assert fixture.analytical_value == value


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_finite_float_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValidationError):
        NumericBoundaryFixture(
            financial_value=Decimal("10.25"),
            analytical_value=value,
        )


@pytest.mark.parametrize("value", [True, 1, "1.0", Decimal("1.0")])
def test_finite_float_rejects_implicit_coercion(value: object) -> None:
    with pytest.raises(ValidationError):
        NumericBoundaryFixture(
            financial_value=Decimal("10.25"),
            analytical_value=value,  # type: ignore[arg-type]
        )


def test_decimal_and_finite_float_authority_boundary() -> None:
    valid = NumericBoundaryFixture(
        financial_value=Decimal("10.25"),
        analytical_value=0.125,
    )
    assert valid.financial_value == Decimal("10.25")
    assert valid.analytical_value == 0.125

    with pytest.raises(ValidationError):
        NumericBoundaryFixture(financial_value=10.25, analytical_value=0.125)


def test_probability_accepts_boundaries_and_rejects_invalid_values() -> None:
    payload = valid_fixture().model_dump()
    for value in (Decimal("0"), Decimal("1")):
        payload["probability"] = value
        assert CommonFixture.model_validate(payload).probability == value
    for value in (Decimal("-0.0001"), Decimal("1.0001"), Decimal("NaN"), Decimal("Infinity")):
        payload["probability"] = value
        with pytest.raises(ValidationError):
            CommonFixture.model_validate(payload)


def test_uuid_round_trip_and_production_generation() -> None:
    fixture = valid_fixture()
    restored = CommonFixture.model_validate_json(fixture.model_dump_json())
    assert restored.identity == fixture.identity
    generated = new_opaque_id()
    assert isinstance(generated, UUID)
    assert generated.version == 4


def test_json_decimal_requires_canonical_string_encoding() -> None:
    serialized = valid_fixture().model_dump_json()
    assert CommonFixture.model_validate_json(serialized) == valid_fixture()
    with pytest.raises(ValidationError):
        CommonFixture.model_validate_json(
            serialized.replace('"amount":"12.50"', '"amount":12.50')
        )


def test_fixture_id_is_stable_and_namespaced() -> None:
    expected = UUID("485b1efd-b7cf-5ecf-8e2b-f16c2fa912c9")
    assert fixture_id("a01/common-fixture") == expected
    assert fixture_id("a01/common-fixture") == expected
    assert fixture_id("a01/other-fixture") != expected
    with pytest.raises(ValueError):
        fixture_id("")


def test_clock_protocol_supports_substitution() -> None:
    fixed = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

    class FakeClock:
        def now(self) -> datetime:
            return fixed

    clock: ClockProtocol = FakeClock()
    assert isinstance(clock, ClockProtocol)
    assert clock.now() == fixed


def test_system_clock_returns_aware_utc_timestamp() -> None:
    timestamp = SystemClock().now()
    assert timestamp.tzinfo is UTC
    assert timestamp.utcoffset() == timedelta(0)


def test_string_enum_values_are_stable_and_unknown_values_fail() -> None:
    assert ExampleState.READY.value == "ready"
    with pytest.raises(ValueError):
        ExampleState("unknown")
