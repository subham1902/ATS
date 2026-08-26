"""R14 hardening: India cost stack, conservative fills, anti-overfit, robustness, lineage, overlapping labels."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from ats.contracts.domain.types import DataQualityState, SessionState
from ats.contracts.intelligence.types import ScorecardValidationStatus
from ats.intelligence.strategy_lab.anti_overfit import (
    build_lineage,
    build_overfit_evidence,
    cscv_evidence,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    pbo_evidence,
    probabilistic_sharpe_ratio,
)
from ats.intelligence.strategy_lab.cost_model import (
    ConservativeCostModel,
    IndiaCashCostModel,
    ZeroCostModel,
    default_india_conservative_cost_model,
)
from ats.intelligence.strategy_lab.leakage_scanner import scan_leakage
from ats.intelligence.strategy_lab.experiment_runner import build_experiment
from ats.contracts.intelligence.types import ExperimentType
from ats.intelligence.strategy_lab.robustness import (
    parameter_perturbation_score,
    walk_forward_dispersion,
)
from ats.intelligence.strategy_lab.types import BacktestResult, ResearchFill, ResearchTrade
from ats.intelligence.strategy_lab.scorecard import build_scorecard
from ats.market.replay.models import ReplayBar, ReplayDataset, ReplayManifest


def _bars(n: int = 20) -> ReplayDataset:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    bars: list[ReplayBar] = []
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


# ---- F01: India cost stack is explicit and versioned ----

def test_india_cost_breakdown_sums_to_total() -> None:
    m = IndiaCashCostModel(
        cost_model_version="india-cash-v1",
        brokerage_bps=Decimal("2"),
        exchange_fee_bps=Decimal("0.5"),
        stt_bps=Decimal("2"),
        stamp_duty_bps=Decimal("1"),
        sebi_bps=Decimal("0.1"),
        spread_bps=Decimal("2"),
        slippage_bps=Decimal("3"),
    )
    bd = m.breakdown_per_fill(price=Decimal("1000"), quantity=Decimal("10"), side="BUY")
    recomputed = sum(v for k, v in bd.items() if k != "total")
    assert bd["total"] == recomputed


def test_india_cost_gst_only_on_brokerage_plus_exchange() -> None:
    m = IndiaCashCostModel(
        cost_model_version="india-cash-v1",
        brokerage_bps=Decimal("10"),
        exchange_fee_bps=Decimal("10"),
        stt_bps=Decimal("0"),
        stamp_duty_bps=Decimal("0"),
        sebi_bps=Decimal("0"),
        spread_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        gst_rate=Decimal("0.18"),
    )
    bd = m.breakdown_per_fill(price=Decimal("100"), quantity=Decimal("10"), side="BUY")
    assert bd["gst"] == (bd["brokerage"] + bd["exchange_fee"]) * Decimal("0.18")


def test_conservative_adds_extra_slippage() -> None:
    inner = IndiaCashCostModel(cost_model_version="india-cash-v1", brokerage_bps=Decimal("1"))
    cons = ConservativeCostModel(inner=inner, extra_slippage_bps=Decimal("5"))
    base = inner.cost_per_trade(price=Decimal("100"), quantity=Decimal("10"), side="BUY")
    bumped = cons.cost_per_trade(price=Decimal("100"), quantity=Decimal("10"), side="BUY")
    assert bumped > base


def test_default_india_conservative_is_authoritative_and_versioned() -> None:
    m = default_india_conservative_cost_model()
    assert m.cost_model_authoritative is True
    assert m.cost_model_version == "india-cash-conservative-v1"
    assert m.inner.cost_model_version == "india-cash-v1"
    c = m.cost_per_trade(price=Decimal("100"), quantity=Decimal("10"), side="BUY")
    assert c >= 0
    assert c.is_finite()


def test_spread_and_slippage_labelled_separately() -> None:
    m = IndiaCashCostModel(
        cost_model_version="india-cash-v1",
        spread_bps=Decimal("4"),
        slippage_bps=Decimal("6"),
    )
    bd = m.breakdown_per_fill(price=Decimal("100"), quantity=Decimal("10"), side="BUY")
    assert bd["spread"] != bd["slippage"]
    assert bd["spread"] > 0 and bd["slippage"] > 0


# ---- F03: purge/embargo/overlapping labels ----

def test_insufficient_purge_is_rejected_with_dataset() -> None:
    ds = _bars(20)
    exp = build_experiment(
        experiment_id=uuid4(),
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_type=ExperimentType.BACKTEST,
        instrument_universe=("NSE_EQ-TCS",),
        timeframe="5m",
        dataset_manifest_id=ds.manifest.dataset_id,
        dataset_version=ds.manifest.dataset_version,
        dataset_cutoff=ds.manifest.last_bar,
        train_start=ds.bars[0].bar_timestamp,
        train_end=ds.bars[9].bar_timestamp,
        test_start=ds.bars[10].bar_timestamp,
        test_end=ds.bars[15].bar_timestamp,
        purge_bars=5,
        embargo_bars=0,
        cost_model_version="v1",
        parameter_set_hash="a" * 64,
        seed=1,
    )
    res = scan_leakage(exp, ds)
    from ats.contracts.intelligence.types import LeakageScanStatus

    assert res.status is LeakageScanStatus.FAIL
    assert "insufficient_purge_gap" in res.reason_codes


def test_overlapping_label_protection_requires_embargo() -> None:
    ds = _bars(20)
    exp = build_experiment(
        experiment_id=uuid4(),
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_type=ExperimentType.BACKTEST,
        instrument_universe=("NSE_EQ-TCS",),
        timeframe="5m",
        dataset_manifest_id=ds.manifest.dataset_id,
        dataset_version=ds.manifest.dataset_version,
        dataset_cutoff=ds.manifest.last_bar,
        train_start=ds.bars[0].bar_timestamp,
        train_end=ds.bars[9].bar_timestamp,
        test_start=ds.bars[11].bar_timestamp,
        test_end=ds.bars[15].bar_timestamp,
        purge_bars=1,
        embargo_bars=0,
        cost_model_version="v1",
        parameter_set_hash="a" * 64,
        seed=1,
    )
    res = scan_leakage(exp, ds, label_horizon_bars=5)
    from ats.contracts.intelligence.types import LeakageScanStatus

    assert res.status is LeakageScanStatus.FAIL
    assert "overlapping_label_protection_failed" in res.reason_codes


def test_walk_forward_overlap_is_rejected() -> None:
    ds = _bars(20)
    from ats.intelligence.strategy_lab.walk_forward import build_rolling_plan
    from ats.intelligence.strategy_lab.types import WalkForwardPlan, WalkForwardWindow

    w1 = WalkForwardWindow(
        window_id=uuid4(),
        train_start=ds.bars[0].bar_timestamp,
        train_end=ds.bars[4].bar_timestamp,
        test_start=ds.bars[6].bar_timestamp,
        test_end=ds.bars[9].bar_timestamp,
        purge_bars=1,
        embargo_bars=1,
    )
    w2 = WalkForwardWindow(
        window_id=uuid4(),
        train_start=ds.bars[10].bar_timestamp,
        train_end=ds.bars[13].bar_timestamp,
        test_start=ds.bars[8].bar_timestamp,
        test_end=ds.bars[14].bar_timestamp,
        purge_bars=1,
        embargo_bars=1,
    )
    plan = WalkForwardPlan(plan_id=uuid4(), windows=(w1, w2), mode="rolling")
    exp = build_experiment(
        experiment_id=uuid4(),
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_type=ExperimentType.WALK_FORWARD,
        instrument_universe=("NSE_EQ-TCS",),
        timeframe="5m",
        dataset_manifest_id=ds.manifest.dataset_id,
        dataset_version=ds.manifest.dataset_version,
        dataset_cutoff=ds.manifest.last_bar,
        train_start=ds.bars[0].bar_timestamp,
        train_end=ds.bars[4].bar_timestamp,
        test_start=ds.bars[6].bar_timestamp,
        test_end=ds.bars[9].bar_timestamp,
        purge_bars=1,
        embargo_bars=1,
        cost_model_version="v1",
        parameter_set_hash="a" * 64,
        seed=1,
    )
    res = scan_leakage(exp, ds, walk_forward_plan=plan)
    from ats.contracts.intelligence.types import LeakageScanStatus

    assert res.status is LeakageScanStatus.FAIL


# ---- Anti-overfit: PSR/DSR/PBO/CSCV return UNKNOWN when insufficient ----

def test_psr_insufficient_returns_string() -> None:
    r = probabilistic_sharpe_ratio(1.0, n=10)
    assert r == "INSUFFICIENT_EVIDENCE"


def test_psr_sufficient_returns_float() -> None:
    r = probabilistic_sharpe_ratio(1.0, n=50)
    assert isinstance(r, float)
    assert 0 <= r <= 1


def test_dsr_insufficient_trials() -> None:
    r = deflated_sharpe_ratio(1.5, n=50, n_trials=2)
    assert r == "INSUFFICIENT_EVIDENCE"


def test_dsr_sufficient() -> None:
    r = deflated_sharpe_ratio(0.8, n=100, n_trials=100)
    assert isinstance(r, float)


def test_pbo_insufficient() -> None:
    assert pbo_evidence([1.0, 2.0], [1.0, 2.0]) == "INSUFFICIENT_EVIDENCE"


def test_pbo_sufficient() -> None:
    r = pbo_evidence([1.0] * 6, [0.5] * 6)
    assert isinstance(r, float)
    assert 0 <= r <= 1  # type: ignore[operator]


def test_cscv_insufficient() -> None:
    assert cscv_evidence([1.0, 2.0]) == "INSUFFICIENT_EVIDENCE"


def test_expected_max_sharpe_insufficient() -> None:
    assert expected_max_sharpe(n_trials=2, n_obs=10) == "INSUFFICIENT_EVIDENCE"
    assert isinstance(expected_max_sharpe(n_trials=10, n_obs=50), float)


def test_overfit_evidence_returns_unknown_when_insufficient() -> None:
    now = datetime(2024, 1, 10, tzinfo=UTC)
    ev = build_overfit_evidence(
        strategy_definition_id=uuid4(),
        experiment_ids=(uuid4(),),
        sample_count=5,
        trial_count=1,
        sharpe=0.5,
        n_trials=1,
        created_at=now,
    )
    assert ev.psr in ("UNKNOWN", "INSUFFICIENT_EVIDENCE")
    assert ev.dsr in ("UNKNOWN", "INSUFFICIENT_EVIDENCE")
    assert ev.pbo == "INSUFFICIENT_EVIDENCE"


def test_overfit_evidence_sufficient_yields_floats() -> None:
    now = datetime(2024, 1, 10, tzinfo=UTC)
    ev = build_overfit_evidence(
        strategy_definition_id=uuid4(),
        experiment_ids=(uuid4(),),
        sample_count=100,
        trial_count=20,
        sharpe=1.2,
        n_trials=20,
        pbo_is=[1.0] * 6,
        pbo_oos=[0.5] * 6,
        cscv_folds=[0.8, 0.9, 1.0, 1.1],
        created_at=now,
    )
    assert isinstance(ev.psr, float)
    assert isinstance(ev.dsr, float)
    assert isinstance(ev.pbo, float)


# ---- Robustness ----

def test_parameter_perturbation_uses_scorecard() -> None:
    now = datetime(2024, 1, 10, tzinfo=UTC)
    fills = (
        ResearchFill(
            fill_id=uuid4(),
            signal_id=uuid4(),
            instrument_id="NSE_EQ-TCS",
            side="BUY",
            price=Decimal("100"),
            quantity=Decimal("10"),
            bar_timestamp=now,
            bar_sequence=1,
            cost=Decimal("1"),
        ),
        ResearchFill(
            fill_id=uuid4(),
            signal_id=uuid4(),
            instrument_id="NSE_EQ-TCS",
            side="SELL",
            price=Decimal("102"),
            quantity=Decimal("10"),
            bar_timestamp=now,
            bar_sequence=2,
            cost=Decimal("1"),
        ),
    )
    trades = (
        ResearchTrade(
            trade_id=uuid4(),
            instrument_id="NSE_EQ-TCS",
            entry_fill=fills[0],
            exit_fill=fills[1],
            entry_time=now,
            exit_time=now,
            pnl_fraction=Decimal("0.015"),
            pnl_r=Decimal("1.5"),
        ),
    ) * 5
    base = BacktestResult(
        result_id=uuid4(),
        experiment_id=uuid4(),
        trades=tuple(trades),  # type: ignore[arg-type]
        fills=fills,
        signals=(),
        start_time=now,
        end_time=now,
        seed=1,
        cost_model_version="v1",
        cost_model_authoritative=True,
    )
    score = parameter_perturbation_score(base, [base, base], cost_version="v1")
    assert 0 <= score <= 1


def test_walk_forward_dispersion_unknown_when_insufficient() -> None:
    assert walk_forward_dispersion([1.0]) == "UNKNOWN"
    assert walk_forward_dispersion([None, None]) == "UNKNOWN"


def test_walk_forward_dispersion_float_when_sufficient() -> None:
    r = walk_forward_dispersion([1.0, 1.1, 0.9, 1.05])
    assert isinstance(r, float)


# ---- Lineage ----

def test_lineage_requires_trial_count() -> None:
    now = datetime(2024, 1, 10, tzinfo=UTC)
    with pytest.raises(Exception):
        build_lineage(
            strategy_definition_id=uuid4(),
            strategy_definition_version=1,
            parent_strategy_ref=None,
            origin="PARAMETER_SEARCH",
            dataset_manifest_id=uuid4(),
            dataset_version="v1",
            trial_count=0,
            parameter_search_count=0,
            seed=42,
            cost_model_version="v1",
            created_at=now,
        )


def test_lineage_ok() -> None:
    now = datetime(2024, 1, 10, tzinfo=UTC)
    lin = build_lineage(
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        parent_strategy_ref=None,
        origin="PARAMETER_SEARCH",
        dataset_manifest_id=uuid4(),
        dataset_version="v1",
        trial_count=10,
        parameter_search_count=8,
        seed=42,
        cost_model_version="v1",
        created_at=now,
    )
    assert lin.trial_count == 10
    assert lin.parameter_search_count == 8
    assert lin.seed == 42


# ---- Cost realism: no magical closes ----

def test_fill_assumption_labels_uncertainty() -> None:
    from ats.intelligence.strategy_lab.types import FillAssumption

    fa = FillAssumption(
        model_version="india-cash-conservative-v1",
        description="next open, no candle-close fills",
        cost_stack_version="india-cash-v1",
    )
    assert "conservative" in fa.ohlc_uncertainty_label or "no_candle" in fa.ohlc_uncertainty_label


def test_leakage_intentionally_leaking_sample_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_experiment(
            experiment_id=uuid4(),
            strategy_definition_id=uuid4(),
            strategy_definition_version=1,
            experiment_type=ExperimentType.BACKTEST,
            instrument_universe=("NSE_EQ-TCS",),
            timeframe="5m",
            dataset_manifest_id=uuid4(),
            dataset_version="v1",
            dataset_cutoff=datetime(2024, 1, 20, tzinfo=UTC),
            train_start=datetime(2024, 1, 5, tzinfo=UTC),
            train_end=datetime(2024, 1, 15, tzinfo=UTC),
            test_start=datetime(2024, 1, 10, tzinfo=UTC),
            test_end=datetime(2024, 1, 18, tzinfo=UTC),
            purge_bars=0,
            embargo_bars=0,
            cost_model_version="v1",
            parameter_set_hash="a" * 64,
            seed=1,
        )
