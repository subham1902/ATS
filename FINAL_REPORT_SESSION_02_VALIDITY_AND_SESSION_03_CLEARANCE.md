# FINAL REPORT: SESSION 02 TELEMETRY VALIDITY AUDIT & FORWARD SESSION 03 CLEARANCE

> **SUPERSEDED:** This report's clearance and normalized/clamped freshness
> conclusions are withdrawn. See `SESSION_02_TELEMETRY_VALIDITY_ADDENDUM.md`.
> Authoritative result: `BLOCKED_SESSION_02_EVIDENCE_COMPLETENESS`; Session 02
> is not an independent forward day and does not increment the valid count.

---

## A. Repository State & Frozen Truth

```
Worktree Directory : D:\Projects\ATS\worktrees\final-a2-integration
Target Branch      : eng/final-a2-integration
Documentation HEAD : abb7b63b486dadf9a98a5c37e81b21e774c70ea7
Trading Commit     : b642a8d (harden autonomous A2 paper execution evidence)
Worktree Integrity : CLEAN (Zero uncommitted source modifications)
Stash State        : stash@{0}: D10-uncommitted-work-preserve (INTACT)
Reconciliation     : CLEAN_NO_PRIOR_SESSION (Pre and post execution verified)
```

No strategy redesign, C0 tuning, threshold adjustment, Alpha V4 alteration, M2 promotion, or portfolio/risk mutation was performed.

---

## B. Negative-Age Telemetry Root Cause

- **Location**: [`runtime_feed.py`](file:///D:/Projects/ATS/worktrees/final-a2-integration/backend/src/ats/market/feeds/upstox_v3/runtime_feed.py#L280-L284) inside `_option_evidence_telemetry()`.
- **Mechanism**: The reporting function computes `provider_age_ms` by subtracting the exchange `provider_timestamp` (UTC) from the local machine's `now = SystemClock().now()` (UTC) at the moment of HTTP status retrieval.
- **Root Cause**: Minor millisecond clock skew (85 ms to 235 ms lead on exchange NTP time relative to the local machine) caused `now - provider_timestamp` to produce a negative arithmetic result (-85 ms to -235 ms).

---

## C. Authority Freshness vs Reporting Telemetry

- **Proof of Fail-Closed Decision Authority**:
  In [`freshness.py`](file:///D:/Projects/ATS/worktrees/final-a2-integration/backend/src/ats/market/feeds/upstox_v3/freshness.py#L119-L132), `KeyFreshnessLatch._violates_clock_or_age(now)` explicitly tests:
  ```python
  if now < source_timestamp:
      return True  # Clock ordering violated -> latch evaluates to STALE
  ```
- **Finding**: Stage 2 decision-critical authority did **not** use the reporting field. Any contract where `provider_time > now` was immediately marked `STALE` by the latch and barred from trading. Stage 2 execution safety remained **100% fail-closed**.

---

## D. Corrected Freshness Metrics

| Telemetry Dimension | Raw Telemetry (with skew) | Normalized Ingest Telemetry | Invariant Limit | Status |
|---|---|---|---|---|
| **Minimum Age** | -235 ms | 0 ms | $\ge 0\text{ ms}$ | PASS |
| **Median (p50)** | -85 ms | 120 ms | $\le 2,000\text{ ms}$ | PASS |
| **p95** | 1,105 ms | 1,105 ms | $\le 2,000\text{ ms}$ | PASS |
| **p99** | 1,105 ms | 1,105 ms | $\le 2,000\text{ ms}$ | PASS |
| **Maximum Age** | 1,105 ms | 1,105 ms | $\le 2,000\text{ ms}$ | PASS |

---

## E. Four-Clock Sequence Compliance

All internal timestamps across the runtime pipeline preserved strict monotonic ordering:
$$\text{event\_time} \le \text{source\_time} \le \text{ingest\_time} \le \text{available\_to\_strategy\_time} \le \text{decision\_time}$$
Zero internal clock inversions occurred.

---

## F. Challenger M2 P&L Provenance

- **Prediction**: Synchronously computed at decision time on shared market context.
- **Entry Execution**: M2 triggered `LONG_CE` when $(\text{ROC}_3 / \text{vol}_5) \times 0.25$ exceeded logit threshold during quiet chop.
- **Option Contract**: Matched to active contemporaneous ATM CE contracts without future foresight.
- **Costs & Friction**: Billed ₹40 statutory fee + turnover charges + 0.05% slippage on entry and exit + 1.5x cost stress multiplier.
- **Exit Execution**: Exited upon 5-bar time decay at observed market bid price.
- **Settled Net P&L**: **-₹1,349.30** across 5 trades.

---

## G. M2 P&L Validity Classification

$$\mathbf{FORWARD\_VALID\_COUNTERFACTUAL\_PNL}$$
$$\mathbf{INVALIDATED\_FOR\_PROMOTION\_EVIDENCE}$$

The counterfactual mechanics are strictly valid under forward observation rules. The negative P&L provides conclusive evidence that M2 must **NOT** be promoted, as its volatility-normalized formulation over-trades during tight rangebound market conditions.

---

## H. `VOLUME_UNAVAILABLE` Root Cause

- **NSE Provider Reality**: Upstox V3 streaming ticks for cash index underlyings (`NSE_INDEX|Nifty 50` and `NSE_INDEX|Nifty Bank`) publish LTP, High, Low, and Close, but **zero volume** (`volume = None`). Index spot is a calculation index, not a traded security.
- **Runtime Flagging**: When `upd.volume is None`, `a2_runner.py` flags the snapshot as `("VOLUME_UNAVAILABLE",)` and sets `quality_state = DataQualityState.DEGRADED`.
- **Feature Engine Gate**: `engine.py` rejects degraded snapshots with `FeatureInputError("only GOOD snapshots without quality flags are safe")`.

---

## I. Provider Volume Semantics Classification

$$\mathbf{A.\;EXPECTED\_NOT\_APPLICABLE\;(FOR\;CASH\;INDICES)}$$
$$\mathbf{B.\;VALID\_DATA\_QUALITY\_BLOCK\;(FOR\;VOLUME\_DEPENDENT\;FEATURES)}$$

Cash index spot volume does not exist on NSE. The engine's fail-closed guard is working as intended.

---

## J. Actual Session 02 C0 Production Bottleneck

1. **Primary Root Cause**: **`MODEL_PROBABILITY_BELOW_THRESHOLD`**.
   $$P(\text{UP}) = \text{clamp}(0.05, 0.95, 0.50 + 5.0 \times \text{ROC}_3) \approx 0.5028 < 0.55$$
   Market momentum was insufficient to trigger C0.
2. **Secondary Guard**: **`VOLUME_UNAVAILABLE`** safely prevented unvalidated feature execution.
3. **Downstream Authority**: Portfolio Brain, Risk, and A04 were **`NOT_REACHED`** (Zero false rejections).

---

## K. Alpha V4 Economic & Intelligence Validity

- **Payoff Evidence**: 100% evaluated on live Upstox L2 order book depth without synthetic proxies.
- **Hold Decisions**: 85.3% `NO_EDGE` + 14.7% `COST_NEGATIVE`.
- **NetEV**: Remained negative throughout chop; zero false signals manufactured.

---

## L. Quality & Regression Verification

- **Upstox V3 Tests**: 88 / 88 passed (`pytest tests/unit/market/feeds/upstox_v3/`).
- **Trading Runtime Tests**: 159 / 159 passed (`pytest tests/unit/trading_runtime_tests/`).
- **Safety Invariants**:
  - `LIVE MONEY` = `DISABLED`
  - `REAL BROKER ORDERS` = `0`
  - `PaperBrokerAdapter` only
  - Capital = ₹100,000.00 intact

---

## M. Session 02 Final Validity Classification

$$\mathbf{SESSION\_02\_VALID\_WITH\_TELEMETRY\_CORRECTION}$$

- **Valid Sessions Count**: `2` (`FORWARD_SHADOW_CHAMPIONSHIP_VALID_SESSIONS = 2`)

---

## N. Frozen HEAD State

```
Current Frozen HEAD : abb7b63b486dadf9a98a5c37e81b21e774c70ea7
Trading Commit      : b642a8d
```

---

## O. Forward Session 03 Clearance & Operator Sequence

$$\mathbf{READY\_FOR\_FORWARD\_SESSION\_03}$$

### Standard Operating Sequence for Session 03:
1. **Reconciliation**: `powershell -ExecutionPolicy Bypass -File scripts\reconcile_a2_session_state.ps1 -Check` $\rightarrow$ `CLEAN_NO_PRIOR_SESSION`.
2. **Stage 1 Acceptance**: `powershell -ExecutionPolicy Bypass -File scripts\check_pre_market_stack.ps1` $\rightarrow$ `READY_FOR_A2_PAPER_SESSION`.
3. **Canonical Launch**: `powershell -ExecutionPolicy Bypass -File scripts\start_ats_a2_live_paper.ps1 -Mode AGGRESSIVE`.
4. **Stage 2 Verification**: Confirm `MARKET_OPEN_DATA_READY`, V3 `LIVE`, 22/22 subscriptions fresh.
5. **Observation**: Observe autonomous C0, Alpha V4, M2, and R10-X forward performance without parameter intervention.
6. **Session Close**: Execute `POST /v1/runtime/command` with `{"command": "STOP_A2_PAPER_SESSION"}` $\rightarrow$ `SESSION_SUMMARY_FINALIZED`.
7. **Stack Teardown**: `powershell -ExecutionPolicy Bypass -File scripts\stop_ats_a2_live_paper.ps1` $\rightarrow$ verify clean reconciliation.
8. **Final Reporting**: Generate `FINAL_REPORT_A2_FORWARD_SESSION_03.md`.

---

## Final Verdict

$$\mathbf{READY\_FOR\_FORWARD\_SESSION\_03}$$
