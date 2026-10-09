# XAU-019: GoldTriple S2 intraday retest

Definition: `gold_triple_s2_intraday_retest`. Version: 1. Status: **RESEARCH**. Canonical instrument: XAUUSD. Direction: BOTH. Horizon: INTRADAY.

A completed M15 opening-range breakout with H1 EMA context publishes a parent signal. The tactical retest level is that M15 signal candle's **close**, not an undocumented substitution for the opening-range boundary. Within 30 minutes, a fully completed M5 candle must touch/reclaim that level and close with a body in the signal direction. Admission uses the next observed quote, UTC 12:00–17:00 and the parent strategy's constraints.

The selected $1,000 historical variant uses three completed M5-bar structural extremes plus 0.1 M5 ATR, an outward-rounded SL, 2R TP rounded toward entry on the observed broker tick grid, no optional break-even/trail, target holding 240 minutes and first observed quote at/after 17:30 UTC expiry. Planned stop-and-cost risk ceiling is 1.25% of balance, further limited by remaining 2.5% daily/6% monthly admission budgets. Round down volume; reject below the broker minimum.

The source-volume filter is conditional: supplied volume semantics are UNKNOWN and have not been demonstrated equivalent to native MT5 tick volume. The recorded stressed later return is economically marginal. This directory/index is descriptive research documentation, not runtime evidence admission, account routing or execution authority. No automatic promotion is permitted.
