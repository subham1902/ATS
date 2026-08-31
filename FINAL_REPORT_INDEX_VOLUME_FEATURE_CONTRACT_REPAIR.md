# FINAL REPORT — INDEX VOLUME FEATURE CONTRACT REPAIR

**Worktree**: `D:\Projects\ATS\worktrees\final-a2-integration`  
**Branch**: `eng/final-a2-integration`  
**Base Qualified HEAD**: `6bb5a0a05866617352cf12a1fe7daf43538d313f`  
**New Qualified HEAD**: `45bc2ab4a76da38a9968842a18867e549fcb4112`  
**Execution Mode**: `PAPER` (Live Money Disabled)

---

## 1. ROOT CAUSE

The Upstox V3 live WebSocket index ticks for `NSE_INDEX|Nifty 50` and `NSE_INDEX|Nifty Bank` legitimately lack continuous traded volume (`volume = 0` / absent volume in provider feed).
When ingested, `A2PaperSessionController` tags snapshots with `quality_flags = ("VOLUME_UNAVAILABLE",)` and `quality_state = DataQualityState.DEGRADED`.

Prior to this repair:
- `backend/src/ats/market/features/engine.py` contained a blanket assertion `if snapshot.quality_state is not DataQualityState.GOOD or snapshot.quality_flags: raise FeatureInputError(...)`.
- This rejected all snapshots carrying `VOLUME_UNAVAILABLE`, completely preventing `compute_feature_bundle` from extracting price-derived features (`roc_3_fraction`, returns, candle metrics, realized volatility).
- Consequently, downstream `detect_regime` and `C0ProductionChampion` evaluations were blocked on live streaming updates, outputting `FEATURE_ERROR_FeatureInputError` and causing `REGIME = NOT_COMPUTED` and `VOLATILITY = NOT_COMPUTED`.

---

## 2. FILES CHANGED

1. [`backend/src/ats/market/features/engine.py`](file:///D:/Projects/ATS/worktrees/final-a2-integration/backend/src/ats/market/features/engine.py)
   - Updated `_validate_prefix()` to allow `DataQualityState.DEGRADED` specifically when caused by `VOLUME_UNAVAILABLE`, while remaining fail-closed against all other quality flags or corrupted payload hashes.
   - Updated `_compute_rolling_features()` so that volume-dependent features (`rolling_volume_mean_3`, `relative_volume_3`) are computed **only** when authoritative traded volume is present across the lookback window.
   - Updated `compute_feature_bundle()` to attach `VOLUME_UNAVAILABLE` to `FeatureBundle.quality_flags` as truthful provenance without fabricating synthetic volume or synthetic metrics.
2. [`backend/src/ats/intelligence/regime/detector.py`](file:///D:/Projects/ATS/worktrees/final-a2-integration/backend/src/ats/intelligence/regime/detector.py)
   - Updated `detect_regime()` quality check to allow `VOLUME_UNAVAILABLE` provenance on feature bundles while strictly gating on fatal quality flags and requiring price-only feature prerequisites (`roc_3_fraction`, `rolling_price_position_3`, `realized_volatility_3_population`).
3. [`tests/unit/market/features/test_volume_unavailable_contract.py`](file:///D:/Projects/ATS/worktrees/final-a2-integration/tests/unit/market/features/test_volume_unavailable_contract.py)
   - Added focused regression and contract unit tests verifying price feature extraction, volume omission, fail-closed handling of fatal quality flags, and regime detection.

---

## 3. FEATURE REQUIREMENT MATRIX

| Feature Code | Mathematical Dependency | Requires Traded Volume | Behavior when `VOLUME_UNAVAILABLE` |
|---|---|---|---|
| `simple_return` | Price ($P_t, P_{t-1}$) | NO | Computes normally |
| `log_return` | Price ($P_t, P_{t-1}$) | NO | Computes normally |
| `candle_body` | Price ($O_t, C_t$) | NO | Computes normally |
| `candle_range` | Price ($H_t, L_t$) | NO | Computes normally |
| `upper_wick` | Price ($O_t, H_t, C_t$) | NO | Computes normally |
| `lower_wick` | Price ($O_t, L_t, C_t$) | NO | Computes normally |
| `rolling_price_position_3` | Price ($C_t, H_{t-2:t}, L_{t-2:t}$) | NO | Computes normally |
| `atr_3_sma` | Price ($H_t, L_t, C_{t-1}$) | NO | Computes normally |
| `realized_volatility_3_population` | Price returns | NO | Computes normally |
| `roc_3_fraction` | Price ($C_t, C_{t-3}$) | NO | Computes normally |
| `rolling_volume_mean_3` | Traded Volume ($V_{t-2:t}$) | **YES** | **Omitted / Fail-Closed** |
| `relative_volume_3` | Traded Volume ($V_t, \bar{V}$) | **YES** | **Omitted / Fail-Closed** |

---

## 4. PRICE ONLY FEATURES

- `simple_return`
- `log_return`
- `candle_body`
- `candle_range`
- `upper_wick`
- `lower_wick`
- `rolling_price_position_3`
- `atr_3_sma`
- `realized_volatility_3_population`
- `roc_3_fraction`

---

## 5. VOLUME REQUIRED FEATURES

- `rolling_volume_mean_3`
- `relative_volume_3`

---

## 6. QUALITY PROVENANCE MODEL

- Snapshots lacking traded volume are marked with `quality_flags = ("VOLUME_UNAVAILABLE",)`.
- When volume is unavailable, `FeatureBundle` preserves the truthful provenance by setting `quality_flags = ("VOLUME_UNAVAILABLE",)`.
- Zero volume is never treated as positive trade volume.
- No synthetic volume ($1$ or average) is injected.
- All non-volume data corruption or timestamp inversions immediately raise `FeatureInputError`.

---

## 7. C0 / REGIME / VOLATILITY BEFORE & AFTER

| Component | Before Repair | After Repair |
|---|---|---|
| **C0 Evaluation** | Blocked with `FeatureInputError` on tick updates | Evaluates repeatedly on continuous live ticks ($P(\text{UP}) = 0.501 - 0.506$) |
| **C0 Activation Threshold** | `0.55` (Unchanged) | `0.55` (Unchanged) |
| **C0 Mathematical Formula** | $\text{clamp}(0.05, 0.95, 0.50 + 5.0 \times \text{ROC}_3)$ | $\text{clamp}(0.05, 0.95, 0.50 + 5.0 \times \text{ROC}_3)$ (Unchanged) |
| **Regime Detection** | `NOT_COMPUTED` (None) | Computes price-based structural regime |
| **Volatility Detection** | `NOT_COMPUTED` (None) | Computes price-based return volatility |

---

## 8. TEST & VERIFICATION RESULTS

- **Ruff Lint & Format**: `All checks passed!`
- **Mypy Static Typing**: `Success: no issues found in 8 source files`
- **Feature & Regime Suites**: `39 passed in 0.56s` (Unit + Property + Integration)
- **Full Trading Runtime & Forensics Suite**: `249 passed, 2 skipped in 134.76s`
- **Bytecode Compilation**: `python -m compileall` passed 100% cleanly across all market and intelligence modules.
- **Live Connected Requalification Run (`c2107efa-8a36-46d3-acbf-170243a100e7`)**:
  - `92` Authoritative C0 evaluations recorded in live market conditions.
  - `92` `FEATURE_STATE` events emitted with clean price features.
  - `0` `FEATURE_ERROR_FeatureInputError` rejections occurred.
  - `0` Paper or real broker orders executed (deterministic safety preserved as C0 scores $0.501 - 0.506 < 0.55$).

---

## 9. RELEASE & SAFETY INVARIANT AUDIT TABLE

```
BASE_HEAD              : 6bb5a0a05866617352cf12a1fe7daf43538d313f
FILES_CHANGED          : backend/src/ats/market/features/engine.py, backend/src/ats/intelligence/regime/detector.py, tests/unit/market/features/test_volume_unavailable_contract.py
DIFF_SCOPE             : NARROW_FEATURE_CONTRACT_ONLY
TEST_RESULTS           : 288 passed, 2 skipped across all test suites
MYPY                   : CLEAN (0 errors in 8 source files)
RUFF                   : CLEAN (All checks passed)
COMPILE                : CLEAN (python -m compileall passed)
C0_FORMULA_CHANGED     : FALSE
C0_THRESHOLD_CHANGED   : FALSE (0.55 strictly maintained)
PORTFOLIO_CHANGED      : FALSE
RISK_CHANGED           : FALSE
A04_CHANGED            : FALSE
PAPERBROKER_CHANGED    : FALSE
LIVE_MONEY             : DISABLED
REAL_BROKER_ORDERS     : 0
D10_STASH              : INTACT (stash@{0}: D10-uncommitted-work-preserve)
RECONCILIATION         : CLEAN_NO_PRIOR_SESSION
COMMIT_CREATED         : 45bc2ab4a76da38a9968842a18867e549fcb4112
NEW_HEAD               : 45bc2ab4a76da38a9968842a18867e549fcb4112
WORKTREE_FINAL         : CLEAN
```

---

## 10. FINAL VERDICT

**`INDEX_VOLUME_FEATURE_REPAIR_COMMITTED_AND_QUALIFIED`**
