"""Contract-facing checks for R10's frozen evidence-only output."""

from __future__ import annotations

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.governance.models import OpportunityCandidate
from ats.governance.opportunity import construct_opportunity_candidate

from tests.unit.governance.opportunity.helpers import bound_inputs


def test_output_is_the_frozen_opportunity_candidate_contract() -> None:
    result = construct_opportunity_candidate(**bound_inputs())

    assert isinstance(result.candidate, OpportunityCandidate)
    assert result.candidate is not None
    assert result.candidate.schema_version == "1.0"
    assert compute_payload_hash(result.candidate) == result.candidate.payload_hash


def test_output_cannot_embed_authority_before_a04() -> None:
    result = construct_opportunity_candidate(**bound_inputs())
    assert result.candidate is not None

    assert result.candidate.risk_decision_id is None
    assert result.candidate.advisory_id is None
    assert result.candidate.autonomy_token_id is None
