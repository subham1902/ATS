"""R11 emits the frozen advisory PositionThesis contract and no execution command."""

from __future__ import annotations

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.governance.models import PositionThesis
from ats.governance.position import evaluate_position

from tests.unit.governance.position.helpers import observation


def test_position_governor_emits_hashed_frozen_contract() -> None:
    result = evaluate_position(observation())

    assert isinstance(result.thesis, PositionThesis)
    assert compute_payload_hash(result.thesis) == result.thesis.payload_hash
