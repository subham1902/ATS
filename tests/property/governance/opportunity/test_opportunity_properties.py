"""Deterministic boundary properties for R10 evidence construction."""

from __future__ import annotations

from decimal import Decimal

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.governance.opportunity import (
    OpportunityConstructionStatus,
    OpportunityEconomicsFacts,
    construct_opportunity_candidate,
)

from tests.unit.governance.opportunity.helpers import bound_inputs


@pytest.mark.parametrize("net_pnl", (Decimal("0"), Decimal("-0.01")))
def test_non_positive_selector_edge_never_creates_candidate(net_pnl: Decimal) -> None:
    values = bound_inputs()
    instrument = values["instrument_candidate"].model_copy(
        update={"expected_net_pnl": net_pnl, "payload_hash": "0" * 64}
    )
    values["instrument_candidate"] = instrument.model_copy(
        update={"payload_hash": compute_payload_hash(instrument)}
    )

    result = construct_opportunity_candidate(**values)

    assert result.status is OpportunityConstructionStatus.INELIGIBLE
    assert result.reason_codes == ("INSTRUMENT_EDGE_NON_POSITIVE",)


@pytest.mark.parametrize(
    ("maximum_loss", "expected_reward"),
    ((Decimal("1"), Decimal("1")), (Decimal("6500"), Decimal("13000"))),
)
def test_reward_and_edge_are_derived_only_from_explicit_economics(
    maximum_loss: Decimal, expected_reward: Decimal
) -> None:
    values = bound_inputs()
    values["economics"] = OpportunityEconomicsFacts(
        maximum_loss=maximum_loss,
        expected_reward=expected_reward,
        proposed_stop_price=Decimal("80"),
        proposed_target_price=Decimal("130"),
    )

    result = construct_opportunity_candidate(**values)

    assert result.candidate is not None
    assert result.candidate.expected_reward_risk == expected_reward / maximum_loss
    assert result.candidate.expected_net_edge_r > 0
