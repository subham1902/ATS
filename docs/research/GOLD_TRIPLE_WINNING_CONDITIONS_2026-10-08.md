# GoldTriple: conditional small-account research results

Date: October 8, 2026 (Asia/Calcutta). Status: HISTORICAL RESEARCH; native implementation and commissioning pending.

The expanded search found two **$1,000 standalone historical candidates**: S3 under a Tuesday–Thursday UTC afternoon filter, and a very marginal S2 under a UTC afternoon filter. No combined S1/S2/S3 portfolio passed the later-period sample requirement at $500, $750 or $1,000. S1 had no eligible condition at any balance. These results supersede the earlier search's practical conclusion for the newly expanded settings; the earlier report remains an accurate checkpoint for its smaller search.

S3 is the stronger research lead, with only five later-period trades per cost scenario. S2's stressed six-month gain is approximately **$0.16**, too small to support a practical edge claim. Neither result establishes future profitability, a calibrated probability, native-EA parity, or readiness for real-money execution.

## Outcome for every balance and strategy

| Initial balance | S1                    | S2                                     | S3                                        | S1/S2/S3 portfolio           |
| --------------- | --------------------- | -------------------------------------- | ----------------------------------------- | ---------------------------- |
| $500            | NO_ELIGIBLE_CONDITION | NO_ELIGIBLE_CONDITION                  | NOT_READY: BASE loses; three later trades | NO_ELIGIBLE_CONDITION        |
| $750            | NO_ELIGIBLE_CONDITION | NO_ELIGIBLE_CONDITION                  | NOT_READY: four later trades              | NOT_READY: zero later trades |
| $1,000          | NO_ELIGIBLE_CONDITION | HISTORICAL_FORWARD_CANDIDATE; marginal | HISTORICAL_FORWARD_CANDIDATE; sparse      | NOT_READY: one later trade   |

`NO_ELIGIBLE_CONDITION` means no condition cleared this bounded training/validation process, not that the strategy is universally impossible. `HISTORICAL_FORWARD_CANDIDATE` requires BOTH later BASE and STRESS runs to have positive booked return, at least five closed trades, and no requested booked-loss cap breach. It is a research flag, not execution authority or a claim of prospective validation. Zero trades are retained as insufficient evidence.

## Exact selected settings

All selected configurations use fully completed **M5 tactical retests** of their source hypothesis. The expanded candidate risk percentages are larger than the prior 0.5–1% search; they are not the earlier preset relabeled.

| Balance | Strategy mask | Admission condition | Per-entry risk ceiling | Target | Structural lookback | Optional protection | Planned maximum holding |
| ------- | ------------- | ------------------- | ---------------------- | ------ | ------------------- | ------------------- | ----------------------- |
| $500    | S3            | NY_TUE_THU          | 1.50%                  | 1.5R   | One M5 bar          | Enabled             | 120 minutes             |
| $750    | S3            | NY_TUE_THU          | 1.50%                  | 1.5R   | One M5 bar          | Enabled             | 120 minutes             |
| $750    | Portfolio     | SPREAD_035          | 1.25%                  | 2R     | Three M5 bars       | Disabled            | 240 minutes             |
| $1,000  | S2            | NEW_YORK            | 1.25%                  | 2R     | Three M5 bars       | Disabled            | 240 minutes             |
| $1,000  | S3            | NY_TUE_THU          | 1.50%                  | 2R     | One M5 bar          | Disabled            | 120 minutes             |
| $1,000  | Portfolio     | SPREAD_035          | 1.25%                  | 3R     | One M5 bar          | Disabled            | 240 minutes             |

Condition meanings are exact UTC research labels:

- `NEW_YORK`: entry quote hour 12:00 ≤ UTC time < 17:00 on otherwise admissible days.
- `NY_TUE_THU`: the same UTC window, restricted to Tuesday, Wednesday and Thursday.
- `SPREAD_035`: observed quote-open Ask minus Bid ≤ $0.35/oz, before the stress surcharge.

These fixed UTC labels do not claim exact New York daylight-saving session boundaries. The native strategy must preserve the explicitly chosen UTC rules or undergo a new test when changing them.

S1 retains the H1 breakout/H4 context hypothesis; S2 retains its M15 opening-range/H1 trend hypothesis and conditional source-volume filter; S3 retains its long-only H4 breakout/EMA context. Each new variant waits for a completed tactical candle to touch/reclaim the parent level. The candle body and close must agree with signal direction. The stop is the selected structural extreme plus 0.1 tactical ATR padding, rounded outward to the price grid. **The original wide stop is not truncated to fit small capital; this is a different entry/stop variant.** Required price distance below four current spreads, spread above $1.50/oz, adverse drift beyond 0.25 tactical ATR, expired parents and below-minimum risk-sized volume are rejected.

Parent-signal admission expires after 120 minutes for S1, 30 for S2 and 90 for S3. Trades enter at the next observed minute open. The target R is the initial price-stop distance ratio, before charges. The optional protection used only by the rejected $500/$750 selections locks 0.1 price R after an earlier observed close reaches +1R, then applies a 1.5 tactical ATR trail after +1.5R. This is not guaranteed net break-even. The $1,000 S2/S3 selections use fixed initial SL/TP and time/session exits, without that optional break-even/trail.

## Later-period results: March–August 2026

Returns, drawdown and worst booked losses are percentages; N is closed trades. Worst day/month includes intermediate postings, not just the final period balance. Drawdown is peak-to-trough marked equity at observed minute closes.

| Balance | Mask      | Cost   | N   | Net booked return % | Close-mark DD % | Worst day % | Worst month % | PF     |
| ------- | --------- | ------ | --- | ------------------- | --------------- | ----------- | ------------- | ------ |
| $500    | S3        | BASE   | 3   | -0.4205             | 1.6581          | -1.3073     | -1.1360       | 0.8272 |
| $500    | S3        | STRESS | 3   | 2.0152              | 1.6102          | -1.3485     | -0.0440       | 2.4451 |
| $750    | S3        | BASE   | 4   | 0.4540              | 1.4617          | -1.4617     | -1.4761       | 1.1811 |
| $750    | S3        | STRESS | 4   | 3.7613              | 1.2086          | -1.0235     | -0.0577       | 4.5054 |
| $750    | Portfolio | BASE   | 0   | 0.0000              | 0.0000          | 0.0000      | 0.0000        | N/A    |
| $750    | Portfolio | STRESS | 0   | 0.0000              | 0.0000          | 0.0000      | 0.0000        | N/A    |
| $1,000  | S2        | BASE   | 7   | 0.1923              | 4.4816          | -1.7283     | -2.7724       | 1.0521 |
| $1,000  | S2        | STRESS | 7   | 0.0159              | 4.6242          | -1.7986     | -2.8768       | 1.0042 |
| $1,000  | S3        | BASE   | 5   | 3.3295              | 1.5276          | -1.4619     | -1.3919       | 2.1381 |
| $1,000  | S3        | STRESS | 5   | 6.5215              | 1.5322          | -1.4885     | -0.0433       | 5.0519 |
| $1,000  | Portfolio | BASE   | 1   | 2.5085              | 0.7789          | -0.0110     | -0.0110       | N/A    |
| $1,000  | Portfolio | STRESS | 1   | 2.5090              | 0.7824          | -0.0220     | -0.0220       | N/A    |

No selected later BASE/STRESS run breached the requested 3% daily or 8% monthly net-booked thresholds. This is a historical observation, not a guarantee. The two standalone candidates cannot simply be added: the selected portfolio uses different shared settings and competing entries, and it has insufficient later trades.

### Why the larger S3 stress return needs care

STRESS reruns sizing, admission and targets under changed prices/costs; it does not apply a fee haircut to an identical trade ledger. At $1,000, S3 has five trades in each scenario, but only **four entry timestamps match**. On August 4, BASE enters at 16:30 UTC and loses $13.925; STRESS rejects that admission and enters at 16:45 UTC, winning $18.92. Lots also differ. The +6.5215% stress result therefore includes a different path of admitted trades and cannot be interpreted as the same five trades becoming more profitable despite higher costs. Price-distance-based R targets can also change when the executable entry moves.

S2 has the same seven entry timestamps and 0.01 lot sizes in both later scenarios. Its STRESS aggregate gain is $0.1595 on $1,000, with PF approximately 1.0042 and 4.6242% close-mark drawdown. Small errors in commissions, slippage or feed reconstruction could remove that gain. The seven-trade sample does not establish a repeatable edge.

## Full 24-month descriptive results

These figures include the training/selection periods and are **selection-contaminated descriptive evidence**, not an out-of-sample profitability claim.

| Balance | Mask      | Cost   | N   | Net booked return % | Close-mark DD % | Worst day % | Worst month % |
| ------- | --------- | ------ | --- | ------------------- | --------------- | ----------- | ------------- |
| $500    | S3        | BASE   | 38  | 7.5290              | 4.9338          | -1.4838     | -2.5934       |
| $500    | S3        | STRESS | 32  | 13.2972             | 4.3615          | -1.4165     | -2.3640       |
| $750    | S3        | BASE   | 42  | 13.2748             | 4.3486          | -1.4956     | -2.1334       |
| $750    | S3        | STRESS | 36  | 19.8619             | 4.6264          | -1.3802     | -2.2124       |
| $750    | Portfolio | BASE   | 24  | 4.7191              | 4.2059          | -2.0987     | -1.9285       |
| $750    | Portfolio | STRESS | 23  | 4.4461              | 3.6498          | -2.2666     | -2.1748       |
| $1,000  | S2        | BASE   | 71  | 24.0382             | 5.7211          | -1.8360     | -3.0820       |
| $1,000  | S2        | STRESS | 66  | 12.0377             | 6.6639          | -1.7916     | -3.2191       |
| $1,000  | S3        | BASE   | 42  | 17.9044             | 6.4432          | -1.4835     | -2.5699       |
| $1,000  | S3        | STRESS | 36  | 30.7969             | 5.0696          | -2.2935     | -3.6049       |
| $1,000  | Portfolio | BASE   | 23  | 19.0062             | 4.3559          | -1.1863     | -2.2282       |
| $1,000  | Portfolio | STRESS | 23  | 11.1971             | 5.4385          | -1.2510     | -4.6017       |

## Loss budget, account compatibility and costs

The requested definition is **net realized/booked P&L divided by start-of-period equity**; profits offset losses. Day and calendar month use UTC. Opening equity uses the previous observed mark; no midnight quote is fabricated. Initial requested day/month budgets are $15/$40 at $500, $22.50/$60 at $750, and $30/$80 at $1,000.

The engine admits entry risk against the strictest of the selected balance-percentage ceiling, remaining 2.5% daily allowance and remaining 6% monthly allowance. Stop price loss and round-trip modeled charges enter lot sizing. It rounds DOWN to 0.01 steps, rejects below 0.01, and caps lots at 0.10. There is at most one open position across the portfolio, at most three entries/day, a pause after two losing trades/day, one entry per parent signal and a 15-minute post-exit cooldown. New risk is blocked when allowance is exhausted. A $1,000 S3 ceiling is initially $15, while S2 is $12.50; remaining day/month budgets can reduce either below that amount. The native implementation must reproduce these controls explicitly; these files do not install a loss breaker.

Read-only current MT5 metadata records a 100-unit contract, 0.01 minimum/step, 0.01 price tick and USD account/profit currency. Observed leverage is 100:1 and SDK-estimated buy margin for 0.01 lot was $41.23 at Ask 4122.85 on 2026-10-08 12:36:14 UTC. The experiment models 100:1 in BASE and 50:1 in STRESS, with at most 30% of balance committed to margin. This is a current-metadata assumption applied to history, not proof of historical broker margin conditions. Higher leverage does not reduce the monetary loss of a given price move. Official [symbol properties](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants), [OrderCalcProfit](https://www.mql5.com/en/docs/trading/ordercalcprofit), [OrderCalcMargin](https://www.mql5.com/en/docs/trading/ordercalcmargin) and [OrderCheck](https://www.mql5.com/en/docs/trading/ordercheck) describe the required runtime checks; no brokerage or smaller-contract availability is endorsed.

BASE uses observed paired Bid/Ask spread plus modeled $22/lot round-trip charges ($7 commission and $15 slippage proxy). STRESS widens spread 1.5 times and charges $44/lot. Charges are half at entry/exit. These are explicit assumptions, not an audited tariff. Longs enter Ask and exit Bid; shorts reverse. Stop/target orders are active in the entry minute; if both are touched within a minute, stop is first. Adverse stop gaps fill at the observed executable open; favorable target gaps fill conservatively at target. Same-minute intrabar proceeds cannot fund an entry at an earlier open.

Time/session exits fill only when another observed quote exists. All selected expanded-search ledgers were checked: **no UTC date crossings and no holdings beyond their configured target** were recorded. Candidate S3 later maximum holding was 120 minutes; S2 was 130 minutes against a 240-minute target. No overnight financing was charged in this intraday model. Future missing quotes could delay exits or cross rollover and need a separately evidenced cost treatment. No partial fills, latency queues, broker stop/fill rejection, market depth, historical leverage changes or outage reconciliation are modeled. Gaps can still exceed a reservation and the requested caps; booked loss and floating drawdown are different measures.

## Search design and reuse of the data

TRAIN is September 2024–August 2025; VALIDATION is September 2025–February 2026; later TEST is March–August 2026. Indicators use earlier observations; cash and positions reset at evaluation boundaries.

The prior M1/M5 timing search supplied six top training configurations per balance/mask with at least ten trades, scored by equity return minus twice close-mark drawdown. The expansion cloned these shapes at 1.25%, 1.5% and 2% risk, then applied nine observable entry filters: LONDON, NEW_YORK, OVERLAP, TUE_THU, NO_FRIDAY, SPREAD_035, SPREAD_060, LONDON_LOW_SPREAD and NY_TUE_THU. There were 3,888 actual TRAIN rows across both costs, including repeated geometries: 3,510 unique full parameter/condition/cost keys. They are not 3,888 independent hypotheses.

Training admission requires BOTH cost scenarios positive with at least ten trades and no cap breach. The top five use the minimum BASE/STRESS return-minus-two-drawdown score. Validation requires both scenarios positive with at least three trades and no cap breach; it selects by the same worst-cost score. The selected later-period grade requires both positive with at least five trades and no cap breach. The file contains 94 VALIDATION rows, 12 TEST rows and 12 FULL rows. Some selected return/drawdown scores remain negative; they are the best admissible scores among this shortlist, not evidence of a globally optimal setting.

The expansion followed inspection of prior unsuccessful searches on the same data. The later period was already exposed. Calling it TEST identifies its chronological role; it is **not an untouched holdout** or prospective forward result. There is no multiple-testing adjustment, confidence interval, calibrated success probability or proof that the chosen weekday/session condition generalizes. A new prospective dataset and account-specific tick replay are required.

## Provenance and immutable evidence

- 711,286 paired XAUUSD M1 Bid/Ask rows, September 1, 2024 22:00 UTC–August 31, 2026 23:59 UTC.
- Explicit UTC, ascending unique timestamps, positive valid OHLC, no crossed OHLC fields; 538 gaps over one minute. Missing prices were not filled.
- Original inputs remain in `D:\Projects\ATS\ATS trade data`; source vendor/broker is not independently certified. This is not authenticated terminal tick-history evidence.
- Supplied numeric volume provenance is UNKNOWN. S2 remains conditional on that field; it is not certified real volume, MT5 tick-volume parity or a global XAUUSD footprint.
- Bid SHA256: `95b8c21d46fc8e064bb114b48363c5bdc366d08e5b2ccf581c46b94cba530a80`.
- Ask SHA256: `5e3217a2b9a8d322938d09dfba3602d8b5bcb056494d7873fe469aaa42bd9dcf`.
- Expanded condition engine SHA256: `9e2997a706cd604b3a813e6c4ec58893bddd86a25fa5cf6ffd553ce6aa67b7b4`.
- Tactical engine SHA256: `f03068045d3966a944b6a278b29c2a74b52ec4aacfa0ecf80ed54a93f26e70e2`.
- Preserved original GoldTripleDemo main SHA256: `11b3499def32ce5bd8e9023beec9f39e5aa7695bf3900306980bad45d364cffc`; source-core hashes and broker metadata hash are in the [earlier tactical audit](GOLD_TRIPLE_SMALL_ACCOUNT_2026-10-08.md).
- Expanded `selected.json` SHA256: `596dea46fc983076b6e0f6452d2ec043f6ab686b0dd070c99ded3ea1be2faad6`.
- Expanded `search.csv` SHA256: `6ebf416d98b1d5e4f96cfe8afbce38fc279db12771773eeb0eb1291dcfa8d2e7`.
- Expanded `quality.json` SHA256: `45e402b7996794b2a98d1697d27d1f2848cebcc5e7d67a80410338ee4a9157f8`.

Artifacts reside in `reports/small-account-research/conditions-expanded-risk/`: all search rows, selection/quality JSON and selected trade/daily ledgers. Exact complete parameter dictionaries identify candidates; the reused numeric config index alone is insufficient after risk expansion. No broad search was rerun for this report; figures and ledger checks derive from those completed files.

## Frozen broker-target-grid verification and canonical lineages

The original expanded-search metrics above remain unchanged. A separate V3 verification reran only the frozen $1,000 S2/S3 settings with `snap_target=true`, rounding TP toward entry on the observed 0.01 price tick. No parameter search or account action was performed by that verifier. Exact artifacts are `reports/small-account-research/deployment-verification/{selected,quality}.json`, method `SELECTED-PRESET-BROKER-TARGET-GRID-V3`; native physical parity is still `NOT_ESTABLISHED` and `pristine_holdout=false`.

| Canonical lineage | Later cost | N   | Grid-verified return % | Close-mark DD % | Worst day % | Worst month % |
| ----------------- | ---------- | --- | ---------------------- | --------------- | ----------- | ------------- |
| XAU-019 / S2      | BASE       | 7   | 0.1913                 | 4.4816          | -1.7283     | -2.7724       |
| XAU-019 / S2      | STRESS     | 7   | 0.01495                | 4.6242          | -1.7986     | -2.8768       |
| XAU-020 / S3      | BASE       | 5   | 3.3280                 | 1.5277          | -1.4619     | -1.3919       |
| XAU-020 / S3      | STRESS     | 5   | 6.51925                | 1.5322          | -1.4885     | -0.0433       |

The snapped S2 stressed gain is approximately $0.1495 on $1,000. Both historical flags remain candidates only; target rounding does not resolve small samples, changed stress admissions, costs/volume provenance or prospective validation.

Verification `selected.json` SHA256: `5b925e6f2d38ff027815d711586edc056dc29098beb8c299406223cddf18bfa9`; `quality.json` SHA256: `eb1f969034cd97301fc696d3219cf04fbb6cc61d0e1e9484141500afca8038d4`. The quality record binds verifier `0c55110d318bf7aaf65b060d3cf3bf60d3f313769232e8efff749bd895bfdb40`, replay `c40c970251e1f180789ca821af8dbf73222ea6ee82404cc51fcb5fd2b2b94a7b`, original selected configuration and raw-data hashes.

Three immutable definitions now have documentation workspaces: [XAU-018](../../strategies/XAU-018/STRATEGY.md) `gold_triple_s1_intraday_retest`, [XAU-019](../../strategies/XAU-019/STRATEGY.md) `gold_triple_s2_intraday_retest`, and [XAU-020](../../strategies/XAU-020/STRATEGY.md) `gold_triple_s3_h4_close_retest`. All retain canonical **RESEARCH** status and empty authority-bearing evidence arrays. The S3 tactical retest is explicitly the completed breakout H4 candle's **CLOSE**; the prior-ten-high threshold is parent qualification, not its retest price. S2 similarly retests its published M15 signal close. This documentation/index projection neither changes a durable strategy database nor automatically promotes a lineage or authorizes execution.

## Implementation status and acceptance still required

This report establishes the research checkpoint only. Native implementation, compilation, tester parity, terminal attachment, live permission observations and any actual broker execution must be documented separately from the completed backtest. A source file or installed EA is not proof that ATS controls or authorizes its orders.

Priorities are the $1,000 S3 variant as a cautious demo research lead and S2 as conditional, marginal comparison evidence. Do not enable rejected $500/$750 settings or infer that independently selected S2 and S3 form a validated portfolio. Preserve all rejected and no-trade outcomes.

Before promotion: version the new source-hypothesis variants explicitly; verify parent/tactical ATR, UTC sessions, risk-sizing, SL/TP and exit parity on actual broker ticks; certify historical costs and S2 volume; enforce start-of-period booked-loss budgets and deterministic account authorization; commission reconciliation and gap/rollover handling; collect prospective forward evidence. No execution request, account setting, terminal action or order was performed while producing this report.
