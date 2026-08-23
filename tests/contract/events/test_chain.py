"""Deterministic golden-chain and integrity evidence for A03."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ats.contracts.events import EventEnvelope, EventType, validate_event_chain
from ats.contracts.hashing import canonical_json_bytes, canonical_sha256
from pydantic import ValidationError

from tests.unit.contracts.events.fixtures import HASH_A, make_golden_chain, make_payloads, uid


def _replace(event: EventEnvelope, **updates: object) -> EventEnvelope:
    data = event.model_dump(exclude={"payload"})
    data["payload"] = event.payload
    data.update(updates)
    return EventEnvelope(**data)


def test_golden_chain_is_stable_and_valid() -> None:
    first = make_golden_chain()
    second = make_golden_chain()
    validate_event_chain(first)
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert [event.sequence for event in first] == [1, 2, 3, 4, 1]
    assert len({event.correlation_id for event in first}) == 1
    assert first[0].causation_id is None
    assert [event.causation_id for event in first[1:]] == [event.event_id for event in first[:-1]]


def test_chain_rejects_correlation_causation_duplicate_and_gap() -> None:
    chain = list(make_golden_chain())
    cases = []
    cases.append(
        [chain[0], _replace(chain[1], correlation_id=uid("wrong-correlation")), *chain[2:]]
    )
    cases.append([chain[0], _replace(chain[1], causation_id=uid("wrong-cause")), *chain[2:]])
    cases.append([chain[0], _replace(chain[1], sequence=1), *chain[2:]])
    cases.append([chain[0], _replace(chain[1], sequence=3), *chain[2:]])
    for invalid in cases:
        with pytest.raises(ValueError):
            validate_event_chain(invalid)


def test_new_aggregate_restarts_at_one() -> None:
    validate_event_chain(make_golden_chain())
    assert make_golden_chain()[-1].sequence == 1


def test_payload_hash_covers_payload_only_and_nested_domain_hash_is_distinct() -> None:
    payload = make_payloads()[EventType.MARKET_SNAPSHOT_READY]
    chain = make_golden_chain()
    assert payload.payload_hash == HASH_A
    assert canonical_sha256(payload) != payload.payload_hash
    assert chain[0].payload_hash == canonical_sha256(chain[0].payload)
    changed = payload.model_copy(update={"sequence": 2})
    assert canonical_sha256(changed) != canonical_sha256(payload)
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})


def test_invalid_hash_cannot_be_constructed() -> None:
    event = make_golden_chain()[0]
    data = event.model_dump(exclude={"payload"})
    data["payload"] = event.payload
    with pytest.raises(ValidationError):
        EventEnvelope(**{**data, "payload_hash": HASH_A})


def test_chain_validator_rejects_a_corrupted_existing_envelope() -> None:
    chain = list(make_golden_chain())
    chain[0] = chain[0].model_copy(update={"payload_hash": HASH_A})
    with pytest.raises(ValueError, match="payload hash mismatch"):
        validate_event_chain(chain)


def test_literal_golden_hashes_and_envelope_bytes() -> None:
    chain = make_golden_chain()
    golden = json.loads(Path(__file__).with_name("golden_chain.json").read_text(encoding="utf-8"))
    actual = [json.loads(canonical_json_bytes(event)) for event in chain]
    assert actual == golden
    assert [event.payload_hash for event in chain] == [row["payload_hash"] for row in golden]
