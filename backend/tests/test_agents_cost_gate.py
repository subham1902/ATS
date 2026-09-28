"""Verify the cost gate reproduces the audit and blocks the unprofitable config.

The 2026-09-28 audit found Rs.336 of charges against a Rs.450 target and a
Rs.220 stop, requiring an 83% win rate. These tests pin that behaviour so a
future change cannot silently re-open the bleeding.
"""

from __future__ import annotations

import pytest
from ats.agents.costs import (
    CostAwareSizer,
    assess_trade,
    calculate_charges,
    estimate_round_trip_charges,
    min_lots_for_viability,
    pnl_multiplier,
    required_win_rate,
)

GOLDM = "MCX:GOLDM FUT"
LOT_SIZE = 100.0
PRICE = 147_232.0


def test_charges_match_audited_value():
    """The 1-lot round-trip charge must match the audit's Rs.336."""
    c = estimate_round_trip_charges(
        exchange="MCX",
        entry_price=147_232.0,
        exit_price=147_277.0,
        symbol=GOLDM,
        lot_size=LOT_SIZE,
        lots=1.0,
    )
    assert c.total_charges == pytest.approx(336.65, abs=0.05)
    assert c.brokerage == 40.0
    assert sum(
        [c.stt_ctt, c.exchange_charges, c.gst, c.sebi_charges, c.stamp_duty]
    ) + c.brokerage == pytest.approx(c.total_charges, abs=0.01)


def test_charges_exceed_stated_stop_at_one_lot():
    """The core pathology: friction costs more than the whole stop."""
    c = estimate_round_trip_charges(
        exchange="MCX",
        entry_price=PRICE,
        exit_price=PRICE + 22,
        symbol=GOLDM,
        lot_size=LOT_SIZE,
        lots=1.0,
    )
    stop_value = 22.0 * pnl_multiplier(
        symbol=GOLDM, lot_size=LOT_SIZE, total_quantity=LOT_SIZE
    )
    assert c.total_charges > stop_value


def test_required_win_rate_matches_audit():
    """83% break-even win rate, as computed in the audit."""
    net_win = 45.0 * 10 - 336.65
    net_loss = -(22.0 * 10) - 336.65
    assert required_win_rate(net_if_win=net_win, net_if_loss=net_loss) == pytest.approx(
        0.831, abs=0.005
    )


def test_pre_audit_geometry_is_blocked_at_every_size():
    """The 45/22 configuration must be rejected regardless of lot size."""
    for lots in (1.0, 2.0, 4.0, 10.0, 20.0):
        e = assess_trade(
            exchange="MCX",
            entry_price=PRICE,
            symbol=GOLDM,
            lot_size=LOT_SIZE,
            lots=lots,
            target_points=45.0,
            stop_points=22.0,
            strategy_win_rate=0.5,
            max_lots_allowed=30.0,
        )
        assert not e.tradable, f"{lots} lots should be blocked"
        assert e.block_reason_code in {
            "LOT_SIZE_UNECONOMICAL",
            "NEGATIVE_EXPECTANCY",
        }


def test_wider_target_is_tradable():
    """A 200pt target clears the gate - this is the recommended configuration."""
    e = assess_trade(
        exchange="MCX",
        entry_price=PRICE,
        symbol=GOLDM,
        lot_size=LOT_SIZE,
        lots=2.0,
        target_points=200.0,
        stop_points=67.0,
        strategy_win_rate=0.45,
        max_lots_allowed=30.0,
    )
    assert e.tradable
    assert e.edge_to_cost_ratio > 3.0
    assert e.required_win_rate < 0.45


def test_nonsense_win_rate_cannot_rescue_a_bad_trade():
    """No achievable win rate makes the pre-audit geometry profitable."""
    for wr in (0.5, 0.7, 0.9, 0.99):
        e = assess_trade(
            exchange="MCX",
            entry_price=PRICE,
            symbol=GOLDM,
            lot_size=LOT_SIZE,
            lots=1.0,
            target_points=45.0,
            stop_points=22.0,
            strategy_win_rate=wr,
            max_lots_allowed=5.0,
        )
        assert not e.tradable


def test_min_lots_reports_when_size_helps():
    """Small targets need many lots; the function must say so honestly."""
    needed = min_lots_for_viability(
        expected_edge_per_lot=45.0 * 10,
        round_trip_cost_at_one_lot=336.65,
        min_edge_multiple=3.0,
    )
    # At 45pts/lot no size up to the search bound qualifies.
    assert needed == 0.0

    needed_wide = min_lots_for_viability(
        expected_edge_per_lot=200.0 * 10,
        round_trip_cost_at_one_lot=336.65,
        min_edge_multiple=3.0,
    )
    assert needed_wide > 0.0


def test_gold_multiplier_uses_ten_gram_quote():
    assert pnl_multiplier(symbol=GOLDM, lot_size=100.0, total_quantity=100.0) == 10.0
    assert pnl_multiplier(symbol=GOLDM, lot_size=1000.0, total_quantity=1000.0) == 100.0
    assert pnl_multiplier(symbol="NIFTY FUT", lot_size=25.0, total_quantity=25.0) == 25.0


def test_sizer_respects_risk_budget():
    """A wide risk budget must not be overridden by the sizer."""
    sizer = CostAwareSizer(
        max_lots=10.0,
        max_risk_pct=0.05,
        capital=100_000.0,
        margin_per_lot=45_000.0,
        min_edge_multiple=3.0,
    )
    lots, econ = sizer.size_for(
        exchange="MCX",
        entry_price=PRICE,
        symbol=GOLDM,
        lot_size=LOT_SIZE,
        target_points=200.0,
        stop_points=67.0,
        strategy_win_rate=0.45,
    )
    if lots > 0:
        risk = 67.0 * 10 * lots
        assert risk <= 100_000.0 * 0.05 + 1e-6
    else:
        assert not econ.tradable


def test_empty_turnover_costs_are_finite():
    """Even with zero notional, flat brokerage plus GST on it is owed."""
    c = calculate_charges(exchange="MCX", turnover=0.0)
    assert c.brokerage == 40.0
    assert c.gst == pytest.approx(7.2)
    assert c.total_charges == pytest.approx(47.2)
