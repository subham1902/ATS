# XAU-020: GoldTriple S3 H4-close retest

Definition: `gold_triple_s3_h4_close_retest`. Version: 1. Status: **RESEARCH**. Canonical instrument: XAUUSD. Direction: LONG. Horizon: INTRADAY.

A fully completed H4 candle must close above the prior ten H4 highs and above a rising EMA30 context. That candle's published **H4 CLOSE** is the retest level. The prior-ten-high threshold determines parent eligibility; it is not the tactical retest level. Within 90 minutes, a fully completed M5 candle must touch/reclaim the H4 close and have a bullish body. Admission uses the next observed quote during UTC 12:00–17:00 on Tuesday, Wednesday or Thursday.

The selected $1,000 historical variant uses the completed M5 retest low minus 0.1 M5 ATR, SL rounded downward, 2R TP rounded downward toward entry on the broker grid, no optional break-even/trail and target holding 120 minutes with UTC intraday expiry. Planned stop-and-cost risk ceiling is 1.5% balance, further constrained by remaining 2.5% daily/6% monthly admission budgets. Round down lots and reject below the observed minimum; do not shorten the required stop to force a trade.

Five later trades in each scenario make this a sparse research hypothesis. STRESS changes lot sizes/admission and is not an identical-trade fee test. This documentation/index confers no execution authority or approved evidence. No automatic promotion is permitted.
