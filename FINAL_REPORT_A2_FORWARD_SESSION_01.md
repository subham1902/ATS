# FINAL REPORT: ATS A2 PAPER SESSION — LIVE LAUNCH & FORWARD EVIDENCE OBSERVATION (SESSION 01)

## A. REPOSITORY STATE
- **Worktree**: `D:\Projects\ATS\worktrees\final-a2-integration`
- **Branch**: `eng/final-a2-integration`
- **HEAD**: `1965aca1537a4cb0b0e64c82e63d580879c65dc0`
- **Dirty State**: Clean (0 uncommitted source code modifications)
- **Stash State**: Preserved `stash@{0}: D10-uncommitted-work-preserve` intact.

---

## B. LAUNCH RESULT
- **Launch Command**: `powershell -ExecutionPolicy Bypass -File scripts/start_ats_a2_live_paper.ps1 -Mode AGGRESSIVE`
- **Execution Target**: `PaperBrokerAdapter` (ONLY)
- **Live Money**: `DISABLED` (Strict Invariant)
- **Real Orders Placed**: `0` (Impossible)
- **Harness Integration**: `ADVISORY_ONLY` (Governor-Gated)
- **Requested Mode**: `AGGRESSIVE`
- **Effective Mode**: `AGGRESSIVE`
- **Session ID**: `5e6b3b09-896e-452c-a3ce-bd9ab6db249c`
- **Process Ownership**:
  - `Backend` (FastAPI / Runtime): PID `12304` (Listening on `127.0.0.1:8000`)
  - `Frontend` (Control Center UI): PID `34652` (Listening on `127.0.0.1:3000`)
  - `Backend Launcher`: PID `8376`
  - `Frontend Launcher`: PID `18372`
- **Health Check Responses**:
  - `http://127.0.0.1:8000/health/live` -> `{"status": "LIVE", "ready": true, "reason_codes": []}`
  - `http://127.0.0.1:8000/health/ready` -> `{"status": "READY", "ready": true, "reason_codes": []}`
  - `http://127.0.0.1:3000/` -> HTTP `200 OK`

---

## C. PROVIDER & FEED STATE
- **Provider**: Upstox (Read-Only Market Data API)
- **Authentication**: `PASS` (Bearer token resolved securely)
- **BOD Reference Master**: `PASS` (NSE BOD contracts downloaded, decompressed, and parsed)
- **Feed Transport**: Upstox V3 Protobuf WebSocket
- **Decoder**: `UpstoxV3ProtobufDecoder` (Protobuf binary wire format)
- **Subscription Plan**: Active dynamic option universe over NIFTY 50 and NIFTY BANK.

---

## D. INSTRUMENT SPECS RESOLVED
- **NIFTY**:
  - Underlying Key: `NSE_INDEX|Nifty 50`
  - Lot Size: `65` (Authoritative provider truth)
  - Tick Size: `0.050`
  - Expiry: `2026-09-01`
  - Option Keys: 10 ATM contracts (`NSE_FO|46989` .. `NSE_FO|46998`)
- **BANKNIFTY**:
  - Underlying Key: `NSE_INDEX|Nifty Bank`
  - Lot Size: `30` (Authoritative provider truth)
  - Tick Size: `0.050`
  - Expiry: `2026-09-29`
  - Option Keys: 10 ATM contracts (`NSE_FO|69817` .. `NSE_FO|69827`)
- **Duplicate Subscriptions**: `0`
- **Invalid Subscriptions**: `0`

---

## E. STAGE 2 FRESHNESS & MARKET DATA
- **Current Observation Time**: `2026-08-30T03:24:00 IST` (Outside NSE trading hours)
- **Stage 2 Market Data Gate**: `PRE_OPEN_NOT_APPLICABLE`
- **Risk Entry State**: `can_enter_new_risk = false`
- **Freshness Policy**: Strict <= 2,000ms instrument-specific quote freshness required before new risk is evaluated during market open. Zero synthetic/stale ticks accepted.

---

## F. SESSION FSM TIMELINE
- **Phase**: `CLOSED` (Derived dynamically via `resolve_session_status`)
- `can_enter`: `false`
- `can_reduce`: `false`
- `must_flatten`: `false`
- `is_halted`: `false`

---

## G. CAPITAL INTEGRITY
- **Starting Capital**: `₹100,000.00`
- **Available Capital**: `₹100,000.00`
- **Reserved Capital**: `₹0.00`
- **Inflight Capital**: `₹0.00`
- **Used Capital**: `₹0.00`
- **Ending Capital**: `₹100,000.00`
- **Realized P&L**: `₹0.00`
- **Unrealized P&L**: `₹0.00`
- **Drawdown Fraction**: `0.0`

---

## H. PRODUCTION C0 ENGINE
- **Status**: Champion Model Active
- **Threshold**: `0.55` (Strictly Unchanged)
- **Predictions**: `0`
- **Thesis Activations**: `0`
- **Thesis Rejections**: `0`
- **Candidates Qualified**: `0`
- **Executed Trades**: `0`

---

## I. ALPHA V4 SHADOW OBSERVATION
- **Status**: `SHADOW_ONLY` (Governor-gated; Zero execution authority)
- **Regimes Observed**: Initializing / Dormant (Pre-open)
- **Directional States**: `HOLD`
- **Economic Evaluability**: `NetEV = None` (Awaiting live option market depth)
- **Micro-Edge Signals**: `0`
- **Conviction Classes**: Standard / High Conviction / Convex / Rare Event all tracked.

---

## J. M2 SHADOW MODEL
- **Status**: Shadow Competitor (Forward Championship)
- **Authority**: None

---

## K. R10-X SHADOW MODEL
- **Status**: Extreme Convexity Shadow Worker
- **Authority**: None

---

## L. LIVE OPTION EVIDENCE
- Total Contracts Monitored: `20` (10 NIFTY ATM CE/PE, 10 BANKNIFTY ATM CE/PE)
- Option Evidence Failures: `0`
- Spreads / Greeks: Ready for live quote stream ingestion upon market open.

---

## M. PRODUCTION FUNNEL
| Funnel Stage | Cumulative Count | Outcome |
| :--- | :--- | :--- |
| Raw Provider Messages | 0 | Off-market hours |
| Normalized Feed Frames | 0 | Off-market hours |
| Fresh Feature States | 0 | Awaiting market open |
| C0 Predictions | 0 | Dormant outside open window |
| C0 Candidates | 0 | Blocked by session FSM |
| Portfolio Brain Decisions | 0 | Not Reached |
| Risk Budget Checks | 0 | Not Reached |
| A04 Governance Invocations | 0 | Not Reached |
| Paper Orders | 0 | Zero risk created |
| Paper Fills | 0 | Zero fills |
| Open Positions | 0 | Zero exposure |
| Exits / Stops | 0 | Clean |

---

## N. WHY-TRADE / WHY-NO-TRADE DETERMINATION
- **Dominant Blocker**: `SESSION` (`CLOSED`)
- **Downstream Layers Reached**: `NOT_REACHED`
- **Root Cause Rationale**: Current observation occurred outside NSE trading hours (03:24 AM IST). The system deterministically blocks candidate evaluation and entry generation during closed session phases.

---

## O. PAPER BROKER ORDER & POSITION STATE
- **Orders Submitted**: `0`
- **Orders Filled**: `0`
- **Open Positions**: `0`
- **Position Discrepancies**: `0`
- **Runtime Checkpoint**: Clean initial state.

---

## P. FORENSIC & LIFECYCLE EVIDENCE INTEGRITY
- **Session ID**: `5e6b3b09-896e-452c-a3ce-bd9ab6db249c`
- **Evidence Directory**: `data/runtime/sessions/2026-08-30/5e6b3b09-896e-452c-a3ce-bd9ab6db249c`
- **Events Logged**:
  1. `SESSION_CREATED` (payload: `{"state": "CONFIGURED_PAPER_SESSION"}`)
  2. `SESSION_STARTED` (payload: `{"state": "RUNNING"}`)
- **Hash Chain Status**: Cryptographically valid SHA-256 chain linked to session ID.

---

## Q. REAL BROKER ORDERS = 0 PROOF
- Real broker orders placed: **Strictly 0**.
- Live money flag: **`DISABLED`**.
- Execution adapter: **`PaperBrokerAdapter` only**.

---

## R. FORWARD EVIDENCE CHECKPOINT
- Running runtime state is persisted and synchronized between backend process (PID 12304) and frontend UI (PID 34652).
- Continuous polling and operator intelligence provider are active and healthy.

---

## S. LIMITATIONS
- Current session execution occurred on Sunday pre-dawn (03:24 AM IST), outside NSE regular trading hours (09:15–15:30 IST).
- Live tick streaming and orderbook depth from Upstox will resume when the exchange market opens on the next trading day.

---

## T. NEXT OPERATOR ACTION
The live-connected stack is fully initialized, healthy, and operational.
- The operator can view real-time system metrics at `http://127.0.0.1:3000`.
- The stack will autonomously ingest live Upstox V3 protobuf ticks at market open (09:15 IST), evaluate Stage 2 data freshness (<= 2,000ms), and execute autonomous paper trading under strict A04 deterministic authority.

---

# FINAL VERDICT
```
A2_FORWARD_SESSION_VALID
```
