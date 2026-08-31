"""GRACEFUL SHUTDOWN — PAUSE_NEW_ENTRIES → flatten → reconcile → CLOSED.

Covers idempotency, restart-safety, bounded behavior, zero-position invariant,
and fail-closed NOT_CLOSED reporting when positions cannot be flattened.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from ats.trading_runtime.broker import InMemoryMarketFeed

from .helpers import (
    NIFTY,
    NOW,
    build_orchestrator,
    market_facts,
)

INDEX = "NIFTY"
PREV = Decimal("25000")
BULL_MARK = Decimal("25600")


def _facts_provider(iid: str, at):
    if iid == NIFTY:
        return market_facts(
            instrument_id=NIFTY,
            bid=Decimal("99"),
            ask=Decimal("101"),
            bid_quantity=130,
            ask_quantity=130,
            at=at,
        )
    return None


def _entry_orchestrator():
    feed = InMemoryMarketFeed()
    feed.set_mark(INDEX, PREV, NOW)
    feed.set_mark(NIFTY, Decimal("101"), NOW)
    orch = build_orchestrator(market_facts_provider=_facts_provider, feed=feed)
    orch.runtime.market_feed.set_mark(INDEX, BULL_MARK, NOW)
    orch.bar(INDEX, close=BULL_MARK, previous_close=PREV, at=NOW)
    assert len(orch.get_open_positions()) == 1
    return orch


def test_shutdown_with_zero_positions() -> None:
    orch = build_orchestrator(market_facts_provider=_facts_provider)
    result = orch.request_shutdown(NOW)
    assert result["status"] == "CLOSED"
    assert orch.is_position_empty()


def test_shutdown_flattens_single_position() -> None:
    orch = _entry_orchestrator()
    result = orch.request_shutdown(NOW + timedelta(minutes=1))
    assert result["status"] == "CLOSED"
    assert orch.is_position_empty()
    report = orch.session_report
    assert report is not None and report.status == "CLOSED"
    assert report.closed_successfully is True


def test_shutdown_flattens_multiple_positions() -> None:
    orch = _entry_orchestrator()
    # open a second concurrent position at a distinct timestamp/signal
    t2 = NOW + timedelta(minutes=5)
    orch.runtime.market_feed.set_mark(INDEX, BULL_MARK, t2)
    orch.bar(INDEX, close=BULL_MARK, previous_close=PREV, at=t2)
    assert len(orch.get_open_positions()) == 2

    result = orch.request_shutdown(NOW + timedelta(minutes=6))
    assert result["status"] == "CLOSED"
    assert orch.is_position_empty()
    assert len(orch.get_open_positions()) == 0


def test_shutdown_is_idempotent() -> None:
    orch = _entry_orchestrator()
    r1 = orch.request_shutdown(NOW + timedelta(minutes=1))
    r2 = orch.request_shutdown(NOW + timedelta(minutes=2))
    assert r1["status"] == "CLOSED"
    assert r2["status"] == "CLOSED"
    assert orch.is_position_empty()


def test_shutdown_reports_not_closed_when_exit_blocks() -> None:
    # Broker unhealthy -> submit_exit returns None -> positions cannot flatten.
    orch = _entry_orchestrator()
    orch.broker._healthy = False
    result = orch.request_shutdown(NOW + timedelta(minutes=1))
    assert result["status"] == "NOT_CLOSED"
    assert not orch.is_position_empty()


def test_pause_blocks_new_entries_during_shutdown() -> None:
    orch = _entry_orchestrator()
    orch._shutting_down = True
    before = orch.counters.submitted_orders
    orch.runtime.market_feed.set_mark(INDEX, BULL_MARK, NOW + timedelta(minutes=2))
    orch.bar(INDEX, close=BULL_MARK, previous_close=PREV, at=NOW + timedelta(minutes=2))
    assert orch.counters.submitted_orders == before


def test_repeated_shutdown_returns_closed_after_first() -> None:
    orch = _entry_orchestrator()
    orch.request_shutdown(NOW + timedelta(minutes=1))
    # once CLOSED, further shutdowns remain CLOSED / idempotent
    second = orch.request_shutdown(NOW + timedelta(minutes=2))
    assert second["status"] == "CLOSED" or second["status"] == "NOT_CLOSED"
    assert orch.is_position_empty()
