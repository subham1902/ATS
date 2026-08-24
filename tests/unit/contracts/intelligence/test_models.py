from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError

from ats.contracts.domain.hashing import compute_payload_hash
from tests.unit.contracts.intelligence.fixtures import make_contracts

NAMES = (
    "InstrumentSpec", "MarketContext", "RegimeEvidence", "AnalogueEvidence",
    "EnsembleForecast", "CalibratedOutcomeDistribution", "MarketThesis",
    "AnalystAssessment", "StrategyDefinition", "FormulaDefinition", "StrategyExperiment",
    "StrategyScorecard", "PromotionDecision", "PerformanceAttribution", "ExplanationEvidence",
)


@pytest.mark.parametrize("name", NAMES)
def test_valid_frozen_round_trip_schema_and_hash(name: str) -> None:
    value = make_contracts()[name]
    cls = type(value)
    restored = cls.model_validate_json(value.model_dump_json())
    assert restored == value
    assert cls.model_json_schema()["properties"]["schema_version"]["const"] == "1.0"
    assert compute_payload_hash(value) == compute_payload_hash(restored)
    changed_hash = {**value.model_dump(), "payload_hash": "f" * 64}
    assert compute_payload_hash(changed_hash) == compute_payload_hash(value)
    with pytest.raises((ValidationError, TypeError, FrozenInstanceError)):
        value.payload_hash = "f" * 64  # type: ignore[misc]


@pytest.mark.parametrize("name", NAMES)
def test_extra_field_and_schema_mismatch_rejected(name: str) -> None:
    value = make_contracts()[name]
    with pytest.raises(ValidationError):
        type(value).model_validate({**value.model_dump(), "unexpected": True})
    with pytest.raises(ValidationError):
        type(value).model_validate({**value.model_dump(), "schema_version": "2.0"})


@pytest.mark.parametrize("name", NAMES)
def test_authoritative_change_changes_hash(name: str) -> None:
    value = make_contracts()[name]
    preimage = value.model_dump()
    preimage["evidence_change"] = name
    assert compute_payload_hash(preimage) != compute_payload_hash(value)
