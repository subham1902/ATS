"""Cost-stress simulator: prove a configuration can or cannot be profitable.

Purpose
-------
Before any configuration is allowed near capital, this answers one question
honestly:

    Given this instrument, target, stop, size, win rate and cost schedule,
    can this configuration ever make money?

It models the full round trip including statutory charges and execution
slippage, then sweeps the plausible parameter space and reports which regions
are viable. This is the practical form of the audit's core finding: the pre-
audit configuration was not merely unlucky, it was arithmetically incapable of
profit at any achievable win rate.

Usage
-----
    python -m scripts.cost_stress_check
    python -m scripts.cost_stress_check --lots 2 --target 200 --stop 67
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass

from ats.agents.costs import (
    assess_trade,
    estimate_round_trip_charges,
    min_lots_for_viability,
    pnl_multiplier,
    required_win_rate,
)
from ats.agents.execution import ExecutionConfig, ExecutionModel

GOLDM_SYMBOL = "MCX:GOLDM FUT"
GOLDM_LOT = 100.0
DEFAULT_ENTRY = 147_232.0


@dataclass(frozen=True, slots=True)
class Scenario:
    """One fully specified what-if configuration."""

    label: str
    lots: float
    target_points: float
    stop_points: float
    win_rate: float

    def evaluate(self, entry_price: float = DEFAULT_ENTRY) -> dict[str, object]:
        exchange = "MCX"
        mult = pnl_multiplier(
            symbol=GOLDM_SYMBOL, lot_size=GOLDM_LOT, total_quantity=GOLDM_LOT * self.lots
        )

        entry_value = self.target_points * mult
        stop_value = self.stop_points * mult

        charges = estimate_round_trip_charges(
            exchange=exchange,
            entry_price=entry_price,
            exit_price=entry_price + self.target_points,
            symbol=GOLDM_SYMBOL,
            lot_size=GOLDM_LOT,
            lots=self.lots,
        )

        # Execution realism: cost-of-carry from entry and exit slippage.
        exec_model = ExecutionModel(ExecutionConfig(reject_probability=0.0))
        n = 10_000
        total_slip = 0.0
        random.seed(11)
        for i in range(n):
            ef = exec_model.apply_entry(
                price=entry_price, direction="LONG", order_id=f"e{i}"
            )
            xf = exec_model.apply_exit(
                price=entry_price + self.target_points,
                direction="LONG",
                order_id=f"x{i}",
                reason="PROFIT_TARGET",
            )
            total_slip += (ef.slippage_points + xf.slippage_points) * mult
        avg_slip_cost = total_slip / n

        net_win = entry_value - charges.total_charges - avg_slip_cost
        net_loss = -stop_value - charges.total_charges - avg_slip_cost
        breakeven = required_win_rate(net_if_win=net_win, net_if_loss=net_loss)

        expectancy = self.win_rate * net_win + (1.0 - self.win_rate) * net_loss
        edge = entry_value / charges.total_charges

        gate = assess_trade(
            exchange=exchange,
            entry_price=entry_price,
            symbol=GOLDM_SYMBOL,
            lot_size=GOLDM_LOT,
            lots=self.lots,
            target_points=self.target_points,
            stop_points=self.stop_points,
            strategy_win_rate=self.win_rate,
            min_edge_multiple=3.0,
            max_lots_allowed=60.0,
        )

        return {
            "label": self.label,
            "lots": self.lots,
            "target_points": self.target_points,
            "stop_points": self.stop_points,
            "rr": round(self.target_points / self.stop_points, 2),
            "win_rate_pct": round(self.win_rate * 100, 1),
            "turnover_charges": round(charges.total_charges, 2),
            "slippage_cost": round(avg_slip_cost, 2),
            "net_if_target": round(net_win, 2),
            "net_if_stop": round(net_loss, 2),
            "edge_to_cost": round(edge, 2),
            "required_win_rate_pct": round(breakeven * 100, 1),
            "headroom_pp": round((self.win_rate - breakeven) * 100, 1),
            "expectancy_per_trade": round(expectancy, 2),
            "gate_verdict": "PASS" if gate.tradable else f"BLOCK ({gate.block_reason_code})",
            "profitable": expectancy > 0 and breakeven < 1.0,
        }


def build_scenarios() -> list[Scenario]:
    """Reference scenarios: the pre-audit config vs the recommended config."""
    return [
        Scenario("PRE-AUDIT (45/22, 1 lot)", 1.0, 45.0, 22.0, 0.109),
        Scenario("PRE-AUDIT at 50% WR", 1.0, 45.0, 22.0, 0.50),
        Scenario("PRE-AUDIT at 80% WR", 1.0, 45.0, 22.0, 0.80),
        Scenario("Size-up fix (45/22, 20 lots)", 20.0, 45.0, 22.0, 0.50),
        Scenario("Wider target (99/30, 2 lots)", 2.0, 99.0, 30.0, 0.45),
        Scenario("Swing (200/67, 2 lots)", 2.0, 200.0, 67.0, 0.45),
        Scenario("Swing (400/133, 2 lots)", 2.0, 400.0, 133.0, 0.42),
        Scenario("Swing (400/133, 1 lot)", 1.0, 400.0, 133.0, 0.42),
    ]


def print_table(rows: list[dict[str, object]]) -> None:
    cols = [
        ("label", "Configuration", 28),
        ("lots", "Lots", 6),
        ("rr", "R:R", 6),
        ("turnover_charges", "Chg Rs", 9),
        ("edge_to_cost", "E:C", 6),
        ("required_win_rate_pct", "ReqWR%", 8),
        ("win_rate_pct", "ActWR%", 8),
        ("expectancy_per_trade", "Expct Rs", 11),
        ("gate_verdict", "Gate", 28),
    ]
    header = "".join(f"{h:>{w}}" for _, h, w in cols)
    print(header)
    print("-" * len(header))
    for r in rows:
        print("".join(f"{r[k]!s:>{w}}" for k, _, w in cols))


def print_viability_map() -> None:
    """Show the smallest lot count that clears the 3x cost hurdle, and its economics."""
    print("\n\n=== VIABILITY MAP: minimum lots needed at 3x edge requirement ===")
    print(
        f"{'Target pts':>11} | {'Min lots':>9} | {'Chgs Rs':>10} | {'Margin Rs':>11} | "
        f"{'Req WR%':>8} | Verdict"
    )
    print("-" * 74)
    for target in (45, 99, 150, 200, 300, 400, 600, 800, 1200):
        stop = target / 2.0
        mult = pnl_multiplier(
            symbol=GOLDM_SYMBOL, lot_size=GOLDM_LOT, total_quantity=GOLDM_LOT
        )
        edge_per_lot = target * mult
        cost_at_one = estimate_round_trip_charges(
            exchange="MCX",
            entry_price=DEFAULT_ENTRY,
            exit_price=DEFAULT_ENTRY + target,
            symbol=GOLDM_SYMBOL,
            lot_size=GOLDM_LOT,
            lots=1.0,
        ).total_charges

        min_lots = min_lots_for_viability(
            expected_edge_per_lot=edge_per_lot,
            round_trip_cost_at_one_lot=cost_at_one,
            min_edge_multiple=3.0,
        )

        if min_lots <= 0:
            print(f"{target:>11} | {'--':>9} | {cost_at_one:>10.2f} | {'--':>11} | "
                  f"{'--':>8} | NOT VIABLE AT ANY SIZE")
            continue

        charges = estimate_round_trip_charges(
            exchange="MCX",
            entry_price=DEFAULT_ENTRY,
            exit_price=DEFAULT_ENTRY + target,
            symbol=GOLDM_SYMBOL,
            lot_size=GOLDM_LOT,
            lots=min_lots,
        )
        margin = min_lots * 45_000.0
        econ = assess_trade(
            exchange="MCX",
            entry_price=DEFAULT_ENTRY,
            symbol=GOLDM_SYMBOL,
            lot_size=GOLDM_LOT,
            lots=min_lots,
            target_points=float(target),
            stop_points=stop,
            strategy_win_rate=0.45,
            min_edge_multiple=3.0,
            max_lots_allowed=120.0,
        )
        principal_ok = "FITS 1 LAC" if margin <= 100_000.0 else "needs bigger book"
        print(
            f"{target:>11} | {min_lots:>9.2f} | {charges.total_charges:>10.2f} | "
            f"{margin:>11,.0f} | {econ.required_win_rate * 100:>8.1f} | {principal_ok}"
        )


def print_worst_case() -> None:
    """Prove the pre-audit configuration cannot be rescued by any win rate."""
    print("\n\n=== CAN ANY WIN RATE SAVE THE PRE-AUDIT CONFIG? ===")
    for wr in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99):
        s = Scenario("x", 1.0, 45.0, 22.0, wr).evaluate()
        print(
            f"  WR {wr * 100:>5.0f}%  ->  expectancy Rs.{s['expectancy_per_trade']:>8,.2f} "
            f"per trade  (needs {s['required_win_rate_pct']:.0f}% to break even)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Cost-stress check for agent configs")
    parser.add_argument("--lots", type=float, default=None)
    parser.add_argument("--target", type=float, default=None)
    parser.add_argument("--stop", type=float, default=None)
    parser.add_argument("--win-rate", type=float, default=None)
    args = parser.parse_args()

    if args.lots and args.target and args.stop:
        scenarios = [
            Scenario(
                "CUSTOM PROBE",
                args.lots,
                args.target,
                args.stop,
                args.win_rate or 0.45,
            )
        ]
    else:
        scenarios = build_scenarios()

    print("=" * 100)
    print("ATS AGENTS PLAYGROUND - COST STRESS CHECK")
    print("=" * 100)
    rows = [s.evaluate() for s in scenarios]
    print_table(rows)

    print_viability_map()
    print_worst_case()

    print("\n\n=== CONCLUSION ===")
    print(
        "Charges have a large fixed brokerage floor plus a notional component, so\n"
        "small targets can never amortise them. Either widen the target materially\n"
        "(swing horizon) or trade sizes where the edge-to-cost ratio exceeds 3x.\n"
        "The pre-audit 45pt / 1-lot configuration is unprofitable at ANY win rate.\n"
    )


if __name__ == "__main__":
    main()
