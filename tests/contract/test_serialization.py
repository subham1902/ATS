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
    assert canonical_sha256(fixture()) == "423053e554f03f7c5232b429a571c45b8eea902ace903b8b008cbbdb5edb36c1"


def test_mapping_insertion_order_does_not_change_hash() -> None:
    first = {"alpha": Decimal("1.0"), "beta": [1, 2, 3]}
    second = {"beta": [1, 2, 3], "alpha": Decimal("1.00")}
    assert canonical_sha256(first) == canonical_sha256(second)


def test_material_value_change_changes_hash() -> None:
    assert canonical_sha256({"value": Decimal("1")}) != canonical_sha256(
        {"value": Decimal("2")}
    )


def test_decimal_representation_is_stable() -> None:
    representations = (Decimal("1"), Decimal("1.0"), Decimal("1.000"), Decimal("1E+0"))
    assert {canonical_json_bytes(value) for value in representations} == {b'"1"'}
    assert canonical_json_bytes(Decimal("-0.00")) == b'"0"'
    with pytest.raises(ValueError):
        canonical_json_bytes(Decimal("NaN"))
    with pytest.raises(TypeError):
        canonical_json_bytes(0.1)


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
