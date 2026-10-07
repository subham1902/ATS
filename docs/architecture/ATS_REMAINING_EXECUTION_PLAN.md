# ATS remaining execution plan

Date: 2026-10-07. Status: proposed sequence after the current Step 1 checkpoint.
This plan replaces the older integration plan's parallel-provider and rollout
assumptions. It does not begin Steps 2–4 or claim they are implemented.

Use the existing MetaTrader package, account registry, canonical observations,
fabric, strategy definitions, research engine, managed agents and deterministic
paper core. Build one complete path at a time. Keep the requested order and green
boundary reports; shorten work by reducing duplicate infrastructure, not gates.

| Gate                              | Smallest coherent deliverable                                                                                | Acceptance                                                                                                                               |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Finish Step 1 physical acceptance | Document source timestamp semantics; verify two isolated authenticated terminals through the account service | Correct UTC provenance, fresh admitted XAUUSD quotes, isolated reconnect/failure, protected secrets, exact-HEAD CI green                 |
| Step 2: Strategy OS and research  | One durable strategy registry, one bounded research queue, typed agent outputs and strategy cards            | Immutable XAU IDs, reproducible dataset/cost/version-bound jobs, honest probabilities, no agent execution capability                     |
| Step 3: External execution        | One account-bound authority/router/MT5 adapter path with risk, ledger and reconciliation                     | Stubbed failure matrix green; actual terminal validation documented; A2 cannot reach SDK orders; user routing and kill switches enforced |
| Step 4: Trade intelligence        | One observation/forensics pipeline, Exit Watch advisory and authorized manual reduction                      | Causal MFE/MAE/quality metrics, auditable manual exit, immutable hypothetical continuation, no agent exit authority                      |

## 0. Close current acceptance gaps

Resolve the +3-hour tick epoch with documented broker/terminal evidence. Never
subtract a guessed timezone offset or use receive time as source time. Record raw
and normalized timestamps and conversion provenance if a justified correction is
needed. Verify current source freshness and the full journal/fabric/chart path.

Obtain two distinct authenticated terminal installations/profiles, then test
connect, disconnect, reconnect, mode detection and independent failures through
the real account-service workers. Use secure local submission; no passwords in
chat, logs or reports. Stub tests already cover these software paths. MT4 accounts
remain NOT_CONFIGURED until a real authenticated bridge is implemented and tested.

## 1. Step 2: one strategy registry and one research job engine

Assign never-reused XAU-### lineage IDs transactionally, preserving explicit aliases
only as historical references. Runtime/API lookup is exact. Store one canonical
record per version and generate STRATEGY_INDEX.yaml and strategy documents from
it rather than maintaining divergent registries. Record hypothesis, LONG/SHORT/BOTH,
SCALP/INTRADAY/SWING/POSITION, timeframes/sessions, entry/exit/SL/TP/sizing,
features/data requirements, failure modes, evidence/results and validation dates.
S5 stays DESIGN/RESEARCH_ONLY until its open design topics are resolved.

Use the existing research engine behind one persistent bounded queue. Each run
binds agent/config, strategy/version, dataset/hash, parameters, method, costs,
budget, start/finish/status and result hash. Cadence supports manual, dataset/version
events, nightly and weekly. Enforce concurrency, timeout/trial/resource limits,
deduplication and restart recovery. No infinite optimization loops or new broker
services are needed. A queued approved research job may run; it cannot promote.

Create specialized managed-agent templates for Research, Backtest, Validation and
Signal Analysis first. Add Regime, SL/TP, Entry Quality, Exit Watch, Forensics and
Librarian as templates over the same job engine, not ten independently scheduled
workers. Agents read safe market/research views only. Source contracts reject broker,
credential and authority imports, including capability escalation through job tools.

Typed signal output includes strategy/version/time, direction/horizon/regime,
entry status/zone/invalidation, SL, TP targets/trailing, risk/reward, expected
duration, supporting/contradicting factors and freshness. Separate heuristic model
confidence from empirical probability. Uncalibrated probability is UNKNOWN; a value
requires a versioned calibration artifact, dataset and validation run. Never display
illustrative trading values as current signals.

Lifecycle DRAFT -> RESEARCH -> CANDIDATE -> PAPER -> DEMO -> MICRO_LIVE -> ACTIVE,
plus PAUSED/RETIRED, uses explicit deterministic evidence requirements. Agents
recommend only. Strategy UI combines version/history, results and current signals;
leaderboard shows return, drawdown, PF, Sharpe, average R, trades, profitable months,
stability, holdout/cost stress and forward/entry/exit quality. Missing results stay
unknown. Prior market results remain excluded. User data is required for real
research claims, not for building or testing the queue.

## 2. Step 3: one execution path for DEMO and LIVE

Add external authority separately from A2_PAPER. Bind every permission to strategy/
version, account, observed mode, canonical symbol, side, quantity, risk and expiry.
Keep the paper token schema and trusted kernel unchanged where possible; use pure
external authorization predicates and durable single-use consumption. Neither
frontend nor agents construct authority.

Start with a market order plus required broker SL/TP in one selected account, then
multi-account child executions, pending orders/cancellation where supported and
authorized position reduction. Support both directions only after runtime and
accounting tests prove them. Use the same adapter for demo/live; account mode is
displayed and authority-bound, not a blanket LIVE prohibition.

Connect & Enable becomes effective only with explicit user strategy association
and finite risk limits: trade risk, daily loss, total open risk, size, position count
and strategy exposure. Account enable/disable and selected/all-enabled routing are
operator-only. Each child has separate execution/order/deal IDs and account-bound
reservation. Cross-account fan-out is not atomic: report partial success honestly;
never retry or undo another account's trade to manufacture all-or-nothing behavior.

A single approved MT5 execution adapter owns SDK order functions. Extend the common
interface with submit/query/cancel, positions/account/deals, close, health and
reconcile. No duplicate connector package. MT4 uses the same interface only when
a tested real bridge exists. It remains explicitly unavailable otherwise.

Before new risk, require fresh quotes, account identity, metadata grids, valid
authority, risk reservation, connection and reconciliation. Global/account/strategy
kill switches block new risk while separately authorized reduction remains possible.
Observe broker orders/deals/positions; mismatch becomes RECONCILIATION_REQUIRED.
Timeout is UNKNOWN: query before any retry. Persist intent/submission state before
calling the SDK, then reconcile after restart. Dedupe keys and single-use authority
must prevent duplicate submissions even across crash/timeout windows.

Ledger evidence includes requested/actual entry, SL/TP, spread/slippage/latencies,
commission/swap, rejection and broker IDs. Correlate strategy/version, agent run,
signal, authority, account, execution and position. UI clearly shows LIVE ACCOUNT /
AUTONOMOUS EXECUTION ENABLED and gates. Tests use mocked SDKs; CI never requires or
trades an account. Actual demo-terminal validation is reported separately. Enabling
a real account is an explicit operator action under its accepted risk profile.

## 3. Step 4: one causal trade-quality pipeline

Record signal/request/fill, initial/current SL and targets, spread/slippage,
regime/session/ATR, elapsed time, MFE/MAE, current/peak R per account/execution.
Use executable bid for long liquidation and ask for short liquidation; document
cost treatment, denominators and missing-quote handling. Unknown initial risk or
incomplete path yields unknown metrics. Evaluate entry after sufficient future
information without rewriting its original signal or using P&L alone.

Version deterministic entry/exit label thresholds. Compute immediate MAE, time to
favorable movement, entry-zone deviation, MFE capture, realized R, giveback and
time from peak to exit. Produce the four good/bad entry/exit diagnoses and supported
tags such as chased entry, spread, trail distance and missed scale-out. Require
sufficient samples before strategy-level recommendations.

Exit Watch is advisory-only. It reports observed R/giveback/momentum/trail evidence
and MANUAL EXIT REVIEW; it cannot close positions. Manual Exit goes through a
deterministic reduction route and records operator time, reason/source, market
snapshot, watch state and broker result. Preserve a separate non-executing shadow
lifecycle with original strategy/version/rules to compare human and hypothetical
strategy exits. Gaps or ambiguous fills make that comparison UNKNOWN.

Use Accounts for connections, Positions for trade/manual-exit views, Strategies
for evidence/quality, and Agents for jobs/advisories. Final navigation: Dashboard,
Market, Strategies, Agents, Accounts, Positions, Research, Datasets, System.
Dashboard derives connection/consent/positions/signals/watch/risk/system facts from
the same read models; no duplicate stores or invented status counters.

## Validation and delivery rhythm

For each slice: focused unit/fault/contracts first; one full local suite at the
boundary; pinned frozen installs; lint/types/frontend build; commit; push once;
verify exact-HEAD CI including PostgreSQL execution, secret scanning, trusted-core
coverage and tracked-file cleanliness. Fix defects without weakening gates. Reuse
completed evidence; rerun only for affected changes. Never run durability tests
concurrently against one shared database. Boundary reports list HEAD/commits/status,
pass/fail/skip/not-run counts, CI, implemented/missing work, risks and next step.

Keep architecture documentation beside each implemented boundary:
STRATEGY_OPERATING_SYSTEM.md and AGENT_RESEARCH_SYSTEM.md in Step 2;
update METATRADER_MULTI_ACCOUNT_EXECUTION.md in Step 3;
TRADE_ENTRY_EXIT_INTELLIGENCE.md in Step 4. Update ATS_IMPLEMENTATION_REPORT.md
without allowing historical entries to describe current capability.

The speed gain comes from one registry, one queue, one adapter/router/ledger and
one quality pipeline. Physical acceptance, calibrated probabilities, evidence-based
promotion and deterministic financial authority are never shortcuts.
