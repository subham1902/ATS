# ATS system report — October 8, 2026

## Delivery status

**The requested Steps 2–4 are not complete.** This checkpoint implements and tests
the Strategy OS foundation and reports the remaining acceptance gaps explicitly.
Step 2 is partial. Steps 3 and 4 have not been implemented. This document must not
be used as an external-execution acceptance certificate.

The inspected starting revision was `67f0ae8251f26ba1026b7f5eb81378dbe7a45677`
on `main` in `D:\Projects\ATS\ats`. The starting worktree was clean. No completed
specialization or earlier tournament experiment was repeated. The outer
`D:\Projects\ATS` workspace was not staged.

## Current architecture and authority

ATS is a focused XAUUSD research laboratory with MetaTrader broker observations,
immutable dataset ingestion, research definitions, managed proposal-only agents
and deterministic internal paper execution. AI proposes; deterministic ATS
authorizes. Production currently remains paper-only.

The trusted contract/kernel/portfolio/persistence/authority implementations were
not rewritten by this checkpoint. `A2_PAPER` remains the execution scope. There
are no external demo/live scopes, MetaTrader execution adapter, external router
or account risk-reservation ledger. Account connection consent does not mint
financial authority. No external broker orders were sent by this work.

The console still rejects `LIVE_MONEY` values other than FALSE. This is a current
implementation fact, not a permanent rule against LIVE accounts. The newer user
program allows governed demo and live execution; that extension remains future
work. Removing this guard before implementing external authority would be wrong.

## MetaTrader and accounts

Step 1 already supplies a durable account registry, UUID internal identities,
DEMO/LIVE/UNKNOWN mode observation, user-bound Windows DPAPI credential storage,
one bounded spawned MT5 worker per account, sanitized snapshots and per-account
market fabrics/journals. Credentials are references in ordinary account state;
passwords are not served, logged or supplied to agents.

The Accounts UI offers Connect Only and Connect & Enable Execution. The latter
currently records consent; the UI/API explicitly report external routing as
unimplemented. Consent is revoked on restart, reconnect, disconnect or account
failure. Multiple connections require separate terminal installations and
observed profiles. Failure isolation is tested with stubs; actual concurrent
authenticated terminals remain unverified.

MT5 uses the pinned official SDK through the existing MetaTrader package. MT4
has a quote-snapshot boundary and read-only EA bridge; authenticated accounts and
execution remain NOT_CONFIGURED. No reliable MT4 execution transport is claimed.

The prior sanitized local probe established SDK import, terminal IPC and an
authenticated demo session. Its source tick epoch was approximately three hours
ahead of receive time and correctly failed with FUTURE_SOURCE_TIMESTAMP. This
checkpoint did not re-probe the terminal or guess a timezone correction. Fresh
admitted observations and real multi-terminal acceptance remain open.

## Market data and provenance

Internal identity is always XAUUSD. Per-account broker mapping accepts forms such
as XAUUSDm, XAUUSD.a or GOLD without creating another ATS instrument. Metadata
comes from the broker rather than global hardcoded precision or contract sizes.
The canonical observation model is shared by ingestion and live delivery.
Observations are journaled before fabric mutation/fanout. Receive and source
timestamps are distinct; freshness and connection failures are explicit.

MT5 retail data is broker/OTC data. Footprints are BROKER_TICK_PROXY, not a global
exchange tape. Quotes, available spread, price levels and tick counts can be
observed. Aggressor information, where inferred, must disclose its method.
Global volume, depth, bid/ask quantity and true aggressor cannot be assumed.
BROKER_VOLUME, TICK_VOLUME, REAL_VOLUME and UNKNOWN remain separate; missing
values remain null/N/A. Wilder ATR is the canonical chart/research definition.

## Historical datasets and research

CSV/Parquet ingestion assigns immutable content/provenance identities and
records UTC normalization version, broker/canonical symbol, timezone, schema,
row counts/range, hashes, import time and quality findings. Replay validates the
normalized content digest. Corrupt, unordered or duplicate rows make the dataset
NOT_ELIGIBLE; gap findings are research warnings. Cost assumptions are explicit
and versioned. Test data is isolated from product data roots.

No user-provided two-year dataset or clean-room strategy validation has been
established by this checkpoint. Existing research/backtest infrastructure
survives, but the new queue is not connected to it. An earlier backtest engine's
generic feature fallback must be rejected or corrected before the new worker
can treat unknown features as research evidence; unavailable features must never
silently become close prices. Strategy-to-executable-recipe and normalized
dataset-to-replay bindings still need an explicit adapter.

## Strategies

The new frozen lineage mapping is:

| ID | Definition | Current status |
| --- | --- | --- |
| XAU-001 | atr_expansion | RESEARCH |
| XAU-002 | close_location | RESEARCH |
| XAU-003 | donchian | RESEARCH |
| XAU-004 | fade_extreme | RESEARCH |
| XAU-005 | gap_fill | RESEARCH |
| XAU-006 | hurst_regime | RESEARCH |
| XAU-007 | moment_skew | RESEARCH |
| XAU-008 | oi_volume | RESEARCH |
| XAU-009 | regime_gate | RESEARCH |
| XAU-010 | session_seasonality | RESEARCH |
| XAU-011 | squeeze | RESEARCH |
| XAU-012 | tick_velocity | RESEARCH |
| XAU-013 | tsmom | RESEARCH |
| XAU-014 | volume_divergence | RESEARCH |
| XAU-015 | vwap_trend | RESEARCH |
| XAU-016 | zscore | RESEARCH |
| XAU-017 | S5_ORB_XAUUSD | RESEARCH / design only |

The new typed records include complete strategy metadata and separate result
categories. Unreviewed direction/horizon/rules remain UNKNOWN rather than inferred
from names. No datasets, results or calibration were imported into the new
lineages. Volume/OI-dependent definitions must abstain when their required
observations are unavailable. S5 retains its unresolved design decisions.

Version history is append-only with digest checks and optimistic concurrency.
Retirement does not release an ID. Public registry lookups are exact. Existing
internal strategy-function signal IDs have not all been migrated to canonical
lineage/version bindings. Promotion and evidence mutation deliberately fail
closed until an independent evidence verifier is wired.

## Agents and continuous research

Managed-agent boundaries and XAUUSD scopes remain intact. Ten research templates
are available in Agents, including Exit Watch and Forensics, but they are
templates rather than active continuous workers. They have no financial
authority. The persistent queue primitive binds job provenance, bounds,
idempotency, a single claim and result hashes. Cadence is recorded intent only.
No scheduler, supervised backtest worker or automatic strategy evidence update
is implemented. The typed signal schema separates model confidence from
empirical probability; the latter remains UNKNOWN.

## Frontend and operator behavior

Current navigation remains Dashboard, Market, Research, Strategies, Agents,
Accounts, Paper Trading, Datasets and System. Strategies now reads canonical
lineages, displays version/definition and UNKNOWN direction/horizon, and shows
NOT_RUN evidence. Agents displays purpose, status and allowed capabilities for
the research templates. Account secrets remain absent from these surfaces.

There is no external Positions workstation, live autonomous execution indicator,
strategy/account routing selector, account risk-profile editor or deterministic
manual-exit control. A template called Exit Watch must not be interpreted as
actual position monitoring.

## Steps 3 and 4: explicitly not implemented

External execution still needs mode-bound single-use authority, finite per-account
risk limits, serialized durable reservations, operator account/strategy routing,
the approved MT5 order adapter, global/account/strategy new-risk kill switches,
reconciliation, timeout/UNKNOWN query handling and child execution evidence.
`A2_PAPER` must remain unusable externally. Demo authority must not replay on LIVE.
LIVE must be allowed when explicit consent and all deterministic requirements pass.

Trade intelligence still needs executable-side quote observations, immutable
trade paths, MFE/MAE/current/peak R, versioned quality labels, giveback/capture,
entry/exit diagnosis, Exit Watch advisories and operator manual reductions through
deterministic authorization. Hypothetical continuation must preserve original
rules and be UNKNOWN on gaps/ambiguous fills; it cannot rewrite the original trade.

## Validation and completion ledger

See `ATS_STEPS_2_4_SYSTEM_REPORT.md` for exact local results, final source revision
and remote CI run. New focused tests cover identities, concurrent allocation,
history/conflicts, corruption, fail-closed evidence, queue claims/idempotency/
interruption, probability/geometry honesty, templates, projections, SQLite
cleanup and API isolation. Existing source contracts still prohibit SDK order
calls in the market package and prevent agents importing brokers or credentials.

Tests passing for storage/schema foundations do not prove continuous research,
external execution or trade intelligence. Profitability and strategy edge remain
unestablished. No acceptance gate is weakened to manufacture completion.
