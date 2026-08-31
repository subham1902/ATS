# ATS autonomous A2 paper readiness — 2026-09-01

## Executive verdict

**READY_WITH_LIMITATIONS_FOR_2026-09-01_A2_PAPER**

The corrected system is ready to attempt the canonical autonomous **paper** session on Tuesday, 2026-09-01, subject to a fresh 09:00 IST Stage 1 pass and post-launch `MARKET_OPEN_DATA_READY`. It is not approved for live money, cannot guarantee profits, and must never trade merely to create activity.

The production path now fails closed when genuine option-payoff evidence is unavailable. Because the worktree does not contain a governed champion calibration artifact and there is only one locally observed option session, zero trades tomorrow is the expected safe possibility—not a reason to relax controls.

## Frozen checkpoint

- Branch: `eng/final-a2-integration`
- Original market-ready base: `de4ca8a2c3ba0eedc880670a847ab26356a24c9b`
- Corrected trading-source commit: `b642a8d4d2ee1a0fb6d2242ed8e8d71578ccb471`
- Execution: PaperBroker only
- Live money: disabled
- Real broker authority: false
- Canonical capital: INR 100,000
- C0 threshold: 0.55, unchanged
- Alpha V4, M1-M9, M2, and R10-X: shadow/research only
- Portfolio Brain, Risk, A04, costs, sizing, cutoff, and exit policy: unchanged
- D10 preservation stash: `stash@{0}: D10-uncommitted-work-preserve`

## Corrections completed

1. Enforced Stage 2 inside the execution path. New risk requires a live V3 connection, the exact dynamic 22-key subscription set, and every decision-critical key fresh within the inclusive 2,000 ms policy.
2. Aligned production V3 silence/staleness thresholds and A2 quote age to 2,000 ms.
3. Corrected live option quote/Greek field access and added scanner-failure telemetry.
4. Repaired canonical session-forensics discovery, manifest identity, reader loading, legacy fallback, hash-chain and session consistency handling.
5. Made market snapshots use provider timestamps, actual provider volume when available, and truthful missing-volume quality; removed fabricated volume `1000` and zero-age claims.
6. Removed placeholder gross-edge/cost/NetEV telemetry. Unknown economics now serialize as `None`.
7. Required explicitly observed option-payoff evidence in production instrument selection. Missing payoff returns `ECONOMIC_PAYOFF_EVIDENCE_UNAVAILABLE` and HOLD.
8. Disabled operator-created paper orders by default in autonomous mode while retaining provider lot-size registration.
9. Added official NSE F&O 2026 holiday filtering. September 1 is a trading day; September 14 is excluded. The ATS 15:30 close remains a conservative internal policy.
10. Removed machine-specific default calibration paths. Production does not silently load ungoverned evidence from another checkout.
11. Corrected research attribution: challenger probability results no longer inherit C0 trades/P&L. Synthetic `spot * 0.012` option economics are prohibited and cannot authorize promotion.
12. Fixed test isolation, replay lot authority, frontend mutation-route contract, market-feed protocol, and repository-wide lint findings.

## Verification evidence

| Check | Result |
|---|---|
| Python | 3.11.15 |
| Canonical launcher Node | 24.19.0 (verified installed and launcher-pinned) |
| pnpm | 11.9.0 |
| Ruff | PASS, zero findings |
| Mypy | PASS, 305 source files |
| Python compileall | PASS |
| Backend tests | 1,892 passed, 25 skipped, 0 failed |
| Focused safety/forensics tests | 53 passed |
| Frontend tests | 73 passed (12 API client + 61 control center) |
| Next.js production build | PASS, 18 static pages |
| Production dependency audit | No known vulnerabilities |
| High-confidence secret scan | 0 matching files; gitleaks unavailable |
| Reconciliation | `CLEAN_NO_PRIOR_SESSION` |
| Real broker orders | 0; no real-order endpoint called |

Skipped tests depend on unavailable PostgreSQL/external data or explicitly absent governed research artifacts. They do not weaken the paper-execution safety proof, but they limit research/performance conclusions.

## Connected provider evidence captured 2026-08-31

Provider authentication, BOD reference authority, V3 transport capability, dynamic subscriptions, PaperBroker configuration, recorder, forensics, A04, and reconciliation all passed.

The provider resolved the following observations at check time; tomorrow's fresh provider truth remains authoritative:

| Underlying | Key | Lot | Tick | Expiry | Selected options |
|---|---|---:|---:|---|---:|
| NIFTY | `NSE_INDEX|Nifty 50` | 65 | 0.050 | 2026-09-01 | 10 |
| BANKNIFTY | `NSE_INDEX|Nifty Bank` | 30 | 0.050 | 2026-09-29 | 10 |

The 11:01 IST Stage 1 invocation returned `BLOCKED_MARKET_OPEN_DATA_NOT_READY` because the canonical session had not been launched before market open, so no running feed could prove Stage 2. This is the correct late-launch fail-closed behavior. It does not substitute for tomorrow's 09:00 check.

## Tomorrow's canonical runbook

At approximately 09:00 IST:

```powershell
cd D:\Projects\ATS\worktrees\final-a2-integration
git status --short
git branch --show-current
git rev-parse HEAD
git stash list
powershell -ExecutionPolicy Bypass -File scripts/reconcile_a2_session_state.ps1 -Check
powershell -ExecutionPolicy Bypass -File scripts/check_pre_market_stack.ps1
```

Proceed only with a clean tree, branch `eng/final-a2-integration`, corrected HEAD (or a later documentation-only commit), intact D10 stash, reconciliation clean, and exact verdict `READY_FOR_A2_PAPER_SESSION`.

At 09:10-09:14 IST:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_ats_a2_live_paper.ps1 -Mode AGGRESSIVE
```

After 09:15 IST, do not permit new risk until the running system reports `MARKET_OPEN_DATA_READY` for both underlyings and required CE/PE subscriptions. Never override stale, missing-volume, clock-order, calibration, option-payoff, Portfolio, Risk, or A04 holds.

At close, use `STOP_A2_PAPER_SESSION`, canonical stack shutdown, then:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/reconcile_a2_session_state.ps1 -Check
```

## Profitability assessment

No reliable expected-profit claim can be made. C0 has not completed a valid forward option-economic session, the repository lacks a governed multi-session calibration artifact, and one real option day is inadequate for performance inference. The system is safer because it will choose HOLD instead of manufacturing expected payoff.

The correct objective for tomorrow is evidence collection under unchanged policy. A valid session requires real NSE observations, Stage 2, predictions, valid recording, finalized summary, and a verified hash chain. Only after multiple valid forward sessions can probability dispersion, trade economics, drawdown, and model comparison be assessed.

## Limitations and residual risks

- No genuine full forward session has yet completed; `VALID_SESSIONS = 0` until tomorrow succeeds.
- No profit guarantee exists, and positive paper P&L would not establish live profitability.
- Missing governed calibration/option-payoff evidence can legitimately produce zero trades.
- PostgreSQL integration tests were excluded because the external service was unavailable.
- FastAPI emits deprecation warnings for `on_event`; this is non-safety-critical and should not be hot-fixed during a session.
- The interactive shell is Node 26.4.0; only the canonical launcher uses the verified Node 24.19.0 binary.
- Current provider lot, expiry, and selection truth must be re-resolved tomorrow and never copied from this report.
- SEBI/broker compliance and any future live deployment require separate broker authorization and regulatory review. This report approves paper execution only.

## Final recommendation

Run the fresh Stage 1 check at 09:00 IST. If it passes, launch canonically, require Stage 2, allow autonomous paper observation/execution without intervention, and accept zero trades. Do not alter source, thresholds, models, costs, or policies during the session.

**Next action:** `COLLECT_FORWARD_SESSION_01_ON_2026-09-01`.

