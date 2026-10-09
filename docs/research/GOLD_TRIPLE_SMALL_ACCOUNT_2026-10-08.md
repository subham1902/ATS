# GoldTriple small-account tuning: $500–$1,000

Date: October 8, 2026 (Asia/Calcutta). Status: RESEARCH_ONLY / NOT DEPLOYED.

## Decision

No combined-portfolio candidate passed this search's chronological admission and later-period acceptance rules at $500, $750 or $1,000. Do not deploy a best-looking failed configuration as though it passed. No standalone selection passed the stronger requirement that BOTH BASE and STRESS later-period runs have positive booked return, at least five trades and no booked-loss cap breach. No production-ready preset was found.

All three source hypotheses were evaluated separately and together. They are new tactical
intraday variants; the original H1/H4-wide-stop strategies are not silently renamed or
claimed validated by this experiment. No terminal setting, native EA, broker credential,
account execution consent or ATS live preset is changed by this report renderer.

## Account comparison and why capital changes feasibility

| $ account | portfolio outcome                | searched entry budget | initial 3% day cap $ | initial 8% month cap $ | later stress trades | later stress booked return % |
| --------- | -------------------------------- | --------------------- | -------------------- | ---------------------- | ------------------- | ---------------------------- |
| 500.00    | NO_VALIDATION_ELIGIBLE_CANDIDATE | $2.50–$5.00           | 15.00                | 40.00                  | N/A                 | N/A                          |
| 1000.00   | NO_VALIDATION_ELIGIBLE_CANDIDATE | $5.00–$10.00          | 30.00                | 80.00                  | N/A                 | N/A                          |

Minimum size is 0.01 lot on a
100.00-unit contract,
with 0.01-lot steps. For the observed USD-quoted contract,
0.01 lot represents one ounce; a $1/oz adverse move costs approximately $1 before charges.
The $500 account starts with $2.50–$5 entry-risk budgets; $1,000 starts with $5–$10.
The engine rounds DOWN and rejects below-minimum sizes. It never forces 0.01 lot when
the required stop exceeds the risk budget. Capital-specific selections are independent.

Current read-only SDK observation at `2026-10-08T12:36:14.180342+00:00` reported leverage
100:1 and approximately $41.23 buy margin for
0.01 lot at Ask 4122.85. This corrects the earlier experiment's explicit
9:1 modeling assumption; it does not establish historical broker leverage. This experiment
models 100:1 in BASE and 50:1 in STRESS,
with at most 30% of balance committed to modeled margin. Current leverage does not reduce
the price-loss exposure of a lot. Contract/margin/stop-level behavior must be rechecked
on the actual account and order before commissioning.

## Source hypotheses and new tactical entry/exit rules

- S1 retains the completed H1 breakout / H4 context hypothesis.
- S2 retains the completed M15 opening-range breakout / H1 trend context hypothesis,
  including the source-volume filter. Volume provenance remains UNKNOWN: S2 evidence
  is conditional on this supplied field, not certified real/tick volume.
- S3 retains the long-only completed H4 breakout / EMA trend hypothesis.

After a valid parent signal, require an observed, fully completed M1 or M5 retest/reclaim,
as explicitly recorded in the selected timing. The completed candle must touch the
breakout level within 0.1 tactical ATR, close back in the signal direction, and have a
same-direction body. Admission starts after one completed tactical candle (1 or5min)
and expires after120min for S1, 30min for S2 or90min for S3. The selected one- or
three-completed-tactical-bar structural extreme plus0.1 tactical ATR defines a NEW stop.
Price is rounded outward to the
observed tick grid. Required stops are not truncated to fit capital.

Enter only at the next observed minute open. Reject nonpositive stop distances,
spread above $1.50/oz, stop distance below four current spreads and an adverse drift
beyond 0.25 tactical ATR through the level. One position at a time across the combined
portfolio; priority S1, then S2, then S3. One entry per parent signal; 15-minute
post-exit cooldown; at most three entries per UTC day; stop after two net losing trades.

Targets are 1.5R, 2R or 3R of the initial price-stop distance; R in these target settings
is a price ratio before fees. Optional protection uses only earlier observed minute-close
excursions: after +1R, move to entry +0.1R in the trade direction; after +1.5R, apply
a 1.5 completed-tactical-bar ATR trail. The 0.1R price lock is not guaranteed net break-even after
costs or a gap. Targets are causal rules, not exits retrofitted to historical peaks.

Planned holding is 120 or 240 minutes. All periods use UTC. S1/S3 new entries are admitted
06:00–19:45 and plan to exit at/after 20:00; S2 exits at/after 17:30 with its original
parent-session admission. Expiry/session exits use the first observed quote; a missing
market quote can exceed the target holding or cross a date. No unobserved fill is invented.

## Exact selected configurations and lifecycle

| $ account | strategy  | outcome                          | both-cost grade             | entry risk % | target R | timing min | structure bars | protection                | target hold min |
| --------- | --------- | -------------------------------- | --------------------------- | ------------ | -------- | ---------- | -------------- | ------------------------- | --------------- |
| 500.00    | S1        | NO_VALIDATION_ELIGIBLE_CANDIDATE | NO_SELECTED_RUN             | N/A          | N/A      | N/A        | N/A            | N/A                       | N/A             |
| 500.00    | S2        | NO_VALIDATION_ELIGIBLE_CANDIDATE | NO_SELECTED_RUN             | N/A          | N/A      | N/A        | N/A            | N/A                       | N/A             |
| 500.00    | S3        | NO_VALIDATION_ELIGIBLE_CANDIDATE | NO_SELECTED_RUN             | N/A          | N/A      | N/A        | N/A            | N/A                       | N/A             |
| 500.00    | PORTFOLIO | NO_VALIDATION_ELIGIBLE_CANDIDATE | NO_SELECTED_RUN             | N/A          | N/A      | N/A        | N/A            | N/A                       | N/A             |
| 750.00    | S1        | NO_VALIDATION_ELIGIBLE_CANDIDATE | NO_SELECTED_RUN             | N/A          | N/A      | N/A        | N/A            | N/A                       | N/A             |
| 750.00    | S2        | NO_VALIDATION_ELIGIBLE_CANDIDATE | NO_SELECTED_RUN             | N/A          | N/A      | N/A        | N/A            | N/A                       | N/A             |
| 750.00    | S3        | FORWARD_RESEARCH_CANDIDATE       | FAILED_BOTH_COST_ACCEPTANCE | 0.75         | 2.00     | 5.00       | 1.00           | 0.1R lock / 1.5 ATR trail | 120.00          |
| 750.00    | PORTFOLIO | NO_VALIDATION_ELIGIBLE_CANDIDATE | NO_SELECTED_RUN             | N/A          | N/A      | N/A        | N/A            | N/A                       | N/A             |
| 1000.00   | S1        | NO_VALIDATION_ELIGIBLE_CANDIDATE | NO_SELECTED_RUN             | N/A          | N/A      | N/A        | N/A            | N/A                       | N/A             |
| 1000.00   | S2        | NO_VALIDATION_ELIGIBLE_CANDIDATE | NO_SELECTED_RUN             | N/A          | N/A      | N/A        | N/A            | N/A                       | N/A             |
| 1000.00   | S3        | FAILED_LATER_PERIOD_ACCEPTANCE   | FAILED_BOTH_COST_ACCEPTANCE | 0.50         | 2.00     | 5.00       | 1.00           | 0.1R lock / 1.5 ATR trail | 240.00          |
| 1000.00   | PORTFOLIO | NO_VALIDATION_ELIGIBLE_CANDIDATE | NO_SELECTED_RUN             | N/A          | N/A      | N/A        | N/A            | N/A                       | N/A             |

`NO_VALIDATION_ELIGIBLE_CANDIDATE` means no train/validation-qualified selection exists.
`FAILED_LATER_PERIOD_ACCEPTANCE` means a validation choice failed the later-period grade.
`FORWARD_RESEARCH_CANDIDATE` means it met this bounded statistical admission only; it
does not authorize paper/demo/live promotion. Standalone returns cannot be summed to
predict portfolio returns; masks compete for the same one-position budget.

The raw engine's later-period flag grades STRESS only. It is insufficient when BASE fails:
requiring BOTH cost runs to be positive with at least5trades and no cap breach is the
stronger report qualification, shown separately. A higher stress return can result from
higher costs/minimum-lot constraints rejecting losing trades and changing the trade set;
it does not demonstrate resilience on identical trades. All settings remain NOT_READY
for production until commissioning and prospective evidence pass.

## Chronological selection and evidence limitations

- TRAIN: September 2024–August 2025. Search 144 configurations per account/strategy:
  timingM1/M5; structural lookback1/3; risk0.5/0.75/1%; target1.5/2/3R;
  protectionoff/on; hold120/240min.
  1,728 actual training evaluations were recorded. Require positive booked return,
  at least10 closed trades, and no requested day/month cap breach; shortlist top5 by
  equity return minus twice close-mark drawdown.
- VALIDATION: September 2025–February 2026. Evaluate the shortlist at BASE and STRESS;
  require STRESS positive booked return, at least3 trades and no cap breach. Select
  the highest STRESS equity-return-minus-two-drawdown score.
- TEST: March–August 2026. Parameters remain frozen. Grade STRESS positive booked return,
  at least5 trades and no day/month cap breach. This period does not choose parameters.
- FULL: all24 months; descriptive and selection-contaminated. The data has already been
  inspected in earlier research, so TEST is a later-period check, not a certified sealed
  untouched holdout. This tuning sequence expanded from a provisional M5-only search
  after historical outcomes were inspected, adding selection bias. No multiple-testing
  correction, empirical probability calibration,
  tick parity or prospective validation is claimed.

| $ account | strategy  | train evaluations | minimum trades | maximum trades |
| --------- | --------- | ----------------- | -------------- | -------------- |
| 500.00    | S1        | 144.00            | 7.00           | 54.00          |
| 500.00    | S2        | 144.00            | 3.00           | 39.00          |
| 500.00    | S3        | 144.00            | 9.00           | 62.00          |
| 500.00    | PORTFOLIO | 144.00            | 19.00          | 139.00         |
| 750.00    | S1        | 144.00            | 32.00          | 58.00          |
| 750.00    | S2        | 144.00            | 11.00          | 42.00          |
| 750.00    | S3        | 144.00            | 36.00          | 66.00          |
| 750.00    | PORTFOLIO | 144.00            | 66.00          | 146.00         |
| 1000.00   | S1        | 144.00            | 38.00          | 61.00          |
| 1000.00   | S2        | 144.00            | 20.00          | 42.00          |
| 1000.00   | S3        | 144.00            | 46.00          | 70.00          |
| 1000.00   | PORTFOLIO | 144.00            | 95.00          | 149.00         |

## Requested loss limits and internal risk admission

Loss means NET BOOKED P&L: profits offset losses; reference is start-of-day/month equity.
The opening equity uses the previous observed close mark, not a fabricated midnight quote.

| Control                            | Research rule                                                              |
| ---------------------------------- | -------------------------------------------------------------------------- |
| Monitoring loss caps               | 3% UTC daily / 8% calendar-month net booked loss                           |
| Internal remaining entry allowance | 2.5% daily / 6% monthly, including net postings                            |
| Entry risk                         | Selected 0.5%, 0.75% or 1% of current balance                              |
| Costs in size                      | Initial stop price loss plus modeled round-trip charges                    |
| Total outstanding positions        | One across S1/S2/S3                                                        |
| Volume                             | Round down to observed step; reject below observed minimum; maximum0.10lot |
| Margin                             | At most30% balance; current-metadata historical assumption                 |
| Frequency                          | Maximum3 entries/day; pause after2 losses/day; 15min cooldown              |

Entry fees and each exit posting enter day/month loss tracking immediately. A stop gap
can exceed the reservation and cap: this research monitors breaches, not a guaranteed
financial loss ceiling. Booked-loss caps are distinct from floating-equity drawdown,
gross losing trades and deposits/withdrawals (not modeled). A native EA without these
commissioned controls does not inherit them merely because this research file exists.

## Later-period results: March–August2026

| $ account | strategy | cost   | trades | booked return % | equity return % | close-mark DD % | worst day % | worst month % | PF   | day breach | month breach |
| --------- | -------- | ------ | ------ | --------------- | --------------- | --------------- | ----------- | ------------- | ---- | ---------- | ------------ |
| 750.00    | S3       | BASE   | 7.00   | -0.24           | -0.24           | 3.34            | -0.72       | -1.29         | 0.91 | NO         | NO           |
| 750.00    | S3       | STRESS | 5.00   | 0.54            | 0.54            | 1.31            | -0.70       | -0.70         | 1.28 | NO         | NO           |
| 1000.00   | S3       | BASE   | 5.00   | -0.66           | -0.66           | 1.93            | -0.48       | -0.77         | 0.58 | NO         | NO           |
| 1000.00   | S3       | STRESS | 1.00   | -0.41           | -0.41           | 0.41            | -0.41       | -0.41         | 0.00 | NO         | NO           |

Negative/no-candidate results remain visible. Missing selected runs are not reported as
zero-profit successful strategies. Probability and Sharpe are not calibrated by this run.

## Full-period descriptive results

| $ account | strategy | cost   | trades | booked return % | equity return % | close-mark DD % | worst day % | worst month % | PF   | day breach | month breach |
| --------- | -------- | ------ | ------ | --------------- | --------------- | --------------- | ----------- | ------------- | ---- | ---------- | ------------ |
| 750.00    | S3       | BASE   | 95.00  | 4.16            | 4.16            | 3.91            | -1.28       | -1.76         | 1.16 | NO         | NO           |
| 750.00    | S3       | STRESS | 64.00  | 3.62            | 3.62            | 3.51            | -1.30       | -2.54         | 1.21 | NO         | NO           |
| 1000.00   | S3       | BASE   | 86.00  | 2.66            | 2.66            | 2.78            | -0.90       | -1.27         | 1.18 | NO         | NO           |
| 1000.00   | S3       | STRESS | 52.00  | 1.69            | 1.69            | 2.33            | -0.96       | -1.40         | 1.18 | NO         | NO           |

Full-period results include tuning data and cannot establish future profitability.

## Exit capture and actual holding diagnostics

Excursions use observed minute CLOSE marks plus the modeled exit, not unordered highs
after an exit. Capture is net trade P&L divided by positive observed-close MFE in money;
average R divides trade net by initial stop-and-cost risk. High giveback requires observed
MFE at least1 initial-risk R and capture below60%. This lower-resolution diagnostic cannot
tell whether a missed tick peak was executable.

| $ account | strategy | cost   | average net R | winner capture % | MFE>=1R | giveback cases | ambiguous bars | UTC date crossings | past hold target | max hold min |
| --------- | -------- | ------ | ------------- | ---------------- | ------- | -------------- | -------------- | ------------------ | ---------------- | ------------ |
| 750.00    | S3       | BASE   | -0.18         | 97.74            | 2.00    | 0.00           | 0.00           | 0.00               | 0.00             | 16.00        |
| 750.00    | S3       | STRESS | 0.10          | 95.47            | 2.00    | 0.00           | 0.00           | 0.00               | 0.00             | 18.00        |
| 1000.00   | S3       | BASE   | -0.43         | 97.61            | 1.00    | 0.00           | 0.00           | 0.00               | 0.00             | 16.00        |
| 1000.00   | S3       | STRESS | -1.00         | N/A              | 0.00    | 0.00           | 0.00           | 0.00               | 0.00             | 2.00         |

No closed trade in the selected ledgers crosses a UTC date. This verifies these recorded paths only; missing quotes can still delay a future planned intraday exit.

Actual position-close gaps are retained; overnight or overdue holdings cannot be hidden
behind the word intraday. Any open terminal position is left open in the summary rather
than inventing a final close.

## Fill/cost model

Paired observed Bid/Ask M1 OHLC, not broker tick replay. Long entry Ask/exit Bid; short
entry Bid/exit Ask. Stops/targets are active in the entry minute; both touched means
stopfirst. Adverse stop gaps fill at observed executable open; favorable target gaps
fill at target conservatively. Intrabar proceeds cannot fund a same-open re-entry.

BASE: observed spread and modeled$22/lot round-trip charges ($7 commission+$15 slippage
proxy), half at each side. STRESS: spread1.5x, charges$44/lot, leveragehalved. Commission,
slippage and historical margin are assumptions, not a verified historical broker tariff.
No swap/financing charges are included in this intraday variant; crossing-date rows are
explicit commissioning blockers. No partial fills, latency queues, execution rejects,
variable historic stop distance, depth, price impact or broker outage recovery is modeled.
Drawdown is marked at minute close; the chart samples daily closes and is not worst-tick DD.

## Dataset and reproducibility

- 711,286 paired rows, `2024-09-01 22:00:00+00:00` through `2026-08-31 23:59:00+00:00`.
- Explicit source UTC, valid positive OHLC, ordered unique timestamps;
  538 gaps greater than one minute. No forward price filling.
- Bid SHA256: `95b8c21d46fc8e064bb114b48363c5bdc366d08e5b2ccf581c46b94cba530a80`.
- Ask SHA256: `5e3217a2b9a8d322938d09dfba3602d8b5bcb056494d7873fe469aaa42bd9dcf`.
- Variant engine SHA256: `f03068045d3966a944b6a278b29c2a74b52ec4aacfa0ecf80ed54a93f26e70e2`.
- Parent rules/data engine SHA256: `67f5357eab250dcda9a2e2659c32e8dd85f8ddb9a4c057d5d31f6d2e2ca8d3c2`.
- Broker metadata SHA256: `cb91a0bf24d7903c582252c4141c8f64e79ea8aea469526f15f52ddfa6c70423`.
- Variant method: `SOURCE-HYPOTHESIS-M1-M5-RETEST-INTRADAY-V2`.
- Volume provenance: `UNKNOWN_SOURCE_VOLUME; S2 CONDITIONAL`. Raw vendor/broker provenance is
  not independently certified; this is not authenticated account historical tick evidence.

- `GoldTripleDemo.mq5`: `11b3499def32ce5bd8e9023beec9f39e5aa7695bf3900306980bad45d364cffc`.
- `RiskCore.mqh`: `a44a3bdf8fb08248f527d134a65ddd717a514ec49943257312326f15f98dbeec`.
- `S1Core.mqh`: `dc6eb999792470bb787b01248e0abfc05d7a3990059595663e14a17e34458f9a`.
- `S2Core.mqh`: `1a143d7464541e2aa566e807f861eeb43f498d6448c00fa71291a321b7f97d1a`.
- `S3Core.mqh`: `df040f75d9529a4977aaa8cc0cb82f2702f8f8a78bf20163e47090cd3147260c`.

Tactical signal counts by lookback: `{"(300, 1)": [291, 140, 548], "(300, 3)": [291, 140, 548], "(60, 1)": [640, 279, 1155], "(60, 3)": [640, 279, 1155]}`.
Output identity: selected.json `a4e69c897060836ee952797d4b709e94c1184c2695a10c42ab6a18549ef87dcd`;
search.csv `3d76057ccefbded8bbbdcaad5160b4bc1a3758ff0ddf0336935f18e747d286f3`. The renderer rejects changed engines/metadata
or partial capital/strategy outputs. Original data and native source remain unchanged.

![Selected later-period equity and daily-close drawdown](../../reports/small-account-research/small-account-equity.png)

Artifacts: `reports/small-account-research/search.csv`, `selected.json`, `quality.json`,
`broker-metadata.json`, selected `*-trades.csv`/`*-daily.csv`, source notes and this renderer.
Reproduce after the semantic tests with the existing isolated Python3.11 research
requirements, running `scripts/gold_triple_small_account.py` then this script. No new
production dependency is needed. This report does not independently rerun test/CI gates.

## Authoritative contract sources and remaining work

Official MetaQuotes [symbol properties](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants)
define minimumvolume/step, contract/ticksize/value and calculationmode. [OrderCalcProfit](https://www.mql5.com/en/docs/trading/ordercalcprofit)
provides current-account-currency estimates. [OrderCalcMargin](https://www.mql5.com/en/docs/trading/ordercalcmargin)
explicitly ignores existing positions/pendingorders. [OrderCheck](https://www.mql5.com/en/docs/trading/ordercheck)
provides the request preflight. None guarantees a fill or a hard loss cap. See the
agent-reach/Jina source notes for retrieved semantics; no broker-switch recommendation
or small-contract availability claim is made.

Before promotion: certify data/volume and historical costs; replay account-specific ticks;
verify MetaEditor tester parity; implement/version this tactical variant explicitly;
commission account-specific risk budgets, lot/grid/margin checks, reconciliation, loss
breakers and governed exits; price any carry gaps; gather prospective forward evidence.
The existing native EA's fixed-lot/fixed-dollar settings are not overwritten or accepted
as these research variants. ATS deterministic authorization remains necessary for every
governed order; agents receive no execution authority from this tuning exercise.
