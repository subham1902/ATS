# ATS / MetaTrader controllability audit

Audit date: 2026-10-09. Inspected revision: `1cd57138643ea1b905e14a96b1a69e75ced932f9`, branch `main`, initially clean. This is a read-only capability audit plus a report; it does not enable execution, reconnect accounts, alter risk, attach EAs, or send orders.

## Executive assessment

**ATS is a research/monitoring foundation, not yet the complete MetaTrader control system requested.** The finished interface improves presentation, but major control paths are absent. Account connection and execution-consent storage exist. Actual external execution components exist as dormant development modules. No active console route connects those modules to strategy signals, account assignments, broker execution or a trusted reconciliation loop.

The highest-value next work is integration and state ownership, not another visual redesign. Preserve the deterministic paper kernel. Introduce a separately commissioned external-account control plane that owns assignments, configuration revisions, sizing, authorization, execution and reconciliation. AI remains proposal-only.

## Current live observations

Observed through local APIs at backend 8100 and frontend 3001 during this audit:

| Surface | Observed result | Interpretation |
| --- | --- | --- |
| Account registry | One MT5 DEMO account; DISCONNECTED; execution consent false | Stored identity is not a connected authenticated session |
| Account assignments | No allowed strategies; risk profile null | No executable strategy/account configuration |
| Account positions/orders/balance | Unknown because disconnected | Cannot assert account flatness or current equity |
| Market health | Separate MT5 feed DEGRADED; FUTURE_SOURCE_TIMESTAMP; zero accepted updates | Market is not a validated live source |
| System | DEGRADED; RUNTIME_NOT_ATTACHED; A2_PAPER | Console response is not an attached autonomous runtime |
| Paper | Capital 100000; realized/unrealized zero; no paper positions; feed/broker unhealthy | This is separate from the previously observed $1000 broker account |
| Research | No imported production datasets; no queued research jobs | Continuous production research is not operating |
| Native observer file | authority NONE; commands_supported false; CLOCK_PROFILE_REQUIRED; proposal null | Native strategy cannot currently deliver an executable proposal |

The native JSON was inspected as a retained file; its existence is not proof that the terminal or EA is currently running. No physical terminal interaction was performed in this audit. Previous demo observations and CI results are historical, not fresh account acceptance.

## Capability matrix

| Capability | Current boundary | Required for full ATS control |
| --- | --- | --- |
| Register/adopt/connect MT5 | API and UI implemented, isolated read-only workers | Reliable recovery and current physical acceptance |
| Multiple accounts | Isolation code/tests exist | Concurrent physical sessions with distinct profiles verified |
| MT4 | Common market boundary; authenticated bridge not configured | Real, tested transport; truthful platform capabilities |
| Observe quotes | Journal/fabric pipeline implemented | Commissioned clock, renewed evidence, consistent account selection |
| Manage strategy source | Versioned Python/MQL files and store | Controlled create/revise/retire workflow with build/deployment receipts |
| Edit strategy parameters | Presets/scripts, not integrated operator API | Typed versioned configuration and safe apply lifecycle |
| Assign strategy to accounts | Fields exist; no exposed assignment workflow | Exact ID/version assignment and audited enable/pause actions |
| Configure lots | Metadata validation and research calculations exist | Preview/final broker-calculated sizing tied to authority |
| Configure account risk | Typed dormant profiles | Durable CRUD/versioning, assignment, effective-limit display |
| Enable execution | Stores consent only | Eligibility, risk, reconciliation and external dispatch must also pass |
| Submit external order | Dormant MT5 adapter | Commissioned isolated worker/router integration |
| Modify SL/TP or close | No complete external control path | Separately authorized reduction/exit adapter methods and evidence |
| Kill switches | Paper command API; dormant killed fact | Global/account/strategy external controls with observed acknowledgments |
| Reconcile deals/positions | Snapshots, no full trusted external lifecycle | Persistent broker-order/deal/position reconciliation and period ledger |
| Native EA lifecycle | Scripted install/compile, observer output | ATS inventory, deployment status, version/hash parity and retirement controls |
| Entry/exit intelligence | Pure calculations/tests | Actual position sampling, closed-trade evidence, advisories/UI integration |
| Research jobs | Bounded manual replay | Scheduler with budgets, concurrency, cancellation and results navigation |

## Prioritized findings

### P0-01: Execution consent has no execution path

Evidence: `console/accounts_router.py` offers registration, adoption, connection, disconnection and consent. `market/metatrader/account_service.py:view` returns EXTERNAL_ROUTING_NOT_IMPLEMENTED. `execution/metatrader_adapter.py` explicitly says uncommissioned; the console does not instantiate it. The adapter implements submit and observed_state, not the complete requested order/position lifecycle.

Impact: Connect & Enable cannot produce the requested account execution behavior. The UI honestly explains this, but the action still describes a future capability.

Recommendation: expose separate desired consent and effective readiness. Commission an external router only after account identity, eligible strategy version, effective risk, fresh quote, terminal permissions and reconciliation all pass. Retain A2_PAPER exclusion. Provide a readiness checklist naming every failed prerequisite.

Acceptance: an authorized test intent reaches exactly the selected isolated account, remains idempotent across crashes/timeouts, and is reconciled; unenabled/mismatched/stale accounts cannot receive it. Physical order acceptance must be explicit and separate from stub tests.

### P0-02: No trusted daily/monthly broker loss ledger

Evidence: account risk profile is null; account reconciliation is UNKNOWN. `demo_supervisor.py:PeriodBook` models verified start-period equity/net booked P&L but no collector is wired. The base external RiskProfile has daily but no monthly field; the dormant demo layer performs monthly budgeting.

Impact: the requested 3% daily / 8% monthly net realized limits are not operational broker controls. Native inputs express ceilings, not enforcement.

Recommendation: account-wide deal ingestion including manual/other-strategy trades, commission, swap and cash-flow classifications. Persist verified UTC period equity baselines; reserve open/submitted risk; stop new risk when completeness is unknown. Show booked loss, reserve, remaining budget, baseline and time boundary together. Use a shared period-risk policy for commissioned demo/live, rather than leaving monthly rules only in a demo-specific wrapper.

Acceptance: restart, midnight/month transition, deposits/withdrawals, partial closes, fees, late deals and manual trades cannot reset or understate risk. Caps block new risk; gaps/slippage mean no absolute realized-loss guarantee is possible.

### P0-03: Two market-selection paths produce contradictory state

Evidence: account DISCONNECTED versus automatic Market DEGRADED. `console/market_router.py:market_connection` falls back to standalone connector/fabric when account service returns no connection. Account errors can also differ from retained standalone observations.

Recommendation: make the selected data source/account explicit everywhere. When registered-account mode is selected, no silent standalone fallback. Keep standalone research observations as an explicitly named source. Return account/source/session ID, event timestamp, receive timestamp, effective freshness, rejection reason and accepted-update counters in one typed read model.

Acceptance: account disconnect, selection ambiguity and clock rejection show the same source/readiness on Dashboard, Market and Accounts; retained observations never appear current.

### P0-04: Clock evidence and native signal prerequisites are not operationalized

Evidence: FUTURE_SOURCE_TIMESTAMP and CLOCK_PROFILE_REQUIRED. `market/metatrader/clock.py` provides short-lived independent anchor validation. Native historical signal windows need a separate clock profile. Live offset evidence is not a historical DST rule.

Recommendation: an ATS clock-status panel and trusted renewal service; server/session binding, expiry, raw/normalized time, measured offset and provenance. Separately version historical timezone/DST mapping for strategy warmup. Do not extend an old evidence expiry or silently apply one offset to all history.

Acceptance: timezone changes, expired evidence, weekends/stale ticks and server changes fail closed; renewal restores accepted observations without restarting the entire application.

### P0-05: External reconciliation and reduction lifecycle missing

Evidence: account snapshots do not settle a durable order/deal ledger. External ledger reservations exist, but no commissioned lifecycle resolver, manual-close endpoint or persistent trailing/exit manager is routed. Adapter can return ACCEPTED/UNKNOWN; this is not proof of final filled position state.

Recommendation: account-scoped reconcile worker with durable checkpoints and broker IDs. Distinguish submitted, acknowledgment unknown, partial fill, filled, rejected, cancelled and closed. Add authorized close/reduce/SL/TP operations; kill switches block new risk while valid reductions remain possible.

Acceptance: ambiguous acknowledgment never triggers blind retry; terminal/manual changes are detected; broker-side SL/TP is read back; orphan positions and restart gaps block new entries until resolved.

### P1-01: Strategy and account configuration is not controllable from ATS

Evidence: strategy store register/revise methods exist, but strategy API exposes reads/jobs rather than strategy configuration mutations. Account allowed_strategy_ids/risk_profile_id have no assignment endpoints. Strategies UI searches read-only records, not settings.

Recommendation: separate immutable strategy definition/version, research parameter set, account assignment and effective execution configuration. UI: exact strategy ID/version, direction/horizon, sessions, entry/exit/SL/TP, costs, dataset evidence, account selection, configuration diff, save draft, validate, apply, pause and retire. Agents may propose changes; operator/deterministic services own application and promotion.

Acceptance: optimistic revision conflicts; active trades retain their originating configuration; retiring prevents new entries without abandoning open-position management; IDs are never reused.

### P1-02: Lot sizing needs one authoritative preview and final calculation

Evidence: broker volume-step validation exists; research presets/standalone scripts calculate sizing; no integrated lot-control API/UI. The selected presets deliberately restrict $1000 research variants and cannot be generalized to $500 by changing capital alone.

Recommended model: default risk-based sizing. Obtain observed broker metadata and OrderCalcProfit/OrderCalcMargin. Available trade risk is the strictest of account per-trade, strategy, daily/monthly remaining and aggregate open-risk budgets, with conservative costs/reserves. Floor volume to broker step; reject below minimum; never round up to make a trade fit. Fixed lots, if supported, remain subject to the same limits.

Display: requested risk %, risk $, entry/SL distance, proposed lots, minimum/step/max, observed contract/tick values, loss at SL plus costs, margin/free margin, spread and binding constraint. Explain every rejection. Recalculate at authorization and immediately before submission; a UI preview is not authority.

Acceptance: small-account minimum-lot rejection, unknown metadata, widened spread, changed stops, currency conversion, grid rounding and margin insufficiency remain deterministic. Use actual metadata; do not hardcode a universal XAUUSD contract multiplier.

### P1-03: Native observer is not an ATS-managed execution engine

Evidence: MQL observer writes account-state/proposals/journal; commands_supported=false. Production Python source has no native proposal ingestor. Installer scripts do not create a routed lifecycle controller. Existing original GoldTripleDemo is documented as a separate system, not inherited ATS authority.

Recommendation: choose one execution owner: ATS worker/approved SDK adapter. Native EA provides observed context/proposals if required; it must not become a competing order sender. Add proposal ingestion with schema/hash/session/strategy checks and deduplication. Display deployed versus configured source/executable/preset hashes, chart attachment, heartbeat age, signal reason and rejected proposal reasons.

For add/delete strategies: create a versioned draft; validate/build; stage deployment; verify actual attachment/hash; enable only through assignment. Prefer retire/archive. Removing an EA or strategy cannot strand exposure; reconcile ownership first. A credentialed EA, command file or Algo Trading toggle is not deterministic authority.

### P1-04: Operator controls must be authenticated before external execution

Evidence: console CORS is allowlisted and loopback launcher binding exists. Inspected console routes have no operator authentication dependency, CSRF token or per-command identity. Default CORS includes port3000, which belongs to another local application. CORS is a browser read policy, not authorization for arbitrary local clients or all state-changing requests.

Recommendation: local operator session/auth, exact ATS origin/host validation, CSRF protection for mutations, audit operator identity, idempotent configuration commands, and secret-safe errors. Do not expose execution APIs merely by rebinding to a network interface.

This is a source-level gap, not a demonstrated exploit or penetration-test result. Harden before introducing financial commands; preserve DPAPI and agent secret exclusion.

### P1-05: Observability currently mixes service response, paper state and account readiness

Evidence: System reports RUNTIME_NOT_ATTACHED while runtime status provides paper capital; no integrated broker positions/trade history page. Native signal/clock/preset state is absent from ATS. The new UI displays primitive fields but complex readiness indicators remain in diagnostics.

Recommendation: dashboard grouped into system, selected broker account, execution readiness, risk budget, strategy signals and research. Separate Paper/Broker labels and currency. Build Positions/Orders/Deals with filters and lineage links. Show timestamps, source, stale/unknown badges and reason explanations on every metric. Add alerts for heartbeat loss, reconciliation mismatch, clock expiry and pending acknowledgment. Bound polling or use an event stream with snapshot recovery.

### P2: Research and trade intelligence need usable evidence navigation

Research templates are not running agents. Bounded manual jobs are useful; automatic cadence is not wired. Empty production datasets mean standalone historical research cannot silently become production evidence. Entry/exit calculations are not connected to live sampling/manual exits.

Add bounded scheduling only after reproducible jobs; job progress/cancel/result pages, dataset/hash/cost linkage, and explicit validation states. Connect position samples to MFE/MAE/capture/giveback and closed-trade diagnosis. Exit Watch stays advisory; manual exits pass deterministic reduction authority. Hypothetical continuation needs original immutable rules and observed subsequent data, not hindsight rewriting.

## Proposed implementation sequence

1. **Unify observed state and restore reliable market acceptance.** Explicit account selection, clock status/renewal, native heartbeat/proposal visibility, source identity and clear readiness. No order routing required.
2. **Create the configuration control plane.** Versioned strategy parameters, account assignments, risk profiles, sizing preview and effective-configuration inspector. Draft/apply/pause/retire semantics, operator authentication and audit.
3. **Commission external execution as one vertical slice.** One isolated account and eligible strategy, trusted period ledger, broker-aware sizing, durable authority/reservation, adapter dispatch, deal reconciliation, kill/reduction controls and restart recovery. Demo/live share account abstraction and mode-bound authority; physical acceptance is recorded per mode/account.
4. **Expand operational visibility.** Account/strategy positions, orders/deals, risk budgets, signals, EA deployment receipts and correlated evidence timelines. Then multiple accounts, richer exits, bounded research scheduling and trade-quality intelligence.

Do not rewrite trusted kernel/contracts or build redundant MetaTrader packages. Reuse current store, worker isolation, DPAPI, fabric, external ledger, adapter and tested pure functions. Simplify by assigning one owner to each state and one execution engine.

## Required operating screen structure

- Dashboard: selected account, connection/clock/feed, effective execution status, remaining day/month budget, open exposure, strategy readiness and alerts.
- Accounts: connection identity, broker metadata, risk profile, assignment matrix, consent versus effective enablement, reconnect and account kill.
- Strategies: definition/version/parameters, evidence, direction/horizon, account deployments, draft/apply/pause/retire, signal/entry/SL/TP and sizing preview.
- Market: consistent selected account, observed chart/quotes, freshness/source/reasons and honest proxy footprint.
- Positions: broker/ATS reconciliation, fills, SL/TP, risk, manual reduction/exit, strategy/version/account lineage.
- Research/Datasets/Agents: reproducible jobs, hashes, costs, validation and proposal-only capability boundaries.
- System: subsystem readiness, native/SDK versions, clock evidence, recovery actions and audit diagnostics.

## Completion criteria for fully connected ATS

An operator can connect an account, configure a versioned strategy, assign it and an explicit risk profile, preview broker-valid lots, enable desired execution, see effective deterministic readiness, observe the authorized order/fill/position with server SL/TP, pause new entries, reduce/exit safely, and reconstruct every action. Restart, stale clock, missing deal history and terminal identity changes cannot silently resume or duplicate execution. Manual/native trades remain visible in account-wide risk. Configuration and deployed EA mismatches are shown, not guessed away.

## Verification and limits

Focused command: `uv run --no-sync python -m pytest tests/unit/test_external_authority.py tests/unit/test_demo_execution_supervisor.py tests/unit/strategies/test_small_account_presets.py tests/unit/trading_runtime/test_trade_quality.py tests/contract/test_external_boundary.py backend/tests/test_metatrader_accounts.py backend/tests/test_metatrader_worker_isolation.py -q`.

Result: **69 passed in 7.78 seconds**, zero failed/skipped in this run. Browser Accounts verified the actual disconnected/unknown states and existing connect/reconnect/consent controls. Source trace covered console routing, account sessions, external ledger/adapter/supervisor, native observer/presets, strategy store/jobs and UI.

No full suite rerun, load test, security exploit test, new physical session test, historical backtest, order submission, new CI run or profitability claim was performed for this audit. Previous revision CI green does not commission dormant functionality. Runtime snapshots are point-in-time and may change. No production configuration was changed.
