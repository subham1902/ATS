from __future__ import annotations

from decimal import Decimal

from ats.governance.campaign import mark_campaign_to_market

from tests.unit.contracts.intelligence.fixtures import T0
from tests.unit.governance.campaign.helpers import campaign, state


def test_identical_transition_is_deterministic() -> None:
    active_campaign = campaign()
    current = state(active_campaign)
    first = mark_campaign_to_market(
        active_campaign,
        current,
        unrealized_pnl=Decimal("1"),
        drawdown=Decimal("0.01"),
        occurred_at=T0,
    )
    second = mark_campaign_to_market(
        active_campaign,
        current,
        unrealized_pnl=Decimal("1"),
        drawdown=Decimal("0.01"),
        occurred_at=T0,
    )
    assert first.model_dump_json() == second.model_dump_json()


def test_state_version_only_moves_forward() -> None:
    active_campaign = campaign()
    current = state(active_campaign)
    updated = mark_campaign_to_market(
        active_campaign,
        current,
        unrealized_pnl=Decimal("0"),
        drawdown=Decimal("0"),
        occurred_at=T0,
    )
    assert updated.state_version == current.state_version + 1
