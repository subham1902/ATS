# Final Report — Alpha R&D V4

## A. Recovery

Cline created `alpha-intelligence-v4` / `eng/alpha-intelligence-v4` at `5374abf` and stopped before any change or commit. Codex recovered the repository, created the recovery matrix, removed invalid shadow lot/option assumptions, and implemented/verified the V4 shadow research layer. No Cline code was discarded because none was persisted; pre-existing valid ATS modules were preserved.

## B. Repository

- Worktree: `D:\Projects\ATS\worktrees\alpha-intelligence-v4`
- Branch: `eng/alpha-intelligence-v4`
- Starting HEAD: `5374abf45af33774384fb0d40476883eee7fd09e`
- Codex commits: `b85a749` (recovery and real quote gating), `aab5a16` (V4 shadow intelligence), plus the final report/verification commit.
- Preserved stash: `stash@{0}: D10-uncommitted-work-preserve`
- Original `ats/main`: dirty before recovery and intentionally untouched.

## C. Prior no-trade root cause

Historical evidence showed compressed C0 probabilities and dominant `NEUTRAL_THESIS` termination upstream of Portfolio Brain/Risk/A04. Current code supports that funnel classification, but no dataset in this worktree permits an honest regenerated count. Root cause status: plausible and historically supported, not freshly quantified.

## D–E. R&D findings and rejected ideas

The strongest conclusion is economic: transaction costs create a rational no-trade region. Directional activation must not substitute for net edge. Primary-source findings and adoption decisions are in `ALPHA_RND_V4_SOURCES.md`. Rejected: synthetic option economics, hard-coded contract metadata, fabricated order flow, threshold lowering, oversized ML stacks and auto-promotion.

## F. Alpha V4 architecture

Cutoff-bounded bars → multi-horizon feature bundle → deterministic regime → specialists → disagreement uncertainty → contemporaneous option quote/provider lot → decomposed net EV → HOLD/LONG_CE/LONG_PE research recommendation. The output is SHADOW_ONLY and sits outside production authority.

## G–J. Features, horizons, regimes and specialists

- Features: ROC 1/3/5/10/15/30, velocity, acceleration, realized volatility/change, range position/compression, VWAP deviation, volume z-score, trend persistence.
- Every bar carries event/source/ingest/available-to-strategy time; only evidence available by decision time is read.
- Regimes: RANGE, TREND, VOL_EXPANSION, RARE_EVENT, UNCERTAIN.
- Specialists: trend, mean reversion, breakout estimate, volatility expansion and R10-X convexity.
- Option-flow specialist is deferred until recorded provider depth/OI/IV histories exist.

## K–M. Models, calibration and uncertainty

C0 is unchanged. Existing M1–M9/R10-X remain challengers; M2 remains not promoted. Existing per-challenger calibration isolation is preserved. V4 uses specialist disagreement plus an UNCERTAIN-regime penalty; prediction and uncertainty remain distinct.

## N. Net expected value

`ExpectedOptionPayoff - Spread - Slippage - Brokerage - StatutoryCosts - UncertaintyPenalty - LiquidityPenalty`.

Exact decomposition and higher-cost degradation are unit tested. A configurable positive safety buffer must be cleared.

## O–P. MICRO_EDGE and fast market

- Slow-market verdict: `INSUFFICIENT_DATA`; verified behavior is HOLD when costs exceed payoff.
- Fast-market verdict: `INSUFFICIENT_DATA`; acceleration/vol-expansion/R10-X routing is implemented but economically unproven.

## Q. Options intelligence

Contract key, expiry, strike, type, bid/ask and timestamp are provider evidence. Lot size is mandatory provider metadata. Optional OI, IV and Greeks are modeled but not fabricated. Missing, future or mismatched evidence fails closed.

## R. Exits

Production exit behavior is unchanged. Research counterfactual exits remain versioned, but now settle only from later matching option bids; synthetic spot-derived option marks were removed.

## S–V. Before/after, economics, cost stress and survival

See `BEFORE_VS_AFTER_ALPHA_V4.json`. Promotion-grade probability, P&L, drawdown and 1x/1.5x/2x/3x stress results are null because legitimate chronological option history is unavailable. Unit tests demonstrate monotonic deterioration under increased costs, not profitability. No claim of improved trading or survival is made.

## W. Performance

No promotion-grade hot-path benchmark is claimed. The implementation is pure in-process arithmetic with no network, LLM, RAG, Harness or broker calls. Component p50/p95/p99 must be measured on production-equivalent immutable snapshots during the next paper session.

## X. Failure isolation

Verified: missing provider lot, missing/future option quote, uncertain regime and inadequate net EV all produce HOLD/no counterfactual entry. Existing Forward Shadow catches failures per model. Shadow recorder and full pipeline injection remain next-session acceptance items; production authority was not coupled to V4.

## Y. Test results

- Focused/related pytest final gate: 128 passed (V4, Forward Shadow, regime, calibration, ensemble, Strategy Lab and cutoff invariance). Earlier readiness/shadow gate: 23 passed.
- Ruff: passed for new V4 module/tests.
- Mypy: passed for new V4 module.
- Python: repository-pinned 3.11.15.
- Frontend: not run; no frontend changes.
- Full repository suite: pending final gate.

## Z. Governance

- LIVE MONEY DISABLED
- PAPER ONLY
- REAL BROKER ORDERS 0
- A04 FINAL DETERMINISTIC AUTHORITY
- HARNESS ADVISORY ONLY
- NO FORCED TRADE
- NO MARTINGALE / REVENGE / LOSS-RECOVERY MULTIPLIER / AUTOMATIC AVERAGING DOWN
- NO SHADOW OrderIntent, AutonomyToken, PaperBroker or capital/position authority
- NO PROVIDER BYPASS
- `risk_constraints_unchanged = TRUE`

## AA. Promotion

Production champion: C0, unchanged at threshold 0.55. Shadow champion: none governed. M2 remains not promoted. Recommendation: continue forward shadow; no promotion candidate because real option-economic, walk-forward and final-holdout evidence is insufficient.

## AB. Next live paper session

For NIFTY and BANKNIFTY, record C0 plus M1–M9/R10-X and Alpha V4 on identical `market_state_id`, `feature_bundle_id` and decision time. Persist provider contract/lot, bid/ask/depth, OI/IV/Greeks where present, component latency, rejection reason and later matching option bids. Predeclare quiet/fast regime rules and 1x/1.5x/2x/3x costs before settlement. Do not alter C0 or production authority. Require independent sample size and chronological walk-forward/untouched holdout before any promotion review.

## Final verdict

**MORE_DATA_REQUIRED**
