"""Tests for the risk layer: kill switch, circuit breakers, and sizing limits."""

from __future__ import annotations

import pytest
from ats.agents.risk import (
    GLOBAL_KILL_SWITCH,
    KillSwitch,
    RiskLimits,
    RiskManager,
    correlation,
)

#: Captured at import time, before any fixture mutates the global switch.
_IMPORT_TIME_TRADING_ENABLED = GLOBAL_KILL_SWITCH.armed


@pytest.fixture(autouse=True)
def _armed():
    """Each test starts with the kill switch released so risk logic is reachable."""
    GLOBAL_KILL_SWITCH.release("test fixture")
    yield
    GLOBAL_KILL_SWITCH.engage("test teardown")


def test_kill_switch_defaults_to_disarmed():
    """The safe state is: system refuses to trade until an operator enables it."""
    ks = KillSwitch()
    assert ks.armed is False
    assert not ks.trading_enabled
    assert "DEFAULT SAFE STATE" in ks.reason

    ks.release("operator override")
    assert ks.armed is True
    assert ks.trading_enabled

    ks.engage("halt")
    assert ks.armed is False


def test_global_kill_switch_starts_disarmed():
    """The process-wide switch must not permit trading on startup."""
    assert _IMPORT_TIME_TRADING_ENABLED is False


def test_kill_switch_blocks_all_entries():
    r = RiskManager()
    GLOBAL_KILL_SWITCH.engage("operator halt")
    d = r.can_trade("Alpha", principal=100_000.0)
    assert not d.allowed
    assert d.reason_code == "GLOBAL_KILL_SWITCH"


def test_daily_loss_limit_halts_agent():
    r = RiskManager(RiskLimits(max_daily_loss_pct=5.0))
    r.register_principal("Alpha", 100_000.0)
    # Lose 6% of capital in one trade.
    r.record_trade("Alpha", principal=100_000.0, net_pnl=-6_000.0)
    d = r.can_trade("Alpha", principal=100_000.0)
    assert not d.allowed
    assert "DAILY_LOSS" in d.reason
    assert d.reason_code == "CIRCUIT_BREAKER_TRIPPED"


def test_consecutive_loss_streak_breaker():
    r = RiskManager(RiskLimits(max_consecutive_losses=3, max_daily_loss_pct=99.0))
    r.register_principal("Alpha", 100_000.0)
    for _ in range(3):
        r.record_trade("Alpha", principal=100_000.0, net_pnl=-100.0)
    d = r.can_trade("Alpha", principal=100_000.0)
    assert not d.allowed
    assert "consecutive losses" in d.reason


def test_win_resets_consecutive_losses():
    r = RiskManager(RiskLimits(max_consecutive_losses=3))
    r.register_principal("Alpha", 100_000.0)
    r.record_trade("Alpha", principal=100_000.0, net_pnl=-100.0)
    r.record_trade("Alpha", principal=100_000.0, net_pnl=-100.0)
    r.record_trade("Alpha", principal=100_000.0, net_pnl=500.0)
    assert r.can_trade("Alpha", principal=100_000.0).allowed


def test_trade_frequency_cap():
    r = RiskManager(RiskLimits(max_trades_per_day=2, min_seconds_between_entries=0.0))
    r.register_principal("Alpha", 100_000.0)
    r.record_trade("Alpha", principal=100_000.0, net_pnl=100.0)
    r.record_trade("Alpha", principal=100_000.0, net_pnl=100.0)
    d = r.can_trade("Alpha", principal=100_000.0)
    assert not d.allowed
    assert "Daily trade cap" in d.reason


def test_cooldown_blocks_rapid_reentry():
    r = RiskManager(RiskLimits(min_seconds_between_entries=900.0))
    r.register_principal("Alpha", 100_000.0)
    r.on_entry("Alpha", principal=100_000.0, margin=45_000.0, now_ts=1000.0)
    d = r.can_trade("Alpha", principal=100_000.0, now_ts=1100.0)
    assert not d.allowed
    assert "Cooldown" in d.reason


def test_drawdown_halt():
    r = RiskManager(RiskLimits(max_total_loss_pct=20.0, max_daily_loss_pct=99.0))
    r.register_principal("Alpha", 100_000.0)
    r.record_trade("Alpha", principal=100_000.0, net_pnl=10_000.0)  # peak 110k
    r.record_trade("Alpha", principal=100_000.0, net_pnl=-25_000.0)  # 85k, -23% from peak
    d = r.can_trade("Alpha", principal=100_000.0)
    assert not d.allowed


def test_margin_utilisation_cap():
    r = RiskManager(RiskLimits(max_margin_utilisation_pct=50.0))
    r.register_principal("Alpha", 100_000.0)
    # 45k margin on 100k capital is 45%; a second 45k would be 90%.
    d = r.can_trade("Alpha", principal=100_000.0, proposed_margin=45_000.0)
    assert d.allowed
    d2 = r.can_trade("Alpha", principal=100_000.0, proposed_margin=90_000.0)
    assert not d2.allowed


def test_correlation_function():
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [2.0, 4.0, 6.0, 8.0, 10.0]
    assert correlation(a, b) == pytest.approx(1.0)
    assert correlation(a, [-x for x in b]) == pytest.approx(-1.0)
    assert correlation(a, [5.0, 5.0, 5.0, 5.0, 5.0]) == 0.0
    assert correlation(a, [1.0]) == 0.0


def test_correlation_cap_blocks_concentrated_entry():
    r = RiskManager(RiskLimits(max_pair_correlation=0.6))
    rets = [0.01, 0.02, -0.01, 0.03, 0.005, -0.02, 0.01]
    ok, reason, code = r.correlation_allowed(
        proposed_returns=rets, other_positions=[("Bravo", list(rets))]
    )
    assert not ok
    assert code == "CORRELATED_EXPOSURE_LIMIT"


def test_blocked_signals_are_recorded_for_audit():
    r = RiskManager(RiskLimits(max_trades_per_day=0))
    r.register_principal("Alpha", 100_000.0)
    r.can_trade("Alpha", principal=100_000.0)
    s = r.summary()
    assert s["blocked_signals"]["total"] >= 1
    assert "MAX_TRADES_PER_DAY_REACHED" in s["blocked_signals"]["by_code"]


def test_portfolio_halt_on_aggregate_drawdown():
    r = RiskManager(
        RiskLimits(max_portfolio_drawdown_pct=10.0, max_daily_loss_pct=99.0)
    )
    for n in ("Alpha", "Bravo", "Charlie"):
        r.register_principal(n, 100_000.0)
    r.record_trade("Alpha", principal=100_000.0, net_pnl=50_000.0)
    r.record_trade("Bravo", principal=100_000.0, net_pnl=50_000.0)
    r.record_trade("Alpha", principal=100_000.0, net_pnl=-40_000.0)
    r.record_trade("Bravo", principal=100_000.0, net_pnl=-40_000.0)
    d = r.can_trade("Charlie", principal=100_000.0)
    assert not d.allowed
