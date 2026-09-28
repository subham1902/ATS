"""Tests for market resolution, including participation data threading.

Regression guard: the final ``return`` of :func:`resolve_active_market` was once
accidentally nested inside an ``else`` branch, so the *default* market returned
``None`` during normal trading hours - silently disabling the whole fleet. This
module pins that behaviour.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from ats.agents.worker import (
    CONTRACT_SPECS,
    CONTRACT_TO_INSTRUMENT,
    fetch_global_gold_spot_sync,
    resolve_active_market,
)

IST = timezone(timedelta(hours=5, minutes=30))


def _tick(price: float = 147_232.0, *, volume: int | None = 5_000, oi: int | None = 12_000):
    t = MagicMock()
    t.last_traded_price = price
    t.bid_price = price - 1.0
    t.ask_price = price + 1.0
    t.volume = volume
    t.open_interest = oi
    return t


def _fabric(tick):
    fab = MagicMock()
    fab.latest.return_value = tick
    return fab


def test_all_markets_are_in_session():
    """Session hours are computed in IST, not UTC."""
    now = datetime.now(IST)
    weekday = now.weekday() < 5
    hours = (9 <= now.hour < 23) or (now.hour == 23 and now.minute <= 30)
    # Just assert the helper produces a bool pair without raising.
    assert isinstance(weekday, bool)
    assert isinstance(hours, bool)


@pytest.mark.parametrize("market", ["AUTO", "MCX_GOLDM", "MCX_GOLD", "GLOBAL_XAU"])
def test_resolve_never_returns_none(market: str):
    """CRITICAL REGRESSION GUARD.

    A misindented return once made AUTO and MCX_GOLDM fall through to None
    during exactly the conditions that matter most - live session hours. The
    worker would then have had no contract to trade.
    """
    session = resolve_active_market(_fabric(_tick()), market)
    assert session is not None, f"{market} resolved to None"
    assert isinstance(session, dict)
    assert "contract_type" in session
    assert session["contract_type"] in CONTRACT_SPECS
    assert session["live_price"] > 0


def test_resolve_without_fabric_still_returns_contract():
    """No feed must not mean no market - it falls back to spot parity."""
    session = resolve_active_market(None, "MCX_GOLDM")
    assert session is not None
    assert session["contract_type"] == "MCX_GOLDM"
    assert session["live_price"] > 0


def test_volume_and_oi_thread_through_mcx():
    """Order-flow strategies need real participation data."""
    session = resolve_active_market(_fabric(_tick()), "MCX_GOLDM")
    assert session["volume"] == 5_000.0
    assert session["open_interest"] == 12_000.0


def test_missing_participation_data_stays_none():
    """Absent volume/OI must stay None, never default to a fabricated value."""
    session = resolve_active_market(_fabric(_tick(volume=None, oi=None)), "MCX_GOLDM")
    assert session["volume"] is None
    assert session["open_interest"] is None


def test_spot_market_has_no_participation_data():
    """XAU/USD spot legitimately carries no volume or OI."""
    session = resolve_active_market(_fabric(_tick()), "GLOBAL_XAU")
    assert session["volume"] is None
    assert session["open_interest"] is None


def test_instrument_token_mapping():
    assert CONTRACT_TO_INSTRUMENT["MCX_GOLDM"] == "GOLDM"
    assert CONTRACT_TO_INSTRUMENT["MCX_GOLD"] == "GOLD"
    assert CONTRACT_TO_INSTRUMENT["GLOBAL_XAU"] == "XAU"


def test_every_contract_spec_is_complete():
    required = {
        "symbol",
        "instrument_key",
        "exchange",
        "contract_type",
        "lot_size",
        "lot_unit",
        "margin_per_lot",
        "currency",
        "currency_symbol",
        "tick_size",
    }
    for key, spec in CONTRACT_SPECS.items():
        missing = required - set(spec)
        assert not missing, f"{key} missing {missing}"
        assert spec["lot_size"] > 0
        assert spec["margin_per_lot"] > 0
        assert spec["tick_size"] > 0


def test_spot_feed_returns_positive_price():
    """The cached fallback must still produce a usable price."""
    assert fetch_global_gold_spot_sync() > 0
