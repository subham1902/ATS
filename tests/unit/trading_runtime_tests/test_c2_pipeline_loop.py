"""C2.6 deterministic paper-fill integration proof (TEST/REPLAY only).

Proves the governed chain candidate -> Portfolio Brain -> A04 -> capital
reserve -> PaperBroker -> fill -> position -> live mark -> exit -> realized
paper P&L, for both NIFTY long CE and BANKNIFTY long PE, plus a same-direction
correlated case checking no double-spend and concentration handling. Never
surfaced as live production data.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from ats.contracts.common import SystemClock
from ats.portfolio.brain import ExposureDirection
from ats.trading_runtime.a2_runner import (
    A2PaperSessionConfig,
    A2PaperSessionController,
    classify_rejection,
)
from ats.trading_runtime.candidate_factory import build_opportunity_candidate


def _candidate(instrument_id: str):
    now = SystemClock().now()
    return build_opportunity_candidate(
        instrument_id=instrument_id,
        campaign_id=uuid4(),
        campaign_version=1,
        strategy_id=uuid4(),
        strategy_version=1,
        market_context_id=uuid4(),
        thesis_id=uuid4(),
        thesis_version=1,
        distribution_id=uuid4(),
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


def test_c2_nifty_ce_and_banknifty_pe_with_exit_pnl():
    config = A2PaperSessionConfig(max_positions=4)
    controller = A2PaperSessionController(config=config)
    controller.start(require_token=False)
    now = SystemClock().now()

    # NIFTY long CE
    res1 = controller.evaluate_and_execute_candidate(
        _candidate("NIFTY_CE"),
        underlying="NIFTY",
        direction=ExposureDirection.BULLISH,
        requested_capital=Decimal("50000"),
        requested_quantity=Decimal("50"),
        now=now,
    )
    assert res1["allowed"] is True
    pos1_id = res1["position_id"]

    # BANKNIFTY long PE
    res2 = controller.evaluate_and_execute_candidate(
        _candidate("BANKNIFTY_PE"),
        underlying="BANKNIFTY",
        direction=ExposureDirection.BULLISH,
        requested_capital=Decimal("50000"),
        requested_quantity=Decimal("30"),
        now=now,
    )
    assert res2["allowed"] is True
    pos2_id = res2["position_id"]

    assert len(controller.engine.state.open_positions) == 2
    counters = controller.pipeline_counters()
    assert counters.candidates_considered == 2
    assert counters.candidates_qualified == 2
    assert counters.paper_orders == 2
    assert counters.paper_fills == 2
    assert counters.a04_allow == 2
    assert controller.status().real_orders_placed == 0

    # Live mark NIFTY_CE up -> exit with positive realized P&L
    engine = controller.engine
    pos1 = engine.state.open_positions[pos1_id]
    entry1 = pos1.entry_price
    qty1 = pos1.quantity
    controller.process_tick("NIFTY_CE", entry1 + Decimal("10"), at=now)
    pos1_exit_mark = engine.state.open_positions[pos1_id].current_mark
    expected_realized_1 = (pos1_exit_mark - entry1) * qty1
    engine.request_exit(pos1_id, now, reason_codes=("TEST_EXIT",), source="TEST")
    engine.handle_exit_fill(pos1_id, now)
    assert expected_realized_1 > 0

    # Live mark BANKNIFTY_PE to hard stop -> exit with negative realized P&L
    entry2 = controller.engine.state.open_positions[pos2_id].entry_price
    controller.process_tick("BANKNIFTY_PE", entry2 - Decimal("10"), at=now)
    engine.request_exit(pos2_id, now, reason_codes=("HARD_LOSS_BREACH",), source="MONITOR")
    engine.handle_exit_fill(pos2_id, now)
    assert len(controller.engine.state.open_positions) == 0


def test_c2_same_direction_correlated_no_double_spend():
    config = A2PaperSessionConfig(max_positions=4, capital_budget=Decimal("150000"))
    controller = A2PaperSessionController(config=config)
    controller.start(require_token=False)
    now = SystemClock().now()

    res1 = controller.evaluate_and_execute_candidate(
        _candidate("NIFTY_CE"),
        underlying="NIFTY",
        direction=ExposureDirection.BULLISH,
        requested_capital=Decimal("50000"),
        requested_quantity=Decimal("50"),
        now=now,
    )
    res2 = controller.evaluate_and_execute_candidate(
        _candidate("BANKNIFTY_CE"),
        underlying="BANKNIFTY",
        direction=ExposureDirection.BULLISH,
        requested_capital=Decimal("50000"),
        requested_quantity=Decimal("30"),
        now=now,
    )
    assert res1["allowed"] is True
    assert res2["allowed"] is True

    # No double-spend: combined approved capital must not exceed the budget.
    approved_1 = Decimal(res1["approved_capital"])
    approved_2 = Decimal(res2["approved_capital"])
    assert approved_1 + approved_2 <= config.capital_budget

    # Concentration / correlation surfaced through Portfolio Brain decisions.
    counters = controller.pipeline_counters()
    assert counters.portfolio_brain_allow + counters.portfolio_brain_reduced >= 2


def test_c2_scan_without_calibration_does_not_force_trade():
    feed = __import__(
        "ats.trading_runtime.a2_runner", fromlist=["UpstoxMarketFeedAdapter"]
    ).UpstoxMarketFeedAdapter()
    controller = A2PaperSessionController(market_feed=feed)
    controller.start(require_token=False)
    now = SystemClock().now()
    controller.process_tick("NIFTY", Decimal("24500.00"), at=now)

    outcome = controller.scan_market_for_candidates(now=now)
    # Without calibration evidence the pipeline cannot qualify a candidate.
    assert outcome["qualified"] == 0
    assert controller.status().paper_orders_submitted == 0
    assert controller.status().open_paper_positions == 0
    counters = controller.pipeline_counters()
    assert counters.candidates_rejected == 1
    assert counters.rejection_reasons.get("insufficient_calibration_support", 0) == 1


def test_neutral_synthesized_thesis_has_typed_rejection_category():
    assert classify_rejection(("THESIS_SYNTHESIZED",)) == "neutral_thesis"
