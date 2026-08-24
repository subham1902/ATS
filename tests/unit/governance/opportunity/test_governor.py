"""Unit coverage for deterministic, evidence-only opportunity construction."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ats.contracts.governance.types import CampaignStatus
from ats.governance.opportunity import (
    OpportunityConstructionStatus,
    OpportunityGovernorError,
    construct_opportunity_candidate,
)

from tests.unit.governance.opportunity.helpers import _rehash, bound_inputs


def construct(**updates: object):
    values = bound_inputs()
    values.update(updates)
    return construct_opportunity_candidate(**values)


def test_constructs_exact_eligible_evidence_candidate() -> None:
    result = construct()

    assert result.status is OpportunityConstructionStatus.ELIGIBLE_CANDIDATE
    assert result.candidate is not None
    assert result.candidate.status.value == "ELIGIBLE"
    assert result.candidate.risk_decision_id is None
    assert result.candidate.advisory_id is None
    assert result.candidate.autonomy_token_id is None
    assert result.candidate.payload_hash


def test_repetition_is_deterministic() -> None:
    first = construct()
    second = construct()

    assert first == second


@pytest.mark.parametrize(
    ("field", "reason"),
    (
        ("status", "CAMPAIGN_NOT_ACTIVE"),
        ("cooldown_until", "CAMPAIGN_COOLDOWN"),
        ("trades_started", "CAMPAIGN_TRADE_CEILING"),
        ("open_positions", "CAMPAIGN_CONCURRENCY_CEILING"),
    ),
)
def test_campaign_gates_return_evidence_only_ineligibility(field: str, reason: str) -> None:
    values = bound_inputs()
    state = values["campaign_state"]
    if field == "status":
        campaign = _rehash(values["campaign"], status=CampaignStatus.PAUSED)
        values["campaign"] = campaign
    elif field == "cooldown_until":
        values["campaign_state"] = _rehash(
            state, cooldown_until=values["evaluation_time"] + timedelta(minutes=1)
        )
    elif field == "trades_started":
        campaign = values["campaign"]
        values["campaign_state"] = _rehash(
            state,
            trades_started=campaign.max_trades,
            trades_completed=campaign.max_trades,
            open_positions=0,
        )
    else:
        campaign = values["campaign"]
        values["campaign_state"] = _rehash(
            state,
            trades_started=campaign.max_concurrent_positions,
            open_positions=campaign.max_concurrent_positions,
        )

    result = construct_opportunity_candidate(**values)
    assert result.status is OpportunityConstructionStatus.INELIGIBLE
    assert result.candidate is None
    assert result.reason_codes == (reason,)


def test_strategy_must_be_campaign_and_derivative_compatible() -> None:
    values = bound_inputs()
    strategy = _rehash(values["strategy"], compatible_instruments=("OTHER",))

    result = construct(strategy=strategy)

    assert result.status is OpportunityConstructionStatus.INELIGIBLE
    assert result.reason_codes == ("STRATEGY_NOT_EXECUTION_ELIGIBLE",)


def test_distribution_and_thesis_binding_mismatch_is_hard_failure() -> None:
    values = bound_inputs()
    distribution = _rehash(values["distribution"], instrument_id="OTHER")

    with pytest.raises(OpportunityGovernorError, match="lineage mismatch"):
        construct(distribution=distribution)


def test_invalid_long_ordering_is_hard_failure() -> None:
    values = bound_inputs()
    economics = values["economics"].__class__.model_validate(
        {**values["economics"].model_dump(), "proposed_stop_price": Decimal("120")}
    )

    with pytest.raises(OpportunityGovernorError, match="ordering"):
        construct(economics=economics)
