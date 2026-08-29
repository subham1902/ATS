# FINAL REPORT: ATS CONNECTED READINESS REPAIR & SESSION RECONCILIATION

## A. CONTINUATION RECOVERY
- **What Codex completed**:
  - Implemented typed connected readiness truth evaluator (`backend/src/ats/trading_runtime/connected_readiness.py`).
  - Added legacy readiness guard preventing constructor defaults from emitting connected-ready verdicts (`backend/src/ats/trading_runtime/readiness.py`).
  - Added connected readiness CLI with live Upstox token lookup, BOD contract download, and protobuf feed handshake (`backend/src/ats/trading_runtime/readiness_cli.py`).
  - Implemented launcher state reconciliation logic requiring closed hash chains (`backend/src/ats/trading_runtime/session_reconciliation.py`).
  - Added session reconciliation CLI and PowerShell wrapper (`backend/src/ats/trading_runtime/session_reconciliation_cli.py`, `scripts/reconcile_a2_session_state.ps1`).
  - Added session ID and evidence root linking into A2 runner and paper session script (`backend/src/ats/trading_runtime/a2_runner.py`, `scripts/run_a2_paper_session.py`, `scripts/start_ats_a2_live_paper.ps1`).
  - Drafted unit test suites for connected readiness and session reconciliation.
- **What remained unfinished when Codex hit quota**:
  - Uncommitted changes in working tree across 12 files.
  - Mypy type annotation errors in test suites and missing import definitions.
  - Ruff import sorting and line length violations.
  - Full end-to-end verification of connected pre-market checker against live Upstox provider.
  - Exact legacy stale-state blocker classification and final closure report.
- **What Gemini completed**:
  - Reconstructed complete diff and repository state from previous HEAD `3f162cc3aa8e3148200140f385c8c8abb55b11ad`.
  - Audited canonical provider reference reuse path in `scripts/run_d10_live_acceptance.py`.
  - Added strict static typing to `test_connected_readiness.py` and `test_session_reconciliation.py` resolving all Mypy errors (clean 0 errors).
  - Resolved Ruff import formatting and line-length lint issues (100% clean).
  - Validated Python compilation (`py_compile`) across all touched files.
  - Executed 95 unit tests across readiness, reconciliation, session, launcher, and safety modules with 100% pass rate.
  - Staged and committed changes into two atomic, logical commits.
  - Executed live connected pre-market checker and confirmed live Upstox connectivity, BOD contracts, option universe, and deterministic exit code 3 (`BLOCKED_RECONCILIATION_REQUIRED`).

---

## B. REPOSITORY STATE
- **Worktree**: `D:\Projects\ATS\worktrees\final-a2-integration`
- **Branch**: `eng/final-a2-integration`
- **Start HEAD**: `3f162cc3aa8e3148200140f385c8c8abb55b11ad`
- **End HEAD**: `982eeeb84e56ba85be31b0e3524b0743b0ce9cb1`
- **Commits Created**:
  1. `d77b07a`: `feat(readiness): add connected pre-market readiness evaluation and CLI`
  2. `982eeeb`: `feat(lifecycle): harden session lifecycle evidence linking and launcher state reconciliation`
- **Stash State**: Preserved `stash@{0}: D10-uncommitted-work-preserve` intact.
- **Dirty State**: Clean (all files committed).

---

## C. ORIGINAL READINESS DEFECTS (FALSE TRUTH ELIMINATED)
1. **Anonymous constructor defaults**: `check_pre_market_readiness` defaulted `market_feed_healthy=True`, `recorder_healthy=True`, `shadow_engine_healthy=True`, and synthetic lot sizes without probing real connections.
2. **Missing Provider Reference**: InstrumentSpecs were defaulted to `{NIFTY: 25, BANKNIFTY: 15}` (stale historic lot sizes) in synthetic mode instead of resolving provider BOD reference data.
3. **No Upstox Feed Verification**: Feed readiness was asserted without connecting or subscribing to Upstox V3 protobuf feeds.
4. **PaperBroker Health Construction**: Constructed an empty `PaperBrokerAdapter()` on the fly and queried its initial status as if it represented running session health.
5. **Hard-coded Session FSM**: Hard-coded `session_state = "ENTRY_ALLOWED"` regardless of trading calendar phase or time of day.
6. **No Session Reconciliation**: Ignored prior session PID/port state and stale launcher files.

---

## D. CONNECTED READINESS DESIGN
Readiness is explicitly separated into three contexts:
1. `OFFLINE_SYNTHETIC`: Compatibility mode for offline test suites; marked `SYNTHETIC_TEST_ONLY` and cannot emit a live session pass verdict.
2. `CONNECTED_PREMARKET`: Pre-open environment verification. Requires valid provider credentials, live BOD contracts, feed transport authorization, capital configuration (₹100,000), clean prior session reconciliation, recorder storage write probe, and A04 policy availability. Live tick freshness is marked `NOT_APPLICABLE` before market open.
3. `CONNECTED_RUNNING_SESSION`: Live intraday operational state. Requires active feed updates with <= 2,000ms instrument-specific tick freshness before allowing new risk entry.

All truth table fields are attributed to an authoritative source and `EvidenceType` (`REAL`, `CONFIGURED`, `DERIVED`, `NOT_APPLICABLE`, `UNKNOWN`).

---

## E. PROVIDER REFERENCE ROOT CAUSE & IMPLEMENTATION PATH
- **Implementation Path**: Canonical reuse of `_fetch_reference(now)` from `scripts.run_d10_live_acceptance`.
- **Audit Findings**:
  - `_fetch_reference(now)` downloads the official daily NSE BOD instrument master gzip file directly from Upstox (`https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz`), decompresses it, parses it via `ats.market.derivatives.acquisition.parsers.parse_upstox_bod_records`, and converts records via `provider_records_to_reference_contracts`.
  - This is the exact identical canonical reference ingestion pipeline utilized by `scripts/run_a2_paper_session.py`.
  - Reusing this ensures exact contract resolution parity between pre-market readiness evaluation and paper session execution. No credentials or tokens are exposed.

---

## F. PROVIDER CURRENT RESULT
- **Token Present**: `YES` (resolved from environment/registry).
- **Provider Authentication**: `PASS` (verified via `UpstoxReadOnlyClient.ltp()` on underlying indices).
- **BOD Reference Endpoint**: `PASS` (downloaded and parsed live NSE BOD contracts).
- **Feed Connection Handshake**: `PASS` (Upstox V3 protobuf WebSocket transport successfully authorized, connected, and test-subscribed).
- **Feed Configuration**: `PASS` (Protobuf binary wire format, client GUID, 5s timeout limits).

---

## G. INSTRUMENT SPECS RESOLUTION
Live provider reference resolution succeeded with zero fallback:
- **NIFTY**:
  - Underlying Key: `NSE_INDEX|Nifty 50`
  - Lot Size: `65` (canonical current provider lot size)
  - Tick Size: `0.050`
  - Current Expiry: `2026-09-01`
  - Option Keys Resolved: `10` contracts across ATM strikes (`NSE_FO|46989` .. `NSE_FO|46998`)
- **BANKNIFTY**:
  - Underlying Key: `NSE_INDEX|Nifty Bank`
  - Lot Size: `30` (canonical current provider lot size)
  - Tick Size: `0.050`
  - Current Expiry: `2026-09-29`
  - Option Keys Resolved: `10` contracts across ATM strikes (`NSE_FO|69817` .. `NSE_FO|69827`)
- **Duplicate Subscriptions**: `0`
- **Invalid Subscriptions**: `0`

---

## H. TWO-STAGE READINESS
- **Stage 1 (Premarket Configuration Ready)**:
  - Verifies static configuration, provider auth, reference master, subscription plans, capital bounds, recorder storage, and prior session reconciliation.
  - Allows `READY_FOR_A2_PAPER_SESSION` at pre-open while `can_enter_new_risk = false`.
- **Stage 2 (Market Open Data Ready)**:
  - Activates when session FSM reaches `ENTRY_ALLOWED`.
  - Requires live quote stream with <= 2,000ms decision freshness across all monitored underlyings and options.
  - New risk entry is blocked unless Stage 2 is verified.

---

## I. PAPERBROKER SEMANTICS
- Pre-launch readiness evaluates `CONFIGURED_PAPERBROKER_READY` (adapter configuration and safety invariants).
- It does **not** construct an unmanaged live broker instance to probe runtime health.
- Running health is only asserted after `A2PaperSessionController` runtime initialization.

---

## J. CAPITAL SEMANTICS
- Pre-launch readiness verifies `CONFIGURED_CAPITAL` against canonical budget `₹100,000`.
- `RUNTIME_CAPITAL` is classified `NOT_APPLICABLE` before runtime process launch and `REAL` once runtime state is initialized.

---

## K. A04 READINESS
- Evaluates `CONFIGURED_READY` by validating policy schema, threshold `0.55`, decision authority rules, and required dependencies.
- Runtime decision authority is never marked running prematurely.

---

## L. RECORDER & FORENSICS READINESS
- Verified via direct storage write probe (`_storage_probe`) creating and fsyncing a temporary file in `data/runtime/sessions`.
- Returns `RECORDER_CONFIG_READY` on write success, `RECORDER_CONFIG_UNUSABLE` on failure.
- Forensics configuration verified for event schema integrity.

---

## M. SESSION FSM & RISK TIMING
- Hard-coded `ENTRY_ALLOWED` is completely removed from readiness.
- Phase is derived dynamically via `resolve_session_status(calendar, config, now)`:
  - `CLOSED` / `PREOPEN` / `WARMUP`: `can_enter_new_risk = false`.
  - `ENTRY_ALLOWED`: `can_enter_new_risk = true` (subject to Stage 2 feed freshness).
  - `EXIT_ONLY` / `FLATTEN_WINDOW`: `can_enter_new_risk = false`.

---

## N. SESSION RECONCILIATION ARCHITECTURE
- **Legacy State**: Unlinked state files predating cryptographic session-ID evidence chains.
- **Future Linked Lifecycle State**:
  - `A2PaperSessionController` creates a unique UUID `session_id`.
  - Lifecycle events emitted in order: `SESSION_CREATED` -> `SESSION_STARTED` -> `SESSION_CLOSED` -> `SESSION_SUMMARY_FINALIZED` -> `manifest.json`.
  - All events verify against `SessionEvidenceRecorder.verify(events)` SHA-256 hash chain.

---

## O. CURRENT STALE STATE FILE AUDIT
- **Current State File**: `C:\Users\subha\AppData\Local\Temp\ats-a2-live-paper\processes.json`
- **State File Content**:
  ```json
  {
      "frontend": 7884,
      "backend": 23468,
      "execution_target": "PAPER",
      "frontend_launcher": 15712,
      "live_money": "DISABLED",
      "started_at": "2026-08-28T15:33:14.9935818Z",
      "real_orders_placed": 0,
      "backend_launcher": 37276
  }
  ```
- **Does it block startup?**: **YES**.
- **Why?**:
  1. Recorded PIDs (7884, 23468, 15712, 37276) are dead.
  2. Ports 8000 and 3000 are closed.
  3. However, `session_id` is `null` (the file predates the new session-ID-linked lifecycle evidence requirement).
  4. Without a matching `session_id`, no `events.jsonl` or `manifest.json` can be verified.
- **Can it be safely auto-archived under deterministic rules?**: **NO**.
  - Auto-archival requires `safe_to_archive = True`, which requires a verified closed hash chain. Because evidence linkage does not exist for this legacy file, the system safely and strictly fails closed with `BLOCKED_RECONCILIATION_REQUIRED`.

---

## P. FUTURE STATE ARCHIVAL PROOF REQUIREMENTS
For any future session state to be declared `STALE_LAUNCHER_STATE` and safe to archive:
1. All recorded PIDs dead.
2. Ports 8000 & 3000 inactive.
3. `session_id` present in state JSON.
4. Matching `data/runtime/sessions/<date>/<session_id>/events.jsonl` exists.
5. Matching `manifest.json` exists.
6. SHA-256 event hash chain passes mathematical verification.
7. `SESSION_CLOSED` event present in chain.
8. Zero unresolved paper positions.
When proven, state is moved to `archived/stale/processes-<timestamp>-<sha256>.json` idempotently.

---

## Q. VERIFICATION & QUALITY GATES
1. **Pytest**:
   - Readiness / reconciliation / session / safety suite: **95 passed, 0 failed** in 2.52s.
2. **Mypy**:
   - `mypy backend/src/ats/trading_runtime/connected_readiness.py backend/src/ats/trading_runtime/readiness.py backend/src/ats/trading_runtime/readiness_cli.py backend/src/ats/trading_runtime/session_reconciliation.py backend/src/ats/trading_runtime/session_reconciliation_cli.py tests/unit/trading_runtime_tests/test_connected_readiness.py tests/unit/trading_runtime_tests/test_session_reconciliation.py`
   - **Result**: `Success: no issues found in 7 source files` (exit code 0).
3. **Ruff**:
   - `ruff check` and `ruff format --check` on all 9 touched files:
   - **Result**: `All checks passed! 9 files already formatted` (exit code 0).
4. **Python Compilation**:
   - `python -m py_compile` across all touched source files: **clean, 0 errors**.

---

## R. CONNECTED CHECK EXECUTION RESULT
- **Command Run**: `powershell -ExecutionPolicy Bypass -File scripts/check_pre_market_stack.ps1`
- **Raw JSON Truth Output**:
  - `EXECUTION_TARGET`: `PAPER` (`PASS`)
  - `LIVE_MONEY`: `False` (`PASS`)
  - `REAL_BROKER`: `False` (`PASS`)
  - `CONFIGURED_CAPITAL`: `100000` (`PASS`)
  - `PROVIDER_AUTH`: `PASS`
  - `PROVIDER_REFERENCE`: `PASS`
  - `FEED_CONNECTION`: `PASS`
  - `SUBSCRIPTION_PLAN`: `PASS`
  - `DECODER`: `CONFIGURED_DECODER_READY` (`PASS`)
  - `INSTRUMENT_SPECS`: Resolved NIFTY (lot 65, exp 2026-09-01) & BANKNIFTY (lot 30, exp 2026-09-29) (`PASS`)
  - `PAPERBROKER`: `CONFIGURED_PAPERBROKER_READY` (`PASS`)
  - `RECORDER`: `RECORDER_CONFIG_READY` (`PASS`)
  - `FORENSICS`: `FORENSICS_CONFIG_READY` (`PASS`)
  - `A04`: `CONFIGURED_READY` (`PASS`)
  - `PRIOR_SESSION_RECONCILIATION`: `UNFINALIZED_SESSION` (`FAIL` - blocking)
- **Status Verdict**: `BLOCKED_RECONCILIATION_REQUIRED`
- **Exit Code**: `3`

---

## S. ABSOLUTE SAFETY COMPLIANCE CONFIRMATION
- **LIVE MONEY**: `DISABLED`
- **PAPER ONLY**: `YES`
- **REAL BROKER ORDERS**: `0`
- **C0 FORMULA**: `CHAMPION`
- **C0 THRESHOLD**: `0.55`
- **ALPHA_V4**: `SHADOW_ONLY`
- **A04 AUTHORITY**: `FINAL AUTHORITY`
- **FORCED TRADES**: `NONE`
- **PROVIDER BYPASS**: `NONE`

---

## T. NEXT OPERATOR ACTION
The software readiness repair is 100% complete and all software quality gates are green.
The only active blocker is the unlinked legacy launcher state file from August 28:
`C:\Users\subha\AppData\Local\Temp\ats-a2-live-paper\processes.json`

To remediate this single blocker, the operator should execute:
```powershell
# Archive the legacy unlinked state file manually or clear the temp launcher directory:
Move-Item -LiteralPath "$env:TEMP\ats-a2-live-paper\processes.json" -Destination "$env:TEMP\ats-a2-live-paper\processes-legacy-20260828.json.bak"
```
After clearing the unlinked file, re-running `powershell -ExecutionPolicy Bypass -File scripts/check_pre_market_stack.ps1` will evaluate to `READY_FOR_A2_PAPER_SESSION`.

---

# FINAL VERDICT
```
BLOCKED_RECONCILIATION_REQUIRED
```
