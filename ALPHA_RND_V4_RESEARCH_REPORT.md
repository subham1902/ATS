# Alpha R&D V4 Research Report

## Answer first

Alpha V4 improves the *research contract* for separating no edge, small edge and stronger/convex edge, but current data cannot establish economic superiority over C0. The defensible result is a shadow-only, cost-aware decision layer plus a forward evidence plan—not promotion.

## Prior bottleneck and recovery finding

Existing code and historical mission evidence agree that C0 probabilities were compressed near 0.50 and most states ended at `NEUTRAL_THESIS` before Portfolio Brain, Risk or A04. The current repository has a forensic funnel (`session_forensics.py`) but the Alpha worktree contains no session dataset from which to regenerate a current quantitative funnel. Therefore the upstream discrimination hypothesis remains plausible but not newly quantified.

## Implemented research architecture

`ats.intelligence.alpha_v4` consumes immutable one-minute bars with event, source, ingest and available-to-strategy timestamps. It computes returns at 1/3/5/10/15/30 minutes, velocity, acceleration, realized-volatility change, range position/compression, VWAP deviation, volume z-score and trend persistence. Future/unavailable bars are excluded.

Deterministic routing selects RANGE, TREND, VOL_EXPANSION, RARE_EVENT or UNCERTAIN and emphasizes mean reversion, trend, volatility expansion or R10-X accordingly. A breakout estimate remains available to disagreement/uncertainty but is not independently routed until validated. No LLM or dynamic live weights are involved.

The option decision requires a provider lot plus a contemporaneous CE/PE quote. Expected net value is:

`expected option payoff - spread - slippage - brokerage - statutory costs - uncertainty penalty - liquidity penalty`.

The result is HOLD if the regime is uncertain, evidence is missing/future, or net EV does not exceed the safety buffer.

## Slow and fast market findings

`SLOW_MARKET_EDGE_TEST`: **INSUFFICIENT_DATA**. Unit scenarios verify that a quiet range with no post-cost edge returns HOLD. They do not prove a tradable slow-market edge.

`FAST_MARKET_CONVEXITY_TEST`: **INSUFFICIENT_DATA**. R10-X routing and acceleration features exist, but no legitimate chronological option history is available for economic validation.

## Calibration and uncertainty

Existing ATS challenger-specific calibration stores and chronological validation are preserved. Alpha V4 does not reuse C0 calibration. Ensemble/specialist disagreement is exposed as uncertainty; UNCERTAIN regimes receive an additional penalty and cannot activate. Calibrator fitting is deferred until independent per-model observations exist.

## Rejected ideas

- Hard-coded lot sizes, expiry weekdays or strike schedules.
- Synthetic spot-to-option price/payoff as promotion evidence.
- Lowering C0's threshold to manufacture activity.
- Order-flow features without actual provider depth/trade evidence.
- Giant ML/deep-learning dependencies without a valid dataset.
- Automatic promotion or any shadow execution authority.

## Evidence limitations

Historical Upstox option acquisition remains externally restricted and its tooling explicitly classifies the restriction as non-retryable. The repository contains no promotion-grade option history in this worktree. Accordingly all before/after economic metrics, cost-stress P&L and drawdown fields remain null rather than synthetic.

