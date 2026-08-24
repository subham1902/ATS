from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.governance.types import CampaignStatus
from ats.governance.campaign import (
    CampaignRuntimeConfiguration,
    CampaignRuntimeError,
    mark_campaign_to_market,
    record_trade_completed,
    record_trade_started,
    registered_campaign_transitions,
    transition_campaign,
)
from ats.kernel.types import ALLOW, GateCode, KernelOutcome, KernelResult

from tests.unit.contracts.intelligence.fixtures import T0

from .helpers import campaign, state

CONFIG = CampaignRuntimeConfiguration(bar_duration_ms=300_000)


def start(current=None, **overrides: object):
    active_campaign = campaign()
    arguments = {
        "campaign": active_campaign,
        "state": current or state(active_campaign),
        "authorization": ALLOW,
        "committed_capital": Decimal("1000"),
        "occurred_at": T0,
    }
    arguments.update(overrides)
    return record_trade_started(**arguments)  # type: ignore[arg-type]


def test_initial_state_is_deterministic_and_hash_valid() -> None:
    current = state()
    assert current.status is CampaignStatus.ACTIVE
    assert current.state_version == 1
    assert current.payload_hash == compute_payload_hash(current)
    assert current == state()


def test_trade_start_updates_only_runtime_accounting() -> None:
    updated = start()
    assert updated.trades_started == 1
    assert updated.open_positions == 1
    assert updated.capital_committed == Decimal("1000")
    assert updated.state_version == 2


@pytest.mark.parametrize("outcome", [KernelOutcome.DENY, KernelOutcome.UNKNOWN])
def test_non_allow_cannot_start_trade(outcome: KernelOutcome) -> None:
    result = KernelResult(outcome=outcome, reason_codes=(GateCode.SYSTEM_STATE_DENY,))
    with pytest.raises(CampaignRuntimeError, match="A04"):
        start(authorization=result)


def test_max_trades_is_ceiling_not_quota() -> None:
    completed = transition_campaign(
        campaign(), state(), target=CampaignStatus.COMPLETED, occurred_at=T0
    )
    assert completed.trades_started == 0
    assert completed.status is CampaignStatus.COMPLETED


def test_max_trade_ceiling_blocks_additional_start() -> None:
    limited = campaign(max_trades=1)
    first = record_trade_started(
        limited,
        state(limited),
        authorization=ALLOW,
        committed_capital=Decimal("1"),
        occurred_at=T0,
    )
    with pytest.raises(CampaignRuntimeError, match="trade ceiling"):
        record_trade_started(
            limited,
            first,
            authorization=ALLOW,
            committed_capital=Decimal("1"),
            occurred_at=T0,
        )


def test_concurrency_ceiling_blocks_additional_position() -> None:
    limited = campaign(max_concurrent_positions=1)
    first = record_trade_started(
        limited,
        state(limited),
        authorization=ALLOW,
        committed_capital=Decimal("1"),
        occurred_at=T0,
    )
    with pytest.raises(CampaignRuntimeError, match="concurrent"):
        record_trade_started(
            limited,
            first,
            authorization=ALLOW,
            committed_capital=Decimal("1"),
            occurred_at=T0,
        )


def test_campaign_capital_budget_is_enforced() -> None:
    with pytest.raises(CampaignRuntimeError, match="capital budget"):
        start(committed_capital=Decimal("10001"))


def test_completion_releases_capital_and_records_pnl() -> None:
    active_campaign = campaign()
    opened = start(campaign=active_campaign, state=state(active_campaign))
    completed = record_trade_completed(
        active_campaign,
        opened,
        released_capital=Decimal("1000"),
        realized_trade_pnl=Decimal("250"),
        occurred_at=T0 + timedelta(minutes=5),
        configuration=CONFIG,
    )
    assert completed.trades_completed == 1
    assert completed.open_positions == 0
    assert completed.capital_committed == 0
    assert completed.realized_pnl == Decimal("250")
    assert completed.consecutive_losses == 0


def test_consecutive_losses_start_deterministic_cooldown() -> None:
    active_campaign = campaign()
    current = state(active_campaign)
    for index in range(2):
        opened = record_trade_started(
            active_campaign,
            current,
            authorization=ALLOW,
            committed_capital=Decimal("1"),
            occurred_at=T0 + timedelta(minutes=index * 5),
        )
        current = record_trade_completed(
            active_campaign,
            opened,
            released_capital=Decimal("1"),
            realized_trade_pnl=Decimal("-1"),
            occurred_at=T0 + timedelta(minutes=index * 5 + 1),
            configuration=CONFIG,
        )
    assert current.cooldown_until == T0 + timedelta(minutes=21)
    with pytest.raises(CampaignRuntimeError, match="cooldown"):
        record_trade_started(
            active_campaign,
            current,
            authorization=ALLOW,
            committed_capital=Decimal("1"),
            occurred_at=T0 + timedelta(minutes=10),
        )


def test_positive_completion_resets_consecutive_losses() -> None:
    active_campaign = campaign()
    current = start(campaign=active_campaign, state=state(active_campaign))
    current = current.model_copy(update={"consecutive_losses": 1})
    current = current.model_copy(update={"payload_hash": compute_payload_hash(current)})
    result = record_trade_completed(
        active_campaign,
        current,
        released_capital=Decimal("1000"),
        realized_trade_pnl=Decimal("1"),
        occurred_at=T0 + timedelta(minutes=1),
        configuration=CONFIG,
    )
    assert result.consecutive_losses == 0


def test_drawdown_high_watermark_is_monotonic() -> None:
    active_campaign = campaign()
    first = mark_campaign_to_market(
        active_campaign,
        state(active_campaign),
        unrealized_pnl=Decimal("-10"),
        drawdown=Decimal("0.1"),
        occurred_at=T0,
    )
    second = mark_campaign_to_market(
        active_campaign,
        first,
        unrealized_pnl=Decimal("5"),
        drawdown=Decimal("0.05"),
        occurred_at=T0,
    )
    assert second.maximum_drawdown_observed == Decimal("0.1")
    assert second.unrealized_pnl == Decimal("5")


def test_halt_requires_reason_and_is_terminal() -> None:
    with pytest.raises(CampaignRuntimeError, match="reason"):
        transition_campaign(campaign(), state(), target=CampaignStatus.HALTED, occurred_at=T0)
    halted = transition_campaign(
        campaign(),
        state(),
        target=CampaignStatus.HALTED,
        occurred_at=T0,
        reason_codes=("DAILY_LOSS",),
    )
    assert halted.stop_reason_codes == ("DAILY_LOSS",)
    with pytest.raises(CampaignRuntimeError, match="not registered"):
        transition_campaign(campaign(), halted, target=CampaignStatus.ACTIVE, occurred_at=T0)


def test_frozen_transition_table_has_all_states_and_terminal_sinks() -> None:
    table = registered_campaign_transitions()
    assert set(table) == set(CampaignStatus)
    for terminal in (
        CampaignStatus.REJECTED,
        CampaignStatus.COMPLETED,
        CampaignStatus.HALTED,
        CampaignStatus.EXPIRED,
    ):
        assert table[terminal] == frozenset()


def test_tampered_state_and_backwards_time_fail_closed() -> None:
    changed = state().model_copy(update={"trades_started": 1})
    with pytest.raises(CampaignRuntimeError, match="payload hash"):
        mark_campaign_to_market(
            campaign(),
            changed,
            unrealized_pnl=Decimal("0"),
            drawdown=Decimal("0"),
            occurred_at=T0,
        )
    with pytest.raises(CampaignRuntimeError, match="backwards"):
        mark_campaign_to_market(
            campaign(),
            state(),
            unrealized_pnl=Decimal("0"),
            drawdown=Decimal("0"),
            occurred_at=T0 - timedelta(seconds=1),
        )
