"""ORCHESTRATION — the autonomous loop coordinates domain components.

Covers: non-actionable events produce no order; candidate != authorization;
authorized candidate submits exactly one paper order; duplicate events do not
double-submit; fills reach handle_fill; exits reach handle_exit_fill.
"""

from __future__ import annotations

from decimal import Decimal

from ats.trading_runtime.broker import InMemoryMarketFeed

from .helpers import (
    NIFTY,
    NOW,
    build_orchestrator,
    deny_all,
    market_facts,
)

INDEX = "NIFTY"
PREV = Decimal("25000")
BULL_MARK = Decimal("25600")  # edge_r 0.24 >= 0.2 and change>=0.003 -> candidate


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


def _fresh_orchestrator(at=NOW):
    feed = InMemoryMarketFeed()
    feed.set_mark(INDEX, PREV, at)
    feed.set_mark(NIFTY, Decimal("101"), at)
    return build_orchestrator(market_facts_provider=_facts_provider, feed=feed)


def _bull_bar(orch, at=NOW):
    orch.runtime.market_feed.set_mark(INDEX, BULL_MARK, at)
    orch.bar(INDEX, close=BULL_MARK, previous_close=PREV, at=at)


def test_non_actionable_event_produces_no_order() -> None:
    orch = _fresh_orchestrator()
    before = orch.counters.submitted_orders
    orch.bar(INDEX, close=PREV, previous_close=PREV, at=NOW)  # no change
    assert orch.counters.submitted_orders == before
    assert orch.get_open_positions() == {}


def test_candidate_without_authorization_produces_no_order() -> None:
    orch = _fresh_orchestrator()
    orch._authorization_provider = deny_all
    _bull_bar(orch)
    assert orch.counters.submitted_orders == 0
    assert orch.counters.risk_rejected_candidates == 1
    assert orch.get_open_positions() == {}


def test_authorized_candidate_produces_exactly_one_order_and_fill() -> None:
    orch = _fresh_orchestrator()
    _bull_bar(orch)
    assert orch.counters.submitted_orders == 1
    positions = orch.get_open_positions()
    assert len(positions) == 1
    pos = next(iter(positions.values()))
    assert pos.quantity == Decimal("65")


def test_duplicate_event_does_not_double_submit() -> None:
    orch = _fresh_orchestrator()
    _bull_bar(orch)
    _bull_bar(orch)  # same timestamp + direction -> same order_key -> idempotent
    assert orch.counters.submitted_orders == 1
    assert len(orch.get_open_positions()) == 1


def test_fill_reaches_runtime_open_positions_with_canonical_price() -> None:
    orch = _fresh_orchestrator()
    _bull_bar(orch)
    positions = orch.runtime.state.open_positions
    assert len(positions) == 1
    pos = next(iter(positions.values()))
    assert pos.entry_price == Decimal("101.10")  # canonical fill (ask + slippage)
    assert orch.counters.fees > 0 and orch.counters.taxes > 0


def test_exit_fill_reaches_handle_exit_fill() -> None:
    orch = _fresh_orchestrator()
    _bull_bar(orch)
    pid = next(iter(orch.get_open_positions().keys()))
    orch.runtime.handle_exit_fill(pid, NOW)
    assert orch.get_open_positions() == {}
