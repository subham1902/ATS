==================================================
ATS PROMOTION-GRADE HISTORICAL OPTION ECONOMIC TRUTH
REAL OPTION PAYOFF DATASET + CHALLENGER TOURNAMENT V3
FINAL REPORT (A–Q)
==================================================

FINAL VERDICT: BLOCKED_UPTOX_HTTP_403_QUOTA
(secondary: MORE_DATA_REQUIRED once unblocked)

The mission to build a promotion-grade real-option-economic challenger
tournament could NOT be completed to a promotion decision because the live
Upstox token hit a persistent HTTP_403 quota during this run, leaving only ONE
locally-cached real option session. All infrastructure required for a genuine
promotion-grade run is now built and validated; it only needs the refetch to
proceed.

==================================================
A. REPOSITORY
==================================================
Worktree: D:\Projects\ATS\worktrees\final-a2-integration
Branch: eng/final-a2-integration
Start HEAD: 511a41d
End HEAD: 511a41d (unchanged; explicit staging only, no commit)
Commits in package: none (all new work is untracked / unstaged per policy)
Dirty state: new untracked research scripts + data/replays artifacts; stash
  D10-uncommitted-work-preserve preserved untouched.
No git reset --hard / clean / stash drop / git add . performed.

New artifacts:
- scripts/option_economic_truth.py        (core engine: resolver, cost, exec, evidence)
- scripts/run_tournament_v3.py           (real-option-economics tournament)
- scripts/emit_v3_artifacts.py           (required JSON artifacts)
- scripts/fetch_option_truth_data.py     (real option candle fetcher, blocked by 403)
- scripts/dump_option_contracts.py       (real metadata cache builder)
- scripts/upstox_capability_audit.py     (read-only capability audit)
- scripts/upstox_metadata_audit.py       (metadata endpoint probe)
- tests/unit/research/test_option_economic_truth.py  (8 tests, all pass)
- data/raw/upstox/instrument_cache/*.json (real contract metadata: 1594 NIFTY + 856 BANKNIFTY)
- data/raw/upstox/capability_audit.json  (capability classification)
- data/replays/champion_replacement_tournament_v3/*.json (12 artifacts)

==================================================
B. UPSTOX HISTORICAL OPTION CAPABILITY (read-only audit; token never printed)
==================================================
Probed with the repository token (env or Windows registry), read-only endpoints:

- historical-candle (underlying 1m)            : AVAILABLE
- historical-candle (option instrument 1m)     : AVAILABLE (200 during audit; later 403 under quota)
- option/contract (metadata: strike/expiry/CE-PE/lot/tick) : AVAILABLE
- option/option-chain (live)                   : NOT_AVAILABLE (HTTP_400)
- market-quote/instrument/master               : NOT_AVAILABLE (HTTP_400)
- market-quote/instrument/{key} (single)       : NOT_AVAILABLE (HTTP_400)
- historical-candle under quota                 : HTTP_403 (persistent after cooldown)

Conclusion: real option OHLC + real contract metadata ARE retrievable via
historical-candle + option/contract. The single-instrument/master endpoints are
not usable, but option/contract already supplies all resolver metadata. The only
blocker is the live token's HTTP_403 quota, which prevented backfilling the 18
missing option sessions.

==================================================
C. ECONOMIC EVIDENCE LEVEL (A/B/C/D)
==================================================
- REAL_QUOTE_ECONOMICS (A): 0 sessions (no historical bid/ask depth available)
- REAL_OPTION_BAR_ECONOMICS (B): 1 session (2026-08-25, 10 NIFTY + 10 BANKNIFTY
  real 1m option bars) — but its instrument keys are DELISTED, so strike/lot/tick
  are UNRESOLVABLE from cache -> flagged APPROXIMATE_METADATA, NOT promotion-grade.
- BAR_APPROXIMATION_EXECUTION (C): engine supports conservative within-bar entry/
  exit; used as conservative approximation when only bars exist.
- SYNTHETIC_OPTION_ECONOMICS (D): deliberately NOT used. The prior V2 tournament's
  synthetic delta-proxy (delta=0.50, atm_opt_price = price*0.012, -0.5*bars_held
  decay) was REPLACED by real-bar economics.

Promotion-grade (A/B) real-option session count available: 0 (after delisted-key
disqualification). Underlying directional evidence (19 sessions) is real but is
NOT option economics.

==================================================
D. DATASET
==================================================
Date range intended: 2026-08-04 .. 2026-08-28 (19 sessions)
- Underlying 1m candles: 19 sessions PRESENT (from fetch_prior_sessions.py)
- Real option 1m candles: 1 session PRESENT (2026-08-25); 18 MISSING (fetch 403)
- Contract metadata cached: 2450 contracts (NIFTY 1594 + BANKNIFTY 856), all
  currently-listed (NIFTY weeklies from 2026-09-01; BANKNIFTY monthlies from
  2026-09-29). The 2026-08-27 front weekly is delisted and absent from cache.
- NIFTY contracts in band: ~105 strikes x CE/PE for 2026-09-01 weekly
- BANKNIFTY contracts in band: ~143 strikes x CE/PE for 2026-09-29 monthly
- CE/PE counts: balanced in cache (full straddle/strangle coverage)
Quality failures: 18/19 sessions lack real option candles; the 1 present session
  has unresolvable contract metadata (delisted keys) -> INVALID_FOR_PROMOTION as-is.

==================================================
E. HISTORICAL CONTRACT RESOLUTION
==================================================
Resolver: option_economic_truth.resolve_contract()
- Inputs: underlying, decision_time (unused for static target expiry), expression
  (LONG_CE/LONG_PE), underlying_price.
- Expiry: taken from TARGET_EXPIRY = {"NIFTY":"2026-09-01","BANKNIFTY":"2026-09-29"},
  i.e. the near-term RESOLVABLE listed expiry — NOT hard-coded weekday/weekly rule.
- Strike: nearest strike to underlying_price from cached contracts (offset -1/0/+1).
- Lot size / tick size: taken from the resolved contract metadata.
  Proof: NIFTY ATM CE 25000 -> lot 65, tick 5.0; BANKNIFTY ATM PE -> lot 30, tick 5.0.
  (Prior V2 hard-coded lot NIFTY=25, BANKNIFTY=15 — both WRONG; engine uses real 65/30.)
- No hard-coded NIFTY/BANKNIFTY lot, expiry weekday, or weekly-availability constant.

==================================================
F. COST MODEL (NSE F&O option, versioned + labeled)
==================================================
Version: ATS_NSE_OPTION_V1_APPROX (conservative approximation; must be replaced
with exchange-verified historical rates before any production promotion claim).
Charges (on premium notional, per lot):
- STT: 0.05% of premium on SELL side only
- Exchange txn: 0.053% of premium (both sides)
- GST: 18% on (brokerage + exchange txn)
- SEBI: 0.00015% of premium (both sides)
- Stamp: 0.003% of premium on BUY side
- Brokerage: flat ₹20/order (₹40 round trip)
Verified: costs > 0 and scale with premium; a ₹150 NIFTY premium x65 lot round
trip ≈ ₹65 (~0.6% of premium). Timestamp/version aware via COST_MODEL_VERSION.

==================================================
G. SPLITS (chronological, no shuffle; holdout untouched until gates frozen)
==================================================
- Train: 2026-08-04 .. 2026-08-18 (11 sessions, 1430 underlying obs)
- Validation: 2026-08-19 .. 2026-08-21 (3 sessions, 390 obs)
- Walk-forward: 2026-08-24 .. 2026-08-26 (3 sessions, 390 obs)
- Holdout: 2026-08-27 .. 2026-08-28 (2 sessions, 254 obs)
Underlying directional labels are REAL (underlying returns). Option-economic
labels exist for holdout only as 0 real sessions -> gates cannot be satisfied.

==================================================
H. MODEL RESULTS (C0 + M1..M9)
==================================================
Directional families preserved from V2 (C0 frozen linear; M1 logistic; M2 robust
logit; M3 trend ensemble; M4 regime logistic; M5 range MR; M6 vol-expansion; M7
cost-aware EV; M8 R10-X convexity; M9 mixture). All 10 evaluated.
Real-option-economic scorecards computed only where real option P&L exists
(2026-08-25). For all 19 sessions the directional calibration/activation ran; the
option P&L expectation is UNDEFINED for 18 sessions (no real option data) and was
NOT fabricated. Per-model option economics on the single session: see
model_scorecards.json / holdout_report.json (insufficient for ranking).

==================================================
I. CALIBRATION
==================================================
Brier scores computed on REAL directional (underlying-return) targets per model;
see calibration_report.json. Challenger-specific leakage-safe calibration is
preserved (no reuse of C0 calibration state). Full probability-distribution /
ECE reporting is wired but only meaningful once option-economic labels are present.

==================================================
J. ECONOMIC RESULTS
==================================================
Net expectancy / P&L / profit factor / drawdown / turnover / tail metrics are
produced by the real-bar engine (entry/exit from actual option premiums, costs
from the NSE model). They are reported for the single validated session only and
are explicitly NOT sufficient for promotion. Example engine validation on a
BANKNIFTY 2026-08-25 bar pair: entry 899.02 -> exit 878.0, gross -630.75, costs
94.60, net -725.35 (real bars, no delta proxy).

==================================================
K. COST STRESS (1x/1.5x/2x/3x)
==================================================
cost_stress.json reports multiplier-scaled net (approximate stress proxy, labeled
as such because the 1-session series embeds 1x costs). Promotion REQUIRES positive
net expectancy at >= 1.5x; unverifiable with 1 session. The cost model itself is
separately stressable by raising COST_MODEL rates.

==================================================
L. REGIME RESULTS
==================================================
regime_breakdown.json: per-session TREND/RANGE classification from real underlying
bars (NIFTY + BANKNIFTY). Option-economic regime/CE-vs-PE/time-of-day/expiry
breakdowns are specified and wired but require real option data to populate.

==================================================
M. HOLDOUT (strict, untouched)
==================================================
Holdout (2026-08-27..28) was NOT read for option economics before gate freeze.
It contains underlying data only; no real option candles -> cannot evaluate
holdout net expectancy on option economics. This is the core reason promotion is
blocked.

==================================================
N. PROMOTION GATES
==================================================
promotion_gates.json lists all required gates (positive val/wf/holdout net
expectancy on REAL option economics; 1.5x robustness; calibration; sufficient
trades/sessions; no leakage; deterministic; risk_constraints_unchanged=TRUE).
Result: ALL models FAIL pre-gate due to insufficient real-option sessions
(available=1, required>=5). No model was ranked-to-promote by fabrication.

==================================================
O. CHAMPION DECISION
==================================================
- C0: RETAINS champion (frozen linear, unchanged).
- M2: previously highest-ranked challenger; NOT promoted (no promotion-grade evidence).
- Other challengers: not eligible (same reason).
- Verdict: BLOCKED_UPTOX_HTTP_403_QUOTA (effectively MORE_DATA_REQUIRED).

==================================================
P. FORENSIC INTEGRATION
==================================================
New models MUST persist via existing Session Evidence Recorder: model ID/version,
probability, net EV, threshold, activation, candidate/rejection, option contract,
cost estimate, confidence, uncertainty. The engine emits EconomicObservation
records structured for this. No new opaque model path was introduced. (Wiring to
the recorder is specified; full integration test deferred until real data runs.)

==================================================
Q. SAFETY (unchanged, verified)
==================================================
- LIVE MONEY DISABLED (A2PaperSessionConfig; a2_runner start invariant)
- REAL BROKER ORDERS 0 (execution_target == PAPER; PaperBrokerAdapter only)
- A04 FINAL DETERMINISTIC AUTHORITY preserved; logic unchanged
- HARNESS ADVISORY ONLY (notify_material_event, exception-isolated)
- NO THRESHOLD CHANGE: activation threshold remains 0.55
- NO FORCED TRADE: scanner only acts on real candidate; no synthetic orders
- NO ALPHA BEHAVIOR CHANGE beyond the (research-only) economic replay
- risk_constraints_unchanged = TRUE (mandatory, enforced in promotion_decision)
- C0 remains active champion; M2 NOT promoted; no M2 promotion logic added

==================================================
UNBLOCK PLAN (to reach a real verdict)
==================================================
1. Wait for Upstox HTTP_403 quota reset (or use a fresh/secondary token with
   read-only entitlement). Do NOT hammer the endpoint.
2. Re-run scripts/fetch_option_truth_data.py (fixed ranges: NIFTY 01Sep from
   2026-08-11; BANKNIFTY 29Sep from 2026-08-04) with inter-call delays to backfill
   real 1m option candles for all 19 sessions across an ATM±band.
3. Re-run scripts/run_tournament_v3.py + emit_v3_artifacts.py.
4. If >=5 promotion-grade real-option sessions exist and gates pass at 1.5x
   costs with untouched holdout -> A2_PAPER_SHADOW_CHAMPION_READY.
   Otherwise -> MORE_DATA_REQUIRED / NO_PROMOTION_CANDIDATE.

All code is deterministic and re-runnable; same inputs reproduce the same
scorecard (reproducibility_manifest.json).
