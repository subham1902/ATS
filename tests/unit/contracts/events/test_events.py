"""Unit tests for strict A03 payload and envelope contracts."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ats.contracts.events import (
    EVENT_PAYLOAD_MODELS,
    EVENT_REGISTRY,
    EventEnvelope,
    EventType,
    PolicyDraftedPayload,
    ReconciliationCompletedPayload,
    create_event,
)
from ats.contracts.hashing import canonical_sha256
from pydantic import ValidationError

from .fixtures import HASH_A, NOW, TRACE_ID, make_event, make_payloads, uid


def _envelope_data(event: EventEnvelope) -> dict[str, object]:
    data = event.model_dump(exclude={"payload"})
    data["payload"] = event.payload
    return data


@pytest.mark.parametrize("payload_model", EVENT_PAYLOAD_MODELS)
def test_payload_is_strict_frozen_and_json_round_trips(payload_model) -> None:  # type: ignore[no-untyped-def]
    payload = next(value for value in make_payloads().values() if type(value) is payload_model)
    with pytest.raises(ValidationError):
        payload_model.model_validate({**payload.model_dump(), "unexpected": "value"})
    with pytest.raises(ValidationError):
        payload.model_copy().payload_hash = HASH_A  # type: ignore[attr-defined,misc]
    assert payload_model.model_validate_json(payload.model_dump_json()) == payload
    assert payload_model.model_json_schema()["type"] == "object"


def test_envelope_has_exact_frozen_fields_and_round_trips() -> None:
    event = make_event(EventType.CANDIDATE_CREATED)
    assert tuple(EventEnvelope.model_fields) == (
        "event_id",
        "event_type",
        "event_version",
        "aggregate_id",
        "causation_id",
        "correlation_id",
        "sequence",
        "occurred_at",
        "recorded_at",
        "producer",
        "schema_version",
        "payload",
        "payload_hash",
        "trace_id",
    )
    assert EventEnvelope.model_validate_json(event.model_dump_json()) == event
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate({**_envelope_data(event), "extra": True})
    with pytest.raises(ValidationError):
        event.sequence = 2  # type: ignore[misc]


@pytest.mark.parametrize("version", [0, 2])
def test_event_version_is_exactly_one(version: int) -> None:
    event = make_event(EventType.CANDIDATE_CREATED)
    with pytest.raises(ValidationError):
        EventEnvelope(**{**_envelope_data(event), "event_version": version})


def test_unknown_event_type_and_raw_dict_payload_are_rejected() -> None:
    event = make_event(EventType.CANDIDATE_CREATED)
    with pytest.raises(ValidationError):
        EventEnvelope(**{**_envelope_data(event), "event_type": "UNKNOWN_EVENT"})
    with pytest.raises(ValidationError, match="instantiated registered payload"):
        EventEnvelope(**{**event.model_dump(), "payload": event.payload.model_dump()})


def test_wrong_payload_and_producer_are_rejected() -> None:
    event = make_event(EventType.CANDIDATE_CREATED)
    wrong_payload = make_payloads()[EventType.RISK_EVALUATED]
    with pytest.raises(ValidationError, match="does not match payload model"):
        EventEnvelope(
            **{
                **event.model_dump(exclude={"payload", "payload_hash"}),
                "payload": wrong_payload,
                "payload_hash": canonical_sha256(wrong_payload),
            }
        )
    with pytest.raises(ValidationError, match="producer"):
        EventEnvelope(**{**_envelope_data(event), "producer": "market"})


def test_envelope_time_sequence_trace_and_hash_validation() -> None:
    event = make_event(EventType.CANDIDATE_CREATED)
    invalid_cases = (
        {"sequence": 0},
        {"occurred_at": NOW.replace(tzinfo=None)},
        {"recorded_at": NOW - timedelta(microseconds=1)},
        {"trace_id": ""},
        {"trace_id": "0" * 32},
        {"payload_hash": HASH_A},
        {"schema_version": "2.0"},
    )
    for update in invalid_cases:
        with pytest.raises(ValidationError):
            EventEnvelope(**{**_envelope_data(event), **update})


def test_factory_has_no_ambient_values_and_computes_payload_hash() -> None:
    payload = make_payloads()[EventType.FEATURES_READY]
    event = create_event(
        event_id=uid("factory-event"),
        event_type=EventType.FEATURES_READY,
        aggregate_id=uid("factory-aggregate"),
        correlation_id=uid("factory-correlation"),
        sequence=1,
        occurred_at=NOW,
        recorded_at=NOW,
        producer="features",
        payload=payload,
        trace_id=TRACE_ID,
    )
    assert event.payload_hash == canonical_sha256(payload)


def test_literal_and_decimal_boundaries() -> None:
    drafted = make_payloads()[EventType.POLICY_DRAFTED]
    assert isinstance(drafted, PolicyDraftedPayload)
    with pytest.raises(ValidationError):
        PolicyDraftedPayload(**{**drafted.model_dump(), "executable": True})
    completed = make_payloads()[EventType.RECONCILIATION_COMPLETED]
    assert isinstance(completed, ReconciliationCompletedPayload)
    with pytest.raises(ValidationError):
        ReconciliationCompletedPayload(**{**completed.model_dump(), "differences": 1})
    intent = make_payloads()[EventType.ORDER_INTENT_CREATED]
    with pytest.raises(ValidationError):
        type(intent)(**{**intent.model_dump(), "quantity": 1.5})
    assert intent.quantity == Decimal("2")


@pytest.mark.parametrize(
    ("event_type", "field", "invalid"),
    [
        (EventType.MARKET_SNAPSHOT_READY, "timeframe", "1m"),
        (EventType.POLICY_ACTIVATED, "activation_mode", "A3_LIVE"),
        (EventType.AUTONOMY_GRANTED, "scope", "A3_LIVE"),
        (EventType.PAPER_ORDER_ACCEPTED, "status", "FILLED"),
        (EventType.PAPER_ORDER_REJECTED, "status", "ACCEPTED"),
        (EventType.PAPER_ORDER_FILLED, "status", "PARTIALLY_FILLED"),
    ],
)
def test_catalogue_literals_are_closed(event_type: EventType, field: str, invalid: str) -> None:
    payload = make_payloads()[event_type]
    with pytest.raises(ValidationError):
        type(payload)(**{**payload.model_dump(), field: invalid})


def test_failure_payload_requires_a_difference_and_reason() -> None:
    payload = make_payloads()[EventType.RECONCILIATION_FAILED]
    with pytest.raises(ValidationError):
        type(payload)(**{**payload.model_dump(), "difference_count": 0})
    with pytest.raises(ValidationError):
        type(payload)(**{**payload.model_dump(), "reason_codes": ()})


def test_registry_is_immutable() -> None:
    with pytest.raises(TypeError):
        EVENT_REGISTRY[(EventType.CANDIDATE_CREATED, 1)] = EVENT_REGISTRY[  # type: ignore[index]
            (EventType.RISK_EVALUATED, 1)
        ]
