from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from ats.contracts.intelligence.models import FormulaDefinition, StrategyDefinition
from ats.contracts.intelligence.types import AssetClass, FormulaNode, FormulaNodeKind, FormulaOutputKind, FormulaPurpose, RegisteredCode, StrategyOrigin, VersionedRef
from ats.intelligence.strategy_lab.backtest import BacktestConfiguration, run_backtest
from ats.intelligence.strategy_lab.cost_model import FixedBpsCostModel
from ats.market.replay.models import ReplayBar, ReplayDataset, ReplayManifest
from ats.contracts.domain.types import DataQualityState, SessionState


def _bars(n: int = 20) -> ReplayDataset:
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


def test_determinism_same_seed() -> None:
    dataset = _bars(20)
    formula = _always_true()
    cost = FixedBpsCostModel(cost_model_version="v1", fee_bps=Decimal("0"), per_trade_fee=Decimal("0"))
    from ats.contracts.intelligence.types import StrategyStatus

    strat = StrategyDefinition(
        schema_version="1.0",
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        name="s",
        strategy_family=RegisteredCode("FAM"),
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
    cfg = BacktestConfiguration(
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
    eid = uuid4()
    r1 = run_backtest(
        config=cfg, test_start=dataset.manifest.first_bar, test_end=dataset.manifest.last_bar, experiment_id=eid
    )
    r2 = run_backtest(
        config=cfg, test_start=dataset.manifest.first_bar, test_end=dataset.manifest.last_bar, experiment_id=eid
    )
    assert r1.trades == r2.trades
    assert r1.fills == r2.fills


def test_changed_seed_deterministic() -> None:
    dataset = _bars(10)
    formula = _always_true()
    cost = FixedBpsCostModel(cost_model_version="v1", fee_bps=Decimal("0"), per_trade_fee=Decimal("0"))
    from ats.contracts.intelligence.types import StrategyStatus

    strat = StrategyDefinition(
        schema_version="1.0",
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        name="s",
        strategy_family=RegisteredCode("FAM"),
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
    cfg1 = BacktestConfiguration(
        strategy=strat,
        entry_formula=formula,
        exit_formulas=(),
        dataset=dataset,
        cost_model=cost,
        fill_quantity=Decimal("10"),
        dataset_cutoff=dataset.manifest.last_bar,
        parameter_set_hash="a" * 64,
        seed=1,
    )
    cfg2 = BacktestConfiguration(
        strategy=strat,
        entry_formula=formula,
        exit_formulas=(),
        dataset=dataset,
        cost_model=cost,
        fill_quantity=Decimal("10"),
        dataset_cutoff=dataset.manifest.last_bar,
        parameter_set_hash="a" * 64,
        seed=999,
    )
    eid = uuid4()
    r1 = run_backtest(
        config=cfg1, test_start=dataset.manifest.first_bar, test_end=dataset.manifest.last_bar, experiment_id=eid
    )
    r2 = run_backtest(
        config=cfg2, test_start=dataset.manifest.first_bar, test_end=dataset.manifest.last_bar, experiment_id=eid
    )
    assert len(r1.trades) == len(r2.trades)
