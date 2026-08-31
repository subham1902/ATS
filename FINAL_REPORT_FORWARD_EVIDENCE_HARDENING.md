# Final Report — Forward Evidence Hardening

Date: 2026-08-31  
Branch: `eng/final-a2-integration`  
Starting documentation HEAD: `f078760d401d28648b8629bea5ac7fec072f4818`  
Starting trading source: `b642a8d`  
Valid independent forward sessions: **1**

## Executive verdict

**READY_FOR_FORWARD_SESSION_03_WITH_LIMITATIONS**

The Session-02 evidence-completeness blocker is closed in code and deterministic tests. Future sessions now persist Stage‑1 handoff, Stage‑2 connection/subscription/freshness samples, signed unclamped clocks, market/feature/production/shadow/option facts, same-state links, paper execution facts, counterfactual provenance, recorder health, a hash-chain manifest, and a post-shutdown validity classification.

The remaining limitation is live acceptance: the bounded connected check at 2026-08-31T06:29:58Z passed provider authentication, BOD references, V3 transport capability, the dynamic 22-key plan, PaperBroker, recorder, forensics, A04, and clean reconciliation, but correctly failed `MARKET_OPEN_DATA_NOT_READY` because no running feed existed to produce fresh per-instrument observations. No launch followed and nothing was counted as Session 03.

## A. Starting repository truth

- Worktree and branch matched the charter.
- Worktree was clean.
- D10 stash was preserved as `stash@{0}: D10-uncommitted-work-preserve`.
- Session 02 remained `SESSION_02_INVALID_FOR_FORWARD_RESEARCH`.
- Session 02 remained same-day supplemental evidence and did not increment the count.

## B–C. Blocker and evidence gaps

The accepted four-event Session-02 ledger could not prove Stage 2, clocks, predictions, option economics, funnel attribution, same-state telemetry, or M2 settlement. Its freshness statistics and M2 −₹1,349.30 attribution remain withdrawn. Portfolio, Risk, and A04 remain `NOT_REACHED` for Session 02; observability-only C0 values remain non-authoritative.

## D–E. Stage 2 and clock design

Stage 2 now records transport state, expected/actual subscriptions, keys, per-key samples, source/receipt/availability/evaluation times, signed raw provider age, authority age, skew, 2,000 ms threshold, freshness, and decision. Ready evidence requires V3 LIVE, complete subscriptions, every required key fresh, and valid four-clock order.

Negative age is never clamped. `RECEIPT_CLOCK_AUTHORITY_V1` identifies the normalization authority while retaining raw provider time/skew. Unsafe event/source/ingest/availability/decision ordering is invalid. Tests cover 1999/2000/2001 ms, future clocks, and invalid clock evidence.

## F–G. Production funnel and authority separation

Each cycle persists feature validity or its canonical failure. Valid features permit a `PRODUCTION_PREDICTION` with state ID, ROC_3, p_up, threshold, thesis result and reason. Invalid prerequisites instead persist C0/thesis/candidate/Portfolio/Risk/A04 as `NOT_REACHED` with the upstream reason.

Continuous dashboard C0 is explicitly `NON_AUTHORITATIVE_OBSERVABILITY` and cannot enter production counts. C0 formula and threshold were not changed.

Volume was audited. Index volume is never fabricated. The current production composition intentionally requires a good full bar, so provider-absent index volume yields `VOLUME_UNAVAILABLE` before authoritative C0 even though isolated C0 math uses ROC_3. This conservative behavior was documented, not changed to manufacture activity.

## H–J. Same-state, option and counterfactual evidence

Every eligible evaluation writes a shared record joining market-state ID, decision time, underlying, regime, authoritative C0 status, Alpha V4, M2/R10-X championship output, option availability, and data quality.

Option evidence persists contract identity, expiry, strike/type, dynamic lot/tick, bid/ask/depth, volume/OI/IV/Greeks when supplied, timestamps, signed age and freshness. Missing fields remain missing.

Counterfactual entries now require and persist contemporaneous contract/quote, lot, decision time, observed bid/ask, entry rule, slippage, cost version, fixed exit policy and provenance. Settlement persists the observed exit bid, exit rule, costs, gross/net result, timestamps, and `FORWARD_VALID_COUNTERFACTUAL_PNL`. An unmatched entry deterministically produces `INVALID_COUNTERFACTUAL_EVIDENCE`; monetary attribution cannot be inferred from directional telemetry.

## K–L. Distinct-day enforcement and classifier

The finalizer scans prior valid manifests by trading date. A repeated date classifies `SUPPLEMENTAL_ONLY` and cannot increment the championship. Validity precedence is hash chain, recorder health, Stage 2, clocks, production/same-state reconstruction, distinct date, counterfactual completeness, then declared option limitations.

The machine-readable artifact is `FORWARD_EVIDENCE_MANIFEST.json`. Its classifications and exact rules are defined in `FORWARD_SESSION_VALIDITY_SPEC.md`.

## M–N. Reconstruction and regression qualification

- Full unit suite: **1427 passed, 2 skipped, 0 failed**.
- Skips: two existing/declarative skips surfaced by the suite; none hidden.
- Focused final clock/feed/forensics rerun: **16 passed**.
- Script/reconciliation tests: **12 passed**.
- Mypy: **PASS, 306 source files**.
- Ruff changed files: **PASS**.
- Python compilation (`backend/src`, unit tests): **PASS**.
- Frontend: not touched; rebuild not required by the charter.
- Warnings: 20 FastAPI `on_event` deprecation warnings; non-failing and unrelated to evidence correctness.

Reconstruction tests destroy the recorder object and reload only persisted JSONL/manifest evidence. They cover zero trade, complete paper-trade stage records, same-day supplemental classification, missing Stage 2, future/invalid clocks, recorder failure, valid and incomplete counterfactual settlement, authoritative/observability separation, and hash verification.

## O. Safety invariants

Unchanged: live money disabled; PaperBroker only; real broker orders zero; capital ₹100,000; C0 production at 0.55; Alpha V4/M1–M9/M2/R10-X shadow only; Portfolio, Risk, A04 and autonomy policy source unchanged. No model, threshold, cost assumption, capital, or promotion change was made.

Mandatory recorder I/O is flush+fsync per event and reports latency, failures, drops and sequence/hash state. A recorder write/fsync/drop fault makes the Stage‑2 execution invariant fail closed for subsequent new risk.

## P. Implementation commits

- `dc86c9e` — evidence: persist Stage‑2, clock and production truth
- `e5a684a` — evidence: persist counterfactual settlement provenance
- `7faf5f1` — forensics: qualify forward-session reconstruction
- `7b23bbb` — evidence: enforce complete four-clock ordering

## Q–R. Final repository and reconciliation

Before this report was added, implementation HEAD was `7b23bbb`, the worktree was clean, the D10 stash was intact, and canonical reconciliation returned `CLEAN_NO_PRIOR_SESSION` with no PIDs, ports, state file, unresolved positions, or prior evidence requiring recovery.

The failed connected check did not create a session or launcher state. Final report commits are documentation-only and are reported in the operator handoff/final response.

## S. Session-03 clearance and limitations

The measurement system is qualified for the next **distinct NSE trading day**, subject to a fresh successful Stage 1 and real post-launch Stage 2. The connected Stage‑2 path was not completed today; this is why clearance carries limitations. No claim of live Stage‑2 success is made.

The current runner’s durable funnel truth also exposes that its direct paper-order path has no separately emitted Risk decision or AutonomyToken object; those stages are explicitly recorded `NOT_REACHED`, never silently relabelled. This hardening task did not change authority architecture. Operators must interpret the manifest’s reached/not-reached facts literally.

## Exact Session-03 operator charter

On the next distinct NSE trading day:

1. Verify branch, frozen HEAD, clean status and D10 stash; abort on mismatch.
2. Run `scripts\reconcile_a2_session_state.ps1 -Check`; require `CLEAN_NO_PRIOR_SESSION`.
3. Run `scripts\check_pre_market_stack.ps1`; require `READY_FOR_A2_PAPER_SESSION`. This creates the same-day, same-HEAD durable Stage‑1 handoff. Do not launch on warnings/blockers.
4. Launch only `scripts\start_ats_a2_live_paper.ps1 -Mode AGGRESSIVE`. The launcher verifies Stage‑1 date, HEAD and verdict.
5. Require V3 LIVE, the complete dynamic subscription plan, every authority key fresh at ≤2,000 ms, valid four-clock records, and persisted `MARKET_OPEN_DATA_READY` **before the session may count**.
6. Verify `RECORDER_HEALTH`: zero write/fsync/drop failures and advancing sequence/hash. Any mandatory recorder fault denies new risk and invalidates research use.
7. Run autonomously without source/config/model changes, forced trades, restarts for inactivity, or shadow promotion.
8. At policy cutoff/flatten/close, use `STOP_A2_PAPER_SESSION`, canonical stack stop, and reconciliation. Require `CLEAN_NO_PRIOR_SESSION`.
9. Destroy runtime/process state. Reconstruct solely from `events.jsonl`, `manifest.json`, and `FORWARD_EVIDENCE_MANIFEST.json`.
10. Verify sequence, hash chain, session ID, Stage 2, clocks, funnel, same-state/option/shadow facts, counterfactual completeness, recorder health, and final classification.
11. Increment `FORWARD_SHADOW_CHAMPIONSHIP_VALID_SESSIONS` from 1 to 2 only for `VALID_FORWARD_SESSION` or `VALID_FORWARD_SESSION_WITH_LIMITATIONS` on a new persisted trading date. `SUPPLEMENTAL_ONLY` and every `INVALID_*` result do not increment it.

No Session 03 was launched or counted during this hardening task.
