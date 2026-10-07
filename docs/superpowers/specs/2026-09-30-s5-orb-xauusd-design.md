# S5 Opening Range Breakout — XAUUSD-native Strategy Candidate

**Status:** Design approved in-chat (2026-09-30). Awaiting written-spec review.
**Scope path:** Architectural (per `superpowers:brainstorming`).
**Author:** Claude Sonnet 5, in collaboration with Subham Panigrahi.

## 0. Purpose and authority ceiling

S5 is XAUUSD-native opening-range-breakout research, DESIGN / RESEARCH_ONLY.
No implementation, dataset validation or profitability result is established.
Historical data must be admitted by immutable dataset identity, quality review,
documented broker costs and a pre-registered method before use. Historical claims
of data size or coverage in an earlier design do not establish current admission.
No old-market score, calibration or strategy result supplies a prior or promotion.
Research is proposal-only; this design does not grant execution authority.
The maximum proposed result remains CANDIDATE pending all unresolved review items.

## 1. Proposed workspace and inputs

This document is `docs/superpowers/specs/2026-09-30-s5-orb-xauusd-design.md`.
No S5 implementation or feature cache currently exists. The future strategy
workspace will follow the canonical Strategy OS layout after Step 2. Dataset
admission must use the immutable XAUUSD dataset registry; no external filename,
old report, historical candidate count or previously claimed date coverage
constitutes admitted evidence. The user-provided two-year dataset remains pending.

## 2. Phase 1 — Hypothesis and Economic Rationale

### 2.1 XAUUSD-native session hypothesis

XAUUSD is a broker spot-metal/CFD instrument with broker-dependent trading hours.
Opening-range windows are research classifications, not exchange-session claims.

### 2.2 Proposed New York research anchor

The proposed anchor is 08:20 America/New_York with a 15-minute range and a
two-hour trigger window. Use timezone-aware DST conversion, never fixed UTC offsets.
The claimed exchange-opening rationale remains UNVERIFIED; the choice requires
design review and clean-room evidence. No old strategy performance motivates or
validates this choice, and no pre-registration before prior data access is claimed.

### 2.3 Trivial baseline to beat

Per `ATS_STRATEGY_RESEARCH_STANDARD_v1.0.md` §2.2, the mandatory trivial baseline is:
close beyond `OR_high`/`OR_low` → enter in that direction, hold to end-of-day, no filter,
no stop beyond a fixed catastrophic stop. This baseline must be run through the identical
Phase 3 harness (same costs, same folds) as the candidate strategy, so superiority is
measured strategy-vs-baseline on identical conditions, not strategy-vs-literature.

## 3. Two-Stage Meta-Labeling Architecture

Per `ATS_STRATEGY_RESEARCH_STANDARD_v1.0.md` §3.

### 3.1 Stage 1 — Opportunity Scanner (high recall)

Triggers whenever, within a 2-hour post-anchor window (08:35–10:35 ET), price closes
beyond the opening range high or low on the working bar timeframe (1-minute, aggregated
as needed). Emits one directional candidate per triggering day (first qualifying breakout
only — no re-triggering same-direction, to avoid manufacturing correlated pseudo-trades
from one underlying event).

Feature set attached to each candidate (all computable strictly from information available
at or before the decision instant — see §6 causality contract):

- Breakout magnitude in ATR units (ATR computed on a trailing window ending at the prior
  session close, never using same-day data before the anchor).
- Opening range width relative to the trailing 20-day average opening-range width.
- Pre-anchor overnight range (Asia + London session high/low spread).
- Day-of-week.
- Prior-day realized-volatility bucket (tercile, computed trailing-only).

Stage 1 has no knowledge of outcome and is not permitted to use any forward-looking
information — it is a deterministic rule plus feature extraction, not a fitted model.

### 3.2 Stage 2 — Meta-Classifier (NET_EV)

Trained only on Stage-1-generated candidates (never on all bars — this is the meta-labeling
contract). Label: `REALIZED_EXECUTABLE_NET_PNL`, computed as ask-price-on-entry /
bid-price-on-exit crossing (using the dataset's actual bid and ask series, not a synthetic
spread), minus versioned broker commission, slippage, latency and rollover assumptions.

Outputs:

- `p_cal = P(Y_net > 0 | X)`, calibrated (not raw classifier score — isotonic or Platt
  calibration fit only on the training fold).
- `EXPECTED_NET_EV = p_cal * Ĝ − (1 − p_cal) * L̂ − PointInTimeFrictions`.
- Decision: `META_TAKE` if `EXPECTED_NET_EV ≥ τ_hurdle` and `p_cal ≥ p_min`, else
  `ABSTAIN`. Initial values `p_min = 0.55`, `τ_hurdle = 0` per the Standard's
  `[RESEARCH_INITIALIZATION]` defaults — both are swept, not hand-picked, during Phase 3
  (see §5.4).

Per the model's dataclass/reason-code convention used elsewhere in `ats/`
(`trading_runtime/strategy.py`), both stages return explicit `reason_codes` tuples on
every decision, including abstentions, and never emit a bare `None` without a code.

### 3.3 "Genuine / dataset-independent" as checkable constraints

The user's requirement — "ensure the strategies are independent of getting trained on
any specific data set... they should perform genuinely" — is operationalized as the
following concrete, auditable constraints rather than a promised outcome:

1. **Near-zero hand-fit parameters.** The only fixed constants are the anchor time, the
   15-minute opening-range window, and the 2-hour trigger window — all set by taxonomy/
   economic rationale in §2, to be pre-registered before the new sealed holdout is examined. Stage 2's
   `p_min`/`τ_hurdle` are the only swept hyperparameters, and the sweep grid and selection
   rule are pre-registered (committed to this repo) before results are computed.
2. **No grid search over Stage-1 trigger logic.** The breakout rule itself is fixed by
   taxonomy definition (§2.3's baseline), not searched.
3. **Pre-registration before holdout is opened.** The full Phase 3 harness (splits, cost
   model, null tests, thresholds) is committed and hashed before the pristine holdout
   partition is touched, per `ATS_LIVE_ELIGIBILITY_STANDARD_v1.0.md` §1.2.3.
4. **Holdout touched exactly once.** One evaluation pass on holdout; no iteration based on
   holdout results.
5. **Parameter-perturbation and delay robustness.** Results must survive ±1-bar entry
   delay and ±20% perturbation of the opening-range window length (reusing STRAT-04's
   perturbation methodology) without reversing sign.
6. **Multi-regime validation.** The ~2-year XAUUSD window is split so that each PWFCV fold
   contains both a low-volatility and a high-volatility sub-period (classified by trailing
   realized vol tercile, §3.1), satisfying the Standard's §4.2 multi-regime requirement.
7. **Honest verdict regardless of outcome.** If the strategy fails any gate, the output
   JSON says so plainly (`gate_pass: false`, same schema as
   `ATS_SURVIVOR_PORTFOLIO_V1.json`) — a `NO_SURVIVOR` result is an acceptable and
   expected possible outcome of this work, not a failure to avoid by adjusting the method.

## 4. Phase 2 — Synthetic Toy Validation (`SYNTHETIC_VALIDATION_ONLY`)

Per the Standard §1.2.1, this phase carries **zero promotion authority** — it exists only
to verify the Stage 1/2 pipeline is mechanically correct before it ever touches real data.

Design: generate a synthetic 1-minute OHLC series with a known, injected
breakout-persistence effect (a deterministic drift added after a synthetic "opening
range" on a subset of synthetic days, zero drift on the rest).

- **Positive control:** with the effect injected at a clearly detectable magnitude, the
  full Stage 1 → Stage 2 → NET_EV pipeline must recover a positive, statistically
  significant edge on the synthetic-effect days.
- **Negative control:** with the injected effect set to exactly zero (pure random walk
  opening ranges), the pipeline's Stage 2 must abstain or show statistically
  indistinguishable-from-zero EV — this calibrates that Stage 2 doesn't manufacture
  spurious edge from the scanner's own selection bias.

Any code and results from this phase are tagged `SYNTHETIC_VALIDATION_ONLY` in all
outputs and file names, and are never cited as evidence of real-market edge.

## 5. Phase 3 — Offline Historical PWFCV (Versioned XAUUSD Broker Data)

### 5.1 Candidate universe

Every admitted broker trading day with a qualifying Stage-1 trigger belongs
to the candidate universe. Date coverage and candidate count are UNKNOWN until
an eligible dataset is supplied. Fold feasibility must be measured on that data.

### 5.2 Purged Walk-Forward CV

≥5 folds, walk-forward (train on earlier period, test on later, rolling forward), with
purge and embargo windows sized to the strategy's holding horizon (1–3 hours intraday,
so purge/embargo is set in trading-day units sufficient to prevent any label leakage
across the train/test boundary — concretely, embargo ≥ 1 full trading day beyond the
last possible exit of any training-fold trade).

### 5.3 Null-Hypothesis Testing Battery (§4.3 of the Standard)

All three mandatory tests, run on Phase 3 holdout-eligible results:

1. **Permutation test**, B ≥ 1000, label-shuffle, feature matrix held fixed.
2. **Random-entry null**: replace Stage-1 triggers with Poisson-random entries on
   identical price paths, run through the same Stage 2 + exit stack; net P&L must be
   non-positive.
3. **Deflated Sharpe Ratio**, hurdle DSR > 0.95, correcting for the number of trials
   implied by the §3.3 hyperparameter sweep (not treated as zero trials just because the
   sweep grid is small).

### 5.4 Cost-Stress Testing (§5 of the Standard)

Use the versioned XAUUSD execution-cost model with observed bid/ask where
available, otherwise an explicitly labelled modeled spread. Commission,
slippage, latency and rollover must be declared; no cost schedule transfers
from another market. The fold and holdout protocol remains unresolved.
Required: positive `EXPECTED_NET_EV` at 1.5× total modeled frictions (CHALLENGER level),
and `EXPECTED_NET_EV ≥ 0` at 2.0× (PAPER_ELIGIBLE level) — both evaluated out-of-sample
per fold.

### 5.5 Verdict artifact

A machine-readable JSON verdict, schema-compatible with
`ATS_SURVIVOR_PORTFOLIO_V1.json`, recording: per-fold metrics, gate pass/fail per
criterion (mirroring the `gate` object shape seen in `strategy_results.json`), the
overall `gate_pass` boolean, and an explicit `authority_ceiling: "CANDIDATE_REFERENCE_RESEARCH_ONLY"`
field stamped into every verdict file this work produces, regardless of outcome.

## 6. Causality Contract

All Stage 1 features, Stage 2 training labels, and cost calculations obey the Four-Clock
Causality Contract (`T0 ≤ T1 ≤ T2 ≤ T3 < decision < entry`) from the Quant Research
Constitution: no feature may read data timestamped after the decision instant; ATR,
opening-range-width history, and volatility-tercile features are all computed from bars
strictly before the current day's anchor.

## 7. Testing Strategy

- **Stage 1 determinism**: given a fixed input bar series, the scanner must produce
  identical trigger/direction/feature output on repeated runs (no hidden randomness).
- **Stage 2 EV formula correctness**: unit tests with hand-computed `p_cal`, `Ĝ`, `L̂`,
  friction inputs checked against the `EXPECTED_NET_EV` formula in §3.2 to floating-point
  tolerance.
- **Causality enforcement**: a test that corrupts a single post-anchor bar and asserts no
  feature value changes as a result (proves no look-ahead).
- **PWFCV split integrity**: a test asserting no training-fold trade's exit timestamp
  falls inside the following test fold's embargo window.
- **Null-battery correctness**: run the permutation and random-entry tests against toy
  inputs with an analytically known answer (e.g., pure noise should yield p-values
  uniformly distributed, not systematically low).

## 8. Error Handling and Abstention

- Missing or stale bars at or near the anchor time → Stage 1 emits no candidate for that
  day (not a crash, not a default direction).
- Stage 2 receiving an out-of-distribution feature vector (e.g., ATR of zero, missing
  overnight range) → forced `ABSTAIN`, never a best-effort guess.
- All abstentions and holds must use the canonical reason-code vocabulary referenced in
  the Quant Research Constitution ("Doc 15", 16 canonical abstention codes) rather than
  inventing new codes. **Open item carried into `writing-plans`:** the exact source
  document/file for these 16 codes has not yet been located in this workspace and must be
  found (and reused, not reinvented) before Stage 1/2 code is written. If it cannot be
  located, `writing-plans` must flag this explicitly rather than silently inventing a
  parallel vocabulary.

## 9. Explicit Non-Goals

- No live-money execution, no live broker integration, no bypass of A04/`PaperBrokerAdapter`.
- No claim of `RESEARCH_VALIDATED` or higher status from this work.
- Every artifact must identify its XAUUSD broker source, dataset and methodology.
