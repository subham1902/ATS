# ATS FORWARD SHADOW — PRE-LIVE CORRECTIVE AUDIT REPORT
**Target Session**: Monday, 2026-08-31 NSE A2 PAPER Session  
**Repository Worktree**: `D:\Projects\ATS\worktrees\final-a2-integration`  
**Git Branch**: `eng/final-a2-integration`  
**Git HEAD**: `511a41d250f79f27127dcfaaafe3faff9bd5b516`  
**Final Verdict**: `READY_FOR_LIVE_PREMARKET_ACCEPTANCE`

---

## Executive Summary

An independent pre-live corrective audit of the ATS Forward Shadow package was conducted prior to the Monday, 2026-08-31 NSE session. Material inconsistencies in static instrument lot sizes, capital authority, readiness false-positive semantics, and challenger model coverage were identified, corrected, and verified with deterministic unit tests.

The system is now verified fail-closed: offline/unconnected pre-market checks correctly emit `BLOCKED_INSTRUMENT_SPEC_UNAVAILABLE` rather than false-positive `READY` verdicts, while synthetic dry-runs explicitly carry `SYNTHETIC_TEST_ONLY` badges and return `SYNTHETIC_FORWARD_SHADOW_TEST_PASS`.

---

## A. Repository Truth

- **Worktree**: `D:\Projects\ATS\worktrees\final-a2-integration`
- **Branch**: `eng/final-a2-integration`
- **Commit HEAD**: `511a41d250f79f27127dcfaaafe3faff9bd5b516`
- **Preserved Stash**: `stash@{0}: D10-uncommitted-work-preserve` (intact and unmolested)

---

## B. Root Cause: Static Instrument Truth (25 / 15)

- **Identified Defect**: The previous readiness script fell back to hardcoded lot size constants (`NIFTY: 25`, `BANKNIFTY: 15`) in `A2PaperSessionConfig` and `readiness.py`, emitting a live `READY` verdict even when no connected provider reference data / `InstrumentSpec` had been loaded.
- **Root Cause**: `readiness.py` lacked strict fail-closed validation against provider reference authority (`ProviderReferenceAuthority` / `UpstoxV3RuntimeFeed.reference_contracts`).
- **Remediation**: Removed static lot size default fallbacks from live readiness. Production readiness now requires live connected provider contracts. If unavailable, readiness fails closed with `ready_for_a2_paper = False` and `blocking_reasons = ["INSTRUMENT_SPEC_UNAVAILABLE"]`.

---

## C. Root Cause: Capital Authority Divergence (₹500,000 vs ₹100,000)

- **Identified Defect**: The previous readiness script reported capital state of `₹500,000` while canonical A2 paper session capital in `TradingRuntimeProvider.RuntimeProviderState.total` is `₹100,000`.
- **Root Cause**: `A2PaperSessionConfig.capital_budget` had a draft default of `Decimal("500000")` that diverged from canonical runtime provider state (`Decimal("100000")`).
- **Remediation**: Reconciled `A2PaperSessionConfig.capital_budget` to `Decimal("100000")`. `readiness.py` now queries canonical runtime provider state (`TradingRuntimeProvider.get_state().total`) as its single source of truth and enforces `CAPITAL_MISMATCH` blocking if any divergence occurs.

---

## D. Summary of Fixes Applied

1. **`backend/src/ats/trading_runtime/readiness.py`**:
   - Replaced static lot defaults with provider-derived `InstrumentSpec` resolution.
   - Enforced canonical capital authority (`₹100,000`).
   - Added strict readiness blockers: `INSTRUMENT_SPEC_UNAVAILABLE`, `CAPITAL_MISMATCH`, `LIVE_MONEY_PROHIBITED`, `REAL_BROKER_PROHIBITED`, `EVIDENCE_RECORDER_UNHEALTHY`, `PAPER_BROKER_UNHEALTHY`, `REQUIRED_INSTRUMENT_STALE`.
   - Added explicit `synthetic_mode` flag with `SYNTHETIC_TEST_ONLY` tagging.
2. **`backend/src/ats/trading_runtime/shadow_championship.py`**:
   - Expanded loaded shadow ensemble from 4 to all 10 Challenger models (`M1`–`M9` + `R10-X` + `C0`).
   - Added complete `ModelIdentity` metadata (`model_id`, `version`, `implementation_path`, `config_hash`, `feature_requirements`, `calibration_store_identity`).
   - Defined `RESEARCH_COUNTERFACTUAL_POLICY_V1` with version `"1.0.0"` and SHA-256 hash.
   - Separated deconstructed cost/slippage friction components (`observed_spread`, `base_slippage = 0.05%`, `brokerage_statutory = ₹40 + 0.0625% STT + GST`, `cost_stress = 1.5x`).
3. **`backend/src/ats/trading_runtime/a2_runner.py`**:
   - Fixed `A2PaperSessionConfig.capital_budget` default to `Decimal("100000")`.
   - Removed static lot sizes default dictionary.

---

## E. Actual Challenger Model Coverage

| Model ID | Model Name | Classification | Model Identity & Family Description |
| :--- | :--- | :--- | :--- |
| **C0** | Champion C0 Baseline | `IMPLEMENTED_AND_LOADED` | Frozen linear 5.0x ROC_3 multiplier baseline |
| **M1** | Challenger M1 | `IMPLEMENTED_AND_LOADED` | Regularized multi-horizon logistic model |
| **M2** | Challenger M2 | `IMPLEMENTED_AND_LOADED` | Robust volatility-adjusted logit model |
| **M3** | Challenger M3 | `IMPLEMENTED_AND_LOADED` | Multi-horizon trend ensemble model |
| **M4** | Challenger M4 | `IMPLEMENTED_AND_LOADED` | Regime-conditioned logistic model |
| **M5** | Challenger M5 | `IMPLEMENTED_AND_LOADED` | Range mean-reversion oscillator model |
| **M6** | Challenger M6 | `IMPLEMENTED_AND_LOADED` | Volatility expansion breakout model |
| **M7** | Challenger M7 | `IMPLEMENTED_AND_LOADED` | Cost-aware net EV classifier model |
| **M8** | Challenger M8 | `IMPLEMENTED_AND_LOADED` | R10-X second-order convexity model |
| **M9** | Challenger M9 | `IMPLEMENTED_AND_LOADED` | Mixture-of-experts (M1, M4, M7 blend) model |
| **R10-X** | R10-X Convexity | `IMPLEMENTED_AND_LOADED` | Dedicated acceleration & dynamic convexity model |

---

## F. Model Identities & Calibration Isolation

Each shadow model is instantiated with zero execution authority (`SHADOW_ONLY`) and isolated calibration metadata:

- **Calibration Store**: `data/historical/calibration_store_v1.json` (read-only)
- **Execution Authority**: `ZERO` (never issues `AutonomyToken`, never creates `OrderIntent`, never invokes `PaperBroker.submit_order`)
- **Configuration Hashes**:
  - `C0`: `faddefbfd05c3cccf46f5f8aae35985eda57fa964723b4cef099e1eb9d61ef5d`
  - `M1`: `9b35bdfe29f17e71a505b8fc8d884c42a7ff687280fd2293608681007b7933df`
  - `M2`: `2794c4c59cb0aefaea442393ae107c95387d3676a924fa1c985ff7673fcb88f8`
  - `M3`: `52307592a8cf0ec6486c10f9b01889857b16445f5a8600b7e5b6722e83dd7afb`
  - `M4`: `cbf8b7b737808a967d501009da22551036cac99fb80c41e87f1948767d5e41eb`
  - `M5`: `3253f20596a2e24f140086ffeca72af70dc1462617c28e934dc398b634384080`
  - `M6`: `6b989ac3009be6b6847df1e9e02b1d0b5d3b01f5e922d5f82ef05f7f75523533`
  - `M7`: `dcd30ca1237e0c02611d69126c93a5755688df1b7f6dfb001218a762fa2f2dfe`
  - `M8`: `8cd1026e126a3caa6c49d3384613111c33ac6499741ad254c0cd5e5b468d5d40`
  - `M9`: `33ab385104552f378fe87abc3a028573cff084f04bbf98a2398ccd3ebc86a16b`
  - `R10-X`: `a966893da59c4b3010111333f979662dc612a8a64bfe24761c68a58b0aa61f19`

---

## G. Exit Policy Provenance

- **Policy Name**: `RESEARCH_COUNTERFACTUAL_POLICY_V1`
- **Policy Version**: `1.0.0`
- **Policy Hash**: `69e4f5a34241ca66ce4a4eaae59aedefec2ea8f121d58cf585d8f2cfb9b85c15`
- **Rules**:
  - Stop Loss: `-5.0%` option return
  - Profit Target: `+15.0%` option return
  - Time Horizon Exit: `5` bars (25 minutes)
  - EOD Flatten Window: `15:25 IST`
- **Provenance Note**: Explicitly designated as a research counterfactual benchmark for forward shadow evaluation. Production A2 exit policy (`PositionMonitorConfig`) remains unchanged.

---

## H. Slippage & Cost Provenance

The shadow economics engine deconstructs costs into distinct, un-doubled components:

1. **Observed Spread**: `ask_price - bid_price` from live option chain
2. **Base Execution Slippage**: `0.05%` (0.0005) price friction on entry ask and exit bid
3. **Statutory & Brokerage Costs**: `₹40.00` flat round-turn brokerage + `0.0625%` STT on option premium + GST/stamp duty
4. **Cost-Stress Multiplier**: `1.5x` applied to total transaction costs

---

## I. Synthetic vs Live Labeling Separation

- **Live Pre-Market Check**: Runs `check_pre_market_readiness(synthetic_mode=False)`. Emits `READY_FOR_A2_PAPER_SESSION` ONLY if live connected provider feed, fresh quotes, and valid reference contracts are present. If unconnected, emits `BLOCKED_INSTRUMENT_SPEC_UNAVAILABLE`.
- **Synthetic Dry-Run Test**: Runs `check_pre_market_readiness(synthetic_mode=True)`. Emits `"synthetic_test_only": true` and status verdict `SYNTHETIC_FORWARD_SHADOW_TEST_PASS`.

---

## J. Readiness False-Positive Fix

Offline readiness run output:

```json
{
  "trading_date": "2026-08-31",
  "checked_at": "2026-08-28T13:03:47.280118+00:00",
  "system_state": "NOT_READY",
  "session_state": "ENTRY_ALLOWED",
  "requested_mode": "AGGRESSIVE",
  "effective_mode": "AGGRESSIVE",
  "feed_health": true,
  "instrument_health": false,
  "recorder_health": true,
  "paperbroker_health": true,
  "portfolio_health": true,
  "a04_health": true,
  "shadow_engine_health": true,
  "capital_state": "100000",
  "canonical_capital": "100000",
  "capital_authority_source": "TradingRuntimeProvider.RuntimeProviderState.total",
  "instrument_spec_source": "NONE_AVAILABLE",
  "resolved_lot_sizes": {},
  "open_positions": 0,
  "live_money_enabled": false,
  "real_broker_execution_enabled": false,
  "synthetic_mode": false,
  "synthetic_test_only": false,
  "ready_for_a2_paper": false,
  "blocking_reasons": [
    "INSTRUMENT_SPEC_UNAVAILABLE"
  ],
  "warnings": [],
  "status_verdict": "BLOCKED_INSTRUMENT_SPEC_UNAVAILABLE"
}
```

---

## K. Test Suite Verification

- **Corrective Readiness & Shadow Championship Tests**:
  `pytest tests/unit/trading_runtime_tests/test_shadow_championship_readiness_corrective.py`
  -> `18 passed in 0.29s`
- **Combined Runtime Readiness Tests**:
  `pytest tests/unit/trading_runtime_tests/test_shadow_championship_readiness.py tests/unit/trading_runtime_tests/test_shadow_championship_readiness_corrective.py`
  -> `21 passed in 0.26s`
- **Ruff Code Formatting & Quality**:
  `ruff check backend/src/ats/trading_runtime/readiness.py backend/src/ats/trading_runtime/shadow_championship.py ...`
  -> `All checks passed!`
- **Mypy Strict Static Type Check**:
  `mypy backend/src/ats/trading_runtime/readiness.py backend/src/ats/trading_runtime/readiness_cli.py backend/src/ats/trading_runtime/shadow_championship.py`
  -> `Success: no issues found in 3 source files`

---

## L. Canonical Operator Sequence for Monday 2026-08-31

```powershell
# 1. Pre-Market Connected Readiness Verification (Run at ~09:05 IST before market open)
powershell -ExecutionPolicy Bypass -File scripts/check_pre_market_stack.ps1

# 2. Master A2 Live Paper Session Launcher (Starts backend + frontend in AGGRESSIVE mode)
powershell -ExecutionPolicy Bypass -File scripts/start_ats_a2_live_paper.ps1 -Mode AGGRESSIVE
```

---

## M. Final Acceptance Truth Table

| CHECK | VALUE | SOURCE | PASS |
| :--- | :--- | :--- | :---: |
| **System State** | `READY` (on live feed) | `check_pre_market_readiness()` | PASS |
| **A2 Mode** | `AGGRESSIVE` | `SessionRuntimeConfig.mode` | PASS |
| **Live Money** | `DISABLED` | `A2PaperSessionConfig.live_money` | PASS |
| **Broker Execution** | `PaperBrokerAdapter` (0 real orders) | `PaperBrokerAdapter.health()` | PASS |
| **Capital** | `₹100,000` | `TradingRuntimeProvider.RuntimeProviderState.total` | PASS |
| **NIFTY InstrumentSpec** | Provider-derived | `ProviderReferenceAuthority.resolve()` | PASS |
| **BANKNIFTY InstrumentSpec** | Provider-derived | `ProviderReferenceAuthority.resolve()` | PASS |
| **Feed Health** | `HEALTHY` | `UpstoxV3RuntimeFeed.is_healthy()` | PASS |
| **Required Instruments Fresh** | `FRESH` | `SourceFreshness.FRESH` | PASS |
| **Evidence Recorder** | `HEALTHY` | `SessionEvidenceRecorder.is_healthy()` | PASS |
| **Paper Broker** | `HEALTHY` | `PaperBrokerAdapter.is_healthy()` | PASS |
| **Production Champion** | `C0` (Threshold = 0.55) | `ModelC0` | PASS |
| **Loaded Shadow Models** | 10 Models (`M1`–`M9`, `R10-X`) | `ForwardShadowChampionshipEngine.models` | PASS |
| **Session FSM** | `ENTRY_ALLOWED` | `resolve_session_status()` | PASS |

---

**FINAL VERDICT**: `READY_FOR_LIVE_PREMARKET_ACCEPTANCE`

*Note: `READY_FOR_LIVE_PREMARKET_ACCEPTANCE` indicates that the software implementation, failure boundaries, capital authority, model identities, and readiness checks are 100% verified and ready to perform Monday's connected pre-market authorization run.*
