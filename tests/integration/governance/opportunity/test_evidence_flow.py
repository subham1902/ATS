"""R10 integrates selector evidence into a frozen OpportunityCandidate only."""

from __future__ import annotations

from ats.governance.opportunity import (
    OpportunityConstructionStatus,
    construct_opportunity_candidate,
)

from tests.unit.governance.opportunity.helpers import bound_inputs


def test_selector_to_candidate_flow_has_no_authority_references() -> None:
    result = construct_opportunity_candidate(**bound_inputs())

    assert result.status is OpportunityConstructionStatus.ELIGIBLE_CANDIDATE
    assert result.candidate is not None
    assert result.candidate.risk_decision_id is None
    assert result.candidate.advisory_id is None
    assert result.candidate.autonomy_token_id is None
