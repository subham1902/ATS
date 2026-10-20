"""Freeze the recorded research results and guard strategy promotion.

Two failure modes this repository is structurally exposed to, neither of which
any existing job detects:

1. A recorded research number changes without anyone noticing. The later-period
   results in the conditions report are the only evidence the project has about
   whether anything works. They are prose in a markdown table, editable by a
   human or an agent in one keystroke, with no checksum and no test. An
   unfavourable number quietly becoming favourable is the single most damaging
   undetected change this repository admits.

2. A strategy acquires a lifecycle beyond RESEARCH without the evidence that is
   supposed to be prerequisite. The runtime kernel enforces this for durable
   records; the documentation projections under `strategies/` do not, and they
   are what a reader looks at.

Both are frozen here against a committed baseline. Changing a number is still
allowed -- it just has to be a deliberate, reviewed baseline update rather than
a silent edit.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Sequence

RESULTS_HEADING: Final[str] = "## Later-period results"
LIFECYCLE_RE: Final[re.Pattern[str]] = re.compile(
    r"^Status:\s*\**([A-Z_]+)\**", re.MULTILINE
)
STATUS_IN_PROSE_RE: Final[re.Pattern[str]] = re.compile(
    r"Status:.*?\*\*([A-Z_]+)\*\*|Status:\s*([A-Z_]+)"
)

# A lineage may only claim one of these without independent promotion evidence.
UNPROMOTED: Final[frozenset[str]] = frozenset({"RESEARCH"})

# Markers whose presence in VALIDATION.md means evidence is absent.
ABSENCE_MARKERS: Final[tuple[str, ...]] = (
    "NOT_ESTABLISHED",
    "NO_ELIGIBLE_CONDITION",
    "no independently verified promotion evidence",
)


@dataclass(frozen=True)
class ResultRow:
    balance: str
    mask: str
    cost: str
    trades: str
    net_return_pct: str
    drawdown_pct: str
    worst_day_pct: str
    worst_month_pct: str
    profit_factor: str

    @property
    def key(self) -> str:
        return f"{self.balance}|{self.mask}|{self.cost}"

    def as_dict(self) -> dict[str, str]:
        return {
            "trades": self.trades,
            "net_return_pct": self.net_return_pct,
            "drawdown_pct": self.drawdown_pct,
            "worst_day_pct": self.worst_day_pct,
            "worst_month_pct": self.worst_month_pct,
            "profit_factor": self.profit_factor,
        }


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_results(report: Path) -> dict[str, ResultRow]:
    """Extract the later-period results table verbatim.

    Values are kept as strings. Parsing them as floats would let 0.1923 and
    0.19230 compare equal, and the point of this gate is that the recorded
    characters do not move.
    """
    text = report.read_text(encoding="utf-8")
    index = text.find(RESULTS_HEADING)
    if index < 0:
        raise SystemExit(
            f"BASELINE_GATE_FAILED: {report} no longer contains '{RESULTS_HEADING}'"
        )
    rows: dict[str, ResultRow] = {}
    for line in text[index:].splitlines():
        stripped = line.strip()
        if stripped.startswith("##") and RESULTS_HEADING not in stripped:
            break
        if not stripped.startswith("|"):
            continue
        cells = _cells(stripped)
        if len(cells) != 9:
            continue
        if cells[0] in {"Balance", ""} or set(cells[0]) <= {"-", ":"}:
            continue
        row = ResultRow(*cells)  # type: ignore[arg-type]
        if row.key in rows:
            raise SystemExit(
                f"BASELINE_GATE_FAILED: duplicate result row {row.key} in {report}"
            )
        rows[row.key] = row
    if not rows:
        raise SystemExit(
            f"BASELINE_GATE_FAILED: no result rows parsed from {report}; the gate "
            "would pass vacuously"
        )
    return rows


def compare_results(
    observed: dict[str, ResultRow], baseline: dict[str, dict[str, str]]
) -> list[str]:
    problems: list[str] = []
    for key in sorted(set(baseline) - set(observed)):
        problems.append(f"result row removed from the report: {key}")
    for key in sorted(set(observed) - set(baseline)):
        problems.append(
            f"result row added without a baseline update: {key} "
            f"({observed[key].as_dict()})"
        )
    for key in sorted(set(observed) & set(baseline)):
        current, expected = observed[key].as_dict(), baseline[key]
        for field in sorted(set(expected) | set(current)):
            if current.get(field) != expected.get(field):
                problems.append(
                    f"{key}: {field} changed {expected.get(field)!r} -> "
                    f"{current.get(field)!r}"
                )
    return problems


def check_promotions(strategies_root: Path) -> list[str]:
    """Refuse any documented lifecycle above RESEARCH that lacks evidence."""
    problems: list[str] = []
    for directory in sorted(p for p in strategies_root.iterdir() if p.is_dir()):
        strategy_md = directory / "STRATEGY.md"
        if not strategy_md.exists():
            continue
        match = STATUS_IN_PROSE_RE.search(strategy_md.read_text(encoding="utf-8"))
        if match is None:
            problems.append(f"{directory.name}: STRATEGY.md states no Status")
            continue
        lifecycle = match.group(1) or match.group(2)
        if lifecycle in UNPROMOTED:
            continue
        validation = directory / "VALIDATION.md"
        if not validation.exists():
            problems.append(
                f"{directory.name}: claims {lifecycle} with no VALIDATION.md"
            )
            continue
        body = validation.read_text(encoding="utf-8")
        present = [marker for marker in ABSENCE_MARKERS if marker in body]
        if present:
            problems.append(
                f"{directory.name}: claims lifecycle {lifecycle} while "
                f"VALIDATION.md still records absent evidence ({', '.join(present)})"
            )
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("docs/research/GOLD_TRIPLE_WINNING_CONDITIONS_2026-10-08.md"),
    )
    parser.add_argument(
        "--baseline", type=Path, default=Path("tests/baselines/research_results.json")
    )
    parser.add_argument("--strategies", type=Path, default=Path("strategies"))
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="regenerate the baseline from the report; review the diff by hand",
    )
    args = parser.parse_args(argv)

    observed = parse_results(args.report)

    if args.write_baseline:
        payload = {
            "_note": (
                "Frozen later-period research results. Regenerating this file is a "
                "reviewed act: it records that the project's only evidence about "
                "whether anything works has deliberately changed."
            ),
            "source": str(args.report),
            "rows": {key: row.as_dict() for key, row in sorted(observed.items())},
        }
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(
            json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8"
        )
        print(f"wrote baseline with {len(observed)} row(s) to {args.baseline}")
        return 0

    if not args.baseline.exists():
        print(
            f"BASELINE_GATE_FAILED: {args.baseline} is missing. Generate it with "
            "--write-baseline and commit it.",
            file=sys.stderr,
        )
        return 1

    stored = json.loads(args.baseline.read_text(encoding="utf-8"))
    baseline_rows: dict[str, dict[str, str]] = stored.get("rows", {})
    problems = compare_results(observed, baseline_rows)
    problems.extend(check_promotions(args.strategies))

    print(f"result rows checked   : {len(observed)}")
    print(f"strategy lineages     : "
          f"{sum(1 for p in args.strategies.iterdir() if p.is_dir())}")

    if problems:
        print(f"\nBASELINE_GATE_FAILED: {len(problems)} problem(s)", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nIf a change is intended, rerun with --write-baseline, review the "
            "diff, and commit it as a deliberate revision of recorded evidence.",
            file=sys.stderr,
        )
        return 1

    print("\nrecorded research results unchanged; no undocumented promotion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
