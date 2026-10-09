from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from ats.market.observations import MarketObservation
from ats.trading_runtime.trade_quality import TradeOpening, TradePath


def path(side="LONG"):
    return TradePath(
        TradeOpening(
            execution_id="EXE",
            account_id="ACC",
            strategy_id="XAU-003",
            strategy_version=1,
            mode="PAPER",
            signal_id="signal",
            broker_symbol="XAUUSDm",
            side=side,
            time=datetime(2026, 1, 5, 12, tzinfo=UTC),
            signal_price=2000,
            entry=2000,
            initial_sl=1990 if side == "LONG" else 2010,
            initial_tp=2030 if side == "LONG" else 1970,
            quantity=1,
            spread_at_entry=".2",
        )
    )


def quote(trade, seconds, bid=2000, ask=2001):
    stamp = trade.opening.time + timedelta(seconds=seconds)
    return MarketObservation(
        broker_symbol="XAUUSDm",
        timestamp=stamp,
        received_at=stamp,
        source="TEST_FIXTURE",
        bid=Decimal(str(bid)),
        ask=Decimal(str(ask)),
    )


def test_liquidation_side_and_unknown_costs():
    long, short = path(), path("SHORT")
    long.observe(quote(long, 1, 2010, 2012))
    short.observe(quote(short, 1, 1990, 1992))
    assert long.report()["MFE_R"] == "1"
    assert short.report()["MFE_R"] == "0.8"
    long.close(price=Decimal(2010), time=long.last_time, source="STRATEGY")
    assert long.report()["net_realized_R"] is None
    assert long.report()["entry_quality"] == "UNKNOWN"


def test_good_entry_bad_exit_advisory_and_shadow_freeze():
    trade = path()
    for seconds in range(1, 302):
        bid = 2020 if seconds < 301 else 2010
        trade.observe(quote(trade, seconds, bid, bid + 1))
    report = trade.report()
    assert report["exit_watch"] == "MANUAL_EXIT_REVIEW"
    assert report["financial_authority"] == "NONE"
    trade.close(price=Decimal(2010), time=trade.last_time, source="OPERATOR")
    assert trade.report()["diagnosis"] == "GOOD_ENTRY_BAD_EXIT"
    trade.observe(quote(trade, 302, 2030, 2031))
    assert trade.report()["MFE_R"] == "2"
    assert trade.report()["shadow_exit_R"] == "3"
    assert trade.report()["human_minus_shadow_R"] == "-2"


def test_gap_and_missing_side_destroy_quality_eligibility():
    trade = path()
    trade.observe(quote(trade, 30))
    assert not trade.report()["path_complete"]
    stamp = trade.last_time + timedelta(seconds=1)
    trade.observe(
        MarketObservation(
            broker_symbol="XAUUSDm",
            timestamp=stamp,
            received_at=stamp,
            source="TEST_FIXTURE",
            ask=Decimal(2001),
        )
    )
    assert trade.report()["entry_quality"] == "UNKNOWN"


def test_future_backwards_wrong_symbol_duplicate_fail_closed():
    trade = path()
    observation = quote(trade, 1)
    for item in [
        observation.model_copy(update={"broker_symbol": "OTHER"}),
        observation.model_copy(update={"received_at": trade.opening.time}),
        quote(trade, -1),
    ]:
        with pytest.raises(ValueError):
            trade.observe(item)
    trade.observe(observation)
    with pytest.raises(ValueError):
        trade.observe(observation)
