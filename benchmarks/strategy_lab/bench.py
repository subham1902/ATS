"""Small benchmark harness for Strategy Lab — no optimization, no GPU."""

from __future__ import annotations

import time
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
from ats.intelligence.formula import FormulaEvaluationContext, evaluate
from ats.intelligence.strategy_lab.backtest import BacktestConfiguration, run_backtest
from ats.intelligence.strategy_lab.cost_model import FixedBpsCostModel
from ats.market.replay.models import ReplayBar, ReplayDataset, ReplayManifest


def _make_bars(n: int = 1000) -> ReplayDataset:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    bars: list[ReplayBar] = []
    for i in range(n):
        bars.append(
            ReplayBar(
                instrument_id="NSE_EQ-RELIANCE",
                exchange="NSE",
                segment="CASH",
                timeframe="5m",
                bar_timestamp=base + timedelta(minutes=5 * i),
                open=Decimal("100") + Decimal(i % 10),
                high=Decimal("102") + Decimal(i % 10),
                low=Decimal("99") + Decimal(i % 10),
                close=Decimal("101") + Decimal(i % 10),
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
        source_description="bench",
        instrument="NSE_EQ-RELIANCE",
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


def _make_formula_always_true() -> FormulaDefinition:
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
        name="always_true",
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


def bench() -> None:
    dataset = _make_bars(1000)
    formula = _make_formula_always_true()
    from ats.market.replay.engine import DeterministicReplay, ReplayConfiguration

    cfg = ReplayConfiguration(start_at=dataset.manifest.first_bar, received_delay_ms=10)
    start = time.perf_counter()
    replay = DeterministicReplay(dataset, cfg)
    for _ in range(len(dataset.bars)):
        replay.advance()
    elapsed = time.perf_counter() - start
    count = len(dataset.bars)
    print(f"B01 replay {count} bars: {elapsed:.4f}s throughput {count/elapsed:.0f} bars/s")

    ctx = FormulaEvaluationContext(evaluation_index=500, series={"close": [float(i) for i in range(501)]})
    start = time.perf_counter()
    n_eval = 10000
    for _ in range(n_eval):
        evaluate(formula, ctx)
    elapsed = time.perf_counter() - start
    print(f"R13 eval {n_eval} evals: {elapsed:.4f}s {n_eval/elapsed:.0f} evals/s")

    cost = FixedBpsCostModel(cost_model_version="v1", fee_bps=Decimal("1"), per_trade_fee=Decimal("0.1"))
    strat = StrategyDefinition(
        schema_version="1.0",
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        name="bench",
        strategy_family=RegisteredCode("BENCH"),
        status=StrategyStatus.DRAFT,
        feature_formula_refs=(),
        entry_formula_ref=VersionedRef(id=formula.formula_definition_id, version=1),
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
    config = BacktestConfiguration(
        strategy=strat,
        entry_formula=formula,
        exit_formulas=(),
        dataset=dataset,
        cost_model=cost,
        fill_quantity=Decimal("10"),
        dataset_cutoff=dataset.manifest.last_bar,
        parameter_set_hash="a" * 64,
        seed=42,
    )
    start = time.perf_counter()
    result = run_backtest(
        config=config,
        test_start=dataset.manifest.first_bar,
        test_end=dataset.manifest.last_bar,
        experiment_id=uuid4(),
    )
    elapsed = time.perf_counter() - start
    approx_mem = len(result.trades) * 200
    count_bars = len(dataset.bars)
    print(f"StrategyLab backtest {count_bars} bars -> {len(result.trades)} trades: {elapsed:.4f}s mem~{approx_mem} bytes")


if __name__ == "__main__":
    bench()
