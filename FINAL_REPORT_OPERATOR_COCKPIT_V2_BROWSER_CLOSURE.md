# Operator Cockpit V2 — Browser Closure Report

## A. Repository

- Start HEAD: `8625ce46e742ef26d564e0bd0513c2935e5db7a7`
- Branch: `ui/operator-cockpit-v2`
- Source base: `511a41d250f79f27127dcfaaafe3faff9bd5b516`
- Closure implementation commits: `200afef` and `8523bb1`; this report and the
  operating note are in the containing documentation commit.
- `stash@{0}: D10-uncommitted-work-preserve` remained untouched.

## B. Chrome blocker

The earlier `BLOCKED_CHROME_EXTENSION` verdict was not a valid statement about the
machine's browser runtime. Google Chrome exists at
`C:\Program Files\Google\Chrome\Application\chrome.exe`; Edge also exists locally.
No browser extension is required by ATS itself.

The browser-control channel available to this implementation session could not attach
to Chrome (`Browser is not available: chrome`). Session policy did not permit replacing
that channel with an unmanaged browser profile or direct standalone automation. No user
profile, broker session, extension, or external trading site was accessed. Consequently,
interactive screenshots and real Chrome click-path claims remain unverified rather than
fabricated. This is a limitation, not `BLOCKED_CHROME_EXTENSION`.

## C. Browser acceptance

The local isolated stack was started with the cockpit feature flag, Python 3.11.15,
Node 24.19.0 and pnpm 11.9.0. Backend `/health/live` returned `LIVE`,
`/health/ready` returned `READY`, runtime status returned the correct `CLOSED` session,
and the frontend returned HTTP 200. Browser-control attachment was unavailable, so no
screenshots or physical 1366/1440/1920 and 90/100/110 percent zoom assertions are made.

| Screen / flow | 1366 | 1440 | 1920 | Functional evidence | Clear | Blocker |
|---|---|---|---|---|---|---|
| Overview through System | pending visual | pending visual | pending visual | build, component tests, local HTTP | pending visual | browser-control transport |
| Manual trade | pending visual | pending visual | pending visual | governed backend and ticket tests | pending visual | browser-control transport |
| Managed exit | pending visual | pending visual | pending visual | engine/restart tests | pending visual | browser-control transport |
| Reconnect | pending visual | pending visual | pending visual | bounded dedupe projection tests | pending visual | browser-control transport |

## D. UX defects

| ID | Screen | Defect | Severity | Fix | Status |
|---|---|---|---|---|---|
| UX-01 | Chart | Only 1m static OHLC; no crosshair/volume/current line | high | Added real-bar aggregation, crosshair, volume, price line and IST freshness | fixed |
| UX-02 | Chart | No lifecycle evidence markers | high | Added event-ID-backed entry/exit/reduction/qualification/A04/flatten markers and evidence drawer | fixed |
| UX-03 | Position chart | No canonical stop/target/entry overlay | medium | Added overlays only for populated server fields | fixed |
| UX-04 | Browser matrix | Prior verdict depended on unrelated extension | high | Reclassified accurately; verified installed Chrome/Edge and local stack | fixed, visual execution pending |
| OPS-01 | Restart | Manual origin and managed-exit mode lost | critical | Added atomic PAPER operational checkpoint | fixed |
| TEST-01 | Scanner | Test treated inclusive 10s freshness boundary as stale | medium | Test now exceeds configured boundary by 1ms | fixed |

## E. Live chart

The chart consumes deduplicated SSE OHLC events and retains 120 source candles. It
supports 1m plus deterministic 3m/5m/15m aggregation from received 1m bars; missing
intervals are not invented. Volume renders only when supplied and otherwise says
`VOLUME UNAVAILABLE`. It now has a crosshair, current-price line, IST timestamp,
time/price scales, and keyboard-operable markers. Markers are created only from real
stream event IDs for ATS/manual entry and exit, partial reduction, session flatten,
C0 qualification and A04 denial. Position entry, stop, target, and trailing lines render
only when canonical fields exist.

## F. Manual paper trade

The previously delivered CE/PE long-only ticket and `OperatorOrderIntent` remain the
entry route. The frontend has no PaperBroker client. InstrumentSpec, provider expiry,
strike, option type, lot quantity, quote freshness, session, halt, capital, Risk/A04
decision/token and the restricted gateway remain required. Denials are authoritative;
stages not invoked remain `NOT REACHED`.

## G. Managed exit

`MONITOR_ONLY` still suppresses ordinary governed automatic exits but not mandatory
session/account safety reductions. `ATS_MANAGED_EXIT` permits only deterministic
safe-reduction flow. Agent recommendations cannot submit orders. The checkpoint retains
the explicit mode across restart without replaying an order or fill.

## H. Autonomous steel thread

Existing autonomous scanner/authority/runtime tests passed in the full suite. No C0
math, 0.55 threshold, portfolio envelope, A04 rule, or shadow authority changed. A fully
clicked browser visualization of the synthetic steel thread remains pending the browser
control channel.

## I. Manual steel thread

Backend tests cover governed allow/deny, fill adoption, origin, capital committed,
monitor-only semantics, managed exit selection, manual exit, and restart restoration.
Ticket and client projection tests pass. CE and PE physical browser submissions remain
pending browser-control availability.

## J. Restart durability

An optional `ATS_A2_RUNTIME_CHECKPOINT_PATH` configures an atomic local JSON projection
for the A2 PAPER runtime. It stores open position identity, instrument, origin, quantity,
entry/risk capital terms, explicit exit-management mode and equity summary. Restart
restores the same position ID without generating an order, fill, P&L, or agent event.
Broker fills and authority evidence remain canonical; the checkpoint is monitoring state,
not execution authority. A restart unit test proves manual position continuity. The
existing durable authority store continues to restore autonomous governed positions.

## K. Stale scanner test

Classification: **A — stale test**. Production freshness accepts age less than or equal
to the configured 10,000 ms. The test used exactly 10 seconds while its comment claimed
a 2,000 ms threshold, so the scanner correctly reached the next safe rejection,
`CALIBRATION_EVIDENCE_REQUIRED`. The test now uses configured maximum plus 1 ms. The
production fail-closed implementation was not changed.

## L. Agent UX

Presence remains derived from typed/material events, collapses to one latest state per
role, becomes IDLE after 30 seconds and can be hidden without hiding activity. Agents
remain advisory-only. A04 remains separate deterministic authority.

## M. P&L / capital UX

The persistent bar exposes capital, available capital, net today and position count.
Positions expose current authoritative unrealized P&L and committed premium. Stops,
targets and costs are never fabricated. A selected matching position is summarized on
the chart with origin and exit mode.

## N. Reconnect

SSE event IDs continue to deduplicate replay. Candle retention is 120 and marker
retention is 40; agent projection retains only the latest record for five roles. Snapshot
recovery remains server-authoritative. A physical disconnect/reconnect browser run is
pending browser-control availability.

## O. Performance

A 10,000-event projection test completes in the normal Vitest run (75 ms on this host)
and proves bounded chart, marker and presence projections. No checkpoint write was added
to the market-tick path; writes occur only on fill, mode transition, exit request/fill.
No LLM or UI work was added to P0/P1. Browser long-task/memory profiling remains pending.

## P. Tests

- Python: 3.11.15 through repository-local uv cache.
- Full repository backend collection: **214 passed, 1,632 skipped, 0 failed**.
- Ruff, touched authority/restart scope: PASS.
- Mypy, runtime checkpoint/engine/operator order: PASS.
- Python compile: PASS.
- Node: **24.19.0**; pnpm: **11.9.0**.
- Vitest: **61/61 PASS**.
- TypeScript: PASS.
- Next production build: PASS, 18 static routes.
- Playwright/Chrome physical acceptance: not executed; browser-control transport unavailable.

## Q. Connected status

After-hours local read-only smoke passed for backend, frontend and runtime API. Session
state was truthfully `CLOSED`, entry false, with no fabricated tick or position. No broker
order API or authenticated brokerage page was touched.

`PENDING_MARKET_OPEN_CONNECTED_VISUAL_ACCEPTANCE` applies to active Upstox ticks and
market-open chart behavior.

## R. Safety proof

- PAPER ONLY; LIVE MONEY DISABLED; REAL BROKER ORDERS = 0.
- A04 remains final deterministic authority.
- C0 remains champion with threshold 0.55.
- M1-M9 and R10-X retain zero production authority.
- Agents retain zero direct order authority.
- Manual orders remain governed; managed exits remain deterministic safe reductions.
- No forced trades, model promotion, broker browser automation, or historical Upstox
  1010 retry was introduced.

## S. Profitability status

- OPERATIONAL TRADE CAPABILITY: **YES, A2 PAPER**.
- ALPHA PROFITABILITY VALIDATED: **NO**.

## T. Integration plan

Cherry-pick `200afef` and `8523bb1`, followed by the containing documentation commit,
after the prior cockpit
foundation commits. Expected conflict areas are `engine.py`, `a2_runner.py`, cockpit
chart/model/CSS, and API OpenAPI allowlists if integration has advanced independently.
Set `NEXT_PUBLIC_ATS_OPERATOR_COCKPIT_V2=1` for reviewed deployments and configure
`ATS_A2_RUNTIME_CHECKPOINT_PATH` to a writable PAPER runtime data path. Keep the legacy UI
available until market-open and physical-browser acceptance are signed off.

## Final verdict

**READY_WITH_LIMITATIONS**

The remaining limitations are physical Chrome/Playwright visual acceptance, browser
disconnect profiling, and market-open connected visual acceptance. They are not an ATS
authority or paper-trading capability gap, and the verdict is not
`BLOCKED_CHROME_EXTENSION`.
