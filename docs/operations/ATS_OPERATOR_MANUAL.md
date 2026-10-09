# ATS operator manual

Verified product baseline: October 9, 2026. This manual describes the running
XAUUSD laboratory, not the full proposed external execution program.

## What ATS currently does

ATS observes XAUUSD broker quotes through MetaTrader, keeps research strategy
lineages and dataset provenance, manages proposal-only research agents, and
provides deterministic paper-runtime status. AI proposes; deterministic ATS
authorizes. A connected terminal, green Algo Trading button, positive backtest,
or recorded execution consent does not create execution authority.

| Capability | Current availability |
| --- | --- |
| MT5 authenticated account monitoring | Available; one physical DEMO account checked |
| Broker alias mapped to canonical XAUUSD | Available |
| Bid, ask, spread, freshness, connection health | Available from actual observations |
| Multiple account isolation | Implemented and mock-tested; two physical terminals not accepted |
| MT4 authenticated accounts | NOT_CONFIGURED; genuine account bridge required |
| Live chart, quote bars, Wilder ATR, RSI | Available; warmup and history coverage matter |
| Broker tick footprint proxy | Available; no claim of exchange order flow |
| CSV/Parquet quality assessment and versioning | Available through local-path import |
| Immutable XAU strategy IDs and versions | Available; 20 lineages, all RESEARCH |
| Managed agent configuration and research templates | Available; templates are not active agents |
| Bounded quote backtests | Available for five supported recipes and eligible bid/ask ticks |
| Scheduled continuous research | Not installed; manual dispatch only |
| GoldTriple S1/S2/S3 experiments | Repository research scripts and reports; not wired into production jobs |
| Calibrated empirical probability | Unavailable; UNKNOWN |
| Autonomous paper-forward strategy session | Not commissioned; validation/A04 gates remain |
| Demo/live external execution | Development components exist but are not routed or commissioned |
| Live Positions UI, manual broker exit, Exit Watch alerts | Not integrated |
| Trade-quality calculations | Tested pure components; no durable live-trade ingestion yet |

## Start and status

Open PowerShell and run:

```powershell
ats-start
ats-status
```

The installed command wrapper resolves `ATS_RELEASE_ROOT` to
`D:\Projects\ATS\ats`. Current default addresses:

- Control center: `http://127.0.0.1:3001/`.
- Current backend: `http://127.0.0.1:8100/`.
- API requests from the browser use the frontend `/v1/...` BFF path.
- Port 3000 is reserved and was not modified.

`ats-start` may reuse an existing current backend. It now checks the Accounts API
both directly and through the frontend before declaring application READY. An
unavailable market need not prevent offline research startup.

For explicit engineering ports:

```powershell
pwsh -File D:\Projects\ATS\ats\scripts\ats-operator.ps1 -Action Start -FrontendPort 3001 -BackendPort 8100
```

Frontend proxy destinations are selected at **build time**. If the backend origin
changes, stop only the verified ATS frontend and rebuild with the pinned runtime:

```powershell
$env:Path = 'D:\Projects\ATS\toolchains\node-v24.19.0-win-x64;' + $env:Path
$env:ATS_BACKEND_ORIGIN = 'http://127.0.0.1:8100'
pnpm --filter @ats/control-center build
ats-start
```

Run build commands from `D:\Projects\ATS\ats`. Avoid building while another
ATS frontend process is modifying the same `.next` directory. Do not kill a
listener solely because it uses an expected port; verify ownership first.

`ats-restart` is disruptive to the ATS connection workers. It is not a clock
renewal or execution commissioning command. Reconnect and recheck Accounts after
a backend restart. Consent is cleared on restart/disconnect/reconnect.

## Daily operator workflow

1. Run `ats-start`, then open **Accounts**.
2. Verify the expected internal account ID, server, DEMO/LIVE mode and XAUUSD alias.
3. Check connection state separately from market health. CONNECTED with DEGRADED
   means authentication works but the data is not eligible as a fresh live feed.
4. Inspect balance, equity, margin, positions and orders. N/A means unknown.
5. Open **Market**, choose the correct data account, and inspect freshness and
   provenance. With several connections, choose an account explicitly.
6. Use **Strategies**, **Research**, **Datasets** and **Agents** for research.
7. Check **Paper Trading** and **System** for paper-runtime gates; do not equate
   market connectivity with a commissioned trading session.

## Accounts

### Reuse an authenticated MT5 terminal

Choose **Use authenticated MT5 session**. Enter a display name, terminal
executable and broker symbol. The default executable is
`C:\Program Files\MetaTrader 5\terminal64.exe`. Submit **Connect Only**.

This adopts the terminal's existing authenticated session and credential cache.
It does not enable execution. Use **Reconnect Only** for an existing record rather
than repeatedly creating accounts for the same terminal.

### Register an account with credentials

Choose **+ Connect Account**, then supply platform, display name, broker/server,
login, password, terminal path and broker XAUUSD alias. Password is a masked input
and is cleared after submission. ATS stores user-bound Windows DPAPI encrypted
credentials behind references; password/login are not returned by the account API.

The form has two distinct choices:

- **Connect Only**: monitor the account.
- **Connect & Enable Execution**: connect and record consent. In this build,
  external routing remains unavailable; this choice cannot issue an order.

**Enable Execution Consent** on an account card also records consent only.
The visible gate is `EXTERNAL_ROUTING_NOT_IMPLEMENTED`. Do not interpret that
button as a working autonomous trading switch.

**Disconnect** ends ATS monitoring for the account and clears consent. It does
not close broker positions or stop the MetaTrader application. **Reconnect Only**
attempts a fresh isolated account connection and keeps consent disabled.

Different concurrently monitored MT5 accounts require distinct terminal
installations/data profiles. Sharing the same underlying profile is rejected.
LIVE/DEMO is observed account metadata, not the authorization decision. MT4
registration can be saved, but its account transport remains NOT_CONFIGURED.

## Market workstation

The page displays source platform, broker symbol, canonical XAUUSD, bid/ask/spread,
UTC observation time, session research label, volume provenance, chart and proxy
footprint. Available chart intervals: 1m, 5m, 15m, 1h and 1d.

The chart initially contains only quotes collected by the current fabric. It is
not automatically a downloaded multi-year MetaTrader chart. Bars may be partial;
unobserved intervals are not fabricated. Wilder ATR and RSI remain N/A until
sufficient observed bars exist.

Broker quote levels, tick counts and inferred up/down movements can support a
**BROKER_TICK_PROXY**. They do not establish global traded XAUUSD volume, true
buyer/seller aggressor flow or centralized exchange depth. Missing tick/real
volume remains N/A/UNKNOWN. Do not interpret absent fields as zero activity.

### Clock and freshness

The checked broker publishes server-wall epochs approximately three hours ahead
of independent UTC. A short-lived, server-bound clock evidence file permits live
normalization. It expires after 900 seconds in the acceptance configuration.
On expiry, `CLOCK_EVIDENCE_EXPIRED` and DEGRADED are expected fail-closed states.

Automatic independent renewal is not implemented. A new native clock probe must
be corroborated against fresh independent UTC, validated through
`make_clock_evidence`, and loaded by reconnecting. Do not edit an old capture time,
extend its expiry, or reuse its offset as proof of historical/DST timestamps.
Historical strategy proposals still require a separate verified clock profile.

## Strategies

Open **Strategies** to see exact `XAU-###` ID/version, lifecycle, direction/horizon
when recorded, datasets and backtest/walk-forward/holdout/paper evidence references.
UNKNOWN and NOT_RUN are deliberate, not hidden positive results.

The current 20 records are all RESEARCH. Source workspaces live under
`strategies/XAU-###/`, with an index in `strategies/STRATEGY_INDEX.yaml`. A lineage
number is never reused. New research variants require a new version and evidence;
editing a preset or copying an old result does not promote it.

There is no production UI for adding/removing executable MetaTrader strategies,
assigning them to broker accounts, or selecting external routing destinations.
Changes to native Experts are engineering deployments, not an execution grant.

XAU-018/019/020 identify GoldTriple S1/S2/S3 variants. The stronger selected $1,000
S3 research condition is LONG, H4-close retest, completed M5 structure,
Tuesday–Thursday 12:00–17:00 UTC, 1.5% planned risk, 2R target, no protection and
120-minute maximum hold. S2 is marginal. $500/$750, S1 and combined-portfolio
conditions remain unqualified. See the repository research report for exact
costs, hashes, sample sizes and reused-holdout limitations.

The native `ATSSmallAccountS3_1000` Expert currently **observes only**. Its
`execution_authority` is NONE and its signal reports CLOCK_PROFILE_REQUIRED.
MetaTrader Algo Trading being enabled does not change this boundary.

## Datasets

Open **Datasets**, enter the absolute local CSV/Parquet path, source/broker
provenance, broker alias and source timezone. Select timeframe and price basis
truthfully, then choose **Import and assess quality**.

Use UTC only when the source really is UTC. Do not label an M1 bid OHLC file as
tick BID_ASK data. The paired GoldTriple source files are not automatically merged
by this form into a production research dataset.

Each import records content identity, normalization version, source/schema,
row counts, time range and quality findings. Ordering, duplicates, malformed
prices/volumes, symbol consistency, gaps and missing fields affect eligibility.
Unknown provenance cannot silently become validated evidence. Use the dataset ID
and normalized hash in every research run, not just its filename.

The acceptance session began with zero imported production datasets. Do not
confuse standalone research files with entries in this registry.

## Agents and bounded backtests

**Agents** opens `/agents/managed`; `/agents` is an alias of the same research
surface. The ten laboratory templates describe research, backtest, validation,
signal/regime/SL-TP analysis, entry quality, Exit Watch, forensics and librarian
roles. A TEMPLATE is not a configured or running agent.

Choose **+ Add Agent**. The wizard covers identity, provider/model,
responsibilities, data access, research scope, capabilities, runtime limits and
review. Credentials are environment-variable references, never pasted secrets.
New agents start disabled. The detail page supports configuration/version
history, enable/disable, duplication and archive; archive preserves prior records.
Configuration does not imply that an arbitrary external LLM provider is connected.

For a bounded quote job:

1. Import eligible, observed bid/ask **tick** data.
2. Create and enable an agent with RUN_BACKTEST and XAUUSD_DATASETS plus
   XAUUSD_STRATEGIES scopes. Its current config version must match the job.
3. In **Run quote research**, choose that agent and exact dataset.
4. Choose supported strategy v1: XAU-003 Donchian, XAU-013 time-series momentum,
   XAU-016 z-score, XAU-009 regime gate, or XAU-001 ATR expansion.
5. Supply positive tick size/quantity, explicit commission/slippage/latency,
   quote-bar interval and finite timeout within the agent budget.
6. Select **Run Backtest Agent**. Inspect QUEUED/RUNNING/COMPLETED/FAILED state and
   versioned evidence; cancel a queued/running job when required.

Quantity is **price units**, not automatically MetaTrader lots. Commission is
per unit per side; slippage is in price units; latency is milliseconds. The method
is CAUSAL-QUOTE-V1 with QUOTE-COST-V1. It fills on subsequent observed quotes,
uses explicit costs, and does not claim depth/queue realism. It disallows
overnight/weekend holding under its documented research policy.

The form is disabled when agent/dataset prerequisites are absent. Daily/weekly
cadence is not an installed scheduler. GoldTriple recipes, robust validation,
calibration and promotion are not integrated into this worker. Agents cannot
hold broker credentials, import execution adapters or mint authority.

## Paper Trading, System and loss limits

**Paper Trading** exposes runtime status and gate state. Its paper capital is
separate from the MetaTrader account balance; the checked default paper runtime
reported 100,000 capital while the broker account had $1,000. No active validated
paper-forward session was accepted. **System** shows deterministic control-plane
status; READY application health can coexist with DEGRADED trading state.

The requested loss policy is 3% daily / 8% calendar-month **net realized P&L**,
relative to start-of-period equity. At an unchanged $1,000 baseline, those are
$30/$80; at $500, $15/$40. Profits offset losses. Those arithmetic examples are
not verified runtime budgets: period baselines, full deals, risk reservations,
reconciliation and exits still need commissioning. No guaranteed cap is claimed.

## Troubleshooting

| Symptom | Check/action |
| --- | --- |
| ATS READY but Accounts API missing | Verify current 8100 backend; do not reuse the legacy 8000 paper experiment |
| Frontend Accounts returns 404 | Rebuild with correct ATS_BACKEND_ORIGIN; Next rewrites are build-time |
| CONNECTED plus DEGRADED | Read market reason; authentication and quote eligibility are separate |
| CLOCK_EVIDENCE_EXPIRED | Fresh independent attestation and reconnect; never extend old evidence |
| MT5 DISCONNECTED | Verify terminal/server/profile, then Reconnect Only |
| MARKET_API_UNAVAILABLE with multiple accounts | Explicitly select a connected data account |
| Empty chart / ATR N/A | Wait for observed bars; history is not fabricated or automatically backfilled |
| No backtest agents/datasets | Configure eligible prerequisites; templates alone do not run |
| RESEARCH / UNKNOWN probability | Obtain versioned validation evidence; do not promote from LLM confidence |
| Execution consent enabled but no orders | Routing is uncommissioned; consent alone grants no authority |

## Evidence and remaining integration

The dated live acceptance report accompanies this manual. Raw screenshots,
browser/API checks and logs are under `reports/live-acceptance-2026-10-09/`.
The separate small-account implementation report records research methodology.

The shortest next engineering path is one isolated DEMO execution supervisor,
trusted clocks and genuine period ledger, account-wide reconciliation and
governed reductions, unchanged S3 forward acceptance, then broker-event
trade-quality/Exit Watch integration. Real-money execution and profitability
are not established by this operator acceptance.
