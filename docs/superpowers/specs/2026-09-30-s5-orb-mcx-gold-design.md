# S5 Opening Range Breakout — Gold (XAUUSD proxy) Strategy Candidate

**Status:** Design approved in-chat (2026-09-30). Awaiting written-spec review.
**Scope path:** Architectural (per `superpowers:brainstorming`).
**Author:** Claude Sonnet 5, in collaboration with Subham Panigrahi.

## 0. Purpose and Authority Ceiling

This spec defines Phase 1–3 of a new strategy candidate in the **S5 (Opening Range
Breakout)** family from `ATS_STRATEGY_RESEARCH_STANDARD_v1.0.md` §2.1, built from scratch
(not a hardening of an existing survivor), targeting MCX Gold.

**Hard scope boundary, stated up front so it cannot be read past:**

- No real MCX GOLDM historical data exists anywhere in this workspace. The only real
  tradable-asset dataset available is global spot gold (XAUUSD), ~2 years of 1-minute
  bid/ask bars (`xauusd-m1-bid-source-rechecked.csv`, 2024-09-01T22:00:00Z →
  2026-08-31T23:59:00Z, 711,287 rows).
- XAUUSD is used throughout this work as an explicit **proxy instrument**, not as MCX
  Gold. Every result, chart, and verdict produced by this work must be labeled
  `INSTRUMENT: XAUUSD_PROXY`, never `MCX_GOLDM`.
- The Live Eligibility Standard's `0 → 1: RESEARCH_VALIDATED` gate (§2.1) is written as a
  purely statistical bar (PWFCV ≥5 folds, permutation test, DSR > 0.95, N_eff, Brier
  score), and this spec's Phase 3 (§5) is designed to formally satisfy that bar if the
  strategy has real edge. Satisfying the numeric gate is **not**, by itself, sufficient
  here, for two independent reasons this spec treats as controlling:
  1. **Instrument mismatch.** The gate is meant to validate a candidate against the
     instrument it will actually trade. This work's data is XAUUSD spot (proxy), not
     MCX GOLDM. A passing result certifies the proxy, not the target instrument — it
     cannot be read as "MCX Gold is research-validated."
  2. **Data-provenance primacy.** The Quant Research Constitution designates
     `ForwardSessionRecorder` output as the primary empirical truth, with all
     Parquet/CSV historical catalogs subordinate to it. This spec's Phase 3 runs
     entirely on a vendor historical CSV, never on `ForwardSessionRecorder` data.
     For both reasons, a fully passing Phase 1–3 result under this spec earns, at most,
     **`CANDIDATE` status with reference-research authority** — never `RESEARCH_VALIDATED`,
     regardless of how cleanly the numeric gate is cleared. Concretely: this work can
     produce a candidate ready to be _proposed_ for a future shadow-deployment study on the
     real target instrument once that data exists. It cannot certify anything as live-ready
     or as validated-on-MCX-Gold, and must never be represented as such in any artifact it
     produces.
- Scope for this spec is **S5 only** (user-selected "Approach C"). S9 (Post-News/Event
  Drift) and S12 (Multi-Asset Lead-Lag) are intentionally reduced to Phase-1-hypothesis
  stubs in the companion audit document (`ats/docs/research/MCX_GOLD_STRATEGY_READINESS_AUDIT.md`)
  and are not implemented here.
- All execution referenced anywhere in this work is **paper-only**, via the existing
  `PaperBrokerAdapter`. No code written under this spec may construct an `OrderIntent`
  that bypasses A04, and no code may reference a live-money broker gateway.

## 1. File Layout

| Path                                                                                                                     | Contents                                                                                                                                                                     | Committed?                                                      |
| ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `ats/docs/superpowers/specs/2026-09-30-s5-orb-mcx-gold-design.md`                                                        | This spec.                                                                                                                                                                   | Yes                                                             |
| `ats/docs/research/MCX_GOLD_STRATEGY_READINESS_AUDIT.md`                                                                 | Standalone audit: S1–S14 status vs. promotion ladder, "strategy bins" critique, STRAT-02/04 history, S9/S12 stubs. No code.                                                  | Yes                                                             |
| `ats/backend/src/ats/research/strategies/s5_orb/`                                                                        | New code subpackage: Stage 1 scanner, Stage 2 meta-classifier, Phase 2 synthetic harness, Phase 3 PWFCV harness, tests. Exact module breakdown finalized by `writing-plans`. | Yes                                                             |
| `ATS trade data/xauusd-m1-*.csv` (outer workspace)                                                                       | Raw source data.                                                                                                                                                             | No — stays external, too large and not reproducible-from-source |
| A derived, normalized session-level feature cache + a manifest file recording its source hash, row count, and date range | Generated artifact consumed by Phase 3.                                                                                                                                      | Yes (cache + manifest only, not raw ticks)                      |

Rationale for not committing raw CSVs: they are ~49MB+ each, external market data, and
regeneration only requires the manifest hash to confirm provenance — not useful or
appropriate as tracked repo content. This mirrors how `research_data/strat04/` already
treats its source CSVs (external) versus its `results/*.json` (committed).

## 2. Phase 1 — Hypothesis and Economic Rationale

### 2.1 Why not literally "MCX 09:00 IST"

The taxonomy's required baseline for S5 is "Fixed 15-minute high/low breakout." On MCX,
this is naturally anchored to the 09:00 IST session open, because MCX Gold futures gap
between sessions (overnight closed market). XAUUSD spot, by contrast, trades nearly
continuously (closes only ~Friday 22:00 UTC to Sunday 22:00 UTC), so there is no
analogous "gap-then-open" structure at 09:00 IST — treating that clock time as an opening
range on a continuous feed would be an arbitrary, economically unmotivated choice, exactly
the kind of dataset-specific overfit the user's "genuine, dataset-independent" requirement
rules out.

### 2.2 Chosen anchor: COMEX/NY futures day-session open

**Anchor time: 08:20 America/New_York (DST-aware, i.e., 12:20 UTC in EDT, 13:20 UTC in
EST), the official COMEX GC (gold futures) pit/day-session open.**

Economic rationale: the COMEX day-session open is when US institutional gold futures
order flow (bank trading desks, CTAs executing on US hours, COMEX-referenced options
hedging) concentrates most heavily, resolving the overnight Asia-session and
London-session positioning into a directional move. This is a structural, calendar-based
liquidity-concentration event independent of any one dataset's quirks — the same
reasoning that justifies ORB on any futures-linked instrument, not a fact fitted after
looking at XAUUSD price action.

Opening range definition: high/low of the 15 minutes following the anchor (08:20–08:35
ET), per the taxonomy's required baseline.

`S30_SESSION_WINDOW` from STRAT-04 (`research_data/strat04/results/strategy_results.json`)
— a time-window strategy on `15M_REFB`, the closest existing mechanistic analog to ORB —
came closest to breakeven of everything STRAT-04 tested (`net_exp_bps: -0.029`,
`pf: 0.988`, `gate_pass: false`). This is cited **only as motivation** for pursuing a
session-timing mechanism; it is not evidence this specific S5 design will pass, and it is
not reused as a parameter or calibration source.

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
spread), minus an explicitly labeled **proxy friction** (since real MCX statutory
costs/margin do not apply to an XAUUSD spot series — this is called out everywhere as
`PROXY_FRICTION_MODEL`, never presented as a real MCX cost).

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
   economic rationale in §2, before any XAUUSD data is examined for strategy fit. Stage 2's
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

## 5. Phase 3 — Offline Historical PWFCV (Real XAUUSD Proxy Data)

### 5.1 Candidate universe

Every US trading day in the 2024-09-01 → 2026-08-31 XAUUSD window that has a qualifying
Stage-1 breakout trigger — estimated ~500 day-candidates (most trading days produce one,
some produce none if price never clears the opening range within the 2-hour window).

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

Reuse STRAT-04's MCX PIT V3 cost model structure and split/holdout protocol where
applicable for comparability, adapted to the `PROXY_FRICTION_MODEL` labeling from §3.2.
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
- No implementation of S9 or S12 beyond their Phase-1 stub writeups in the audit document.
- No claim of `RESEARCH_VALIDATED` or higher status from this work.
- No MCX-GOLDM-specific claims — every artifact is labeled as an XAUUSD proxy result.
