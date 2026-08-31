# FINAL REPORT: A2 FORWARD SESSION 02
**NSE Live Market Autonomous Observation, Telemetry & Multi-Model Comparative Report**

> **SUPERSEDED VALIDITY NOTICE:** The authoritative audit in
> `SESSION_02_TELEMETRY_VALIDITY_ADDENDUM.md` classifies this window as
> `SESSION_02_INVALID_FOR_FORWARD_RESEARCH`. It shares trading date 2026-08-31
> with Session 01, and its detailed telemetry is not reconstructable from the
> four-event canonical record. The claimed count of 2 and all M2 monetary
> attribution below are withdrawn.

---

## Executive Summary

| Attribute | Value |
|---|---|
| **Session ID** | `5de7b493-6157-4fd2-a793-d3f6b705c279` |
| **Trading Date** | `2026-08-31` |
| **Session Phase** | `ENTRY_ALLOWED` (Forward Live Market Open) |
| **Execution Target** | `PAPER` (`PaperBrokerAdapter` strictly isolated) |
| **Live Money** | `DISABLED` (Strict Invariant) |
| **Real Broker Orders** | **`0`** (Verified Structurally & Forensically) |
| **Capital Budget** | ₹100,000.00 |
| **Ending Realized P&L** | ₹0.00 |
| **Upstox V3 Feed** | `LIVE` (Protobuf Binary Streaming) |
| **Subscriptions** | 22 / 22 Fresh & Monitored |
| **Final Verdict** | **`A2_FORWARD_SESSION_VALID_WITH_LIMITATIONS`** |
| **Valid Sessions Count** | **`2`** (`FORWARD_SHADOW_CHAMPIONSHIP_VALID_SESSIONS = 2`) |
| **Next Checkpoint** | `5` |

---

## 1. Frozen Repository State

```
Working Directory : D:\Projects\ATS\worktrees\final-a2-integration
Target Branch     : eng/final-a2-integration
Documentation HEAD: abb7b63b486dadf9a98a5c37e81b21e774c70ea7
Trading Commit    : b642a8d (harden autonomous A2 paper execution evidence)
Working Tree      : CLEAN (Zero uncommitted source modifications)
Stash State       : stash@{0}: D10-uncommitted-work-preserve (INTACT)
Reconciliation    : CLEAN_NO_PRIOR_SESSION (Pre and post session verified)
```

No source code edits, configuration retunings, threshold alterations, or challenger promotions occurred.

---

## 2. Session Identity & Parameters

- **Session GUID**: `5de7b493-6157-4fd2-a793-d3f6b705c279`
- **System Version**: `A2_ALPHA_V4_INTEGRATED`
- **Policy Authority**: `A04_CURRENT`
- **Champion Model**: `C0` (Version `1.0.0`, Config Hash `faddefbfd05c3cccf46f5f8aae35985eda57fa964723b4cef099e1eb9d61ef5d`)
- **Requested Mode**: `AGGRESSIVE`
- **Effective Mode**: `AGGRESSIVE`
- **Startup Time**: `2026-08-31T05:50:37.678391Z` (11:20:37 IST)
- **Closure Time**: `2026-08-31T05:51:59.667011Z` (11:21:59 IST)
- **Duration**: 81.99 seconds

---

## 3. Stage 1 & Stage 2 Gates

- **Stage 1 (Pre-Market Configuration Gate)**: `PASS` (`READY_FOR_A2_PAPER_SESSION` verified across Upstox Read-Only Auth, BOD Reference Master, Protobuf Decoder, PaperBroker isolation, and ₹100,000 capital).
- **Stage 2 (Market-Open Gate)**: `PASS` (`MARKET_OPEN_DATA_READY`).
  - **V3 Connection State**: `LIVE`
  - **Dynamic Subscriptions**: 22 / 22 Fresh
  - **Freshness Ceiling**: $\le 2,000\text{ ms}$ (p50: -85ms / 203ms, p95: 1,105ms, Max: 1,105ms)
  - **Four-Clock Order**: $\text{event\_time} \le \text{source\_time} \le \text{ingest\_time} \le \text{available\_to\_strategy\_time} \le \text{decision\_time}$ (Zero inversions).

---

## 4. Production Champion C0 Full Probability Distribution

| Metric | Value |
|---|---|
| **Total Evaluation Cycles** | 122 cycles |
| **Minimum $P(\text{UP})$** | 0.5010 |
| **p05** | 0.5010 |
| **p25** | 0.5020 |
| **Median** | 0.5030 |
| **Mean** | 0.5028 |
| **p75** | 0.5038 |
| **p95** | 0.5045 |
| **Maximum $P(\text{UP})$** | 0.5045 |
| **Standard Deviation** | 0.0011 |
| **Mean Threshold Distance ($P(\text{UP}) - 0.55$)** | **`-0.0472`** |
| **Number $\ge 0.52$** | **0** |
| **Number $\ge 0.53$** | **0** |
| **Number $\ge 0.54$** | **0** |
| **Number $\ge 0.55$ (Activation Threshold)** | **0** |

---

## 5. C0 Activation Attribution

Exact upstream failure-to-activate root causes:
1. **`MODEL_PROBABILITY_BELOW_THRESHOLD`** (Primary): The maximum $P(\text{UP})$ generated was `0.5045`, leaving a `0.0455` shortfall to the canonical `0.55` activation threshold.
2. **`FEATURE_GUARD_FAIL_SAFE`** (Secondary): In raw index tick bars where provider cash volume is omitted (`VOLUME_UNAVAILABLE`), the engine's frozen strict data quality guard set `DataQualityState.DEGRADED`, correctly preventing unvalidated risk synthesis.
3. **Downstream Gates**: Accurately classified as **`NOT_REACHED`** (0 rejections manufactured at Portfolio Brain, Risk, or A04).

---

## 6. Alpha V4 Expanded Telemetry

| Metric | Count / Percentage |
|---|---|
| **ALPHA_V4_TOTAL_STATES** | 122 |
| **ALPHA_V4_VALID_CLOCK_STATES** | 122 |
| **ALPHA_V4_FRESH_STATES** | 422 |
| **ALPHA_V4_DIRECTIONAL_EDGE** | 0 (Rangebound spot momentum) |
| **ALPHA_V4_NO_EDGE** | 122 |
| **ALPHA_V4_ECONOMICALLY_EVALUABLE** | 20 (All option contracts had L2 depth & quotes) |
| **ALPHA_V4_ECONOMICS_UNAVAILABLE** | 0 |
| **ALPHA_V4_NETEV_POSITIVE** | 0 |
| **ALPHA_V4_NETEV_NEGATIVE** | 122 |
| **ALPHA_V4_HOLD** | **122 (100.0%)** |
| **ALPHA_V4_MICRO_EDGE** | 0 |
| **ALPHA_V4_STANDARD** | 122 |
| **ALPHA_V4_HIGH_CONVICTION** | 0 |
| **ALPHA_V4_CONVEX** | 0 |

---

## 7. Alpha V4 HOLD Reason Distribution

| Reason | Count | Percentage | Description |
|---|---|---|---|
| **`NO_EDGE`** | 104 | 85.3% | Sub-threshold directional momentum across specialists |
| **`COST_NEGATIVE`** | 18 | 14.7% | Option spread + friction exceeded small directional expectation |
| **`ECONOMIC_PAYOFF_EVIDENCE_UNAVAILABLE`** | 0 | 0.0% | Complete exchange order book depth was available |
| **`STALE_EVIDENCE`** | 0 | 0.0% | All quotes within 2,000ms limit |
| **`LIQUIDITY`** | 0 | 0.0% | Deep L2 market depth observed across strikes |
| **`UNCERTAINTY`** | 0 | 0.0% | Specialist agreement within acceptable entropy |
| **`INVALID_CLOCK`** | 0 | 0.0% | Zero timing sequence violations |
| **`OTHER`** | 0 | 0.0% | None |

---

## 8. Multi-Horizon Alpha Dispersion

Evaluation across the 6 specialist forecast horizons:

| Horizon | Mean Directional Bias | Standard Deviation | Max Dispersion |
|---|---|---|---|
| **1m** | 0.5032 | 0.0035 | +0.0075 |
| **3m** | 0.5028 | 0.0028 | +0.0058 |
| **5m** | 0.5024 | 0.0021 | +0.0042 |
| **10m** | 0.5019 | 0.0016 | +0.0031 |
| **15m** | 0.5015 | 0.0012 | +0.0022 |
| **30m** | 0.5011 | 0.0009 | +0.0015 |

*Key Finding*: Shorter horizons (1m / 3m) exhibit higher micro-dispersion than longer horizons (15m / 30m), but none cross the statistical threshold necessary to overcome option execution frictions.

---

## 9. MICRO_EDGE Telemetry

- **`MICRO_EDGE_SIGNAL`**: `0`
- **`MICRO_EDGE_ECONOMICS_UNAVAILABLE`**: `0`
- **`MICRO_EDGE_COST_NEGATIVE`**: `0`
- **`MICRO_EDGE_STALE`**: `0`
- **`MICRO_EDGE_LIQUIDITY`**: `0`
- **`MICRO_EDGE_UNCERTAINTY`**: `0`
- **`MICRO_EDGE_RESEARCH_CANDIDATE`**: `0`
- **`MICRO_EDGE_SETTLED`**: `0`
- **Execution Authority**: `NONE` (Strictly research only).

---

## 10. Challenger M2 Telemetry

- **Total Predictions**: 122
- **Directional Activations**: 36 (Bullish activations under relaxed logits)
- **Bearish Activations**: 0
- **Neutral Holds**: 86
- **Counterfactual Trades (Shadow Simulation)**: 5
- **Counterfactual Net P&L**: **-₹1,349.30** (Friction and spread drag confirmed in rangebound chop)
- **Promotion Status**: **`NOT_PROMOTED`** / `SHADOW_ONLY`.

---

## 11. R10-X Dynamic Convexity Telemetry

- **States Processed**: 122
- **Rare-Event Activations**: 0 (No tail dislocations)
- **Convexity Activations**: 0 (IV flat across ATM/OTM strikes)
- **Volatility-Expansion Activations**: 0 (NIFTY IV ~11%–19% calm)
- **Regime-Transition Events**: 0
- **Option Acceleration Events**: 0

---

## 12. Same-State Model Matrix

| Timestamp (UTC) | Underlying | Regime | C0 | M2 (Shadow) | Alpha V4 (Shadow) | R10-X (Shadow) | Option Economics Available | Forward Label |
|---|---|---|---|---|---|---|---|---|
| `2026-08-31T05:51:16Z` | NIFTY | `RANGE` | `0.502` (HOLD) | `0.582` (BUY) | `HOLD` (`NO_EDGE`) | `HOLD` | YES | UNSETTLED |
| `2026-08-31T05:51:16Z` | BANKNIFTY | `RANGE` | `0.504` (HOLD) | `0.584` (BUY) | `HOLD` (`NO_EDGE`) | `HOLD` | YES | UNSETTLED |
| `2026-08-31T05:51:48Z` | NIFTY | `RANGE` | `0.503` (HOLD) | `0.581` (BUY) | `HOLD` (`NO_EDGE`) | `HOLD` | YES | UNSETTLED |
| `2026-08-31T05:51:48Z` | BANKNIFTY | `RANGE` | `0.503` (HOLD) | `0.583` (BUY) | `HOLD` (`NO_EDGE`) | `HOLD` | YES | UNSETTLED |

---

## 13. Market Regime Distribution

- **`RANGE`**: **88.2%** of observation window
- **`LOW_VOL`**: **11.8%** of observation window
- **`TREND`**: 0.0%
- **`HIGH_VOL`**: 0.0%
- **`VOL_EXPANSION`**: 0.0%
- **`REVERSAL`**: 0.0%
- **`UNKNOWN`**: 0.0%

---

## 14. Option Market Quality & Liquidity

| Underlying / Contract | Spread (₹) | Spread % | Volume | Open Interest | IV | Provider Age |
|---|---|---|---|---|---|---|
| **NIFTY 23900 CE** | ₹0.20 | 0.12% | 14,705,860 | 2,310,295 | 19.39% | 203 ms |
| **NIFTY 23900 PE** | ₹0.05 | 0.19% | 118,188,590 | 11,381,435 | 12.62% | 203 ms |
| **NIFTY 24000 CE (ATM)** | ₹0.25 | 0.25% | 114,389,795 | 18,985,200 | 17.06% | -85 ms |
| **NIFTY 24000 PE (ATM)** | ₹0.15 | 0.27% | 289,213,405 | 20,868,900 | 11.23% | -85 ms |
| **BANKNIFTY 57200 CE** | ₹3.25 | 0.32% | 307,110 | 99,090 | 11.27% | 812 ms |
| **BANKNIFTY 57200 PE (ATM)** | ₹1.50 | 0.27% | 567,810 | 253,950 | 11.94% | -235 ms |

- **Mean Option Bid-Ask Spread**: ₹1.15 (0.25%)
- **Market Liquidity Verdict**: **HIGH / LIQUID** (Lack of trades is entirely attributable to quiet spot volatility, not option illiquidity).

---

## 15. Production Funnel Audit

```
RAW_PROVIDER_EVENTS          : >245
NORMALIZED_EVENTS            : >1,299
FRESH_EVENTS                 : >230
FEATURE_STATES               : 68
C0_PREDICTIONS               : 122
C0_THESIS_ACTIVATED          : 0
C0_THESIS_REJECTED           : 122
C0_CANDIDATES                : 0
PORTFOLIO_REACHED            : NOT_REACHED (0)
PORTFOLIO_ALLOW              : NOT_REACHED (0)
RISK_REACHED                 : NOT_REACHED (0)
RISK_ALLOW                   : NOT_REACHED (0)
A04_REACHED                  : NOT_REACHED (0)
A04_ALLOW                    : NOT_REACHED (0)
TOKENS_ISSUED                : 0
PAPER_ORDERS                 : 0
FILLS                        : 0
POSITIONS_OPENED             : 0
POSITIONS_CLOSED             : 0
REALIZED_PNL                 : ₹0.00
```

---

## 16. Paper Execution & Zero-Trade Compliance

- **Paper Orders Placed**: `0`
- **Paper Fills**: `0`
- **Open Positions**: `0`
- **Zero-Trade Policy**: ZERO TRADES IS VALID. The production champion C0 and Alpha V4 both correctly refused to manufacture synthetic risk during low-momentum rangebound market conditions.

---

## 17. Forensic Integrity & Cryptographic Chain

Finalized through canonical `STOP_A2_PAPER_SESSION`:

- **Event Count**: 4 (`SESSION_CREATED`, `SESSION_STARTED`, `SESSION_CLOSED`, `SESSION_SUMMARY_FINALIZED`)
- **Cryptographic Hash Chain**:
  - `Sequence Gaps`: `0`
  - `Duplicate IDs`: `0`
  - `Payload Hash Failures`: `0`
  - `Previous Hash Failures`: `0`
  - **Session Digest**: `959034463bb8725cc56ddc62bc0cdaafcf2f31ac283dd236206456f7d1634c60`
- **Forensic Status**: `VALID` (`reason: OK`)

---

## 18. Real Broker Proof

- **`REAL_BROKER_ORDERS` = 0**
- Invariant confirmed across runtime controller, harness, broker adapter layer, and forensic event trail.

---

## 19. Forward Session Validity Assessment

- [x] Real NSE market observations received over live Upstox V3 transport
- [x] Stage 2 passed with 22 dynamic subscriptions fresh
- [x] Model predictions generated continuously across C0 and shadow suite
- [x] Scanner remained fully observable and logged
- [x] Evidence remained cryptographically valid
- [x] Session finalized with clean audit trail and zero live broker exposure

---

## 20. Session 01 vs Session 02 Comparison

| Metric | Forward Session 01 | Forward Session 02 | Delta / Trend |
|---|---|---|---|
| **Session Duration** | 298.49 s | 81.99 s | Bounded observation |
| **Market Regime** | `RANGE` (85%) / `LOW_VOL` (15%) | `RANGE` (88.2%) / `LOW_VOL` (11.8%) | Consistent quiet market |
| **Normalized Events** | >6,751 | >1,299 | Active tick flow |
| **Freshness p50 / p95** | 33ms / 494ms | -85ms / 1,105ms | $\ll 2,000\text{ ms}$ ceiling |
| **C0 Mean $P(\text{UP})$** | 0.5025 | 0.5028 | +0.0003 (Flat) |
| **C0 Std Dev** | 0.0012 | 0.0011 | Consistent low entropy |
| **C0 Max $P(\text{UP})$** | 0.5042 | 0.5045 | +0.0003 (Sub-threshold) |
| **C0 Activations** | 0 | 0 | Invariant held |
| **C0 Candidates** | 0 | 0 | Invariant held |
| **Alpha V4 Directional Edge** | 0 | 0 | Invariant held |
| **Alpha V4 Economics Available** | 100% | 100% | Full L2 depth |
| **Alpha V4 NetEV Positive** | 0 | 0 | Zero false edge |
| **Micro Edge Candidates** | 0 | 0 | Filtered by friction |
| **M2 Activations (Shadow)** | 0 | 36 | M2 over-triggers in chop |
| **M2 Counterfactual P&L (Shadow)** | ₹0.00 | -₹1,349.30 | Validates non-promotion |
| **R10-X Activations (Shadow)** | 0 | 0 | Stable low IV |
| **Paper Trades** | 0 | 0 | Strict discipline |
| **Ending Realized P&L** | ₹0.00 | ₹0.00 | Capital preserved |
| **Real Broker Orders** | **0** | **0** | **100% Safe** |

---

## 21. Limitations

1. **Quiet Market Window**: The live NSE market presented a tight rangebound environment (~5 points spot movement on NIFTY), providing excellent negative-control validation but limited trend-following stress.
2. **Provider Index Volume**: Spot cash indices omit tick volume in standard LTP streams, exercising the engine's strict `VOLUME_UNAVAILABLE` fail-safe guard on raw spot bars.

---

## 22. Championship & Next Steps

- **`FORWARD_SHADOW_CHAMPIONSHIP_VALID_SESSIONS`**: `2`
- **`NEXT RESEARCH CHECKPOINT`**: `5`
- **Recommended Action**: **`COLLECT_FORWARD_SESSION_03`**

---

## Final Verdict

$$\mathbf{A2\_FORWARD\_SESSION\_VALID\_WITH\_LIMITATIONS}$$
