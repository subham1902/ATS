"""Golden contract tests for A01 canonical serialization and hashing."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from enum import auto
from uuid import UUID

import pytest
from ats.contracts import (
    ATSBaseModel,
    ATSStringEnum,
    FiniteDecimal,
    FiniteFloat,
    OpaqueId,
    UTCDateTime,
    canonical_json_bytes,
    canonical_sha256,
)


class FixtureState(ATSStringEnum):
    READY = auto()


class NestedFixture(ATSBaseModel):
    quantity: FiniteDecimal
    tags: tuple[str, ...]


class SerializationFixture(ATSBaseModel):
    identity: OpaqueId
    timestamp: UTCDateTime
    amount: FiniteDecimal
    state: FixtureState
    nested: NestedFixture
    optional_note: str | None = None


class FloatNestedFixture(ATSBaseModel):
    values: tuple[FiniteFloat, ...]


class MixedNumericFixture(ATSBaseModel):
    financial_value: FiniteDecimal
    analytical_value: FiniteFloat
    identity: OpaqueId
    timestamp: UTCDateTime
    state: FixtureState
    nested: FloatNestedFixture


class FeatureCompatibilityFixture(ATSBaseModel):
    features: dict[str, FiniteFloat]


def fixture() -> SerializationFixture:
    return SerializationFixture(
        identity=UUID("12345678-1234-5678-9234-567812345678"),
        timestamp=datetime(2026, 1, 2, 3, 4, 5, 6000, tzinfo=UTC),
        amount=Decimal("123.4500"),
        state=FixtureState.READY,
        nested=NestedFixture(quantity=Decimal("2.000"), tags=("alpha", "beta")),
    )


def test_canonical_serialization_matches_committed_golden() -> None:
    expected = (
        b'{"amount":"123.45","identity":"12345678-1234-5678-9234-567812345678",'
        b'"nested":{"quantity":"2","tags":["alpha","beta"]},"optional_note":null,'
        b'"state":"ready","timestamp":"2026-01-02T03:04:05.006000Z"}'
    )
    assert canonical_json_bytes(fixture()) == expected
    assert json.loads(expected) == {
        "amount": "123.45",
        "identity": "12345678-1234-5678-9234-567812345678",
        "nested": {"quantity": "2", "tags": ["alpha", "beta"]},
        "optional_note": None,
        "state": "ready",
        "timestamp": "2026-01-02T03:04:05.006000Z",
    }


def test_canonical_hash_matches_committed_golden() -> None:
    assert (
        canonical_sha256(fixture())
        == "423053e554f03f7c5232b429a571c45b8eea902ace903b8b008cbbdb5edb36c1"
    )


def test_mapping_insertion_order_does_not_change_hash() -> None:
    first = {"alpha": Decimal("1.0"), "beta": [1, 2, 3]}
    second = {"beta": [1, 2, 3], "alpha": Decimal("1.00")}
    assert canonical_sha256(first) == canonical_sha256(second)


def test_material_value_change_changes_hash() -> None:
    assert canonical_sha256({"value": Decimal("1")}) != canonical_sha256({"value": Decimal("2")})


def test_decimal_representation_is_stable() -> None:
    representations = (Decimal("1"), Decimal("1.0"), Decimal("1.000"), Decimal("1E+0"))
    assert {canonical_json_bytes(value) for value in representations} == {b'"1"'}
    assert canonical_json_bytes(Decimal("-0.00")) == b'"0"'
    with pytest.raises(ValueError):
        canonical_json_bytes(Decimal("NaN"))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, b"0.0"),
        (-0.0, b"0.0"),
        (1.0, b"1.0"),
        (-1.0, b"-1.0"),
        (0.1, b"0.1"),
        (1.5, b"1.5"),
        (1e-12, b"1e-12"),
        (1e12, b"1000000000000.0"),
        (1.2345678901234567, b"1.2345678901234567"),
    ],
)
def test_finite_float_canonical_goldens(value: float, expected: bytes) -> None:
    assert canonical_json_bytes(value) == expected
    assert canonical_json_bytes(value) == expected


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_float_canonicalization_fails(value: float) -> None:
    with pytest.raises(ValueError):
        canonical_json_bytes(value)


def test_nested_float_payload_matches_committed_golden() -> None:
    first = {"feature_a": 0.125, "feature_b": -2.75}
    second = {"feature_b": -2.75, "feature_a": 0.125}
    expected = b'{"feature_a":0.125,"feature_b":-2.75}'
    expected_hash = "06b19a1d4be1892f79a2398012b5b2be053dc8dc2ecbdc8eaf67d8a33ba004b8"
    assert canonical_json_bytes(first) == expected
    assert canonical_json_bytes(second) == expected
    assert canonical_sha256(first) == expected_hash
    assert canonical_sha256(second) == expected_hash


def test_changed_float_changes_hash() -> None:
    assert canonical_sha256({"feature": 0.125}) != canonical_sha256({"feature": 0.126})


def test_decimal_and_float_have_distinct_canonical_json_types() -> None:
    assert canonical_json_bytes(Decimal("1")) == b'"1"'
    assert canonical_json_bytes(1.0) == b"1.0"


def test_mixed_numeric_payload_matches_committed_golden() -> None:
    value = MixedNumericFixture(
        financial_value=Decimal("10.500"),
        analytical_value=0.1,
        identity=UUID("12345678-1234-5678-9234-567812345678"),
        timestamp=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        state=FixtureState.READY,
        nested=FloatNestedFixture(values=(0.125, -2.75)),
    )
    expected = (
        b'{"analytical_value":0.1,"financial_value":"10.5",'
        b'"identity":"12345678-1234-5678-9234-567812345678",'
        b'"nested":{"values":[0.125,-2.75]},"state":"ready",'
        b'"timestamp":"2026-01-02T03:04:05.000000Z"}'
    )
    assert canonical_json_bytes(value) == expected
    assert (
        canonical_sha256(value)
        == "c6bb983577c4a76f8645b9027c0de782a9a61a992cb6c83c55f30ac4806ca39d"
    )


def test_feature_compatibility_fixture_validates_and_hashes_repeatably() -> None:
    value = FeatureCompatibilityFixture(features={"momentum": 0.125, "volatility": 1.75})
    expected = b'{"features":{"momentum":0.125,"volatility":1.75}}'
    assert canonical_json_bytes(value) == expected
    assert FeatureCompatibilityFixture.model_validate_json(value.model_dump_json()) == value
    first_hash = canonical_sha256(value)
    assert first_hash == "1af826337970ddd811592f9ffe6c49f49d9e926969194ac8001a3d6f5ffc336a"
    assert canonical_sha256(value) == first_hash


def test_equivalent_utc_instants_are_stable() -> None:
    utc_value = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    offset_value = datetime(
        2026,
        1,
        2,
        8,
        34,
        5,
        tzinfo=timezone(timedelta(hours=5, minutes=30)),
    )
    assert canonical_json_bytes(utc_value) == b'"2026-01-02T03:04:05.000000Z"'
    assert canonical_sha256(utc_value) == canonical_sha256(offset_value)
    with pytest.raises(ValueError):
        canonical_json_bytes(datetime(2026, 1, 2, 3, 4, 5))


def test_uuid_and_enum_serialization_are_stable() -> None:
    identity = UUID("12345678-1234-5678-9234-567812345678")
    assert canonical_json_bytes(identity) == b'"12345678-1234-5678-9234-567812345678"'
    assert canonical_json_bytes(FixtureState.READY) == b'"ready"'


def test_nested_model_serialization_is_repeatable() -> None:
    first = fixture()
    second = SerializationFixture.model_validate(first.model_dump())
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert canonical_sha256(first) == canonical_sha256(second)


def test_unsupported_values_are_rejected() -> None:
    with pytest.raises(TypeError):
        canonical_json_bytes({1: "not-a-string-key"})
    with pytest.raises(TypeError):
        canonical_json_bytes({"unordered"})
