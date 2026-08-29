# Final Report — Alpha V4 Validity Repair

## A. Repository

- Worktree: `D:\Projects\ATS\worktrees\alpha-intelligence-v4`
- Branch: `eng/alpha-intelligence-v4`
- Starting HEAD: `e5e3e2f96a31eb3fde44234450d169a1c9f1e265`
- Repair implementation HEAD: `4d6d9f9` (`alpha-v4-validity-repair`)
- Package ending HEAD: the commit containing this report
- Target integration worktree was not modified or integrated.
- Preserved stash: `stash@{0}: D10-uncommitted-work-preserve`

## B. Four-clock defect

Old behavior checked only `event_time <= decision_time` and
`available_to_strategy_time <= decision_time`, allowing invalid source/ingest
ordering. New ingress validation requires every decision-critical bar to have
timezone-aware UTC clocks satisfying:

`event_time <= source_time <= ingest_time <= available_to_strategy_time <= decision_time`.

Missing, naive, non-UTC, future or incorrectly ordered clocks are not repaired,
reordered or synthesized. `evaluate_alpha_v4` returns HOLD with
`INVALID_TEMPORAL_EVIDENCE`. The latest underlying evidence is independently
age-checked and stale evidence returns `STALE_UNDERLYING_EVIDENCE`.

Tests cover valid/equal clocks, every adjacent ordering violation, event/final
availability after decision, missing clock, naive clock, non-UTC offset, mixed
valid/invalid inputs and stale underlying evidence.

## C. NetEV defect

Removed formula:

`quote.ask * abs(underlying_return_5m) * directional_edge`.

It was invalid because a real quote cannot convert an underlying-return proxy
into observed or validated option payoff. Alpha V4 now requires a separate
`ExpectedOptionPayoffEvidence` carrying value, model identity/version, as-of
time and explicit provenance. Without it, directional research remains
available but `expected_value`/NetEV is `None`, action is HOLD, state is
`EDGE_NOT_EVALUABLE`, and reason is
`ECONOMIC_PAYOFF_EVIDENCE_UNAVAILABLE`.

Supported provenance is explicit: `REAL_OPTION_PAYOFF_MODEL` or
`SYNTHETIC_TEST_ONLY`. Test-only evidence is rejected on the default
live/shadow research path and works only when the explicit test gate is enabled.
No new payoff model or proxy was introduced.

Numeric NetEV retains the single decomposition:

`payoff - spread - slippage - brokerage - statutory - uncertainty - liquidity`.

Tests verify exact accounting, cost stress, negative/cost-dominated payoff,
uncertainty monotonicity, unavailable-not-zero behavior and positive test-only
shadow math.

## D. Freshness defect

Old behavior rejected only future quote timestamps. New behavior validates the
selected option instrument's own timestamp and uses the canonical inclusive
`DEFAULT_MAXIMUM_QUOTE_AGE_MS = 2_000` authority from
`ats.market.derivatives.option_universe`.

Outcomes are explicit: missing quote, invalid/missing timestamp, future quote,
fresh quote, and stale quote. Exact boundary is fresh; one millisecond beyond
is stale. Stale selected CE cannot be masked by a fresh PE, and global feed
health is not used as a substitute for instrument freshness.

## E. Invalid input behavior

- Invalid four-clock evidence: HOLD / `INVALID_TEMPORAL_EVIDENCE`.
- Stale underlying: HOLD / `STALE_UNDERLYING_EVIDENCE`.
- Missing option: HOLD / `MISSING_OPTION_EVIDENCE`.
- Future option: HOLD / `FUTURE_OPTION_EVIDENCE`.
- Stale option: HOLD / `STALE_OPTION_EVIDENCE`.
- Fresh quote without payoff model: directional research is retained; NetEV is
  unavailable and final action is HOLD.
- Quiet market and cost-dominated payoff do not force activity.

## F. Shadow authority

Alpha V4 remains a pure `SHADOW_ONLY` value-returning module. It imports no
AutonomyToken, OrderIntent, PaperBroker, Portfolio, Risk, A04 or capital
reservation service and exposes no token/order/broker methods. The positive
test-only economic steel thread produces only an Alpha research decision.

## G. C0 isolation

No C0 production code, calibration or candidate path was modified by repair
commit `4d6d9f9`. Behavioral tests cover negative, neutral and positive ROC_3
inputs and prove the unchanged formula
`clamp(0.05, 0.95, 0.50 + 5.0 * ROC_3)` and threshold `0.55`.

## H. Test differential

Prior independent classifications are preserved:

- Three option-economic tests: baseline 8/8 pass; Alpha 3 fail because required
  ignored/generated instrument-master data is absent from the Alpha worktree.
  Classification: `ENVIRONMENT_FAILURE`; no provider data was committed.
- `test_paper_broker_execution_only`, `test_stop_flattens_open_paper_positions`,
  `test_multi_position_paper_flow`: fail identically on baseline and Alpha;
  `PRE_EXISTING_BASELINE_FAILURE`.
- `test_automatic_qualifying_candidate_paper_broker_pipeline`: identical
  baseline/Alpha failure; `PRE_EXISTING_BASELINE_FAILURE`.
- Tournament execution and walk-forward determinism exceed the 30-second bound
  on both worktrees; `PRE_EXISTING_UNBOUNDED_TEST`. Full shadow replay passes
  on both in approximately 14.5 seconds.
- Alpha launcher test invokes a hard-coded final-integration worktree under the
  Alpha environment; classification `TEST_INFRASTRUCTURE_FAILURE`.

None is attributable to the validity repair.

## I. Quality

- Focused Alpha validity tests: 28 passed.
- Related Alpha/Forward Shadow/regime/calibration/ensemble/Strategy Lab/cutoff
  qualification: 150 passed.
- Ruff: passed.
- Mypy: passed for `alpha_v4.py`.
- Python compilation: passed under repository-pinned Python 3.11.15.
- Frontend: not run; no frontend files changed.

## J. Validity answers

- Is any synthetic option payoff still used in default live/shadow NetEV? **No.**
- Is full four-clock ordering enforced? **Yes, at Alpha bar ingress for every input.**
- Can stale option evidence create a candidate? **No.**
- Can unavailable economics become numeric zero? **No; expected value is `None`.**

Alpha V4 remains economically unproven. Correct HOLD behavior does not change
the existing `MORE_DATA_REQUIRED` research limitation.

## K. Safety

- LIVE MONEY DISABLED
- PAPER ONLY
- REAL BROKER ORDERS 0
- C0 ACTIVE CHAMPION
- C0 THRESHOLD 0.55
- ALPHA_V4 SHADOW_ONLY
- A04 FINAL AUTHORITY
- NO FORCED TRADE
- NO PROVIDER BYPASS
- `risk_constraints_unchanged = TRUE`

## Final verdict

**ALPHA_V4_VALIDITY_REPAIRED**

