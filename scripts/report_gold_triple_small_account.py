"""Render completed small-account research evidence without touching execution settings.

Run after gold_triple_small_account.py with the existing isolated research environment.
No backtest, broker connection, preset mutation, terminal compile or order is performed.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "small-account-research"
REPORT = ROOT / "docs" / "research" / "GOLD_TRIPLE_SMALL_ACCOUNT_2026-10-08.md"
CAPITALS = (500, 750, 1000)
STRATEGIES = ("S1", "S2", "S3", "PORTFOLIO")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value: object, decimals: int = 2) -> str:
    if value is None or value == "":
        return "N/A"
    if isinstance(value, bool):
        return "YES" if value else "NO"
    try:
        parsed = float(str(value))
    except (TypeError, ValueError):
        return str(value).replace("|", "\\|")
    if not math.isfinite(parsed):
        return "N/A"
    return f"{parsed:.{decimals}f}"


def table(rows: list[dict], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return "No selected run exists for this table."
    result = [
        "| " + " | ".join(label for _, label in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        cells = []
        for key, _ in columns:
            value = row.get(key)
            cells.append(number(value) if not isinstance(value, str) else value.replace("|", "\\|"))
        result.append("| " + " | ".join(cells) + " |")
    return "\n".join(result)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def selected_rows(selected: list[dict], split: str) -> list[dict]:
    rows = []
    for item in selected:
        for result in item.get("results", []):
            if result["split"] == split:
                rows.append(dict(account=int(item["account"]), strategy=item["strategy"], **result))
    return rows


def both_cost_grade(item: dict) -> str:
    results = [result for result in item.get("results", []) if result["split"] == "TEST"]
    if {result["cost"] for result in results} != {"BASE", "STRESS"}:
        return "NO_SELECTED_RUN"
    if all(
        result["trades"] >= 5
        and result["realized_return_pct"] > 0
        and not result["daily_breach"]
        and not result["monthly_breach"]
        for result in results
    ):
        return "BOTH_COST_HISTORICAL_PASS_ONLY"
    return "FAILED_BOTH_COST_ACCEPTANCE"


def status_rows(selected: list[dict]) -> list[dict]:
    rows = []
    for item in selected:
        config_present = "config" in item
        rows.append(
            dict(
                account=int(item["account"]),
                strategy=item["strategy"],
                status=item["status"],
                both_cost_grade=both_cost_grade(item),
                risk_pct=item["risk"] * 100 if config_present else None,
                target_R=item.get("rr"),
                timing_minutes=item.get("bar_seconds", 300) / 60 if config_present else None,
                structure_bars=item.get("lookback"),
                protection="0.1R lock / 1.5 ATR trail"
                if item.get("protect")
                else ("NONE" if config_present else "N/A"),
                hold_minutes=item.get("hold"),
            )
        )
    return rows


def ledger_diagnostics(selected: list[dict], contract: float) -> list[dict]:
    rows = []
    for item in selected:
        if "config" not in item:
            continue
        for result in item["results"]:
            split, cost = result["split"], result["cost"]
            path = OUT / f"{int(item['account'])}-{item['strategy']}-{split}-{cost}-trades.csv"
            if not path.is_file():
                raise FileNotFoundError(f"Selected trade evidence missing: {path}")
            trades = read_csv(path)
            overnight = 0
            over_target = 0
            max_hold = 0.0
            net_r = []
            capture = []
            high_giveback = 0
            at_least_one_r = 0
            ambiguous = 0
            for trade in trades:
                entry = datetime.fromisoformat(trade["entry_time"])
                exit_time = datetime.fromisoformat(trade["exit_time"])
                if entry.tzinfo is None or exit_time.tzinfo is None:
                    raise ValueError("Ledger timestamps must carry timezone evidence")
                holding = (exit_time - entry).total_seconds() / 60
                if holding < 0:
                    raise ValueError("Ledger exit precedes entry")
                max_hold = max(max_hold, holding)
                over_target += holding > float(item["hold"])
                overnight += entry.date() != exit_time.date()
                ambiguous += int(float(trade["ambiguous"]))
                initial_risk = float(trade["initial_risk"])
                net = float(trade["net"])
                peak = float(trade["close_mfe_price"]) * float(trade["lots"]) * contract
                if initial_risk > 0:
                    net_r.append(net / initial_risk)
                    if peak >= initial_risk:
                        at_least_one_r += 1
                        high_giveback += net / peak < 0.6
                if peak > 0 and net > 0:
                    capture.append(net / peak * 100)
            if len(trades) != result["trades"]:
                raise ValueError(f"Ledger/summary trade count differs: {path}")
            rows.append(
                dict(
                    account=int(item["account"]),
                    strategy=item["strategy"],
                    split=split,
                    cost=cost,
                    trades=len(trades),
                    overnight=overnight,
                    beyond_target=over_target,
                    max_hold_minutes=max_hold,
                    ambiguous=ambiguous,
                    average_R=sum(net_r) / len(net_r) if net_r else None,
                    winner_close_capture_pct=sum(capture) / len(capture) if capture else None,
                    peak_at_least_1R=at_least_one_r,
                    high_giveback=high_giveback,
                )
            )
    return rows


def chart(selected: list[dict]) -> str:
    paths = []
    for item in selected:
        if "config" in item:
            for cost in ("BASE", "STRESS"):
                path = OUT / f"{int(item['account'])}-{item['strategy']}-TEST-{cost}-daily.csv"
                if path.is_file():
                    paths.append((int(item["account"]), item["strategy"], cost, path))
    if not paths:
        return "No chart was generated: no selected later-period daily series exists."
    # Existing isolated research dependencies only; no installation or production import.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, constrained_layout=True)
    for capital, strategy, cost, path in paths:
        values = read_csv(path)
        dates = [datetime.fromisoformat(next(iter(row.values()))) for row in values]
        equity = [float(row["equity"]) for row in values]
        returns = [(value / capital - 1) * 100 for value in equity]
        peak = float(capital)
        drawdown = []
        for value in equity:
            peak = max(peak, value)
            drawdown.append((value / peak - 1) * 100)
        label = f"${capital:,} {strategy} {cost}"
        axes[0].plot(dates, returns, label=label)
        axes[1].plot(dates, drawdown, label=label)
    axes[0].set_ylabel("Modeled equity return (%)")
    axes[1].set_ylabel("Daily-close drawdown (%)")
    axes[0].legend(ncol=2)
    for axis in axes:
        axis.grid(alpha=0.2)
    figure.suptitle(
        "GoldTriple small-account variants: later-period research, not execution validation"
    )
    destination = OUT / "small-account-equity.png"
    figure.savefig(destination, dpi=170)
    plt.close(figure)
    return (
        "![Selected later-period equity and daily-close drawdown]"
        "(../../reports/small-account-research/small-account-equity.png)"
    )


def main() -> None:
    for name in (
        "selected.json",
        "search.csv",
        "quality.json",
        "broker-metadata.json",
        "broker-source-notes.md",
    ):
        if not (OUT / name).is_file():
            raise FileNotFoundError(f"Research must finish before report rendering: {OUT / name}")
    quality = json.loads((OUT / "quality.json").read_text(encoding="utf-8"))
    metadata = json.loads((OUT / "broker-metadata.json").read_text(encoding="utf-8"))
    selected = json.loads((OUT / "selected.json").read_text(encoding="utf-8"))
    search = read_csv(OUT / "search.csv")
    expected = {(capital, strategy) for capital in CAPITALS for strategy in STRATEGIES}
    actual = {(int(item["account"]), item["strategy"]) for item in selected}
    if actual != expected or len(selected) != len(expected):
        raise ValueError(
            "Expected one exact selection record per capital/strategy; partial research refused"
        )
    for file_name, key in (
        ("gold_triple_small_account.py", "engine_hash"),
        ("gold_triple_risk_research.py", "parent_engine_hash"),
    ):
        if quality.get(key) != digest(ROOT / "scripts" / file_name):
            raise ValueError(f"Source changed after research: {file_name}")
    if quality.get("broker_metadata_hash") != digest(OUT / "broker-metadata.json"):
        raise ValueError("Broker metadata changed after research")
    train = [row for row in search if row["split"] == "TRAIN"]
    train_counts = []
    for capital in CAPITALS:
        for strategy in STRATEGIES:
            values = [
                int(row["trades"])
                for row in train
                if int(float(row["account"])) == capital and row["strategy"] == strategy
            ]
            if not values:
                raise ValueError("Training evidence missing for a capital/strategy")
            train_counts.append(
                dict(
                    account=capital,
                    strategy=strategy,
                    evaluations=len(values),
                    min_trades=min(values),
                    max_trades=max(values),
                )
            )
    tests = selected_rows(selected, "TEST")
    full = selected_rows(selected, "FULL")
    diagnostics = ledger_diagnostics(selected, float(metadata["trade_contract_size"]))
    later_diag = [row for row in diagnostics if row["split"] == "TEST"]
    passed = [
        item for item in selected if both_cost_grade(item) == "BOTH_COST_HISTORICAL_PASS_ONLY"
    ]
    portfolios = [item for item in passed if item["strategy"] == "PORTFOLIO"]
    if portfolios:
        decision = (
            "The bounded search found portfolio forward-research candidates for "
            + ", ".join(f"${int(item['account']):,}" for item in portfolios)
            + ". Their exact settings and later-period base/stress results appear below. "
            "A forward-research candidate is not execution eligibility or a validated "
            "profitability claim."
        )
    else:
        decision = (
            "No combined-portfolio candidate passed this search's chronological admission "
            "and later-period acceptance rules at $500, $750 or $1,000. Do not deploy a "
            "best-looking failed configuration as though it passed."
        )
    if not passed:
        decision += (
            " No standalone selection passed the stronger requirement that BOTH BASE and "
            "STRESS later-period runs have positive booked return, at least five trades "
            "and no booked-loss cap breach. No production-ready preset was found."
        )
    comparison = []
    for capital in (500, 1000):
        item = next(
            item
            for item in selected
            if int(item["account"]) == capital and item["strategy"] == "PORTFOLIO"
        )
        stress = next(
            (
                result
                for result in item.get("results", [])
                if result["split"] == "TEST" and result["cost"] == "STRESS"
            ),
            {},
        )
        comparison.append(
            dict(
                account=capital,
                status=item["status"],
                initial_risk_range=f"${capital * 0.005:.2f}–${capital * 0.01:.2f}",
                daily_dollars=capital * 0.03,
                monthly_dollars=capital * 0.08,
                stress_return_pct=stress.get("realized_return_pct"),
                stress_trades=stress.get("trades"),
            )
        )
    crossing = sum(row["overnight"] for row in diagnostics)
    carry_warning = (
        f"Commissioning blocker: {crossing} closed-trade ledger rows across the reported "
        "selected runs cross a UTC date. Runs overlap, so this is not a unique-trade count. "
        "Target holding is not guaranteed when quotes are missing; these paths omit overnight "
        "financing. Their results must not be promoted until broker rollover/swap costs and "
        "gap handling are modeled."
        if crossing
        else "No closed trade in the selected ledgers crosses a UTC date. This verifies these "
        "recorded paths only; missing quotes can still delay a future planned intraday exit."
    )
    columns = [
        ("account", "$ account"),
        ("strategy", "strategy"),
        ("cost", "cost"),
        ("trades", "trades"),
        ("realized_return_pct", "booked return %"),
        ("equity_return_pct", "equity return %"),
        ("max_drawdown_pct", "close-mark DD %"),
        ("worst_day_pct", "worst day %"),
        ("worst_month_pct", "worst month %"),
        ("profit_factor", "PF"),
        ("daily_breach", "day breach"),
        ("monthly_breach", "month breach"),
    ]
    sources = quality.get("source_hashes", {})
    source_text = (
        "\n".join(f"- `{name}`: `{value}`." for name, value in sorted(sources.items()))
        or "Source lineage refers to the preserved GoldTriple audit in the earlier risk report; "
        "this run records raw-data and research-engine identities below."
    )
    comparison_table = table(
        comparison,
        [
            ("account", "$ account"),
            ("status", "portfolio outcome"),
            ("initial_risk_range", "searched entry budget"),
            ("daily_dollars", "initial 3% day cap $"),
            ("monthly_dollars", "initial 8% month cap $"),
            ("stress_trades", "later stress trades"),
            ("stress_return_pct", "later stress booked return %"),
        ],
    )
    status_table = table(
        status_rows(selected),
        [
            ("account", "$ account"),
            ("strategy", "strategy"),
            ("status", "outcome"),
            ("both_cost_grade", "both-cost grade"),
            ("risk_pct", "entry risk %"),
            ("target_R", "target R"),
            ("timing_minutes", "timing min"),
            ("structure_bars", "structure bars"),
            ("protection", "protection"),
            ("hold_minutes", "target hold min"),
        ],
    )
    train_table = table(
        train_counts,
        [
            ("account", "$ account"),
            ("strategy", "strategy"),
            ("evaluations", "train evaluations"),
            ("min_trades", "minimum trades"),
            ("max_trades", "maximum trades"),
        ],
    )
    diagnostic_table = table(
        later_diag,
        [
            ("account", "$ account"),
            ("strategy", "strategy"),
            ("cost", "cost"),
            ("average_R", "average net R"),
            ("winner_close_capture_pct", "winner capture %"),
            ("peak_at_least_1R", "MFE>=1R"),
            ("high_giveback", "giveback cases"),
            ("ambiguous", "ambiguous bars"),
            ("overnight", "UTC date crossings"),
            ("beyond_target", "past hold target"),
            ("max_hold_minutes", "max hold min"),
        ],
    )
    text = f"""# GoldTriple small-account tuning: $500–$1,000

Date: October 8, 2026 (Asia/Calcutta). Status: RESEARCH_ONLY / NOT DEPLOYED.

## Decision

{decision}

All three source hypotheses were evaluated separately and together. They are new tactical
intraday variants; the original H1/H4-wide-stop strategies are not silently renamed or
claimed validated by this experiment. No terminal setting, native EA, broker credential,
account execution consent or ATS live preset is changed by this report renderer.

## Account comparison and why capital changes feasibility

{comparison_table}

Minimum size is {number(metadata["volume_min"])} lot on a
{number(metadata["trade_contract_size"])}-unit contract,
with {number(metadata["volume_step"])}-lot steps. For the observed USD-quoted contract,
0.01 lot represents one ounce; a $1/oz adverse move costs approximately $1 before charges.
The $500 account starts with $2.50–$5 entry-risk budgets; $1,000 starts with $5–$10.
The engine rounds DOWN and rejects below-minimum sizes. It never forces 0.01 lot when
the required stop exceeds the risk budget. Capital-specific selections are independent.

Current read-only SDK observation at `{metadata["observed_at"]}` reported leverage
{metadata["leverage"]}:1 and approximately ${number(metadata["margin_001_buy"])} buy margin for
0.01 lot at Ask {number(metadata["ask"])}. This corrects the earlier experiment's explicit
9:1 modeling assumption; it does not establish historical broker leverage. This experiment
models {metadata["leverage"]}:1 in BASE and {float(metadata["leverage"]) / 2:g}:1 in STRESS,
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

{status_table}

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
  {len(train):,} actual training evaluations were recorded. Require positive booked return,
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

{train_table}

## Requested loss limits and internal risk admission

Loss means NET BOOKED P&L: profits offset losses; reference is start-of-day/month equity.
The opening equity uses the previous observed close mark, not a fabricated midnight quote.

| Control | Research rule |
| --- | --- |
| Monitoring loss caps | 3% UTC daily / 8% calendar-month net booked loss |
| Internal remaining entry allowance | 2.5% daily / 6% monthly, including net postings |
| Entry risk | Selected 0.5%, 0.75% or 1% of current balance |
| Costs in size | Initial stop price loss plus modeled round-trip charges |
| Total outstanding positions | One across S1/S2/S3 |
| Volume | Round down to observed step; reject below observed minimum; maximum0.10lot |
| Margin | At most30% balance; current-metadata historical assumption |
| Frequency | Maximum3 entries/day; pause after2 losses/day; 15min cooldown |

Entry fees and each exit posting enter day/month loss tracking immediately. A stop gap
can exceed the reservation and cap: this research monitors breaches, not a guaranteed
financial loss ceiling. Booked-loss caps are distinct from floating-equity drawdown,
gross losing trades and deposits/withdrawals (not modeled). A native EA without these
commissioned controls does not inherit them merely because this research file exists.

## Later-period results: March–August2026

{table(tests, columns)}

Negative/no-candidate results remain visible. Missing selected runs are not reported as
zero-profit successful strategies. Probability and Sharpe are not calibrated by this run.

## Full-period descriptive results

{table(full, columns)}

Full-period results include tuning data and cannot establish future profitability.

## Exit capture and actual holding diagnostics

Excursions use observed minute CLOSE marks plus the modeled exit, not unordered highs
after an exit. Capture is net trade P&L divided by positive observed-close MFE in money;
average R divides trade net by initial stop-and-cost risk. High giveback requires observed
MFE at least1 initial-risk R and capture below60%. This lower-resolution diagnostic cannot
tell whether a missed tick peak was executable.

{diagnostic_table}

{carry_warning}

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

- {quality["rows"]:,} paired rows, `{quality["start"]}` through `{quality["end"]}`.
- Explicit source UTC, valid positive OHLC, ordered unique timestamps;
  {quality["gaps_over_one_minute"]} gaps greater than one minute. No forward price filling.
- Bid SHA256: `{quality["hashes"]["bid"]}`.
- Ask SHA256: `{quality["hashes"]["ask"]}`.
- Variant engine SHA256: `{quality["engine_hash"]}`.
- Parent rules/data engine SHA256: `{quality["parent_engine_hash"]}`.
- Broker metadata SHA256: `{quality["broker_metadata_hash"]}`.
- Variant method: `{quality["method"]}`.
- Volume provenance: `{quality["volume_provenance"]}`. Raw vendor/broker provenance is
  not independently certified; this is not authenticated account historical tick evidence.

{source_text}

Tactical signal counts by lookback: `{json.dumps(quality["tactical_signals"], sort_keys=True)}`.
Output identity: selected.json `{digest(OUT / "selected.json")}`;
search.csv `{digest(OUT / "search.csv")}`. The renderer rejects changed engines/metadata
or partial capital/strategy outputs. Original data and native source remain unchanged.

{chart(selected)}

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
"""
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()
