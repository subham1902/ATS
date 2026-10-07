# XAUUSD MetaTrader specialization

Status: software foundation implemented; physical feed acceptance remains blocked.
Current product state takes precedence over historical implementation-log entries.

Before specialization, ATS included multiple-market experiments, Upstox feeds,
Indian derivatives, imported tournaments and derived performance state. Those
active implementations, credentials/configuration, routes, data and rankings were
removed after a classified inventory and local recovery snapshot. Recovery exists
in Git history and an external ZIP, not in a dormant provider package.

The product now uses canonical XAUUSD, broker-specific aliases and MetaTrader
market adapters. MT5 uses the pinned official SDK; MT4 has a read-only snapshot
bridge, with authenticated account transport NOT_CONFIGURED. Missing values stay
unknown, and data-source selection separates accounts rather than blending feeds.

```text
MT5 account worker / MT4 quote bridge / versioned dataset replay
    -> MarketObservation -> journal -> MarketDataFabric -> features/research/chart
    -> proposals -> deterministic authorization -> portfolio authority -> paper execution
```

The pure kernel, frozen contracts, deterministic hashing, single-use paper tokens,
strictest-wins constraints, serialized portfolio authority and fail-closed UNKNOWN
semantics are retained. Agent capabilities remain research/proposal only. Current
authority is A2_PAPER; no terminal order functions are exposed. External execution
is a separate Step 3 extension authorized by the latest user program, not implemented
by this specialization or the account connection consent.

The clean-room catalog retains generic definitions as RESEARCH_ONLY, with empty
datasets/results/calibration/promotion fields. S5 is XAUUSD-native DESIGN /
RESEARCH_ONLY with all fifteen review topics preserved. Old scores, optimization,
paper histories, trained artifacts and unknown-provenance state supply no authority.
The XAUUSD-specialized ATS currently has no repository evidence establishing profitability.

CSV and Parquet imports produce content/provenance-derived dataset IDs, preserved
source files, normalized hashes and quality manifests. Invalid, duplicate or
unordered rows make datasets NOT_ELIGIBLE. Gap findings require research review;
RESEARCH_ONLY is never execution eligibility. Replay checks normalized content.
Deduplication uses temporary disk storage to bound memory for large tick datasets.

Prices, quote spread, broker volume, tick volume and real volume remain separate.
BROKER_TICK_PROXY footprints count sampled ticks by observed metadata price grid;
direction is inferred from quote movement. They cannot establish global exchange
flow, depth, bid/ask size or true aggressor volume. Unsupported quantities show N/A.
Polling does not claim complete tick capture.

All internal timestamps are UTC. Asia, London, New York, overlap, rollover and
estimated weekend labels are research classifications, not authoritative broker
opening hours. Future ticks and unclosed historical bars fail admission. The local
terminal currently reports ticks approximately three hours ahead of UTC; ATS applies
no guessed correction. The chart uses Wilder ATR: first true range high-low, initial
period SMA, then Wilder recurrence, with null warmup.

Primary routes: Dashboard, Market, Research, Strategies, Agents, Accounts, Paper
Trading, Datasets and System. Managed-agent list/detail routes remain useful
subroutes. Legacy ledger, broker, exchange, imported-strategy, optimization and
experimental authority pages were deleted. The chart is decomposed into chart,
candle store, indicators, footprint and MetaTrader feed components.

See [account foundation](METATRADER_MULTI_ACCOUNT_EXECUTION.md) and
[remaining execution plan](ATS_REMAINING_EXECUTION_PLAN.md). Future work includes
terminal timestamp verification, actual concurrent terminal acceptance, the user's
two-year dataset, clean-room research, external account-bound authority and trade
quality intelligence. No backtest result or strategy edge is asserted.
