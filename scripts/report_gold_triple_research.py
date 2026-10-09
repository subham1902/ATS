"""Render local backtest evidence; does not change any terminal settings."""

import hashlib
import json
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "risk-research"


def table(frame, columns):
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for _, row in frame.iterrows():
        values = []
        for c in columns:
            v = row[c]
            values.append(f"{v:.2f}" if isinstance(v, float) else str(v))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main():
    quality = json.loads((OUT / "quality.json").read_text())
    selected = pd.read_json(OUT / "selected.json")
    search = pd.read_csv(OUT / "search.csv")
    tests = selected[selected["split"].eq("TEST")].copy()
    full = selected[selected["split"].eq("FULL")].copy()
    tests["risk_pct"] = tests.risk * 100
    tests["combined_risk_pct"] = tests.maxrisk * 100
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, constrained_layout=True)
    monthly_rows = []
    for capital in (10000, 100000):
        for cost in ("BASE", "STRESS"):
            f = pd.read_csv(
                OUT / f"{capital}-PORTFOLIO-FULL-{cost}-daily.csv", index_col=0, parse_dates=True
            )
            axes[0].plot(f.index, (f.equity / capital - 1) * 100, label=f"${capital:,} {cost}")
            peak = f.equity.cummax().clip(lower=capital)
            axes[1].plot(f.index, (f.equity / peak - 1) * 100, label=f"${capital:,} {cost}")
            if cost == "BASE":
                mon = f.resample("MS").last()
                baseline = mon.equity.shift().fillna(capital)
                pnl = mon.balance.diff()
                pnl.iloc[0] = mon.balance.iloc[0] - capital
                for time, pct in (pnl / baseline * 100).items():
                    monthly_rows.append(
                        dict(account=capital, month=str(time.date()), booked_return_pct=pct)
                    )
    axes[0].set_ylabel("Modeled equity return (%)")
    axes[1].set_ylabel("Daily-close drawdown (%)")
    for ax in axes:
        ax.axvline(pd.Timestamp("2026-03-01", tz="UTC"), color="black", linestyle="--", alpha=0.5)
        ax.grid(alpha=0.2)
    axes[0].legend(ncol=2)
    fig.suptitle("GoldTriple normalized-risk research proxy — not broker execution evidence")
    fig.savefig(OUT / "portfolio-equity.png", dpi=170)
    plt.close(fig)
    pd.DataFrame(monthly_rows).to_csv(OUT / "portfolio-monthly.csv", index=False)
    diagnostics = []
    for capital in (10000, 100000):
        for cost in ("BASE", "STRESS"):
            t = pd.read_csv(OUT / f"{capital}-PORTFOLIO-FULL-{cost}-trades.csv")
            for s, group in t.groupby("strategy"):
                peak_r = group.observed_close_mfe / group.initial_risk
                capture = group.net_ex_financing / group.observed_close_mfe.replace(0, float("nan"))
                diagnostics.append(
                    dict(
                        account=capital,
                        cost=cost,
                        strategy=f"S{int(s)}",
                        trades=len(group),
                        peak_at_least_1R=int((peak_r >= 1).sum()),
                        high_giveback=int(((peak_r >= 1) & (capture < 0.6)).sum()),
                        winner_capture_pct=float(capture[group.net_ex_financing > 0].mean() * 100),
                    )
                )
    pd.DataFrame(diagnostics).to_csv(OUT / "exit-diagnostics.csv", index=False)
    current = (
        search[search.account.eq(1000) & search["split"].eq("TRAIN")]
        .groupby("strategy")
        .trades.agg(["min", "max"])
        .reset_index()
    )
    cols = [
        "account",
        "strategy",
        "cost",
        "trades",
        "realized_return_pct",
        "max_drawdown_pct",
        "worst_day_pct",
        "worst_month_pct",
    ]
    diagnostic_columns = [
        "account",
        "strategy",
        "cost",
        "trades",
        "peak_at_least_1R",
        "high_giveback",
        "winner_capture_pct",
    ]
    text = f"""# GoldTriple S1 / S2 / S3 risk and exit research

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

- Original files read from `D:\\Projects\\ATS\\ATS trade data`; no source or EA was overwritten.
- Bid SHA256: `{quality["hashes"]["bid"]}`.
- Ask SHA256: `{quality["hashes"]["ask"]}`.
- EA main SHA256: `{quality["source_hashes"]["GoldTripleDemo.mq5"]}`.
- Research engine SHA256: `{quality["engine_hash"]}`.
- {quality["rows"]:,} paired rows, {quality["start"]} through {quality["end"]}.
- Explicit UTC, ascending unique timestamps, finite positive prices, valid OHLC,
  nonnegative source volume, zero crossed fields. {quality["gaps_over_one_minute"]} gaps >1 minute.
  Gaps are not price-filled; expected closures and unexpected outages are not fully distinguished.
- The supplied source's broker/vendor provenance is not independently certified.
  This is not the connected MetaQuotes account's historical tick record.
- Volume provenance is UNKNOWN. S2's numeric volume filter is applied to the supplied
  field conditionally; it is not claimed to be real volume or identical to MT5 tick volume.
- Source-rule signals: S1 {quality["signals"]["S1"]}, S2 {quality["signals"]["S2"]},
  S3 {quality["signals"]["S3"]}.

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
- {search[search["split"].eq("TRAIN")].shape[0]} training evaluations across three capital
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

| Setting | Research candidate |
| --- | --- |
| Hard monitoring limits | 3% daily / 8% calendar monthly net booked loss |
| Internal risk admission floors | 2.7% daily / 7% monthly |
| Planned risk per entry | 1% of balance, including stop distance and modeled costs |
| Combined outstanding risk | 2%, remaining daily/monthly allowance also enforced |
| Concurrent positions | At most 3; one per strategy |
| New-entry priority | S1, then S2, then S3; shared reservation prevents oversubscription |
| Lot rule | Round down; reject below broker minimum |
| Margin model | 100-ounce contract / explicit 9:1 leverage, at most80% balance committed |
| Loss allowance | Reserve existing stops + exit costs before admitting more risk |
| Breach handling | Block new entries when budget exhausted; no guaranteed forced flatten |

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

{table(tests, cols)}

## Full 24-month descriptive results (include selection data)

{table(full, cols)}

Full-period results are selection-contaminated descriptive evidence, not a profitability claim.

## $1,000 feasibility

Training trade counts across the searched settings:

{table(current, ["strategy", "min", "max"])}

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

{table(pd.DataFrame(diagnostics), diagnostic_columns)}

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
"""
    report = ROOT / "docs" / "research" / "GOLD_TRIPLE_RISK_BACKTEST_2026-10-08.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(text, encoding="utf-8")
    preset = dict(
        status="RESEARCH_ONLY",
        current_account_eligibility="BLOCKED_NO_ELIGIBLE_CONFIGURATION",
        execution_enabled=False,
        canonical_symbol="XAUUSD",
        equity_reference="START_OF_PERIOD",
        booked_loss_definition="NET_REALIZED",
        timezone="UTC",
        daily_loss_cap=0.03,
        monthly_loss_cap=0.08,
        daily_admission_budget=0.027,
        monthly_admission_budget=0.07,
        hypothetical_portfolio_candidate=dict(
            risk_per_trade=0.01,
            combined_open_risk=0.02,
            max_positions=3,
            exit_profile="ORIGINAL",
            valid_account_sizes=[10000, 100000],
        ),
        source_hashes=quality["hashes"],
        engine_hash=quality["engine_hash"],
    )
    (OUT / "research-preset.json").write_text(json.dumps(preset, indent=2))
    manifest = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in OUT.iterdir()
        if p.is_file() and p.name != "manifest.json"
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(report)


if __name__ == "__main__":
    main()
