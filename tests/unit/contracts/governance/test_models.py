from __future__ import annotations

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from pydantic import ValidationError

from tests.unit.contracts.intelligence.fixtures import make_contracts

NAMES = (
    "TradingCampaign",
    "CampaignState",
    "OpportunityCandidate",
    "PositionThesis",
    "GovernanceContext",
)


@pytest.mark.parametrize("name", NAMES)
def test_valid_strict_frozen_contract(name: str) -> None:
    value = make_contracts()[name]
    restored = type(value).model_validate_json(value.model_dump_json())
    assert restored == value
    assert compute_payload_hash(restored) == compute_payload_hash(value)
    with pytest.raises(ValidationError):
        type(value).model_validate({**value.model_dump(), "extra": 1})


@pytest.mark.parametrize("name", NAMES)
def test_version_is_required_literal(name: str) -> None:
    value = make_contracts()[name]
    raw = value.model_dump()
    del raw["schema_version"]
    with pytest.raises(ValidationError):
        type(value).model_validate(raw)
    with pytest.raises(ValidationError):
        type(value).model_validate({**value.model_dump(), "schema_version": "1"})
