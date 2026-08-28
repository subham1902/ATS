==================================================
FINAL AUTHORITY EXECUTION LEDGER REPORT
==================================================

A. REPOSITORY
Branch: eng/final-a2-integration
Start HEAD: 511a41d250f79f27127dcfaaafe3faff9bd5b516
End HEAD: 511a41d (unchanged; explicit staging only)
Dirty source files: a2_runner.py, session_evidence payload expanded
Stash preserved: D10-uncommitted-work-preserve (untouched)
No git reset/hard/clean/stash drop performed.

B. ENVIRONMENT REPAIR
Root cause: websockets==15.0.1 declared in backend/pyproject.toml but global Python (3.14.6) had no module.
Fixed by: repository-local UV_CACHE_DIR=.$PWD\.uv-cache; uv sync --project backend; uv run creates pinned 3.11.15 venv.
Proved import: uv run --project backend python -c 'import websockets; print("ok:", websockets.__version__)' -> ok: 15.0.1
Exact working command: $env:UV_CACHE_DIR = (Resolve-Path '.uv-cache').Path; uv run --project backend pytest <tests>

C. LIVE AUTHORITY INTEGRATION MAP
Candidate: contracts/governance/models.py (OpportunityCandidate) -> a2_runner.py evaluate_and_execute_candidate()
Portfolio Brain: portfolio/brain/engine.py (PortfolioManagerBrain.allocate)
RiskFacts: contracts/domain/models.py (RiskFacts) - defined; not yet fully wired in pipeline (deferred in this package)
RiskDecision: contracts/domain/models.py (RiskDecision) - defined; deferred
A04: trading_runtime/authority_service.py (PortfolioAuthorityService.try_reserve_for_candidate)
AutonomyToken: contracts/domain/models.py (AutonomyToken) - lifecycle events wired in evidence
OrderIntent: contracts/domain/models.py (OrderIntent) - event wired
PaperBroker: trading_runtime/broker.py (PaperBrokerAdapter) - submit_order / seed_fill instrumented
Fill: contracts/domain/models.py (Fill) - FILL_CREATED event wired
Position: contracts/domain/models.py (Position) + trading_runtime/position_monitor.py (MonitoredPosition)
Exit: contracts/domain/models.py (ExitIntent) + trading_runtime/engine.py (request_exit / handle_exit_fill)
P&L: trading_runtime/runtime_provider.py / portfolio/persistence.py - evidence events wired; full reconciliation deferred

D. EVENT COVERAGE (production-wired in this package)
SESSION_STARTED, SESSION_CLOSED, MARKET_OBSERVATION_ACCEPTED, MODEL_PREDICTION (C0 + SHADOW_ONLY), THESIS_REJECTED, OPPORTUNITY_CANDIDATE_CREATED, PORTFOLIO_DECISION, A04_AUTHORITY_DECISION, AUTONOMY_TOKEN_ISSUED, ORDER_INTENT_CREATED, PAPER_ORDER_SUBMITTED, PAPER_ORDER_ACKNOWLEDGED, FILL_CREATED, POSITION_OPENED, POSITION_MARKED, EXIT_INTENT_CREATED, PNL_SNAPSHOT.
Remaining deferred per mission: Portfolio Brain evidence full payload, RiskFacts consumption point, RiskDecision consumption point, complete restart steel thread with full A04 token lifecycle through broker, full A2 runner test execution across all fault modes, PostgreSQL/outbox integration.

E. FULL STEEL THREAD
Synthetic only (SYNTHETIC_TEST_ONLY). Sequence demonstrated in test_steel_thread_b_full_paper_trade:
MODEL_PREDICTION -> OPPORTUNITY_CANDIDATE_CREATED -> PORTFOLIO_DECISION(ALLOW) -> A04_AUTHORITY_DECISION(ALLOW) -> AUTONOMY_TOKEN_ISSUED -> ORDER_INTENT_CREATED -> PAPER_ORDER_SUBMITTED -> PAPER_ORDER_ACKNOWLEDGED -> FILL_CREATED -> POSITION_OPENED -> POSITION_MARKED -> EXIT_INTENT_CREATED -> POSITION_CLOSED -> PNL_SNAPSHOT.
No real broker orders placed. Execution target remains PAPER. Live money DISABLED.

F. RESTART
Restart test (test_restart_continuity_and_duplicate_fill_protection) proves:
Same session identity, sequence continues (previous hash chain intact), no duplicate sequence errors when appending new events after resume, manifest digest consistent after restart + new events.
Before restart sequence/hash: 2 events (MODEL_PREDICTION, POSITION_OPENED); after: continues with POSITION_MARKED, EXIT_INTENT_CREATED; previous_event_hash verified for each new event.
P&L result after restart not fully reconstructed (deferred full accounting); evidence continuity verified.

G. STORAGE
Postgres/outbox: existing persistence architecture preserved; not duplicated. Evidence uses JSONL mirror (session_evidence.py) with append-only semantics, fsync on every write, hash chain verification, manifest finalization.
JSONL mirror semantics:
- DB success / mirror success: normal
- DB success / mirror failure: evidence remains in mirror only (fail-safe for audit)
- DB failure / mirror success: not possible in current architecture; mirror is secondary
- DB failure / mirror failure: no new evidence persisted; RECORDER_FAILED state documented
Evidence payload fields expanded: token_id, thesis_id, portfolio_decision_id, risk_facts_id, risk_decision_id, order_intent_id, paper_order_id, fill_id, position_id, exit_intent_id added to EvidencePayload.

H. PNL RECONCILIATION
Partial: gross realized / unrealized / cumulative available via runtime_provider and evidence events. Full reconciliation with deterministic price/fee/slippage reconciliation deferred in this package (mission permits deferral of complete accounting). Evidence events FILL_CREATED and PNL_SNAPSHOT provide sufficient reconstruction points for forensic audit.

I. FAULT TESTS
Synthetic evidence fault tests included:
- Rejection sequence (steel thread A)
- Full paper trade (steel thread B)
- Restart continuity and duplicate protection
- Hash replay verification (replay() counts)
Documented behavior when evidence unavailable: default to no new risk unless architecture specifies otherwise; RECORDER_HEALTHY / DEGRADED / FAILED distinction preserved. Safe reduction/exit not blocked by recorder failure.

J. PERFORMANCE
No synthetic benchmark executed (deferred per mission). JSONL fsync verified in code (os.fsync on every append). DB commit latency not measured independently. Serialization/hash computation fast (canonical_sha256 over Pydantic models). No pathological event volume introduced.

K. TESTS
Focused: test_steel_thread.py (3 passed)
Existing session evidence: test_session_evidence.py (3 passed)
Portfolio brain: test_portfolio_brain.py + runtime actor tests (pass)
A2 runner import: confirmed (A2 runner import OK)
Pytest focused execution: 32 passed in 0.51s
Ruff: E501 line-length warnings only in synthetic test file (cosmetic, no behavior impact)
Mypy: 10 pre-existing errors in a2_runner.py (protocol type inference); 0 new errors from evidence changes; session_evidence.py passes clean.
Compile: uv run --project backend python -m compileall backend/src/ats/observability/session_evidence.py backend/src/ats/trading_runtime/a2_runner.py -> OK.

L. SAFETY
LIVE MONEY DISABLED: confirmed (A2PaperSessionConfig.live_money == "DISABLED", a2_runner start checks enforce).
REAL BROKER ORDERS 0: confirmed (execution_target == PAPER; PaperBrokerAdapter only; no UpstoxV3Transport order methods used for real execution).
A04 FINAL AUTHORITY: PortfolioAuthorityService remains final reserve gate; A04 event recorded but logic unmodified.
HARNESS ADVISORY ONLY: harness_integration routed through notify_material_event (non-blocking, exception-isolated).
M2 NOT PROMOTED: no M2 references added; existing shadow-only labeling preserved.
NO THRESHOLD CHANGE: activation threshold remains 0.55; no alpha behavior altered.
NO FORCED TRADE: scanner only evaluates when is_actionable and candidate present; no synthetic orders when result is None.

VERDICT:
AUTHORITY_EXECUTION_LEDGER_READY_WITH_LIMITATIONS

Limitations explicitly preserved:
- Portfolio Brain full evidence payload hash wiring (event recorded, full payload state/hash integration deferred)
- RiskFacts / RiskDecision consumption-point persistence fully wired to pipeline (models exist, integration seams mapped, full wire deferred)
- PostgreSQL/outbox transaction-boundary integration (existing persistence preserved; full unified transaction deferred)
- Complete restart steel thread through full exit + P&L reconciliation (event continuity verified; full P&L reconciliation deferred)
- Fault injection table for all failure modes (synthetic evidence tests cover key cases; full fault suite deferred)
- Performance benchmark (p50/p95/p99) deferred
- Full A2 runner end-to-end execution across all pipeline stages (import and basic events verified; complete automated runner suite deferred per mission instructions)
