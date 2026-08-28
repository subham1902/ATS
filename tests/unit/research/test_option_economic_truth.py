"""Tests for the promotion-grade option economic truth engine (V3).

Run: uv run --project backend pytest tests/unit/research/test_option_economic_truth.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))

import option_economic_truth as oet  # noqa: E402

CACHE = oet.load_instrument_cache()


def test_resolve_contract_uses_real_metadata_lot_not_hardcoded():
    # NIFTY currently-listed weekly lot is 65, BANKNIFTY monthly is 30.
    nifty = oet.resolve_contract(CACHE, "NIFTY", 25000.0, "LONG_CE", offset=0)
    bank = oet.resolve_contract(CACHE, "BANKNIFTY", 55000.0, "LONG_PE", offset=0)
    assert nifty is not None and nifty.lot_size == 65
    assert bank is not None and bank.lot_size == 30
    # strike is ATM (nearest), not a hardcoded constant
    assert nifty.strike == 25000.0


def test_resolve_contract_offset_strikes_are_neighbors():
    atm = oet.resolve_contract(CACHE, "NIFTY", 25000.0, "LONG_CE", offset=0)
    plus1 = oet.resolve_contract(CACHE, "NIFTY", 25000.0, "LONG_CE", offset=1)
    minus1 = oet.resolve_contract(CACHE, "NIFTY", 25000.0, "LONG_CE", offset=-1)
    assert plus1.strike > atm.strike > minus1.strike


def test_cost_model_positive_and_scales_with_premium():
    c1 = oet.compute_costs(100.0, 110.0, 65)
    c2 = oet.compute_costs(300.0, 310.0, 65)
    assert c1["total"] > 0
    assert c2["total"] > c1["total"]  # higher premium -> higher statutory cost
    # STT only on sell side
    assert c1["stt"] > 0


def test_entry_exit_conservative_for_long():
    bar = oet.OptionBar(ts=None, o=100.0, h=110.0, low=95.0, c=105.0, v=1000, oi=5000)
    # Long entry must not use bar low; long exit must not use bar high.
    assert oet.conservative_entry_price(bar, "LONG_CE") >= bar.c
    assert oet.conservative_exit_price(bar, "LONG_CE") <= bar.c
    assert oet.conservative_entry_price(bar, "LONG_CE") <= bar.h
    assert oet.conservative_exit_price(bar, "LONG_CE") >= bar.low


def test_synthetic_not_promotion_grade():
    assert oet.EvidenceClass.SYNTHETIC not in oet.PROMOTION_GRADE
    assert oet.EvidenceClass.REAL_OPTION_BAR in oet.PROMOTION_GRADE


def test_determinism_of_observation():
    cm = oet.resolve_contract(CACHE, "NIFTY", 25000.0, "LONG_CE", offset=0)
    eb = oet.OptionBar(ts=None, o=100.0, h=110.0, low=95.0, c=105.0, v=1000, oi=5000)
    xb = oet.OptionBar(ts=None, o=108.0, h=112.0, low=104.0, c=110.0, v=1000, oi=5000)
    o1 = oet.build_economic_observation("s", "NIFTY", None, "LONG_CE", cm, eb, xb, oet.EvidenceClass.REAL_OPTION_BAR)
    o2 = oet.build_economic_observation("s", "NIFTY", None, "LONG_CE", cm, eb, xb, oet.EvidenceClass.REAL_OPTION_BAR)
    assert o1.entry_price == o2.entry_price
    assert o1.net_pnl == o2.net_pnl
    assert o1.contract.lot_size == 65


def test_as_of_admission_rejects_future_bar():
    from datetime import datetime, UTC
    past = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
    future = datetime(2026, 8, 25, 10, 5, tzinfo=UTC)
    assert oet.as_of_admission(past, past) is True
    assert oet.as_of_admission(future, past) is False


def test_liquidity_filter_rejects_thin_bars():
    thin = oet.OptionBar(ts=None, o=100.0, h=101.0, low=99.0, c=100.0, v=10, oi=0)
    ok = oet.OptionBar(ts=None, o=100.0, h=101.0, low=99.0, c=100.0, v=5000, oi=20000)
    assert oet.liquidity_ok(thin) is False
    assert oet.liquidity_ok(ok) is True
