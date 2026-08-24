"""R11 only synthesizes advisory position-thesis evidence."""

from __future__ import annotations

from ats.contracts.domain.types import DataQualityState
from ats.contracts.governance.types import PositionRecommendation, PositionThesisState
from ats.governance.position import evaluate_position

from tests.unit.governance.position.helpers import observation


def test_healthy_position_returns_hold_advice_only() -> None:
    result = evaluate_position(observation())

    assert result.thesis.state is PositionThesisState.HEALTHY
    assert result.thesis.recommended_action is PositionRecommendation.HOLD
    assert result.thesis.reason_codes == ("POSITION_THESIS_HEALTHY",)


def test_invalidated_thesis_recommends_exit_without_creating_exit_intent() -> None:
    result = evaluate_position(observation(invalidation_triggered=True))

    assert result.thesis.state is PositionThesisState.INVALIDATED
    assert result.thesis.recommended_action is PositionRecommendation.EXIT
    assert not hasattr(result, "exit_intent")


def test_unknown_market_evidence_fails_closed_to_unknown_advice() -> None:
    result = evaluate_position(observation(data_quality_state=DataQualityState.UNKNOWN))

    assert result.thesis.state is PositionThesisState.UNKNOWN
    assert result.thesis.recommended_action is PositionRecommendation.UNKNOWN


def test_session_exit_precedes_regular_hold_advice() -> None:
    result = evaluate_position(observation(session_exit_required=True))

    assert result.thesis.state is PositionThesisState.DEGRADING
    assert result.thesis.recommended_action is PositionRecommendation.EXIT
