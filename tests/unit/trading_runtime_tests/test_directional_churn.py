from __future__ import annotations

from datetime import UTC, datetime

from ats.trading_runtime.anti_churn import AntiChurnConfig, ChurnFacts, evaluate_churn


def test_same_direction_churn_blocked() -> None:
    now = datetime.now(UTC)
    config = AntiChurnConfig(
        suppress_same_direction_reentry=True,
        same_direction_cooldown_minutes=30,
        same_instrument_cooldown_minutes=15,
        cooldown_after_exit_bars=3,
    )

    # Exited BULLISH 10 minutes ago, trying to enter BULLISH again (blocked)
    facts_same = ChurnFacts(
        instrument_id="NIFTY",
        direction="BULLISH",
        thesis_id=None,
        expected_edge_r=0.25,
        spread_ticks=2,
        bars_since_exit_same_instrument=5,
        minutes_since_exit_same_instrument=10,
        campaign_trades_started=0,
        evaluation_time=now,
        last_exit_direction="BULLISH",
    )
    res_same = evaluate_churn(config=config, facts=facts_same)
    assert not res_same.allowed
    assert "DIRECTIONAL_CHURN_SUPPRESSED" in res_same.reason_codes


def test_opposite_direction_after_exit_allowed_if_cooldown_passed() -> None:
    now = datetime.now(UTC)
    config = AntiChurnConfig(
        suppress_same_direction_reentry=True,
        same_direction_cooldown_minutes=30,
        same_instrument_cooldown_minutes=15,
        cooldown_after_exit_bars=3,
    )

    # Exited BULLISH 20 minutes ago (past 15 min general cooldown, but within 30 min directional cooldown)
    # Trying to enter BEARISH -> allowed because direction is different!
    facts_opposite = ChurnFacts(
        instrument_id="NIFTY",
        direction="BEARISH",
        thesis_id=None,
        expected_edge_r=0.25,
        spread_ticks=2,
        bars_since_exit_same_instrument=5,
        minutes_since_exit_same_instrument=20,
        campaign_trades_started=0,
        evaluation_time=now,
        last_exit_direction="BULLISH",
    )
    res_opposite = evaluate_churn(config=config, facts=facts_opposite)
    assert res_opposite.allowed
