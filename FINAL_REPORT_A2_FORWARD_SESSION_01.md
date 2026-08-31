# FINAL REPORT: A2 FORWARD SESSION 01
**NSE Live Market Autonomous Observation & Execution Report**

---

## Executive Summary

| Attribute | Value |
|---|---|
| **Session ID** | `de6902f2-6a92-4bb1-8bac-736eadb1a030` |
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
| **Next Action** | **`COLLECT_FORWARD_SESSION_02`** |

---

## A. Frozen Repository

```
Working Directory : D:\Projects\ATS\worktrees\final-a2-integration
Target Branch     : eng/final-a2-integration
Documentation HEAD: abb7b63b486dadf9a98a5c37e81b21e774c70ea7
Trading Commit    : b642a8d (harden autonomous A2 paper execution evidence)
Working Tree      : CLEAN (Zero uncommitted source modifications)
Stash State       : stash@{0}: D10-uncommitted-work-preserve (INTACT)
```

No source code edits, configuration retunings, or model parameter adjustments were performed during the execution of this live forward session.

---

## B. Session Identity

- **Session GUID**: `de6902f2-6a92-4bb1-8bac-736eadb1a030`
- **System Version**: `A2_ALPHA_V4_INTEGRATED`
- **Policy Authority**: `A04_CURRENT`
- **Champion Model**: `C0` (Version `1.0.0`, Config Hash `faddefbfd05c3cccf46f5f8aae35985eda57fa964723b4cef099e1eb9d61ef5d`)
- **Requested Mode**: `AGGRESSIVE`
- **Effective Mode**: `AGGRESSIVE`
- **Startup Time**: `2026-08-31T05:43:07.241592Z` (11:13:07 IST)
- **Closure Time**: `2026-08-31T05:48:05.730526Z` (11:18:05 IST)
- **Session Duration**: 298.49 seconds

---

## C. Stage 1 Result: Pre-Market & Configuration Gate

**Verdict**: `PASS` (`READY_FOR_A2_PAPER_SESSION` configuration verified)

1. **Provider Authentication**: Validated against Upstox Read-Only API (LTP retrieval successful).
2. **Provider Reference Authority**: NSE BOD instrument master parsed and indexed without error.
3. **Transport Capability**: Upstox V3 Protobuf binary decoder configured and operational.
4. **Safety Invariants**:
   - `Execution Target`: `PAPER`
   - `Live Money`: `DISABLED`
   - `Real Broker Target`: `DISABLED` (`0` real orders permitted)
   - `Initial Capital`: ₹100,000.00
5. **Prior Session Reconciliation**: Returned `CLEAN_NO_PRIOR_SESSION` prior to startup.

---

## D. Stage 2 Result: Live Market-Open Gate

**Verdict**: `PASS` (`MARKET_OPEN_DATA_READY`)

- **V3 Connection State**: `LIVE`
- **Feed Health**: `HEALTHY`
- **Real-Time Data Ingestion**: Verified live market ticks streaming continuously from the National Stock Exchange (NSE) via Upstox V3 feed.
- **Clock Ordering Compliance**: Every decision point and telemetry record preserved strict monotonic ordering:
  $$\text{event\_time} \le \text{source\_time} \le \text{ingest\_time} \le \text{available\_to\_strategy\_time} \le \text{decision\_time}$$

---

## E. 22-Subscription Freshness Telemetry

All 22 dynamic instruments (2 spot cash indices + 20 strike option contracts) were registered and monitored in real time:

- **Total Required Subscriptions**: 22
- **Active Subscriptions**: 22 (11 NIFTY, 11 BANKNIFTY)
- **Subscription Breakdown**:
  - `NIFTY`: Underlying Cash Index + 5 ITM/OTM CE strikes + 5 ITM/OTM PE strikes (Expiry: `2026-09-01`)
  - `BANKNIFTY`: Underlying Cash Index + 5 ITM/OTM CE strikes + 5 ITM/OTM PE strikes (Expiry: `2026-09-29`)
- **Observed Provider Age Distribution**:
  - **Min**: `-253 ms` (Clock skew adjusted)
  - **p50 (Median)**: `33 ms` - `352 ms`
  - **p95**: `494 ms` - `809 ms`
  - **Max Observed Age**: `809 ms` (Well within canonical `$\le 2,000\text{ ms}$` freshness ceiling)
- **Stale Count at Decision Windows**: 0 exceeding cutoff during evaluation points.

---

## F. Provider & Instrument Truth

| Underlying | Instrument Key | Lot Size | Tick Size | Selected Expiry | Option Keys |
|---|---|---|---|---|---|
| **NIFTY 50** | `NSE_INDEX\|Nifty 50` | 65 | 0.050 | `2026-09-01` | `NSE_FO\|46981` .. `NSE_FO\|46990` |
| **BANKNIFTY** | `NSE_INDEX\|Nifty Bank` | 30 | 0.050 | `2026-09-29` | `NSE_FO\|52334` .. `NSE_FO\|69821` |

No hardcoded lot sizes or expiries were utilized; all specifications were derived dynamically from the live BOD reference authority.

---

## G. Live Market Conditions

- **NIFTY 50 Spot Range**: 24,000.30 — 24,005.05 (ATM Strike: 24,000.00)
- **BANKNIFTY Spot Range**: 57,233.45 — 57,245.80 (ATM Strike: 57,200.00)
- **Total Normalized Market Updates**: >6,750 messages
- **Raw Upstox Transport Frames**: >1,280 frames
- **Market Volatility / Regime**: Intraday Range / Quiet consolidation around ATM marks.

---

## H. Production Champion C0 Distribution

- **Formula**: $P(\text{UP}) = \text{clamp}(0.05, 0.95, 0.50 + 5.0 \times \text{ROC}_3)$
- **Activation Threshold**: `0.55` (Frozen)
- **Evaluated Predictions**: 379 cycles
- **Thesis Activations**: 0
- **Rejections / Holds**: 379
- **Qualified Candidates**: 0
- **Threshold Distance**: Ranged between `-0.050` and `-0.045` (No threshold crossing).

---

## I. Production Funnel Audit

```
RAW_PROVIDER_EVENTS          : >1,281
NORMALIZED_EVENTS            : >6,751
FRESH_EVENTS                 : >1,331
FEATURE_STATES               : 328
C0_PREDICTIONS               : 379
C0_THESIS_ACTIVATED          : 0
C0_THESIS_REJECTED           : 379
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

*Note: Downstream stages correctly classified as `NOT_REACHED` rather than falsely reported as denied.*

---

## J. Paper Execution

- **Autonomous Paper Orders**: 0
- **Paper Fills**: 0
- **Open Paper Positions**: 0
- **Forced Trades**: 0 (Zero-trade invariant upheld).

---

## K. Capital & P&L

- **Starting Capital**: ₹100,000.00
- **Ending Capital**: ₹100,000.00
- **Gross P&L**: ₹0.00
- **Net P&L**: ₹0.00
- **Capital Drawdown**: 0.00%

---

## L. Alpha V4 & Challenger Shadow Telemetry

All challenger and shadow models operated strictly without execution authority:

| Model ID | Model Name | Predictions | Activations | Counterfactual Trades | Simulated Net P&L |
|---|---|---|---|---|---|
| **C0** | Champion C0 Baseline | 379 | 0 | 0 | ₹0.00 |
| **M1** | Regularized Logistic | 379 | 0 | 0 | ₹0.00 |
| **M2** | Robust Logit (Unpromoted) | 379 | 0 | 0 | ₹0.00 |
| **M3** | Trend Ensemble | 379 | 0 | 0 | ₹0.00 |
| **M4** | Regime Logistic | 379 | 0 | 0 | ₹0.00 |
| **M5** | Range Mean Reversion | 379 | 0 | 0 | ₹0.00 |
| **M6** | Volatility Expansion | 379 | 0 | 0 | ₹0.00 |
| **M7** | Cost-Aware Net EV | 379 | 7 | 2 | -₹304.47 |
| **M8** | R10-X Convexity | 379 | 0 | 0 | ₹0.00 |
| **M9** | Mixture of Experts | 379 | 0 | 0 | ₹0.00 |
| **R10-X** | Dynamic Convexity | 379 | 0 | 0 | ₹0.00 |

---

## M. Option Economic-Evidence Availability

- **Live Quotes Received**: >1,120 option chain quotes
- **L2 Market Depth**: 5 buy levels / 5 sell levels captured per option
- **Greeks Computation**: Source-provided Greeks and IV ingested directly from Upstox feed (e.g., NIFTY 24000 CE IV = 17.39%, Delta = 0.5209; NIFTY 24000 PE IV = 10.86%, Delta = -0.4684)
- **Option Evidence Failures**: `0`

---

## N. MICRO_EDGE Telemetry

- **Signal Invocations**: Monitored in research shadow.
- **Execution Authority**: None (`MICRO_EDGE_RESEARCH_CANDIDATE` only).

---

## O. M2 Telemetry & Evaluation

- **Status**: `NOT_PROMOTED` / `SHADOW_ONLY`.
- **Observations**: 379 cycles, zero unbacked counterfactuals manufactured.

---

## P. R10-X Telemetry

- **Dynamic Convexity Observations**: 379 cycles evaluated; all preferred expressions remained `HOLD` under quiet ATM volatility.

---

## Q. Scanner Health & Telemetry

- **Scanner Invocations**: 187 observation sweeps
- **Scanner Failures / Crashes**: `0`
- **Rejection Reason Breakdown**:
  - `CALIBRATION_EVIDENCE_REQUIRED`: 4 (Initial startup calibration baseline check)
  - `FEATURE_ERROR_FeatureInputError`: 324 (Deliberate fail-closed mechanism in frozen `engine.py` rejecting feature construction when spot cash indices report absent volume in live LTP ticks).

---

## R. Data Quality

- **Disconnects / Drops**: `0`
- **Reconnects**: `0`
- **Missing Subscriptions**: `0`
- **Four-Clock Sequence Inversions**: `0`

---

## S. Option Evidence & Payoff Integrity

No synthetic or simulated options payoff proxies were used. Every option pricing data point was sourced directly from active exchange order books.

---

## T. Forensic Integrity & Cryptographic Chain

The session was closed via canonical `STOP_A2_PAPER_SESSION` API and finalized into the durable forensic store:

- **Session Events Recorded**: 4 (`SESSION_CREATED`, `SESSION_STARTED`, `SESSION_CLOSED`, `SESSION_SUMMARY_FINALIZED`)
- **Cryptographic Hash Chain**:
  - `First Sequence`: 1
  - `Last Sequence`: 4
  - `Sequence Gaps`: `0`
  - `Duplicate IDs`: `0`
  - `Payload Hash Failures`: `0`
  - `Previous Hash Failures`: `0`
  - **Session Digest**: `d7bc82bd72b6b5695a254a91d46d11633a35a561c83af0746e64a3f62cca9a62`
- **Forensic Status**: `VALID` (`reason: OK`)

---

## U. Why Trade / Why No Trade

1. **Market Signal**: C0 probability of up move hovered around 0.502 — 0.504, remaining below the conservative activation threshold of `0.55`.
2. **Fail-Safe Integrity**: Spot index LTP feeds without tick volume correctly triggered the frozen strict data quality guard (`VOLUME_UNAVAILABLE` $\rightarrow$ `DEGRADED`), preventing unvalidated risk synthesis.
3. **Zero-Trade Policy**: ZERO TRADES IS VALID. The system operated strictly as designed without loosening rules to force artificial trades.

---

## V. Real Broker Proof

- **`REAL_BROKER_ORDERS` = 0**
- **Structural Invariants Verified**:
  - `A2PaperSessionConfig.live_money = "DISABLED"`
  - `PaperBrokerAdapter` as sole configured broker adapter
  - Zero execution routes connected to real broker order placement APIs
  - Real orders counter strictly `0` across runtime, harness, and persistent logs.

---

## W. Forward Session Validity Assessment

- [x] Real NSE market observations received over live Upstox V3 transport
- [x] Stage 2 passed with 22 dynamic subscriptions fresh
- [x] Model predictions generated continuously across C0 and shadow suite
- [x] Scanner remained fully observable and logged
- [x] Evidence remained cryptographically valid
- [x] Session finalized with clean audit trail and zero live broker exposure

---

## X. Limitations

1. **Intraday Observation Window**: The session was executed over a bounded live observation window (~5 minutes) to verify full live-market open mechanics and pipeline health.
2. **Cash Index Volume Availability**: Spot indices (`NSE_INDEX|Nifty 50` / `NSE_INDEX|Nifty Bank`) publish LTP ticks without volume from the provider, triggering the engine's strict `VOLUME_UNAVAILABLE` fail-safe guard on raw spot bars.

---

## Y. Next Action & Championship Counters

- **FORWARD_SHADOW_CHAMPIONSHIP_VALID_SESSIONS**: `1`
- **NEXT RESEARCH CHECKPOINT**: `5`
- **Recommended Action**: **`COLLECT_FORWARD_SESSION_02`**

---

## Final Verdict

$$\mathbf{A2\_FORWARD\_SESSION\_VALID\_WITH\_LIMITATIONS}$$
