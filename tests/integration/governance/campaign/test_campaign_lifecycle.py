from __future__ import annotations

from decimal import Decimal

from ats.governance.campaign import record_trade_started
from ats.kernel.types import ALLOW

from tests.unit.contracts.intelligence.fixtures import T0
from tests.unit.governance.campaign.helpers import campaign, state


def test_a04_allow_to_campaign_trade_accounting_boundary() -> None:
    active_campaign = campaign()
    updated = record_trade_started(
        active_campaign,
        state(active_campaign),
        authorization=ALLOW,
        committed_capital=Decimal("1000"),
        occurred_at=T0,
    )
    assert updated.trades_started == 1
    assert updated.open_positions == 1
    assert updated.capital_committed == Decimal("1000")
