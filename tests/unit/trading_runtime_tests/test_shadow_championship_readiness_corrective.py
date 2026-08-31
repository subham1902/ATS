"""Comprehensive Unit Tests for Corrective Readiness and Forward Shadow Championship."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from ats.trading_runtime.broker import PaperBrokerAdapter
from ats.trading_runtime.readiness import check_pre_market_readiness
from ats.trading_runtime.shadow_championship import (
    RESEARCH_COUNTERFACTUAL_POLICY_V1_HASH,
    RESEARCH_COUNTERFACTUAL_POLICY_V1_NAME,
    ContemporaneousOptionQuote,
    ForwardShadowChampionshipEngine,
    MarketObservationContext,
)

# ----------------------------------------------------------------------
# 1. Readiness Tests (False Positive & Capital Authority)
# ----------------------------------------------------------------------


def test_readiness_blocks_without_provider_instrument_specs() -> None:
    readiness = check_pre_market_readiness(
        trading_date="2026-08-31",
        synthetic_mode=False,
        provider_contracts=None,
    )
    assert readiness.ready_for_a2_paper is False
    assert "INSTRUMENT_SPEC_UNAVAILABLE" in readiness.blocking_reasons
    assert readiness.instrument_spec_source == "NONE_AVAILABLE"
    assert readiness.to_dict()["status_verdict"] == "BLOCKED_INSTRUMENT_SPEC_UNAVAILABLE"


def test_readiness_capital_mismatch_prevention() -> None:
    readiness = check_pre_market_readiness(
        trading_date="2026-08-31",
        capital_budget=Decimal("500000"),  # Divergent capital
        synthetic_mode=True,
    )
    assert readiness.ready_for_a2_paper is False
    assert "CAPITAL_MISMATCH" in readiness.blocking_reasons
    assert readiness.canonical_capital == "100000"


def test_readiness_false_positive_prevention_suite() -> None:
    # Live money
    r_live = check_pre_market_readiness(synthetic_mode=True, live_money_flag=True)
    assert "LIVE_MONEY_PROHIBITED" in r_live.blocking_reasons

    # Real broker
    r_broker = check_pre_market_readiness(synthetic_mode=True, real_broker_flag=True)
    assert "REAL_BROKER_PROHIBITED" in r_broker.blocking_reasons

    # Unhealthy feed
    r_feed = check_pre_market_readiness(synthetic_mode=True, market_feed_healthy=False)
    assert "MARKET_FEED_UNHEALTHY" in r_feed.blocking_reasons

    # Stale quotes
    r_stale = check_pre_market_readiness(synthetic_mode=False, live_instrument_quotes_fresh=False)
    assert "REQUIRED_INSTRUMENT_STALE" in r_stale.blocking_reasons


def test_synthetic_vs_live_verdict_separation() -> None:
    r_synth = check_pre_market_readiness(synthetic_mode=True)
    assert r_synth.ready_for_a2_paper is True
    assert r_synth.to_dict()["synthetic_test_only"] is True
    assert r_synth.to_dict()["status_verdict"] == "SYNTHETIC_FORWARD_SHADOW_TEST_PASS"


# ----------------------------------------------------------------------
# 2. Challenger Ensemble & Model Identity Tests
# ----------------------------------------------------------------------


def test_all_11_models_loaded_with_identities() -> None:
    engine = ForwardShadowChampionshipEngine()
    identities = engine.loaded_model_identities()
    assert len(identities) == 11

    expected_ids = {
        "C0",
        "M1",
        "M2",
        "M3",
        "M4",
        "M5",
        "M6",
        "M7",
        "M8",
        "M9",
        "R10-X",
    }
    loaded_ids = {m.model_id for m in identities}
    assert loaded_ids == expected_ids

    for m in identities:
        assert m.shadow_status == "SHADOW_ONLY"
        assert len(m.config_hash) == 64
        assert m.calibration_store_identity == "data/historical/calibration_store_v1.json"


def test_shared_market_state_identity_invariant() -> None:
    engine = ForwardShadowChampionshipEngine()
    now = datetime.now(UTC)

    ctx = MarketObservationContext(
        market_state_id="ms_shared_1234",
        feature_bundle_id="fb_shared_1234",
        decision_time=now,
        session="TEST_SESSION",
        underlying="NIFTY",
        spot_price=24150.00,
        vwap=24140.00,
        features={
            "roc_1": 0.001,
            "roc_3": 0.002,
            "roc_5": 0.0025,
            "vol_5": 0.003,
            "is_trend": 1.0,
            "range_pos": 0.75,
            "accel": 0.001,
        },
    )

    preds = engine.evaluate_observation(ctx)
    assert len(preds) == 11
    for p in preds:
        assert p.market_state_id == "ms_shared_1234"
        assert p.feature_bundle_id == "fb_shared_1234"
        assert p.decision_time == now.isoformat()
        assert p.shadow_status == "SHADOW_ONLY"


@pytest.mark.parametrize("model_idx", list(range(11)))
def test_shadow_model_zero_authority_isolation(model_idx: int) -> None:
    engine = ForwardShadowChampionshipEngine()
    model = engine.models[model_idx]
    broker = PaperBrokerAdapter()

    initial_orders_count = len(broker.query_open_orders())
    initial_positions_count = len(broker.query_positions())

    now = datetime.now(UTC)
    ctx = MarketObservationContext(
        market_state_id=f"ms_iso_{model_idx}",
        feature_bundle_id=f"fb_iso_{model_idx}",
        decision_time=now,
        session="TEST_SESSION",
        underlying="NIFTY",
        spot_price=24150.00,
        vwap=24140.00,
        features={
            "roc_1": 0.01,
            "roc_3": 0.02,
            "roc_5": 0.025,
            "vol_5": 0.003,
            "is_trend": 1.0,
            "range_pos": 0.95,
            "accel": 0.01,
        },
    )

    pred = model.predict(ctx)
    assert pred.shadow_status == "SHADOW_ONLY"

    # Zero broker/authority side-effects
    assert len(broker.query_open_orders()) == initial_orders_count
    assert len(broker.query_positions()) == initial_positions_count


def test_research_counterfactual_exit_policy_provenance() -> None:
    engine = ForwardShadowChampionshipEngine()
    now = datetime.now(UTC)

    ctx1 = MarketObservationContext(
        market_state_id="ms_exit_01",
        feature_bundle_id="fb_exit_01",
        decision_time=now,
        session="TEST_SESSION",
        underlying="NIFTY",
        spot_price=24150.00,
        vwap=24140.00,
        features={
            "roc_1": 0.01,
            "roc_3": 0.02,
            "roc_5": 0.025,
            "vol_5": 0.003,
            "is_trend": 1.0,
            "range_pos": 0.95,
            "accel": 0.01,
        },
    )
    entry_quote = ContemporaneousOptionQuote(
        instrument_key="NSE_FO|NIFTY_TEST_CE",
        expiry="2026-09-03",
        strike=24150.0,
        option_type="CE",
        bid_price=99.0,
        ask_price=100.0,
        observed_at=now,
    )
    engine.evaluate_observation(
        ctx1,
        resolved_lot_sizes={"NIFTY": 65},
        contemporaneous_option_quotes={"LONG_CE": entry_quote},
    )
    entries = engine.drain_durable_evidence()
    assert entries
    assert all(kind == "COUNTERFACTUAL_ENTRY" for kind, _ in entries)
    assert all(
        facts["entry_price_rule"] == "OBSERVED_ASK_PLUS_5BPS_SLIPPAGE"
        and facts["dynamic_lot_size"] == 65
        and facts["settlement_provenance"] == "CONTEMPORANEOUS_PROVIDER_OPTION_QUOTES"
        for _, facts in entries
    )

    # Step spot down sharply to trigger STOP_LOSS
    now_later = datetime.fromtimestamp(now.timestamp() + 300, tz=UTC)
    ctx2 = MarketObservationContext(
        market_state_id="ms_exit_02",
        feature_bundle_id="fb_exit_02",
        decision_time=now_later,
        session="TEST_SESSION",
        underlying="NIFTY",
        spot_price=23800.00,  # Sharp drop
        vwap=24100.00,
        features={
            "roc_1": -0.01,
            "roc_3": -0.02,
            "roc_5": -0.025,
            "vol_5": 0.01,
            "is_trend": 1.0,
            "range_pos": 0.05,
            "accel": -0.01,
        },
    )
    exit_quote = ContemporaneousOptionQuote(
        instrument_key="NSE_FO|NIFTY_TEST_CE",
        expiry="2026-09-03",
        strike=24150.0,
        option_type="CE",
        bid_price=90.0,
        ask_price=91.0,
        observed_at=now_later,
    )
    engine.evaluate_observation(
        ctx2,
        resolved_lot_sizes={"NIFTY": 65},
        contemporaneous_option_quotes={"LONG_CE": exit_quote},
    )
    settlements = engine.drain_durable_evidence()
    assert settlements
    assert all(kind == "COUNTERFACTUAL_SETTLEMENT" for kind, _ in settlements)
    assert all(
        facts["monetary_classification"] == "FORWARD_VALID_COUNTERFACTUAL_PNL"
        and facts["exit_price_rule"] == "OBSERVED_BID_MINUS_5BPS_SLIPPAGE"
        for _, facts in settlements
    )

    trades = engine._settled_trades
    assert len(trades) > 0
    for t in trades:
        assert t.exit_policy_name == RESEARCH_COUNTERFACTUAL_POLICY_V1_NAME
        assert t.exit_policy_hash == RESEARCH_COUNTERFACTUAL_POLICY_V1_HASH
        assert t.shadow_status == "SHADOW_ONLY"
        assert t.cost_stress_mult == 1.5


def test_counterfactual_entry_fails_closed_without_provider_metadata_and_quote() -> None:
    engine = ForwardShadowChampionshipEngine()
    now = datetime.now(UTC)
    ctx = MarketObservationContext(
        market_state_id="ms_no_evidence",
        feature_bundle_id="fb_no_evidence",
        decision_time=now,
        session="TEST_SESSION",
        underlying="NIFTY",
        spot_price=24150.0,
        vwap=24140.0,
        features={"roc_3": 0.02, "accel": 0.01},
    )

    engine.evaluate_observation(ctx)

    assert engine._active_shadow_positions == {}


def test_counterfactual_trade_identity_is_deterministic() -> None:
    now = datetime(2026, 8, 31, 4, 0, tzinfo=UTC)
    ctx = MarketObservationContext(
        market_state_id="ms_deterministic",
        feature_bundle_id="fb_deterministic",
        decision_time=now,
        session="TEST_SESSION",
        underlying="NIFTY",
        spot_price=24150.0,
        vwap=24140.0,
        features={"roc_3": 0.02, "accel": 0.01},
    )
    quote = ContemporaneousOptionQuote(
        instrument_key="NSE_FO|NIFTY_TEST_CE",
        expiry="2026-09-03",
        strike=24150.0,
        option_type="CE",
        bid_price=99.0,
        ask_price=100.0,
        observed_at=now,
    )

    engines = [ForwardShadowChampionshipEngine(), ForwardShadowChampionshipEngine()]
    for engine in engines:
        engine.evaluate_observation(
            ctx,
            resolved_lot_sizes={"NIFTY": 65},
            contemporaneous_option_quotes={"LONG_CE": quote},
        )

    ids = [engine._active_shadow_positions["C0:NIFTY"]["shadow_trade_id"] for engine in engines]
    assert ids[0] == ids[1]
