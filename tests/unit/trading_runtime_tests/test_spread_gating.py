from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ats.trading_runtime.anti_churn import AntiChurnConfig, ChurnFacts, evaluate_churn
from ats.trading_runtime.broker import PaperBrokerAdapter


def test_spread_fraction_gating() -> None:
    now = datetime.now(UTC)
    config = AntiChurnConfig(spread_fraction_max=0.03)

    # Spread is 2% of premium (allowed)
    facts_ok = ChurnFacts(
        instrument_id="NIFTY:CE:1",
        direction="BULLISH",
        thesis_id=None,
        expected_edge_r=0.25,
        spread_ticks=2,
        spread_fraction=0.02,
        bars_since_exit_same_instrument=None,
        minutes_since_exit_same_instrument=None,
        campaign_trades_started=0,
        evaluation_time=now,
    )
    res_ok = evaluate_churn(config=config, facts=facts_ok)
    assert res_ok.allowed

    # Spread is 5% of premium (blocked)
    facts_bad = ChurnFacts(
        instrument_id="NIFTY:CE:1",
        direction="BULLISH",
        thesis_id=None,
        expected_edge_r=0.25,
        spread_ticks=2,
        spread_fraction=0.05,
        bars_since_exit_same_instrument=None,
        minutes_since_exit_same_instrument=None,
        campaign_trades_started=0,
        evaluation_time=now,
    )
    res_bad = evaluate_churn(config=config, facts=facts_bad)
    assert not res_bad.allowed
    assert "SPREAD_FRACTION_TOO_WIDE" in res_bad.reason_codes


def test_paper_broker_slippage_application() -> None:
    broker = PaperBrokerAdapter(base_slippage_ticks=2, tick_size=Decimal("0.05"))
    # Buy slippage adds 2 * 0.05 = 0.10
    buy_fill = broker.apply_slippage(Decimal("100.00"), "BUY")
    assert buy_fill == Decimal("100.10")

    # Sell slippage subtracts 0.10
    sell_fill = broker.apply_slippage(Decimal("100.00"), "SELL")
    assert sell_fill == Decimal("99.90")
