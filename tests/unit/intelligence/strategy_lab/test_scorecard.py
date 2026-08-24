from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from ats.intelligence.strategy_lab.scorecard import build_scorecard
from ats.intelligence.strategy_lab.types import BacktestResult, ResearchFill, ResearchSignal, ResearchTrade


def test_zero_trade_semantics() -> None:
    now = datetime(2024, 1, 10, tzinfo=UTC)
    result = BacktestResult(
        result_id=uuid4(),
        experiment_id=uuid4(),
        trades=(),
        fills=(),
        signals=(),
        start_time=now,
        end_time=now,
        seed=42,
    )
    sc = build_scorecard(
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_ids=(uuid4(),),
        result=result,
        created_at=now,
    )
    assert sc.trade_count == 0
    assert sc.win_rate is None
    assert sc.average_win_r is None
    assert sc.average_loss_r is None
    assert sc.profit_factor is None
    assert sc.validation_status.value == "INSUFFICIENT_EVIDENCE"


def test_profit_factor_undefined() -> None:
    now = datetime(2024, 1, 10, tzinfo=UTC)
    # Single winning trade, no losses => profit_factor None
    fill_entry = ResearchFill(
        fill_id=uuid4(),
        signal_id=uuid4(),
        instrument_id="NSE_EQ-TCS",
        side="BUY",
        price=Decimal("100"),
        quantity=Decimal("10"),
        bar_timestamp=now,
        bar_sequence=1,
        cost=Decimal("0"),
    )
    fill_exit = ResearchFill(
        fill_id=uuid4(),
        signal_id=uuid4(),
        instrument_id="NSE_EQ-TCS",
        side="SELL",
        price=Decimal("110"),
        quantity=Decimal("10"),
        bar_timestamp=now,
        bar_sequence=2,
        cost=Decimal("0"),
    )
    trade = ResearchTrade(
        trade_id=uuid4(),
        instrument_id="NSE_EQ-TCS",
        entry_fill=fill_entry,
        exit_fill=fill_exit,
        entry_time=now,
        exit_time=now,
        pnl_fraction=Decimal("0.1"),
        pnl_r=Decimal("5"),
    )
    result = BacktestResult(
        result_id=uuid4(),
        experiment_id=uuid4(),
        trades=(trade,),
        fills=(fill_entry, fill_exit),
        signals=(),
        start_time=now,
        end_time=now,
        seed=42,
    )
    sc = build_scorecard(
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_ids=(uuid4(),),
        result=result,
        created_at=now,
    )
    assert sc.profit_factor is None
    assert sc.win_rate == Decimal("1")


def test_no_nan_inf() -> None:
    now = datetime(2024, 1, 10, tzinfo=UTC)
    result = BacktestResult(
        result_id=uuid4(),
        experiment_id=uuid4(),
        trades=(),
        fills=(),
        signals=(),
        start_time=now,
        end_time=now,
        seed=42,
    )
    sc = build_scorecard(
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_ids=(uuid4(),),
        result=result,
        created_at=now,
    )
    import math

    assert math.isfinite(sc.net_return_fraction)
    assert math.isfinite(sc.expectancy_r)
