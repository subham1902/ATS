# ATS Operator Cockpit V2 — Acceptance Report

## A. Repository

- Start HEAD: `22159d240f8ab69186b1576914aa05d293e9ec3f`
- Branch/worktree: `ui/operator-cockpit-v2` / `D:\Projects\ATS\worktrees\operator-cockpit-v2`
- Source base: `511a41d250f79f27127dcfaaafe3faff9bd5b516`
- Preserved stash: `stash@{0}: D10-uncommitted-work-preserve`
- Implementation commit: `82c97e4 feat(operator):governed-paper-intents-managed-exits`
- Acceptance report commit: the commit containing this report; exact end HEAD is reported in the final handoff.

## B. Top-to-bottom audit

Already correct: A2 PAPER launcher, read-only Upstox feed, provider reference authority, bounded non-blocking SSE, C0 pipeline, Portfolio Brain, existing reduction authority, PaperBroker-only adapter, evidence-backed chat, advisory-only agent tools, confirmed runtime controls, and feature-flagged cockpit foundation.

Broken/incomplete: no operator-entry command; no position origin or managed-exit mode; monitor-only semantics absent; manual ticket disabled; position read model lacked operational fields; manual option freshness/lot/capital/A04 proof absent. These were implemented without changing C0, its 0.55 threshold, shadow models, risk envelopes, or live-broker code.

## C. Chrome UX

Mandatory Chrome interaction is **blocked**. Diagnostics on 2026-08-28 found Google Chrome installed and running and the native-host manifest correct, but the ChatGPT Chrome extension ID `hehggadaopoacecdllhhajmbjkdcmajg` was not installed in Default or Profile 2. Per the required Chrome-control workflow no alternate browser or standalone automation was substituted.

No viewport/zoom screenshot or physical click path is claimed. The matrix below is therefore truthful:

| Screen / flow | 1366 | 1440 | 1920 | Functional | Clear | Blocker |
|---|---|---|---|---|---|---|
| Overview, Markets, Trade Desk, Positions | BLOCKED | BLOCKED | BLOCKED | code/tests only | not visually accepted | Chrome extension missing |
| Opportunities, Agents, Research | BLOCKED | BLOCKED | BLOCKED | existing routes build | not visually accepted | Chrome extension missing |
| Session Review, System | BLOCKED | BLOCKED | BLOCKED | existing routes build | not visually accepted | Chrome extension missing |
| Manual Trade, Managed Exit | BLOCKED | BLOCKED | BLOCKED | backend/unit + typed UI | not visually accepted | Chrome extension missing |
| Pause/Resume, Flatten, Reconnect | BLOCKED | BLOCKED | BLOCKED | existing typed paths | not click-tested | Chrome extension missing |

## D. Live charts

The chart remains bounded to 120 complete OHLC SSE events, deduplicated by event ID, instrument-linked, and truthful when unavailable. Current scope does not yet complete volume, crosshair, timeframe aggregation, markers, or position overlays. Actual market-open visual acceptance is `PENDING_LIVE_SESSION`.

## E–F. Manual PAPER trade and position adoption

`OperatorOrderIntent` supports long BUY CE/PE only and carries operator action, provider instrument key, underlying, expiry, strike, type, lots/quantity, order type/price, origin, timestamp, managed-exit mode, and optional reason. `OperatorOrderService` fails closed on InstrumentSpec, expiry/strike/type, exact provider lot, per-option freshness, entry session/pause/halt, capital, broker health, and deterministic A04/token. Only after all pass can its injected PaperBroker adapter submit. A fill enters the same runtime position dictionary and therefore runtime P&L, capital projection, mark updates, position monitor, and API read model.

The live read-only supervisor attaches provider reference contracts to this service. The UI has no PaperBroker import or endpoint.

## G. Managed exit

Positions persist `MONITOR_ONLY` or `ATS_MANAGED_EXIT`. Ordinary deterministic exit recommendations do not automatically exit monitor-only positions. ATS-managed positions follow the existing deterministic monitor/reduction path. Existing mandatory session/account safety flatten still has priority. UI commands change mode only after an authoritative response; manual exit records `OPERATOR_MANUAL_EXIT`.

## H–I. Autonomous path and agents

The autonomous C0 path is unchanged. No alpha, threshold, promotion, sizing envelope, or qualification logic changed. Agents remain event-backed/advisory; the existing agent tool deny-list excludes financial mutation and the new order service is not exposed to agents.

## J–K. P&L and operations

Position views now expose origin, managed-exit mode, committed capital, stop/trailing state, hold time, deterministic recommendation and reasons. Realized/unrealized/capital/HWM/drawdown remain canonical runtime fields. Pause, resume, flatten and halt remain typed, non-optimistic commands. Manual exit uses one PAPER confirmation.

## L. Toolchain

- Python: 3.11.15 through `uv`, repository-local `.uv-cache`
- Node: 24.19.0 from `D:\Projects\ATS\toolchains\node-v24.19.0-win-x64`
- pnpm: 11.9.0

## M. Performance

Financial processing remains synchronous and independent of UI projection. Operator events retain bounded queues and drop slow subscribers rather than backpressure P0/P1. Frontend SSE retention remains 200 events; chart retention remains 120 candles; option projection deduplicates by provider key. Browser FPS/memory percentiles were not measurable because Chrome control was blocked.

## N. Tests

- New manual governance/adoption/monitor-only tests: 3 passed
- Focused runtime/A2/exit tests: 17 passed
- Ruff on touched Python: passed
- Mypy on new service, position, engine and router: passed
- Python compile: passed
- Vitest: 58/58 passed
- TypeScript: passed
- Next production build: passed, 18 routes
- Broad trading-runtime baseline: one existing stale-scanner failure at 18th test; expected `None`, observed a safe `CALIBRATION_EVIDENCE_REQUIRED` zero-qualified result
- Chrome/Playwright: blocked by missing Chrome extension; no screenshots claimed

## O. Live acceptance

No order was sent to any live broker. Market-open visual acceptance remains `PENDING_LIVE_SESSION`. Connected browser smoke was blocked before navigation by the missing extension.

## P. Profitability

- OPERATIONAL TRADE CAPABILITY: **YES for governed synthetic/local A2 PAPER paths; live-session UI acceptance pending**
- ALPHA PROFITABILITY VALIDATED: **NO**

No profitability or return claim is made.

## Q. Safety

- PAPER ONLY / LIVE MONEY DISABLED / REAL BROKER ORDERS 0
- A04 final deterministic manual authority; C0 production threshold remains 0.55
- M1–M9 and R10-X retain zero production authority
- Agents retain zero direct order/exit/resize/mode authority
- Manual orders are governed and managed exits are deterministic
- No forced trades, model promotion, broker browser automation, or historical Upstox 1010 retry

## R. Integration plan

Merge only the commits created on `ui/operator-cockpit-v2` after architecture and Chrome acceptance review. Expected conflicts remain runtime/controller/router surfaces plus cockpit CSS/component changes. No database migration was introduced; managed-exit persistence is runtime-state persistence and restart durability still requires a future canonical store migration. Keep `NEXT_PUBLIC_ATS_OPERATOR_COCKPIT_V2=1` opt-in until Chrome acceptance completes.

## Final verdict

**BLOCKED_CHROME_EXTENSION**

The implementation materially closes manual PAPER authority and managed-exit semantics, but the explicitly mandatory Chrome acceptance, screenshots, zoom/viewports, physical click paths, and browser performance checks cannot be completed until the ChatGPT Chrome extension is installed and enabled.
