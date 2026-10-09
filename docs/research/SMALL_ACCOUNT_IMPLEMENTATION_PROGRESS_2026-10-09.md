# ATS small-account implementation progress

Report date: October 9, 2026, Asia/Calcutta. This continues the existing checkout
and completed searches; it does not repeat the specialization migration or a
completed broad parameter search.

## Outcome

Two positive $1,000 standalone historical conditions have been implemented as
versioned research presets. S3 is the stronger candidate; S2 is economically
marginal. A configured S3 native observer is running in MetaTrader and publishing
actual account/quote observations. It cannot trade. ATS has submitted zero orders.
External execution is still an uncommissioned development component.

| Candidate    | Later-period BASE |  Later-period STRESS | Trades per scenario |
| ------------ | ----------------: | -------------------: | ------------------: |
| XAU-020 / S3 | +3.3280% / $33.28 | +6.51925% / $65.1925 |                   5 |
| XAU-019 / S2 | +0.1913% / $1.913 |  +0.01495% / $0.1495 |                   7 |

These are the broker-target-grid V3 results, March–August 2026, not forecasts.
The earlier unsnapped results remain preserved. The later period has already
been inspected in prior research and is not a pristine holdout. S3's stress
scenario admits a different retest on August 4; its higher return does not show
that higher costs improve the same trades. Neither sample establishes an edge.

## Exact selected conditions

### XAU-020: S3 H4-close retest

- Direction LONG; trade horizon INTRADAY.
- H4 parent breakout and EMA30/slope gate, followed by a completed M5 retest.
- Retest level is the published H4 close. The previous-ten-bar high only gates
  the parent signal. This is a new variant, not inherited validation of the EA.
- Tuesday–Thursday, 12:00 inclusive to 17:00 exclusive UTC.
- Structural stop uses the last completed M5 bar, plus 0.1 Wilder ATR.
- Planned risk 1.5%; target 2R, snapped toward entry to the broker tick grid.
- Profit protection disabled; maximum holding time 120 minutes.
- Later BASE worst booked day −1.46194%, month −1.39186%, close-mark DD 1.52767%.
- Later STRESS worst day −1.48850%, month −0.04329%, close-mark DD 1.53221%.

### XAU-019: S2 M15-close retest

- Direction BOTH; trade horizon INTRADAY.
- Source M15 parent/context signal followed by a completed M5 retest of its close.
- Monday–Friday, 12:00–17:00 UTC; structural lookback three completed M5 bars.
- Planned risk 1.25%; target 2R; protection disabled; maximum hold 240 minutes.
- Later BASE worst day −1.72831%, month −2.77236%, close-mark DD 4.48160%.
- Later STRESS worst day −1.79864%, month −2.87683%, close-mark DD 4.62417%.
- Its source volume provenance is UNKNOWN. Retail broker tick volume is not
  automatically equivalent. Its stressed gain is only about fifteen cents.

S1, the combined portfolio, and the $500/$750 configurations remain unqualified.
These settings must not inherit evidence at another starting capital or variant.
All three new lineages, XAU-018 through XAU-020, remain RESEARCH. No promotion was
performed; empirical probability remains UNKNOWN.

## Loss limits and simulation

The user-requested limits are 3% daily and 8% calendar-month net booked P&L,
relative to start-of-period equity. Profits offset losses. Research uses internal
2.5% daily and 6% monthly budgets, one position, at most three entries per day,
halt after two losing trades, fifteen-minute reentry delay and a 30% margin cap.
Minimum/step lots are rounded down; required structural stops are never shortened.

BASE uses observed paired bid/ask, $22 per lot roundtrip modeled costs and observed
100:1 leverage. STRESS uses 1.5× spread, $44 costs and explicit modeled 50:1 leverage.
Current metadata is not a certified historical broker schedule. Stops are active
in the entry minute; ambiguous stop/target bars use stop first; adverse gaps use
the executable open. No artificial last-data close is added. Historical observed
caps are not a guarantee against future gaps, slippage or failed liquidation.

## Step 1: accounts and market foundation

Completed software includes MT5 account registry, DPAPI credential references,
isolated read-only account workers, broker alias to canonical XAUUSD mapping,
normalized observations, journal-before-publication and truthful health states.
MT4 remains NOT_CONFIGURED pending a genuine transport.

Physical observations on October 9:

- Authenticated MetaQuotes DEMO; balance/equity $1,000; no positions or pending
  orders at the checked account-wide snapshots. No login/password is reproduced.
- Native Algo Trading remains enabled; Python trading permission was previously
  observed enabled. Permissions themselves never issue ATS authority.
- `ATSSmallAccountS3_1000` is installed and attached to the XAUUSD chart.
- It publishes `account-state.json`, `observations.jsonl` and raw clock anchors
  under `MQL5/Files/ATS/SmallAccount/<internal-account-id>/`.
- Exact S3 preset hash:
  `9752cab9441c424b946949f2ed9b814e23a4b5b3b3655bb3d7bc623b94209f7e`.
- Its authority is NONE, commands are unsupported, and entry proposals report
  CLOCK_PROFILE_REQUIRED. Missing real volume, last-trade price and depth stay unknown.
- A fresh native clock probe was corroborated by independent UTC. Server offset
  was +10,800 seconds. The live-only proof is valid for fifteen minutes, is not
  a historical DST rule, and must be renewed. On expiry ATS must degrade honestly.
- The ATS account API was reconnected in monitor-only mode and showed LIVE broker
  observations. Its execution gate remains EXTERNAL_ROUTING_NOT_IMPLEMENTED.

The original GoldTriple source and executable remain preserved. The old EA was
removed from the chart while flat. The generic observer's first attachment failed
because its account input was blank; that failure is recorded rather than hidden.
The configured deployment fixes initialization without altering the original EA.
Profile/replacement backups and exact installed hashes are retained in ignored
`reports/small-account-research/native-install-recovery/` and `native-install.json`.

Remaining Step 1 acceptance: automatic independent clock renewal, historical
clock segments, fully integrated observer visibility, browser chart acceptance,
two physical concurrent accounts and a real MT4 bridge.

## Step 2: Strategy OS and research

Completed: immutable XAU IDs, append-only versions, durable bounded research queue,
supervised spawn worker, dataset/strategy/agent capability admission, exact dataset
hash checks, next-quote replay and explicit costs. Agent Playground supports job
submission/progress/cancellation/results. New strategy workspaces and typed V3
presets are present; old evidence was not imported as authority.

This experiment uses the user's original paired UTC M1 files, preserved read-only:
711,286 rows, September 2024–August 2026, no duplicates/crossed fields, 538 gaps
longer than a minute. Vendor identity is not independently certified.

- Bid SHA-256: `95b8c21d46fc8e064bb114b48363c5bdc366d08e5b2ccf581c46b94cba530a80`.
- Ask SHA-256: `5e3217a2b9a8d322938d09dfba3602d8b5bcb056494d7873fe469aaa42bd9dcf`.

Completed searches were reused. Only the selected S2/S3 configurations were
re-evaluated for broker target rounding. Independent ledgers reconcile net P&L,
intermediate booked fee postings, risk/margin admission and session/holding rules.
Eight executable C++ fixtures compile the same native numerical headers and
compare their results with Python, including S3's actual parent gate/ATR/retest.
Full terminal warmup, history aggregation and tick execution parity remain open.

Remaining Step 2: integrate GoldTriple recipes into the production research worker
and exact evidence store; independently verify import provenance; new untouched
holdout/forward evidence; scheduled bounded dispatch, walk-forward/cost validation
and calibration. No LLM confidence is represented as empirical probability.

## Step 3: external execution development

Implemented but dormant: separate A3 demo/A4 live scopes, immutable demo operator
approval, intent/account/mode/strategy/version/preset binding, complete risk-profile
hash binding, remaining daily budgets including reservations, broker grids,
actual profit/margin preflight, finite limits and durable single-use dispatch.
The SDK order boundary is isolated in the approved execution adapter. A2_PAPER
was not widened. Accepted/ambiguous submissions retain risk and block new entries;
there is no blind retry.

This is not an active external trading system. Required commissioning remains:

1. Own an isolated execution session and connect the router to it.
2. Verify the proposed strategy/version/preset independently before authority.
3. Capture genuine UTC start-of-day/month equity and complete booked deal history.
4. Reconcile all account positions/orders/deals; settle or resolve reservations.
5. Coordinate durable global/account/strategy kill controls and approved exits.
6. Demonstrate demo entry, server SL/TP, timeout recovery, holding/session exits and
   restart behavior before any real-money deployment.

No live account was activated and no order was submitted. Terminal Algo Trading
being enabled does not satisfy these missing deterministic routing requirements.

## Step 4: entry/exit intelligence

Completed as a tested pure component: lineage, executable-side MFE/MAE/current R,
realized R, capture/giveback, entry/exit labels and diagnosis. Incomplete paths yield
UNKNOWN. Exit Watch has no authority. Manual-exit comparisons currently use a
clearly labeled static initial SL/TP shadow, not a complete trailing counterfactual.

Remaining: durable broker event ingestion, position-monitor integration, partial
exit/cost settlement, Positions UI, advisory delivery, governed manual reduction
and a faithful original-strategy hypothetical continuation.

## Validation and repository state

- Full Python: 1,631 passed, zero failed/errors/skipped; PostgreSQL durability ran.
- Collection: 1,631 collected. Full run: approximately 77 seconds.
- Contracts: 155 passed. Focused supervisor/adapter/authority checks: 75 passed.
- Research semantics: 19 passed after target-grid tests; native numerical fixtures: 8 passed.
- Preset/registry focus: 19 passed; latest preset-only recheck: 8 passed.
- Ruff clean; mypy clean across 245 source files.
- Frontend tests under pinned Node 24.19.0: 58 passed, zero failed/skipped.
- Frontend typecheck, production build, lint and format check passed; lint retains
  three existing copilot `any` warnings.
- An initial frontend test failed under unsupported Node 26.4.0; the unchanged test
  passes under the pinned runtime. No credential assertion was weakened.
- ESLint now excludes ignored generated reports/isolated virtual environments,
  avoiding linting vendored matplotlib JavaScript as product source.
- Official MetaEditor: zero errors/warnings for both generic and configured builds.
- `uv sync --frozen`, `uv pip check`, `uv lock --check` and pinned
  `pnpm install --frozen-lockfile` passed. No product dependency was added for research.
- Native account acceptance tests use observed DEMO state; CI uses mocks and never
  requires or executes a real account.

Research environment and optional compiled numerical fixtures live in ignored
reports storage; standard CI does not certify the native terminal or an empirical
strategy edge. Implementation was committed as `782c2f9`, `05057de`, `86077d7`
and `c9138d3` and pushed to main. CI run 37907325926 passed unit, contract,
smoke/governance, coverage, frontend, property, PostgreSQL durability/fault and
secret-scan jobs. Linux mypy found Windows-only file-lock attributes; the follow-up
fix uses a platform-selected dynamic import while preserving lock behavior.
Dependency Review was skipped for the push event. Exact follow-up HEAD CI must
be checked; the earlier green baseline `da040e3` does not certify this work.

Port 3000 was not touched. AI/agents remain proposal-only. ATS has no repository
evidence establishing future profitability or guaranteed daily/monthly loss bounds.

## Shortest coherent remaining sequence

1. Complete a single DEMO execution supervisor end to end: trusted clock/history,
   period ledger, account-wide reconciliation, authority, adapter and reductions.
2. Connect XAU-020 to that supervisor and production replay with exact source/preset
   identities. Validate one unchanged configuration on fresh data; retain S2 as
   separately labeled marginal research and keep unsupported variants disabled.
3. Feed broker events into the existing pure trade-quality component; expose positions,
   Exit Watch and governed operator exits together, avoiding a second order engine.
4. Schedule bounded research only after those evidence contracts are integrated;
   complete physical acceptance and exact-HEAD CI before claiming completion.
