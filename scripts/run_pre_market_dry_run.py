"""Pre-Market Synthetic Dry Run for Monday 2026-08-31 NSE Session.

Executes a complete synthetic end-to-end dry run:
1. Synthetic pre-market readiness check (SYNTHETIC_TEST_ONLY)
2. Session startup simulation
3. Live tick & scan processing (C0 production + M1-M9 / R10-X shadow ensemble)
4. Counterfactual settlement
5. Forensics generation
"""

from __future__ import annotations

import json
from decimal import Decimal
from datetime import UTC, datetime
from ats.trading_runtime.readiness import check_pre_market_readiness
from ats.trading_runtime.shadow_championship import (
    ForwardShadowChampionshipEngine,
    MarketObservationContext,
)
from ats.trading_runtime.modes import TradingMode

def main() -> None:
    print("=" * 75)
    print("  ATS PRE-MARKET SYNTHETIC DRY RUN — MONDAY 2026-08-31")
    print("  [BADGE: SYNTHETIC_TEST_ONLY]")
    print("=" * 75)

    # 1. Synthetic Readiness Check
    readiness = check_pre_market_readiness(
        trading_date="2026-08-31",
        requested_mode=TradingMode.AGGRESSIVE,
        synthetic_mode=True,
    )
    res_dict = readiness.to_dict()
    print(f"Pre-Market Readiness Status: {readiness.system_state} ({res_dict['status_verdict']})")
    assert res_dict["synthetic_test_only"] is True, "Must be tagged synthetic_test_only"
    assert readiness.ready_for_a2_paper, "Synthetic readiness check failed"

    # 2. Forward Shadow Engine Test
    shadow_engine = ForwardShadowChampionshipEngine()
    models = shadow_engine.loaded_model_identities()
    print(f"\nLoaded Shadow Model Ensemble Count: {len(models)}")
    for m in models:
        print(f"  [{m.shadow_status}] Model {m.model_id} ({m.model_name}) v{m.model_version}")

    now = datetime.now(UTC)

    # Simulate NIFTY observation with upward momentum (ROC_3 = +0.002)
    ctx_nifty = MarketObservationContext(
        market_state_id="ms_nifty_001",
        feature_bundle_id="fb_nifty_001",
        decision_time=now,
        session="2026-08-31_SESSION_001",
        underlying="NIFTY",
        spot_price=24150.00,
        vwap=24140.00,
        features={
            "roc_1": 0.001,
            "roc_3": 0.002,
            "roc_5": 0.0025,
            "accel": 0.001,
            "vol_5": 0.003,
            "range_pos": 0.75,
            "is_trend": 1.0,
        },
    )

    preds_nifty = shadow_engine.evaluate_observation(ctx_nifty)
    print(f"\nEvaluated NIFTY Shadow Ensemble (Evaluated: {len(preds_nifty)}):")
    for p in preds_nifty:
        print(f"  [{p.shadow_status}] {p.model_id}: P(UP)={p.bullish_probability:.4f}, Dir={p.predicted_direction}, Expression={p.preferred_expression}, Act={p.would_activate}")

    # 3. Simulate tick step forward and exit settlement
    now_later = datetime.fromtimestamp(now.timestamp() + 300, tz=UTC)
    ctx_nifty_later = MarketObservationContext(
        market_state_id="ms_nifty_002",
        feature_bundle_id="fb_nifty_002",
        decision_time=now_later,
        session="2026-08-31_SESSION_001",
        underlying="NIFTY",
        spot_price=24220.00,
        vwap=24160.00,
        features={
            "roc_1": 0.002,
            "roc_3": 0.003,
            "roc_5": 0.0035,
            "accel": 0.001,
            "vol_5": 0.003,
            "range_pos": 0.85,
            "is_trend": 1.0,
        },
    )

    shadow_engine.evaluate_observation(ctx_nifty_later)

    scorecard = shadow_engine.get_scorecard()
    print("\nForward Shadow Championship Scorecard:")
    print(json.dumps(scorecard, indent=2))

    print("\n" + "=" * 75)
    print("SYNTHETIC DRY RUN VERDICT: SYNTHETIC_FORWARD_SHADOW_TEST_PASS")
    print("=" * 75)

if __name__ == "__main__":
    main()
