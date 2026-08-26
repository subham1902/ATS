"""Adverse-fill slippage: buys pay up, sells receive less, PnL never improves."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
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
from ats.intelligence.strategy_lab.cost_model import FixedBpsCostModel
from ats.intelligence.strategy_lab.fill_model import (
    FixedBpsSlippageModel,
    ZeroSlippageModel,
)
from ats.market.replay.models import ReplayBar, ReplayDataset, ReplayManifest


def _bars(n: int = 6) -> ReplayDataset:
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


def _literal_formula(*, name: str, purpose: FormulaPurpose, value: bool) -> FormulaDefinition:
    node = FormulaNode(
        node_kind=FormulaNodeKind.LITERAL,
        operator=None,
        arguments=(),
        feature_code=None,
        lag_bars=None,
        literal_decimal=None,
        literal_float=None,
        literal_int=None,
        literal_bool=value,
    )
    return FormulaDefinition(
        schema_version="1.0",
        formula_definition_id=uuid4(),
        formula_version=1,
        name=name,
        purpose=purpose,
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
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
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
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        payload_hash="c" * 64,
    )


def _config(dataset, entry, exit_f, slippage_model) -> BacktestConfiguration:
    cost = FixedBpsCostModel(
        cost_model_version="v1", fee_bps=Decimal("0"), per_trade_fee=Decimal("0")
    )
    return BacktestConfiguration(
        strategy=_strategy(entry),
        entry_formula=entry,
        exit_formulas=(exit_f,),
        dataset=dataset,
        cost_model=cost,
        fill_quantity=Decimal("10"),
        dataset_cutoff=dataset.manifest.last_bar,
        parameter_set_hash="a" * 64,
        seed=42,
        slippage_model=slippage_model,
    )


def test_buy_is_degraded_up_and_sell_down() -> None:
    model = FixedBpsSlippageModel(
        slippage_model_version="slip-v1", slippage_bps=Decimal("5")
    )
    price = Decimal("100")
    assert model.applied_price(price=price, quantity=Decimal("1"), side="BUY") == Decimal(
        "100.05"
    )
    assert model.applied_price(price=price, quantity=Decimal("1"), side="SELL") == Decimal(
        "99.95"
    )


def test_invalid_inputs_are_rejected() -> None:
    model = FixedBpsSlippageModel(
        slippage_model_version="slip-v1", slippage_bps=Decimal("1")
    )
    with pytest.raises(ValueError):
        model.applied_price(price=Decimal("100"), quantity=Decimal("1"), side="HOLD")
    negative = FixedBpsSlippageModel(
        slippage_model_version="slip-v1", slippage_bps=Decimal("-1")
    )
    with pytest.raises(ValueError):
        negative.applied_price(price=Decimal("100"), quantity=Decimal("1"), side="BUY")
    zero = ZeroSlippageModel()
    assert zero.applied_price(price=Decimal("7"), quantity=Decimal("1"), side="BUY") == Decimal("7")


def test_backtest_net_pnl_never_improves_with_slippage() -> None:
    dataset = _bars()
    entry = _literal_formula(name="entry", purpose=FormulaPurpose.ENTRY_FILTER, value=True)
    exit_f = _literal_formula(name="exit", purpose=FormulaPurpose.EXIT_FILTER, value=True)

    baseline = run_backtest(
        config=_config(dataset, entry, exit_f, None),
        test_start=dataset.manifest.first_bar,
        test_end=dataset.manifest.last_bar,
        experiment_id=uuid4(),
    )
    slipped = run_backtest(
        config=_config(
            dataset,
            entry,
            exit_f,
            FixedBpsSlippageModel(slippage_model_version="slip-v1", slippage_bps=Decimal("10")),
        ),
        test_start=dataset.manifest.first_bar,
        test_end=dataset.manifest.last_bar,
        experiment_id=uuid4(),
    )
    assert len(baseline.fills) == len(slipped.fills) > 0
    for clean, degraded in zip(baseline.fills, slipped.fills, strict=True):
        if clean.side == "BUY":
            assert degraded.price > clean.price
        else:
            assert degraded.price < clean.price
    baseline_net = sum(trade.net_cash_pnl for trade in baseline.trades)
    slipped_net = sum(trade.net_cash_pnl for trade in slipped.trades)
    assert slipped_net <= baseline_net


def test_zero_slippage_model_matches_baseline() -> None:
    dataset = _bars()
    entry = _literal_formula(name="entry", purpose=FormulaPurpose.ENTRY_FILTER, value=True)
    exit_f = _literal_formula(name="exit", purpose=FormulaPurpose.EXIT_FILTER, value=True)
    left = run_backtest(
        config=_config(dataset, entry, exit_f, ZeroSlippageModel()),
        test_start=dataset.manifest.first_bar,
        test_end=dataset.manifest.last_bar,
        experiment_id=uuid4(),
    )
    right = run_backtest(
        config=_config(dataset, entry, exit_f, None),
        test_start=dataset.manifest.first_bar,
        test_end=dataset.manifest.last_bar,
        experiment_id=uuid4(),
    )
    assert [fill.price for fill in left.fills] == [fill.price for fill in right.fills]
