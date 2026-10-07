# S5 ORB — Open Design Decisions (Review Addendum)

**Status:** review addendum to `2026-09-30-s5-orb-xauusd-design.md`. **No S5 code is
authorized.** This addendum preserves all fifteen unresolved review topics after the
XAUUSD-native rewrite; it grants no implementation or promotion authority. Answers are given only where repository evidence supports them. Everything else
is marked `UNRESOLVED — REQUIRES DESIGN DECISION` and is deliberately left open.

Standing constraints: XAUUSD-native, DESIGN / RESEARCH_ONLY. No validation
or transferred performance authority. All fifteen review items remain recorded.

| #   | Question                                          | Status                                   | Evidence / note                                                                                                                                                                                                                              |
| --- | ------------------------------------------------- | ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Exact final holdout partition                     | UNRESOLVED — REQUIRES DESIGN DECISION    | Spec §3.3(3–4) requires a "pristine holdout" touched once, and the Eligibility Standard (§1.2.3) requires sealing it before evaluation, but neither defines its size or location relative to the future admitted dataset or the PWFCV folds. |
| 2   | Cost gates (1.5× / 2.0×): per-fold or aggregate   | UNRESOLVED — REQUIRES DESIGN DECISION    | Spec §5.4 says "evaluated out-of-sample per fold" but not whether every fold, a majority, or the pooled result must pass.                                                                                                                    |
| 3   | Permutation-null statistic                        | UNRESOLVED — REQUIRES DESIGN DECISION    | Spec §5.3(1) fixes B ≥ 1000 and label shuffling with fixed features, but not the test statistic (net PnL, Sharpe, EV…) or how temporal structure is respected when shuffling.                                                                |
| 4   | Random-entry null generation                      | UNRESOLVED — REQUIRES DESIGN DECISION    | §5.3(2) says "net P&L must be non-positive", a point test rather than a distribution/p-value. The null's replications and decision rule are undefined.                                                                                       |
| 5   | Poisson entry-rate definition                     | UNRESOLVED — REQUIRES DESIGN DECISION    | Rate is not specified; matching Stage 1's entries per day is a candidate but is a choice, not a repo fact.                                                                                                                                   |
| 6   | DSR trial-count definition                        | UNRESOLVED — REQUIRES DESIGN DECISION    | §5.3(3) says to correct for trials "implied by the sweep" but the sweep grid (item 7) is undefined, so the count is too.                                                                                                                     |
| 7   | Parameter sweep grid (`p_min`, `τ_hurdle`)        | UNRESOLVED — REQUIRES DESIGN DECISION    | Only the initial values (0.55, 0) are given. §3.3(1) says the grid is pre-registered before results; it has not been written.                                                                                                                |
| 8   | Definition of Ĝ                                   | UNRESOLVED — REQUIRES DESIGN DECISION    | §3.2 uses Ĝ in `EXPECTED_NET_EV` without defining its estimator (e.g. conditional mean gain on training-fold winners).                                                                                                                       |
| 9   | Definition of L̂                                   | UNRESOLVED — REQUIRES DESIGN DECISION    | Same as Ĝ for the loss side.                                                                                                                                                                                                                 |
| 10  | Pre-registration audit after prior data access    | UNRESOLVED — REQUIRES DESIGN DECISION    | The native rewrite withdraws the old pre-data-access claim. Commit and hash the new constants, folds and selection rules before opening a new sealed holdout; the exact protocol remains undecided.                                          |
| 11  | Per-fold low/high-volatility requirement          | FEASIBILITY UNPROVEN                     | §3.3(6) requires every fold to contain both regimes. Candidate count and date coverage are UNKNOWN. Per-fold tercile coverage is not guaranteed and has not been checked against an admitted dataset.                                        |
| 12  | `PAPER_ELIGIBLE` label vs. hard CANDIDATE ceiling | UNRESOLVED — REQUIRES DESIGN DECISION    | §5.4 names the 2.0× level "PAPER_ELIGIBLE" although §0/§5.5 cap the outcome at CANDIDATE. Rename the gate (e.g. `COST_STRESS_2X_PASS`) so no artifact reads as a promotion.                                                                  |
| 13  | Source for the 08:20 ET COMEX opening claim       | UNVERIFIED                               | Spec §2.2 asserts it as "the official COMEX GC pit/day-session open". No document in the repo verifies it. Needs an external, citable source or a reworded justification.                                                                    |
| 14  | Broker/session hypothesis implications            | RECORDED, NOT RESOLVED                   | The proposed NY anchor is a XAUUSD research window. Broker trading hours, rollover, DST, missing anchor bars and session-specific costs require documented decisions and evidence; no exchange session or transferred validation is claimed. |
| 15  | Location of the 16 canonical abstention codes     | REFERENCED, CODES NOT FOUND — UNRESOLVED | `ATS_QUANT_RESEARCH_CONSTITUTION_v1.0.md` §2.4(3) cites "the authoritative 16 abstention reason codes (Doc 15)", but no file in the workspace contains them. Stage 1/2 code must not invent a parallel vocabulary.                           |

## Timezone note (not an open question)

The anchor is `08:20 America/New_York`. Implementation must use timezone-aware
conversion (`zoneinfo`), never a fixed UTC offset; the spec's 12:20 UTC (EDT) / 13:20 UTC
(EST) mapping is correct. Stage 1 should abstain on days where the anchor bar is missing,
and DST transition days need explicit tests.

## Gate

`S5 implementation: AWAITING USER GO`
