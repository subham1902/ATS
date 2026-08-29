# Alpha V4 Recovery Audit

Audit date: 2026-08-30 (Asia/Calcutta)

## Recovery conclusion

Cline created `D:\Projects\ATS\worktrees\alpha-intelligence-v4` on branch
`eng/alpha-intelligence-v4` at `5374abf45af33774384fb0d40476883eee7fd09e`
and stopped before persisting Alpha V4 work. The worktree was clean when Codex
recovered it. Its reflog contains only the worktree creation/reset at
2026-08-30 00:23:47 +0530. There are no Alpha V4-specific commits, uncommitted
changes, named deliverables, or similarly named generated artifacts anywhere
under `D:\Projects\ATS`.

The branch starts at the same commit as `eng/final-a2-integration`. Existing
intelligence and research components below predate this mission and must be
preserved where valid; they are not evidence that Cline completed Alpha V4.

The original `D:\Projects\ATS\ats` worktree is on `main` at `2305a40` and has
substantial unrelated modified/untracked Upstox feed code and raw market data.
It will not be modified. `stash@{0}: D10-uncommitted-work-preserve` exists and
will remain untouched.

## Status definitions

- `COMPLETE_AND_VERIFIED`: implementation exists and relevant tests/evidence passed in this recovery.
- `COMPLETE_NOT_VERIFIED`: implementation exists, but Alpha V4 verification has not run yet.
- `PARTIALLY_IMPLEMENTED`: useful foundation exists but the requested V4 contract is incomplete.
- `PLANNED_ONLY`: prose/design evidence exists without the requested implementation.
- `NOT_STARTED`: no repository evidence of the requested V4 work.
- `BLOCKED`: cannot be completed with legitimate current evidence/access.
- `INVALID_IMPLEMENTATION`: existing code violates a mission invariant or cannot support the claimed evidence level.

## Recovery matrix

| # | Workstream | Status | Repository evidence and recovery finding |
|---:|---|---|---|
| 1 | repository audit | COMPLETE_AND_VERIFIED | Git worktree/status/branch/HEAD/log/stash and sibling-worktree checks performed. This document records the result. |
| 2 | no-trade forensic analysis | PARTIALLY_IMPLEMENTED | `backend/src/ats/observability/session_forensics.py` implements funnel/rejection analysis; commits `7d92284`, `3286d0a`. Current V4 quantitative baseline has not been regenerated. |
| 3 | external R&D | NOT_STARTED | No Alpha V4 research artifact or Cline change found. |
| 4 | source bibliography | NOT_STARTED | `ALPHA_RND_V4_SOURCES.md` and equivalents absent. |
| 5 | feature factory | PARTIALLY_IMPLEMENTED | `backend/src/ats/market/features/engine.py`, `registry.py`; option features in `market/derivatives/option_chain/features.py`; IBA feature foundation predates V4. Required V4 feature contracts/families and verification remain incomplete. |
| 6 | multi-horizon forecasting | PARTIALLY_IMPLEMENTED | Generic forecast contracts/worker exist in `backend/src/ats/forecast/`; M3 uses only `roc_1/roc_3/roc_5` in `shadow_championship.py`. No complete 1m/3m/5m/10m/15m/30m V4 output. |
| 7 | regime engine | COMPLETE_NOT_VERIFIED | `backend/src/ats/intelligence/regime/detector.py` (`detect_regime`), models/contracts/tests; commit `94535f3`. V4 routing suitability still requires focused verification. |
| 8 | trend specialist | PARTIALLY_IMPLEMENTED | `ShadowM3` and `ShadowM4` in `backend/src/ats/trading_runtime/shadow_championship.py`; equivalent tournament models in `scripts/run_champion_replacement_tournament.py`; commit `3286d0a`. Heuristic, not a fully contracted V4 specialist. |
| 9 | mean-reversion specialist | PARTIALLY_IMPLEMENTED | `ShadowM5` / `ModelM5` implement range-position reversion, commit `3286d0a`; lacks VWAP/cost-aware slow-market evidence. |
| 10 | breakout specialist | PARTIALLY_IMPLEMENTED | M6 combines ROC and acceleration but has no explicit contemporaneous breakout-distance contract. |
| 11 | volatility-expansion specialist | PARTIALLY_IMPLEMENTED | `ShadowM6` / `ModelM6`, commit `3286d0a`; does not actually require a volatility-expansion feature. |
| 12 | option-flow specialist | NOT_STARTED | Option-chain features exist, but no model using contemporaneous CE/PE flow/relative-strength evidence was found. |
| 13 | R10-X / convexity specialist | PARTIALLY_IMPLEMENTED | `ShadowR10X` exists, but duplicates M8 exactly and uses only acceleration plus ROC; commit `3286d0a`. |
| 14 | calibration | COMPLETE_NOT_VERIFIED | Isolated calibration packages/stores and challenger-specific work exist in `backend/src/ats/intelligence/calibration/`; commits `9ceff6c`, `3d6ad54`, `ac4f7a6`. Shadow model wiring must be checked. |
| 15 | uncertainty | PARTIALLY_IMPLEMENTED | Ensemble disagreement exists in `backend/src/ats/intelligence/ensemble/engine.py`; desired rolling/OOD uncertainty and V4 output wiring are incomplete. |
| 16 | expected-option-payoff model | INVALID_IMPLEMENTATION | `shadow_championship.py` estimates option price as 1.2% of spot and delta/theta payoff synthetically. This is forbidden as promotion-grade economic evidence. |
| 17 | net-EV model | INVALID_IMPLEMENTATION | M7 is a directional probability hurdle, not the required decomposed EV. Shadow candidate EV is not grounded in contemporaneous option payoff/cost evidence. |
| 18 | MICRO_EDGE / slow-market research | NOT_STARTED | No `SLOW_MARKET_EDGE_TEST` or equivalent artifact found. |
| 19 | fast-market research | NOT_STARTED | No `FAST_MARKET_CONVEXITY_TEST` or equivalent artifact found. |
| 20 | option contract selection | PARTIALLY_IMPLEMENTED | Production selector and `tests/integration/intelligence/instrument_selector/test_option_selection_pipeline.py` exist. Shadow engine does not use it and fabricates an ATM proxy. |
| 21 | exit research | PARTIALLY_IMPLEMENTED | `RESEARCH_COUNTERFACTUAL_POLICY_V1` is versioned in `shadow_championship.py`; its synthetic option marks prevent economic validation. Production managed exits are separate. |
| 22 | model lab | PARTIALLY_IMPLEMENTED | C0 and M1-M9 exist in `run_champion_replacement_tournament.py`; research framework under `intelligence/strategy_lab/`; commits `48e2a82`, `d0be41d`, `7a3513a`, `b26ddff`. V4 tests/evidence incomplete. |
| 23 | chronological validation | PARTIALLY_IMPLEMENTED | Tournament declares chronological partitions; Strategy Lab validates chronology. Current runner also depends on synthetic option economics. |
| 24 | walk-forward | COMPLETE_NOT_VERIFIED | `backend/src/ats/intelligence/strategy_lab/walk_forward.py`, `scripts/run_walk_forward_simulation.py`, and tests; commits `48e2a82`, `8b8a4fd`. Alpha V4 candidates not yet evaluated. |
| 25 | final holdout | PARTIALLY_IMPLEMENTED | Tournament isolates a holdout in code, but all models are subsequently evaluated on it and the economics are synthetic; no frozen V4 run. |
| 26 | shadow integration | PARTIALLY_IMPLEMENTED | `ForwardShadowChampionshipEngine`, `A2PaperSessionController` integration, common state IDs, and SHADOW_ONLY records; commits `3286d0a`, `511a41d`. Authority and invalid fallback behavior require verification/fix. |
| 27 | Forward Shadow evidence | PARTIALLY_IMPLEMENTED | Prediction/scorecard recording exists; option quote, payoff, cost, uncertainty, and later-outcome evidence are incomplete. |
| 28 | hot-path performance | NOT_STARTED | No Alpha V4 p50/p95/p99 component benchmark artifact found. |
| 29 | failure isolation | PARTIALLY_IMPLEMENTED | Per-model exception isolation exists in `evaluate_observation`; the full requested injection matrix has not been verified. |
| 30 | dashboard/read-model additions | PARTIALLY_IMPLEMENTED | Existing operator projections expose regime and expected net value (`operator_projection.py`); no complete V4 read model. UI is out of scope unless backend fields require it. |
| 31 | tests | PARTIALLY_IMPLEMENTED | Shadow readiness/replay/tournament tests exist under `tests/unit/trading_runtime_tests/`; full V4 safety, math, temporal, failure, and restart matrix has not run. |
| 32 | before-vs-after evaluation | NOT_STARTED | `BEFORE_VS_AFTER_ALPHA_V4.json` absent. |
| 33 | final report | NOT_STARTED | `FINAL_REPORT_ALPHA_RND_V4.md` absent. |

## Precise stopping point and continuation point

Cline stopped after creating/resetting the dedicated Alpha V4 worktree and
branch. Therefore the first incomplete dependency-safe mission workstream is
the no-trade baseline/feature-contract audit, building on pre-existing modules.
Before adding models, continuation must first remove or quarantine invalid
shadow assumptions (hard-coded lot fallback and synthetic option economics),
then establish deterministic feature/state outputs and evidence-grade tests.

## Immediate safety findings

1. `ForwardShadowChampionshipEngine._enter_counterfactual_position` falls back
   to hard-coded NIFTY/BANKNIFTY lot sizes. Alpha V4 must fail closed without
   provider-resolved metadata.
2. The same engine fabricates option prices from spot and later fabricates
   option payoff. Such records may be labelled synthetic research only and
   cannot become promotion evidence.
3. M8 and R10-X are functionally identical. This is duplicate evidence, not an
   independent convex specialist.
4. M7 does not compute decomposed expected net value despite its name.
5. C0's formula and 0.55 threshold are preserved and must remain unchanged.

## Continuation status

Codex continued from the identified stopping point in commits `b85a749` and
`aab5a16`. The invalid hard-coded lot and synthetic option-settlement findings
were corrected by requiring provider lot metadata and contemporaneous matching
quotes. A pure `SHADOW_ONLY` Alpha V4 module now covers multi-horizon features,
regime/specialist routing, disagreement uncertainty and decomposed net EV.
Historical economic validation, before/after P&L, slow-market edge proof and
fast-market convexity proof remain `BLOCKED`/`INSUFFICIENT_DATA` because no
legitimate chronological option history is available. They were not replaced
with synthetic evidence.
