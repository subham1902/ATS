# MetaTrader multi-account foundation

Step 1 is implemented and tested at the software boundary. Physical account/feed
acceptance remains incomplete. Step 3 external execution is proposed future work.
AI proposes; deterministic ATS authorizes.

One package, `market/metatrader/`, owns the platform boundary. AccountSession is a
read-only protocol; the MT5 implementation runs one spawned process per account
because the SDK maintains process-global terminal session state. Distinct terminal
executables and observed data profiles are required. Every worker read verifies
authenticated login/server identity. Bounded IPC failure terminates that worker;
accounts cannot silently share a terminal session. MT4 quote export is implemented,
but authenticated accounts remain NOT_CONFIGURED pending a reliable bridge.

Account records have UUID-based IDs independent of login, display name, platform,
server/broker, credential references, observed mode, connection state, broker symbol,
strategy/risk references and timestamps. The SQLite registry and administrative audit
commit transactionally. Password and login are persisted only as user-bound Windows
DPAPI ciphertext; registry/API/audit store references. Non-Windows vault use fails
closed. Managed agents never receive account credentials or session objects.

`/v1/accounts` provides register/connect, reconnect-only, disconnect and execution
consent commands. Validation responses never echo submitted credentials. Accounts
supports Connect Only and Connect & Enable Execution. DEMO/LIVE/UNKNOWN mode is
observed and displayed; LIVE is not rejected merely for its mode. Enabling currently
records consent and displays EXTERNAL_ROUTING_NOT_IMPLEMENTED. It cannot create an
order or mint authority. Restart, disconnect, reconnect and account-state failure
clear consent. Risk is RISK_PROFILE_REQUIRED and reconciliation BROKER_SNAPSHOT_ONLY
until Step 3 implements their actual requirements.

Each account owns its connector, snapshot, journal and fabric. The Market page
requires explicit data-account selection when several connections exist. Broker
aliases map to XAUUSD; known contradictory base/profit currencies are rejected.
Snapshot account failure affects that account only. Feed health is independent of
authenticated connection health: CONNECTED can coexist with DEGRADED or STALE data.
Neither is authorization.

Journal persistence precedes fabric mutation and fan-out. Duplicates/out-of-order/
stale observations are rejected. Fabric mutations and snapshots are synchronized;
subscriber delivery runs on the subscriber event loop, not polling threads. Standalone
worker shutdown waits for bounded reads before releasing the shared SDK handle.
Journal failure blocks distribution and reports an error. Captured observations are
broker quote proxies, not a complete exchange tape.

Verified locally: SDK import, terminal IPC, authenticated DEMO metadata and XAUUSD
symbol/quotes. The current source epoch is approximately +3 hours relative to
verified UTC and is rejected. Actual simultaneous authenticated terminal sessions
remain unverified. Stubbed DEMO/LIVE/multi-account tests are not physical acceptance.
No terminal orders have been submitted.

Step 3 will introduce separate account/mode-bound external authority, per-account
risk limits and reservations, a deterministic execution router, idempotency,
reconciliation, reduction routes and kill switches. A2_PAPER must remain unable to
authorize any external order. Agents remain proposal-only. See the
[remaining execution plan](ATS_REMAINING_EXECUTION_PLAN.md).
