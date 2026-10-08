# Agent research system

Status: partial Step 2 implementation, October 8, 2026.

Existing managed agents retain versioned configuration, capability allowlists,
XAUUSD-only scopes, concurrency limits and proposal-only operation.
`agents/research_templates.py` adds ten reusable purpose/capability descriptions:
Strategy Research, Backtest, Validation, Signal Analyst, Regime, SL/TP Analyst,
Entry Quality, Exit Watch, Trade Forensics and Strategy Librarian. The Agents
page presents them as TEMPLATE, not as running agents. They do not create jobs,
install schedules or receive account credentials.

`strategies/research_jobs.py` provides a durable SQLite queue primitive. Requests
bind agent/config version, canonical strategy/version, dataset ID/hash,
method/cost version, parameters, row budget, timeout and cadence intent. Submission
deduplicates by idempotency key and rejects conflicting payloads. One atomic
claim can run at a time. Claim nonces prevent stale workers replacing results.
Completion stores result JSON and a verified SHA-256 digest; restart recovery
explicitly marks interrupted work FAILED. Recovery requires exclusive worker
ownership. No automatic resume or retry is implemented.

This queue is **not an operational backtest service**. It is not yet connected to
the research engine, dataset verification or managed-agent run ledger. The typed
budget and cadence fields record bounds and scheduling intent; no scheduler or
process timeout enforcement exists yet. The internal `submit`/`finish` methods
are storage primitives, not an agent tool or an evidence eligibility verifier.
There is no public job-submission or promotion API. Read APIs expose
`worker_status=NOT_IMPLEMENTED` and only the latest 100 jobs.

`strategies/signal_analysis.py` defines a strict proposal schema for lineage,
version, aware timestamp, direction/horizon/regime, entry zone/invalidation,
SL/TP/trailing, reward/risk, duration, supporting/contradicting factors and
freshness. It rejects malformed geometry, nonfinite values and incomplete/stale
proposals. Model confidence is separate from empirical probability. Without an
independent calibration verifier the latter is structurally null/UNKNOWN; even a
submitted numeric probability is rejected. No live signal-producing worker is
connected to this schema yet.

Remaining integration is one bounded process worker over the existing research
engine, exact dataset and executable-recipe verification, managed-agent run
binding, cadence dispatch, resource/timeout enforcement, validated result
association and an operator submission/result view. No extra agent execution
architecture is needed. Agents cannot promote strategies, mint authority,
select execution accounts, retrieve broker credentials or invoke broker orders.
