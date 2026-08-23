"""Contract evidence for exact event catalogue coverage and binding."""

from __future__ import annotations

import json
from pathlib import Path

from ats.contracts.events import (
    EVENT_PAYLOAD_MODELS,
    EVENT_REGISTRY,
    EVENT_REGISTRY_ENTRIES,
    EventEnvelope,
    EventType,
)

MANIFEST = Path(__file__).with_name("event_catalogue.json")


def test_registry_exactly_matches_machine_readable_catalogue() -> None:
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(rows) == len(EventType) == len(EVENT_REGISTRY) == 24
    assert len({row["event_type"] for row in rows}) == 24
    assert len({(row["event_type"], row["event_version"]) for row in rows}) == 24
    for row, entry in zip(rows, EVENT_REGISTRY_ENTRIES, strict=True):
        assert row == {
            "seq": entry.catalogue_sequence,
            "event_type": entry.event_type.value,
            "event_version": entry.event_version,
            "aggregate": entry.aggregate,
            "producer": entry.producer,
            "payload_fields": list(entry.payload_fields),
            "payload_model": entry.payload_model.__name__,
            "idempotency": entry.idempotency,
            "transition": entry.transition,
        }


def test_all_25_json_schemas_export() -> None:
    schemas = [EventEnvelope.model_json_schema()]
    schemas.extend(model.model_json_schema() for model in EVENT_PAYLOAD_MODELS)
    assert len(schemas) == 25
    assert all(schema["type"] == "object" for schema in schemas)


def test_all_registry_keys_are_version_one_and_payload_fields_are_exact() -> None:
    assert all(version == 1 for _, version in EVENT_REGISTRY)
    assert all(
        entry.payload_fields == tuple(entry.payload_model.model_fields)
        for entry in EVENT_REGISTRY_ENTRIES
    )
