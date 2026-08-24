"""R10 candidate lineage can be monitored by R11 without creating execution authority."""

from __future__ import annotations

from ats.governance.position import evaluate_position

from tests.unit.governance.position.helpers import observation


def test_r10_to_r11_lineage_preserves_advisory_only_boundary() -> None:
    result = evaluate_position(observation())

    assert result.thesis.originating_candidate_id
    assert result.thesis.recommended_action.value == "HOLD"
