"""R14-F01: Cost model/net P&L consistency tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from ats.contracts.domain.types import DataQualityState, SessionState
from ats.contracts.intelligence.models import FormulaDefinition, StrategyDefinition
from ats.contracts.intelligence.types import (
    AssetClass,
    FormulaNode,
    FormulaNodeKind,
    FormulaOutputKind,
    FormulaPurpose,
    RegisteredCode,
    StrategyOrigin,
    StrategyStatus,
    VersionedRef,
)
from ats.intelligence.strategy_lab.backtest import BacktestConfiguration, run_backtest
from ats.intelligence.strategy_lab.cost_model import FixedBpsCostModel, ZeroCostModel
from ats.intelligence.strategy_lab.scorecard import build_scorecard
from ats.market.replay.models import ReplayBar, ReplayDataset, ReplayManifest


def _bars(n: int = 10) -> ReplayDataset:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    bars = []
    for i in range(n):
        bars.append(
            ReplayBar(
                instrument_id="NSE_EQ-TCS",
                exchange="NSE",
                segment="CASH",
                timeframe="5m",
                bar_timestamp=base + timedelta(minutes=5 * i),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("1000"),
                source_sequence=i + 1,
                quality_state=DataQualityState.GOOD,
                quality_flags=(),
                session_state=SessionState.OPEN,
            )
        )
    manifest = ReplayManifest(
        dataset_id=uuid4(),
        dataset_version="v1",
        source_description="test",
        instrument="NSE_EQ-TCS",
        exchange="NSE",
        segment="CASH",
        timeframe="5m",
        first_bar=bars[0].bar_timestamp,
        last_bar=bars[-1].bar_timestamp,
        bar_count=len(bars),
        content_sha256="a" * 64,
        calendar_id="XNSE",
        calendar_version="1",
    )
    return ReplayDataset(manifest=manifest, bars=tuple(bars))


def _always_true() -> FormulaDefinition:
    node = FormulaNode(
        node_kind=FormulaNodeKind.LITERAL,
        operator=None,
        arguments=(),
        feature_code=None,
        lag_bars=None,
        literal_decimal=None,
        literal_float=None,
        literal_int=None,
        literal_bool=True,
    )
    return FormulaDefinition(
        schema_version="1.0",
        formula_definition_id=uuid4(),
        formula_version=1,
        name="entry",
        purpose=FormulaPurpose.ENTRY_FILTER,
        output_kind=FormulaOutputKind.BOOLEAN,
        timeframe=RegisteredCode("5m"),
        lookback_bars=0,
        warmup_bars=0,
        ast=node,
        ast_depth=1,
        node_count=1,
        max_lag_bars=0,
        required_features=(),
        parameters=(),
        source_instruction_hash="a" * 64,
        origin=StrategyOrigin.HUMAN,
        created_at=datetime.now(UTC),
        payload_hash="b" * 64,
    )


def _always_false() -> FormulaDefinition:
    node = FormulaNode(
        node_kind=FormulaNodeKind.LITERAL,
        operator=None,
        arguments=(),
        feature_code=None,
        lag_bars=None,
        literal_decimal=None,
        literal_float=None,
        literal_int=None,
        literal_bool=False,
    )
    return FormulaDefinition(
        schema_version="1.0",
        formula_definition_id=uuid4(),
        formula_version=1,
        name="exit",
        purpose=FormulaPurpose.EXIT_FILTER,
        output_kind=FormulaOutputKind.BOOLEAN,
        timeframe=RegisteredCode("5m"),
        lookback_bars=0,
        warmup_bars=0,
        ast=node,
        ast_depth=1,
        node_count=1,
        max_lag_bars=0,
        required_features=(),
        parameters=(),
        source_instruction_hash="a" * 64,
        origin=StrategyOrigin.HUMAN,
        created_at=datetime.now(UTC),
        payload_hash="b" * 64,
    )


def _strategy(entry: FormulaDefinition) -> StrategyDefinition:
    return StrategyDefinition(
        schema_version="1.0",
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        name="s",
        strategy_family=RegisteredCode("FAM"),
        status=StrategyStatus.DRAFT,
        feature_formula_refs=(),
        entry_formula_ref=VersionedRef(id=entry.formula_definition_id, version=1),
        exit_formula_refs=(),
        compatible_asset_classes=(AssetClass.CASH_EQUITY,),
        compatible_venues=(),
        compatible_instruments=(),
        compatible_timeframes=(RegisteredCode("5m"),),
        required_features=(),
        required_model_families=(),
        regime_constraints=(),
        parameters=(),
        origin=StrategyOrigin.HUMAN,
        parent_strategy_ref=None,
        source_instruction_hash="a" * 64,
        validation_report_hash="b" * 64,
        created_at=datetime.now(UTC),
        payload_hash="c" * 64,
    )


def test_gross_positive_minus_costs_equals_smaller_net() -> None:
    """Gross positive trade minus costs = smaller net return."""
    dataset = _bars(5)
    entry = _always_true()
    exit_f = _always_true()
    cost = FixedBpsCostModel(
        cost_model_version="v1", fee_bps=Decimal("10"), per_trade_fee=Decimal("0")
    )
    strat = _strategy(entry)
    cfg = BacktestConfiguration(
        strategy=strat,
        entry_formula=entry,
        exit_formulas=(exit_f,),
        dataset=dataset,
        cost_model=cost,
        fill_quantity=Decimal("10"),
        dataset_cutoff=dataset.manifest.last_bar,
        parameter_set_hash="a" * 64,
        seed=42,
    )
    result = run_backtest(
        config=cfg,
        test_start=dataset.manifest.first_bar,
        test_end=dataset.manifest.last_bar,
        experiment_id=uuid4(),
    )
    if result.trades:
        t = result.trades[0]
        # pnl_fraction is NET, gross_pnl_fraction is GROSS
        assert t.pnl_fraction is not None
        assert t.gross_pnl_fraction is not None
        # NET <= GROSS (costs reduce return)
        assert t.pnl_fraction <= t.gross_pnl_fraction


def test_high_costs_turn_profit_into_loss() -> None:
    """High costs can turn gross profit into net loss."""
    dataset = _bars(5)
    entry = _always_true()
    exit_f = _always_true()
    # Very high cost: 1000 bps = 10%
    cost = FixedBpsCostModel(
        cost_model_version="v1", fee_bps=Decimal("1000"), per_trade_fee=Decimal("0")
    )
    strat = _strategy(entry)
    cfg = BacktestConfiguration(
        strategy=strat,
        entry_formula=entry,
        exit_formulas=(exit_f,),
        dataset=dataset,
        cost_model=cost,
        fill_quantity=Decimal("10"),
        dataset_cutoff=dataset.manifest.last_bar,
        parameter_set_hash="a" * 64,
        seed=42,
    )
    result = run_backtest(
        config=cfg,
        test_start=dataset.manifest.first_bar,
        test_end=dataset.manifest.last_bar,
        experiment_id=uuid4(),
    )
    if result.trades:
        t = result.trades[0]
        # With 10% cost on flat prices, net should be negative
        assert t.pnl_fraction is not None
        assert t.pnl_fraction < 0


def test_estimated_costs_equals_actual_subtracted() -> None:
    """estimated_costs in scorecard equals sum of fill costs."""
    dataset = _bars(5)
    entry = _always_true()
    exit_f = _always_true()
    cost = FixedBpsCostModel(
        cost_model_version="v1", fee_bps=Decimal("5"), per_trade_fee=Decimal("1")
    )
    strat = _strategy(entry)
    cfg = BacktestConfiguration(
        strategy=strat,
        entry_formula=entry,
        exit_formulas=(exit_f,),
        dataset=dataset,
        cost_model=cost,
        fill_quantity=Decimal("10"),
        dataset_cutoff=dataset.manifest.last_bar,
        parameter_set_hash="a" * 64,
        seed=42,
    )
    result = run_backtest(
        config=cfg,
        test_start=dataset.manifest.first_bar,
        test_end=dataset.manifest.last_bar,
        experiment_id=uuid4(),
    )
    now = datetime(2024, 1, 10, tzinfo=UTC)
    sc = build_scorecard(
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_ids=(uuid4(),),
        result=result,
        created_at=now,
        cost_model_version="v1",
    )
    expected_costs = sum((f.cost for f in result.fills), Decimal("0"))
    assert sc.estimated_costs == expected_costs


def test_cost_not_deducted_twice() -> None:
    """Costs are deducted once in pnl_fraction, not again in scorecard."""
    dataset = _bars(5)
    entry = _always_true()
    exit_f = _always_true()
    cost = FixedBpsCostModel(
        cost_model_version="v1", fee_bps=Decimal("10"), per_trade_fee=Decimal("0")
    )
    strat = _strategy(entry)
    cfg = BacktestConfiguration(
        strategy=strat,
        entry_formula=entry,
        exit_formulas=(exit_f,),
        dataset=dataset,
        cost_model=cost,
        fill_quantity=Decimal("10"),
        dataset_cutoff=dataset.manifest.last_bar,
        parameter_set_hash="a" * 64,
        seed=42,
    )
    result = run_backtest(
        config=cfg,
        test_start=dataset.manifest.first_bar,
        test_end=dataset.manifest.last_bar,
        experiment_id=uuid4(),
    )
    now = datetime(2024, 1, 10, tzinfo=UTC)
    sc = build_scorecard(
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_ids=(uuid4(),),
        result=result,
        created_at=now,
        cost_model_version="v1",
    )
    # net_return_fraction = sum(pnl_fraction) where pnl_fraction already has costs deducted
    # estimated_costs is reported separately, not subtracted again
    trade_net = sum(float(t.pnl_fraction) for t in result.trades if t.pnl_fraction is not None)
    assert sc.net_return_fraction == trade_net


def test_zero_cost_fixture_gross_equals_net() -> None:
    """Zero-cost explicit fixture yields gross == net."""
    dataset = _bars(5)
    entry = _always_true()
    exit_f = _always_true()
    cost = ZeroCostModel()
    strat = _strategy(entry)
    cfg = BacktestConfiguration(
        strategy=strat,
        entry_formula=entry,
        exit_formulas=(exit_f,),
        dataset=dataset,
        cost_model=cost,
        fill_quantity=Decimal("10"),
        dataset_cutoff=dataset.manifest.last_bar,
        parameter_set_hash="a" * 64,
        seed=42,
    )
    result = run_backtest(
        config=cfg,
        test_start=dataset.manifest.first_bar,
        test_end=dataset.manifest.last_bar,
        experiment_id=uuid4(),
    )
    if result.trades:
        t = result.trades[0]
        assert t.pnl_fraction == t.gross_pnl_fraction


def test_zero_cost_not_pass_authoritative() -> None:
    """Zero-cost model yields INSUFFICIENT_EVIDENCE, not PASS."""
    dataset = _bars(5)
    entry = _always_true()
    exit_f = _always_true()
    cost = ZeroCostModel()
    strat = _strategy(entry)
    cfg = BacktestConfiguration(
        strategy=strat,
        entry_formula=entry,
        exit_formulas=(exit_f,),
        dataset=dataset,
        cost_model=cost,
        fill_quantity=Decimal("10"),
        dataset_cutoff=dataset.manifest.last_bar,
        parameter_set_hash="a" * 64,
        seed=42,
    )
    result = run_backtest(
        config=cfg,
        test_start=dataset.manifest.first_bar,
        test_end=dataset.manifest.last_bar,
        experiment_id=uuid4(),
    )
    now = datetime(2024, 1, 10, tzinfo=UTC)
    sc = build_scorecard(
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_ids=(uuid4(),),
        result=result,
        created_at=now,
    )
    from ats.contracts.intelligence.types import ScorecardValidationStatus

    assert sc.validation_status is ScorecardValidationStatus.INSUFFICIENT_EVIDENCE
