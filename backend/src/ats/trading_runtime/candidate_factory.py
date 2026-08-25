"""Production OpportunityCandidate factory — TEST_ONLY builders over frozen contracts.

No fake domain classes. Every object is a frozen production contract.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid5

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import Side
from ats.contracts.governance.models import OpportunityCandidate
from ats.contracts.governance.types import CandidateStatus

_CANDIDATE_NS = UUID("ba8f10bc-f982-5bcb-909f-b6f422902141")


def build_opportunity_candidate(
    *,
    instrument_id: str,
    campaign_id: UUID,
    campaign_version: int,
    strategy_id: UUID,
    strategy_version: int,
    market_context_id: UUID,
    thesis_id: UUID,
    thesis_version: int,
    distribution_id: UUID,
    side: Side = Side.BUY,
    calibrated_probability: Decimal = Decimal("0.65"),
    expected_edge_r: float = 0.4,
    expected_reward_risk: Decimal = Decimal("2"),
    governor_version: str = "test.v1",
    created_at: UTCDateTime,
    expires_at: UTCDateTime,
) -> OpportunityCandidate:
    identity = ":".join(
        (instrument_id, str(thesis_id), str(campaign_id), str(strategy_id), governor_version)
    )
    value = OpportunityCandidate(
        schema_version="1.0",
        candidate_id=uuid5(_CANDIDATE_NS, identity),
        candidate_version=1,
        instrument_id=instrument_id,
        market_context_id=market_context_id,
        thesis_id=thesis_id,
        thesis_version=thesis_version,
        distribution_id=distribution_id,
        campaign_id=campaign_id,
        campaign_version=campaign_version,
        strategy_definition_id=strategy_id,
        strategy_definition_version=strategy_version,
        side=side,
        event_definition_id=distribution_id,
        horizon_bars=3,
        target_outcome_code="UP",
        calibrated_probability=calibrated_probability,
        expected_net_edge_r=expected_edge_r,
        expected_reward_risk=expected_reward_risk,
        entry_conditions=(),
        proposed_stop_price=Decimal("99"),
        proposed_target_price=Decimal("102"),
        evidence_refs=(thesis_id,),
        status=CandidateStatus.CREATED,
        risk_decision_id=None,
        advisory_id=None,
        autonomy_token_id=None,
        created_at=created_at,
        expires_at=expires_at,
        payload_hash="0" * 64,
    )
    return value.model_copy(update={"payload_hash": compute_payload_hash(value)})


__all__ = ["build_opportunity_candidate"]
