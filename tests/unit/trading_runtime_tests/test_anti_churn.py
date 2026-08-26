from __future__ import annotations

from datetime import UTC, datetime

from ats.trading_runtime.anti_churn import AntiChurnConfig, ChurnFacts, evaluate_churn


def test_edge_below_threshold_blocked() -> None:
    result = evaluate_churn(
        config=AntiChurnConfig(minimum_expected_edge_r=0.5),
        facts=ChurnFacts(
            instrument_id="NIFTY",
            direction="BULLISH",
            thesis_id=None,
            expected_edge_r=0.1,
            spread_ticks=None,
            bars_since_exit_same_instrument=None,
            minutes_since_exit_same_instrument=None,
            campaign_trades_started=0,
            evaluation_time=datetime.now(UTC),
        ),
    )
    assert not result.allowed


def test_cooldown_blocks() -> None:
    result = evaluate_churn(
        config=AntiChurnConfig(cooldown_after_exit_bars=5),
        facts=ChurnFacts(
            instrument_id="NIFTY",
            direction="BULLISH",
            thesis_id=None,
            expected_edge_r=1.0,
            spread_ticks=None,
            bars_since_exit_same_instrument=1,
            minutes_since_exit_same_instrument=None,
            campaign_trades_started=0,
            evaluation_time=datetime.now(UTC),
        ),
    )
    assert not result.allowed


def test_allow_when_clean() -> None:
    result = evaluate_churn(
        config=AntiChurnConfig(),
        facts=ChurnFacts(
            instrument_id="NIFTY",
            direction="BULLISH",
            thesis_id=None,
            expected_edge_r=1.0,
            spread_ticks=2,
            bars_since_exit_same_instrument=10,
            minutes_since_exit_same_instrument=20,
            campaign_trades_started=0,
            evaluation_time=datetime.now(UTC),
        ),
    )
    assert result.allowed
