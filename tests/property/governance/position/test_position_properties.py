"""Fail-closed state precedence and deterministic output properties for R11."""

from __future__ import annotations

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import PositionStatus
from ats.contracts.governance.types import (
    CandidateStatus,
    PositionRecommendation,
    PositionThesisState,
)
from ats.governance.position import evaluate_position

from tests.unit.governance.position.helpers import observation


def test_repetition_is_deterministic() -> None:
    assert evaluate_position(observation()) == evaluate_position(observation())


@pytest.mark.parametrize(
    ("updates", "state", "recommendation"),
    (
        (
            {"risk_reduction_required": True},
            PositionThesisState.DEGRADING,
            PositionRecommendation.REDUCE,
        ),
        (
            {"session_exit_required": True},
            PositionThesisState.DEGRADING,
            PositionRecommendation.EXIT,
        ),
        (
            {"invalidation_triggered": True},
            PositionThesisState.INVALIDATED,
            PositionRecommendation.EXIT,
        ),
    ),
)
def test_safety_conditions_never_propose_increased_risk(
    updates: dict[str, bool], state: PositionThesisState, recommendation: PositionRecommendation
) -> None:
    result = evaluate_position(observation(**updates))
    assert result.thesis.state is state
    assert result.thesis.recommended_action is recommendation


def test_invalid_candidate_lineage_is_rejected() -> None:
    item = observation()
    candidate = item.originating_candidate.model_copy(
        update={"status": CandidateStatus.CREATED, "payload_hash": "0" * 64}
    )
    candidate = candidate.model_copy(update={"payload_hash": compute_payload_hash(candidate)})
    invalid = item.model_copy(update={"originating_candidate": candidate})

    with pytest.raises(ValueError, match="authorized candidate"):
        evaluate_position(invalid)


def test_closed_position_never_requests_a_new_action() -> None:
    item = observation()
    position = item.position.model_copy(
        update={
            "status": PositionStatus.CLOSED,
            "closed_at": item.evaluation_time,
            "payload_hash": "0" * 64,
        }
    )
    position = position.model_copy(update={"payload_hash": compute_payload_hash(position)})
    result = evaluate_position(item.model_copy(update={"position": position}))

    assert result.thesis.state is PositionThesisState.CLOSED
    assert result.thesis.recommended_action is PositionRecommendation.UNKNOWN
