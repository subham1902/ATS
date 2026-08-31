"""Unit tests for Pre-Market Readiness and Forward Shadow Championship Engine."""

from __future__ import annotations

from datetime import UTC, datetime

from ats.trading_runtime.modes import TradingMode
from ats.trading_runtime.readiness import NextSessionReadiness, check_pre_market_readiness
from ats.trading_runtime.shadow_championship import (
    ForwardShadowChampionshipEngine,
    MarketObservationContext,
)


def test_pre_market_readiness_checker_synthetic_success() -> None:
    readiness = check_pre_market_readiness(
        trading_date="2026-08-31",
        requested_mode=TradingMode.AGGRESSIVE,
        synthetic_mode=True,
    )
    assert isinstance(readiness, NextSessionReadiness)
    assert readiness.ready_for_a2_paper is True
    assert readiness.system_state == "READY"
    assert readiness.live_money_enabled is False
    assert readiness.real_broker_execution_enabled is False
    assert len(readiness.blocking_reasons) == 0


def test_pre_market_readiness_checker_blocking_on_unhealthy_feed() -> None:
    readiness = check_pre_market_readiness(
        trading_date="2026-08-31",
        market_feed_healthy=False,
        synthetic_mode=True,
    )
    assert readiness.ready_for_a2_paper is False
    assert readiness.system_state == "NOT_READY"
    assert "MARKET_FEED_UNHEALTHY" in readiness.blocking_reasons


def test_shadow_championship_engine_predictions_and_isolation() -> None:
    engine = ForwardShadowChampionshipEngine()
    now = datetime.now(UTC)

    ctx = MarketObservationContext(
        market_state_id="ms_test_001",
        feature_bundle_id="fb_test_001",
        decision_time=now,
        session="TEST_SESSION",
        underlying="NIFTY",
        spot_price=24150.00,
        vwap=24140.00,
        features={"roc_1": 0.001, "roc_3": 0.002, "roc_5": 0.0025, "vol_5": 0.003, "is_trend": 1.0},
    )

    preds = engine.evaluate_observation(ctx)
    assert len(preds) == 11
    for p in preds:
        assert p.shadow_status == "SHADOW_ONLY"
        assert p.market_state_id == "ms_test_001"

    scorecard = engine.get_scorecard()
    assert "C0" in scorecard
    assert "M1" in scorecard
    assert "M2" in scorecard
    assert scorecard["C0"]["shadow_status"] == "SHADOW_ONLY"
