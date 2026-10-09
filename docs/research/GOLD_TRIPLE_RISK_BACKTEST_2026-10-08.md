# GoldTriple S1 / S2 / S3 risk and exit research

Date: October 8, 2026 (Asia/Calcutta). Status: RESEARCH_ONLY / NOT DEPLOYED.

## Decision

No validated execution preset was found for the current $1,000 account. S1 and S3 cannot
trade within the searched 0.25–1% risk budgets using the observed 0.01 minimum lot.
S2 can trade at some training settings but no configuration meets the predeclared
training and validation trade-count admissions. Do not bypass lot or risk limits.

For hypothetical $10,000 and $100,000 accounts, the selected combined-portfolio candidate
uses 1% planned stop-and-cost risk per entry, 2% combined open risk, one position per
strategy, and the ORIGINAL exit profile. This is the best candidate under this bounded
search's score, not a globally optimal setting or an instruction to increase account capital.
The final six-month stress sample remains positive for the combined portfolio. Some
individual strategies do not; see the tables. Historical limits were respected in the
selected runs, but a synthetic adverse-gap test demonstrates that they can be exceeded.

## Inputs and immutable identity

- Original files read from `D:\Projects\ATS\ATS trade data`; no source or EA was overwritten.
- Bid SHA256: `95b8c21d46fc8e064bb114b48363c5bdc366d08e5b2ccf581c46b94cba530a80`.
- Ask SHA256: `5e3217a2b9a8d322938d09dfba3602d8b5bcb056494d7873fe469aaa42bd9dcf`.
- EA main SHA256: `11b3499def32ce5bd8e9023beec9f39e5aa7695bf3900306980bad45d364cffc`.
- Research engine SHA256: `67f5357eab250dcda9a2e2659c32e8dd85f8ddb9a4c057d5d31f6d2e2ca8d3c2`.
- 711,286 paired rows, 2024-09-01 22:00:00+00:00 through 2026-08-31 23:59:00+00:00.
- Explicit UTC, ascending unique timestamps, finite positive prices, valid OHLC,
  nonnegative source volume, zero crossed fields. 538 gaps >1 minute.
  Gaps are not price-filled; expected closures and unexpected outages are not fully distinguished.
- The supplied source's broker/vendor provenance is not independently certified.
  This is not the connected MetaQuotes account's historical tick record.
- Volume provenance is UNKNOWN. S2's numeric volume filter is applied to the supplied
  field conditionally; it is not claimed to be real volume or identical to MT5 tick volume.
- Source-rule signals: S1 234, S2 106,
  S3 266.

## Strategy audit and research changes

S1: completed H1 breakout with H4 efficiency/momentum, volatility expansion, UTC
06:00–20:00 admission, structural/ATR stop, $50/oz target, $30/oz favorable-move trigger
locking $10/oz on the next minute, failed-breakout exit after six hours, and one-week
cooldown after two net losing trades. The source's $39.78/oz maximum initial distance
is retained, but its fixed 0.50 lot is replaced by risk-based sizing for this experiment.

S2: completed M15 opening-range breakout, completed H1 EMA50/EMA200 context, slope,
stretch and source-volume filter. UTC entry window 12:30–16:00, spread <=$1.50/oz,
signal-price drift <=0.25 ATR. Initial stop is max(1.2 ATR, structural distance),
minimum $3/oz, original target 2R, exit at first observed quote at/after 17:30 UTC.

S3: long-only strict 240-observed-minute H4 bars, prior-ten-high breakout with
EMA30 and positive ten-bar EMA slope, 90-minute observed-quote admission window,
2 ATR initial stop, 3 ATR completed-bar trail and prior-five-low channel exit.

S1/S3 ATR uses SMA-seeded Wilder smoothing matching their MQL cores. S2 intentionally
retains its FIRST-TR-seeded source smoothing. The old supplied S3 Python backtester
used the latter seed and was not reused as validation authority.

The original EA's fixed dollar risk floors, Prague daily loss rules, 75-day terminal
readiness gate and broker order engine are not reproduced as-is. This is an explicitly
normalized-risk variant with indicator warmup, UTC risk periods and source-inspired exits.
It has not passed terminal tick parity or MetaEditor strategy-tester parity.

## Search and chronological separation

- TRAIN: September 2024–August 2025; VALIDATION: September 2025–February 2026;
  later-period TEST: March–August 2026.
- Indicators use earlier observed history; portfolio positions/cash reset per evaluation split.
- Risk candidates: 0.25%, 0.50%, 0.75%, 1.00%. Combined risk: 0.75%, 1.50%, 2.00%.
- Three exit profiles: original (S1 target50/trigger30, S2 target2R, S3 trail3ATR);
  tighter (40/25,1.5R,2ATR); looser (60/35,2.5R,4ATR). S1 lock remains10.
- 396 training evaluations across three capital
  sizes and four strategy masks. Sizing is rounded DOWN to 0.01, max100 lots.
- Top five feasible training configurations by equity return minus 1.5 times drawdown
  go to validation. At least ten training and three validation trades required.
  Validation chooses the same score; later-period results are not used to choose parameters.
- These files and strategies were previously researched; TEST is a chronological later
  period, not a certified untouched holdout. No multiple-testing correction or empirical
  probability calibration is claimed.

## Loss policy and candidate limits

User definition: net booked P&L, profits offset losses, divided by start-of-day/month equity.
Day/month use UTC. The opening equity is estimated from the last observed prior quote
mark; no unobserved midnight quote is invented. Deposits/withdrawals are not modeled.

| Setting                        | Research candidate                                                       |
| ------------------------------ | ------------------------------------------------------------------------ |
| Hard monitoring limits         | 3% daily / 8% calendar monthly net booked loss                           |
| Internal risk admission floors | 2.7% daily / 7% monthly                                                  |
| Planned risk per entry         | 1% of balance, including stop distance and modeled costs                 |
| Combined outstanding risk      | 2%, remaining daily/monthly allowance also enforced                      |
| Concurrent positions           | At most 3; one per strategy                                              |
| New-entry priority             | S1, then S2, then S3; shared reservation prevents oversubscription       |
| Lot rule                       | Round down; reject below broker minimum                                  |
| Margin model                   | 100-ounce contract / explicit 9:1 leverage, at most80% balance committed |
| Loss allowance                 | Reserve existing stops + exit costs before admitting more risk           |
| Breach handling                | Block new entries when budget exhausted; no guaranteed forced flatten    |

All booked-loss minima are checked after cost and exit postings, including intermediate
postings within a minute. Loss at a breached stop can exceed its reservation. Daily/monthly
net booked loss is different from floating equity drawdown and from gross losing trades.
An account can respect monthly booked loss and still exceed 8% peak-to-trough equity drawdown.
Daily/monthly breakers, broker reconciliation and emergency controls must be commissioned
before deploying this policy; research code is not an installed ATS risk controller.

## Fill and cost assumptions

- Observed paired Bid/Ask M1 OHLC, not ticks. Long entry Ask/exit Bid; short reverse.
- Completed-bar signals enter at the next observed bar open, never at the completed bar close.
- Minute-open admission freezes balances/reservations. Intrabar exits cannot finance entries
  at the same minute's open. Occupied strategies cannot re-enter on later intrabar information.
- Initial stops/targets are active in the entry minute. Both hit in one minute => stop first.
- Adverse gaps through an existing stop fill at the observed executable open. Favorable
  target gaps fill at the target conservatively. No invented quote path.
- BASE: observed spread plus $22/lot round trip ($7 commission + $15 slippage proxy),
  charged half each side. Overnight modeled debit $15/lot per observed UTC day transition,
  with a triple Wednesday carry charged on Thursday's first observed quote.
- STRESS: spread1.5x, round trip$44/lot, overnight$30/lot. These are modeled assumptions,
  not an audited historical commission/swap schedule. Exact broker holidays and rollover
  charge dates are not modeled; source gaps can make the financing proxy inaccurate.
- Trade ledger net excludes financing attribution; ACCOUNT returns/booked caps include
  the modeled financing debits. Profit factor is explicitly ex-financing.
- Partial fills, latency queues, stop-level rejection, variable leverage, market depth,
  broker outages and actual price-impact are not modeled. Close-mark drawdown is not
  tick-accurate or worst intrabar equity drawdown. No forced final liquidation.

## Final six-month results: independently selected individual strategies and portfolio

Figures are percentages except trades/account; standalone selections differ from portfolio
selection, so do not sum standalone returns. Worst day/month are minimum booked P&L during
the period, including intermediate losses, rather than only period-end results.

| account | strategy  | cost   | trades | realized_return_pct | max_drawdown_pct | worst_day_pct | worst_month_pct |
| ------- | --------- | ------ | ------ | ------------------- | ---------------- | ------------- | --------------- |
| 10000   | S1        | BASE   | 28.00  | 3.80                | 3.76             | -0.85         | -1.29           |
| 10000   | S1        | STRESS | 28.00  | 3.56                | 3.91             | -0.88         | -1.32           |
| 10000   | S2        | BASE   | 18.00  | 1.13                | 3.88             | -1.79         | -1.91           |
| 10000   | S2        | STRESS | 18.00  | 0.11                | 4.29             | -1.71         | -2.52           |
| 10000   | S3        | BASE   | 9.00   | 0.17                | 3.07             | -1.01         | -1.21           |
| 10000   | S3        | STRESS | 9.00   | 0.08                | 3.11             | -1.02         | -1.23           |
| 10000   | PORTFOLIO | BASE   | 58.00  | 9.85                | 3.58             | -1.10         | -2.38           |
| 10000   | PORTFOLIO | STRESS | 57.00  | 7.26                | 4.35             | -1.12         | -2.95           |
| 100000  | S1        | BASE   | 33.00  | 4.80                | 2.98             | -0.74         | -1.08           |
| 100000  | S1        | STRESS | 32.00  | 3.19                | 4.24             | -0.86         | -1.59           |
| 100000  | S2        | BASE   | 18.00  | 0.96                | 4.29             | -1.97         | -2.25           |
| 100000  | S2        | STRESS | 18.00  | -0.11               | 4.91             | -1.96         | -2.93           |
| 100000  | S3        | BASE   | 13.00  | -1.05               | 4.96             | -1.13         | -2.10           |
| 100000  | S3        | STRESS | 13.00  | -1.18               | 5.03             | -1.14         | -2.13           |
| 100000  | PORTFOLIO | BASE   | 62.00  | 9.56                | 5.32             | -1.28         | -2.31           |
| 100000  | PORTFOLIO | STRESS | 61.00  | 6.04                | 7.54             | -1.31         | -3.30           |

## Full 24-month descriptive results (include selection data)

| account | strategy  | cost   | trades | realized_return_pct | max_drawdown_pct | worst_day_pct | worst_month_pct |
| ------- | --------- | ------ | ------ | ------------------- | ---------------- | ------------- | --------------- |
| 10000   | S1        | BASE   | 102.00 | 22.41               | 4.74             | -1.07         | -3.07           |
| 10000   | S1        | STRESS | 101.00 | 19.14               | 4.79             | -1.14         | -3.06           |
| 10000   | S2        | BASE   | 97.00  | 15.67               | 4.88             | -1.96         | -3.48           |
| 10000   | S2        | STRESS | 91.00  | 10.89               | 4.76             | -1.97         | -2.89           |
| 10000   | S3        | BASE   | 65.00  | 25.73               | 3.30             | -0.87         | -1.02           |
| 10000   | S3        | STRESS | 67.00  | 22.60               | 3.43             | -0.89         | -1.07           |
| 10000   | PORTFOLIO | BASE   | 258.00 | 92.72               | 7.46             | -1.87         | -3.59           |
| 10000   | PORTFOLIO | STRESS | 251.00 | 72.61               | 7.94             | -1.86         | -3.70           |
| 100000  | S1        | BASE   | 106.00 | 18.74               | 4.07             | -0.83         | -2.49           |
| 100000  | S1        | STRESS | 105.00 | 15.69               | 4.21             | -0.87         | -2.54           |
| 100000  | S2        | BASE   | 97.00  | 18.18               | 4.96             | -1.98         | -3.59           |
| 100000  | S2        | STRESS | 91.00  | 12.88               | 4.92             | -1.99         | -2.95           |
| 100000  | S3        | BASE   | 68.00  | 33.45               | 5.25             | -1.14         | -2.16           |
| 100000  | S3        | STRESS | 70.00  | 28.02               | 5.17             | -1.12         | -2.13           |
| 100000  | PORTFOLIO | BASE   | 259.00 | 110.88              | 8.00             | -1.97         | -3.87           |
| 100000  | PORTFOLIO | STRESS | 252.00 | 85.91               | 8.57             | -1.98         | -3.94           |

Full-period results are selection-contaminated descriptive evidence, not a profitability claim.

## $1,000 feasibility

Training trade counts across the searched settings:

| strategy  | min | max |
| --------- | --- | --- |
| PORTFOLIO | 0   | 25  |
| S1        | 0   | 0   |
| S2        | 0   | 25  |
| S3        | 0   | 0   |

At $1,000, 1% is $10, the daily hard budget is initially $30 and monthly$80.
The minimum 0.01 lot costs approximately $1 per $1/oz adverse move before charges.
Typical S1/S3 stop distances require more than the $10 per-trade maximum. Increasing
the risk budget merely to buy the minimum lot would invalidate this research constraint.
There is no eligible combined three-strategy setting at this account size under the
predeclared sample-size admission. This does not prove S2 can never trade or that a
larger account will be profitable.

## Exit capture and profit protection

The portfolio selection retained the original exits at both larger research capitals;
tighter or looser exits did not produce the preferred validation score. Standalone
selections can differ. S1 targets are price distances, not account-dollar profits.

The following uses observed minute CLOSE excursions, plus the actual modeled exit mark.
It excludes favorable/adverse high/low marks whose ordering relative to exit cannot be known.
It is a lower-resolution diagnostic, not true tick MFE or proof of excellent entries.
High giveback means peak >=1 initial-risk R and net ex-financing capture <60%.

| account | strategy | cost   | trades | peak_at_least_1R | high_giveback | winner_capture_pct |
| ------- | -------- | ------ | ------ | ---------------- | ------------- | ------------------ |
| 10000   | S1       | BASE   | 105    | 46               | 15            | 70.11              |
| 10000   | S2       | BASE   | 97     | 39               | 10            | 66.87              |
| 10000   | S3       | BASE   | 56     | 36               | 31            | 41.07              |
| 10000   | S1       | STRESS | 104    | 45               | 14            | 71.18              |
| 10000   | S2       | STRESS | 91     | 35               | 9             | 65.89              |
| 10000   | S3       | STRESS | 56     | 36               | 31            | 40.71              |
| 100000  | S1       | BASE   | 106    | 46               | 15            | 69.39              |
| 100000  | S2       | BASE   | 97     | 39               | 10            | 66.87              |
| 100000  | S3       | BASE   | 56     | 36               | 31            | 41.07              |
| 100000  | S1       | STRESS | 105    | 45               | 14            | 70.41              |
| 100000  | S2       | STRESS | 91     | 35               | 9             | 65.89              |
| 100000  | S3       | STRESS | 56     | 36               | 31            | 40.71              |

Do not retrofit exits at historical peaks. Continue causal exit research and forward
Exit Watch observation, especially where high-giveback frequency is large. Changing
trails can improve capture on one path while increasing early exits on another.
No calibrated success probability, future return promise or strategy promotion is issued.
In the portfolio BASE runs, S3 had
31 high-giveback cases among 36 trades reaching at least1R on close marks, and winning
trades captured about41% of their observed favorable close excursions. This is the
clearest priority for further exit research, not proof that tightening trails improves
future portfolio returns.

## Verification and artifacts

Eight semantic tests passed: Wilder seed; adverse-gap fill and breach visibility;
same-bar stop-first ambiguity; minimum-lot rejection; no artificial final close;
financing at month rollover; entry-minute protection; no future-funded re-entry.
Ruff passed for research/test scripts. Production-wide/remote CI was not rerun for
this offline experiment; no new broker orders, account enablement or terminal edits.

- `reports/risk-research/search.csv`: every training/validation/test/full record.
- `selected.json`, `quality.json`: configurations, identities and quality.
- `*-trades.csv`, `*-daily.csv`: selected trade/marked equity evidence.
- `portfolio-monthly.csv`, `exit-diagnostics.csv`, `portfolio-equity.png`.
- `requirements.txt`: exact isolated research dependencies.
- `scripts/gold_triple_risk_research.py` and its semantic test script.

Reproduce with Python3.11, the isolated requirements and ATS_GOLD_TRIPLE_SOURCE pointing
to the unchanged EA source directory; run the semantic tests, research script, then this
report renderer. Original inputs are read only. No production dependency manifests changed.

## Preset change and remaining acceptance

The separate research preset records requested3%/8% limits and the portfolio1%/2%
candidate, but execution eligibility for the current account is BLOCKED. The existing
native EA remains unchanged: ATS's account risk profile is not automatically enforced
by that standalone EA. Its fixed .50-lot/$1,000/$550 settings are not safe substitutes
for this account-specific percentage policy.

Before execution: verify source volume/vendor, reproduce on broker-specific tick history,
test actual costs/rollover/margin/SLTP behavior, establish truly prospective validation,
compile a governed risk-aware strategy version and commission ATS account reconciliation,
loss breakers and execution authority. No setting can guarantee the stated caps through gaps.
