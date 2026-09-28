"""Transaction-cost model and tradability economics for the Agents Playground.

This module is the single authority on "is a trade worth taking?".

The 2026-09-28 forensic audit established the root cause of the playground's
losses: transaction charges (Rs.336 per round trip) *exceeded* the entire stated
stop loss (Rs.220), which required an 83% win rate to break even. No amount of
signal quality can fix a negative expectancy of that shape.

Everything here is deterministic and side-effect free so it can be unit tested
and reused by both the live worker and the offline cost stress harness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Statutory charge schedule (MCX non-agri futures, India, as of 2026-09)
# ---------------------------------------------------------------------------

#: Flat brokerage per executed order in INR.
BROKERAGE_PER_ORDER = 20.0

#: Round trip = entry + exit.
ORDERS_PER_ROUND_TRIP = 2

#: MCX non-agri futures: CTT+STT levied on the sell side only. Expressed against
#: total round-trip turnover this is half the headline rate.
MCX_STT_CTT_RATE = 0.0000625
MCX_EXCHANGE_TURNOVER_RATE = 0.000021
MCX_STAMP_DUTY_RATE = 0.00001

#: NSE equity derivatives fallback.
NSE_STT_CTT_RATE = 0.000125
NSE_EXCHANGE_TURNOVER_RATE = 0.00005
NSE_STAMP_DUTY_RATE = 0.000015

#: SEBI regulatory fee.
SEBI_RATE = 0.000001

#: GST on brokerage + exchange turnover fee.
GST_RATE = 0.18

#: Gold mini is quoted per 10 grams but the lot is 100 grams, so P&L uses a 10x
#: multiplier. The same convention applies to any GOLD contract with lot_size
#: >= 100.
GOLD_QUOTE_DIVISOR = 10.0
GOLD_MIN_LOT_SIZE = 100.0


def pnl_multiplier(*, symbol: str, lot_size: float, total_quantity: float) -> float:
    """Return the P&L multiplier converting a price move into currency units.

    MCX gold contracts are quoted per 10 grams while lots are expressed in
    grams, so a 100g lot is 10 quote-units. Non-gold contracts trade 1:1.
    """
    if "GOLD" in symbol.upper() and lot_size >= GOLD_MIN_LOT_SIZE:
        return total_quantity / GOLD_QUOTE_DIVISOR
    return float(total_quantity)


@dataclass(frozen=True, slots=True)
class ChargeBreakdown:
    """Itemised statutory charges for one round trip."""

    brokerage: float
    stt_ctt: float
    exchange_charges: float
    gst: float
    sebi_charges: float
    stamp_duty: float
    total_charges: float

    def as_dict(self) -> dict[str, float]:
        return {
            "brokerage": self.brokerage,
            "stt_ctt": self.stt_ctt,
            "exchange_charges": self.exchange_charges,
            "gst": self.gst,
            "sebi_charges": self.sebi_charges,
            "stamp_duty": self.stamp_duty,
            "total_charges": self.total_charges,
        }


def calculate_charges(
    *,
    exchange: str,
    turnover: float,
    num_orders: int = ORDERS_PER_ROUND_TRIP,
) -> ChargeBreakdown:
    """Compute statutory charges for a round trip against ``turnover``.

    ``turnover`` is entry notional plus exit notional, matching the convention
    already used by the trade ledger.
    """
    brokerage = round(float(num_orders) * BROKERAGE_PER_ORDER, 2)

    if exchange.upper() == "MCX":
        stt_ctt = round(turnover * MCX_STT_CTT_RATE, 2)
        exchange_fee = round(turnover * MCX_EXCHANGE_TURNOVER_RATE, 2)
        stamp_duty = round(turnover * MCX_STAMP_DUTY_RATE, 2)
    else:
        stt_ctt = round(turnover * NSE_STT_CTT_RATE, 2)
        exchange_fee = round(turnover * NSE_EXCHANGE_TURNOVER_RATE, 2)
        stamp_duty = round(turnover * NSE_STAMP_DUTY_RATE, 2)

    sebi_fee = round(turnover * SEBI_RATE, 2)
    gst = round((brokerage + exchange_fee) * GST_RATE, 2)
    total = round(brokerage + stt_ctt + exchange_fee + gst + sebi_fee + stamp_duty, 2)

    return ChargeBreakdown(
        brokerage=brokerage,
        stt_ctt=stt_ctt,
        exchange_charges=exchange_fee,
        gst=gst,
        sebi_charges=sebi_fee,
        stamp_duty=stamp_duty,
        total_charges=total,
    )


def estimate_round_trip_charges(
    *,
    exchange: str,
    entry_price: float,
    exit_price: float,
    symbol: str,
    lot_size: float,
    lots: float,
) -> ChargeBreakdown:
    """Estimate charges before entry so a trade can be screened for tradability."""
    total_qty = float(lots) * float(lot_size)
    mult = pnl_multiplier(symbol=symbol, lot_size=float(lot_size), total_quantity=total_qty)
    turnover = round((float(entry_price) + float(exit_price)) * mult, 2)
    return calculate_charges(exchange=exchange, turnover=turnover)


# ---------------------------------------------------------------------------
# Tradability economics
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TradeEconomics:
    """Cost-aware viability assessment for a candidate trade.

    ``tradable`` is the only field the entry path should branch on. The rest is
    surfaced to the operator so the rejection is explainable rather than opaque.
    """

    tradable: bool
    reason: str
    expected_edge: float
    round_trip_cost: float
    edge_to_cost_ratio: float
    required_win_rate: float
    win_pct: float
    loss_pct: float
    net_if_win: float
    net_if_loss: float
    min_lots_required: float
    block_reason_code: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "tradable": self.tradable,
            "reason": self.reason,
            "expected_edge": round(self.expected_edge, 2),
            "round_trip_cost": round(self.round_trip_cost, 2),
            "edge_to_cost_ratio": round(self.edge_to_cost_ratio, 2),
            "required_win_rate": round(self.required_win_rate * 100.0, 1),
            "win_pct": round(self.win_pct, 2),
            "loss_pct": round(self.loss_pct, 2),
            "net_if_win": round(self.net_if_win, 2),
            "net_if_loss": round(self.net_if_loss, 2),
            "min_lots_required": round(self.min_lots_required, 3),
            "block_reason_code": self.block_reason_code,
        }


class BlockReason:
    """Stable reason codes for a rejected trade."""

    GLOBAL_KILL = "GLOBAL_KILL_SWITCH"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER_TRIPPED"
    EDGE_BELOW_MINIMUM = "EDGE_BELOW_MINIMUM"
    NEGATIVE_EXPECTANCY = "NEGATIVE_EXPECTANCY_AT_MAX_WIN_RATE"
    LOT_SIZE_UNECONOMICAL = "LOT_SIZE_UNECONOMICAL"
    INSUFFICIENT_CAPITAL = "INSUFFICIENT_CAPITAL"
    LOW_CONFIDENCE = "SIGNAL_CONFIDENCE_BELOW_THRESHOLD"
    FREQUENCY_CAP = "MAX_TRADES_PER_DAY_REACHED"
    CORRELATED_EXPOSURE = "CORRELATED_EXPOSURE_LIMIT"
    RISK_BUDGET = "RISK_BUDGET_EXHAUSTED"
    DRAWDOWN_HALT = "DRAWDOWN_HALT"


def required_win_rate(*, net_if_win: float, net_if_loss: float) -> float:
    """Win rate at which a fixed target/stop pair breaks even.

    Solves ``w * win + (1 - w) * loss == 0`` for ``w``. Returns a value in
    ``[0, 1]``; when the loss is not negative the trade cannot lose and the
    requirement is 0.
    """
    if net_if_win <= 0:
        return 1.0
    if net_if_loss >= 0:
        return 0.0
    return -net_if_loss / (net_if_win - net_if_loss)


def min_lots_for_viability(
    *,
    expected_edge_per_lot: float,
    round_trip_cost_at_one_lot: float,
    min_edge_multiple: float,
    lot_granularity: float = 1.0,
) -> float:
    """Smallest lot count where the trade's edge clears the cost hurdle.

    Statutory charges have a large fixed component (brokerage) plus a notional
    component, while edge scales with size. This is why the pre-audit 1-lot
    configuration was structurally unprofitable: the fixed floor ate the whole
    ticket. Returns 0.0 when no lot size up to a sane bound can qualify.

    ``lot_granularity`` defaults to whole lots because MCX and NSE futures are
    not tradeable in fractions. Allowing 0.1-lot granularity here would make
    sensitivity analysis report answer sizes the exchange will not accept.
    """
    if expected_edge_per_lot <= 0:
        return 0.0
    if min_edge_multiple <= 0:
        min_edge_multiple = 1.0

    best = 0.0
    # Search a bounded, realistic lot range rather than solving analytically:
    # the notional charge term makes this quadratic in lots.
    steps = 400
    max_lots = 60.0
    for i in range(1, steps + 1):
        lots = round(max_lots * i / steps, 4)
        # Recompute the cost curve at this size using the observed per-lot cost
        # decomposition: fixed brokerage plus variable notional cost.
        cost = _charges_for_lots(
            lots=lots,
            cost_at_one_lot=round_trip_cost_at_one_lot,
        )
        edge = expected_edge_per_lot * lots
        if edge >= cost * min_edge_multiple:
            best = lots
            break

    if best <= 0:
        return 0.0
    return max(lot_granularity, round(best / lot_granularity) * lot_granularity)


def _charges_for_lots(*, lots: float, cost_at_one_lot: float) -> float:
    """Approximate total round-trip charge at ``lots``.

    Splits the observed 1-lot cost into its fixed (brokerage) and variable
    (notional) components. Brokerage is flat per order; everything else scales
    linearly with size.
    """
    fixed = BROKERAGE_PER_ORDER * ORDERS_PER_ROUND_TRIP
    variable_per_lot = max(cost_at_one_lot - fixed, 0.0)
    return fixed + variable_per_lot * float(lots)


def assess_trade(
    *,
    exchange: str,
    entry_price: float,
    symbol: str,
    lot_size: float,
    lots: float,
    target_points: float,
    stop_points: float,
    strategy_win_rate: float,
    min_edge_multiple: float = 3.0,
    max_lots_allowed: float = 10.0,
    available_capital: float = 0.0,
    margin_per_lot: float = 0.0,
) -> TradeEconomics:
    """Decide whether a candidate trade is economically worth taking.

    The gate is deliberately strict. A trade must clear three hurdles:

    1. **Edge vs cost** - expected gross edge must be at least
       ``min_edge_multiple`` times the round-trip charge. This is the check
       whose absence caused the audit losses.
    2. **Positive expectancy at a realistic win rate** - even at a generous
       60% win rate, the trade must be net positive.
    3. **Affordability** - the sized position must fit the agent's capital.
    """
    total_qty = float(lots) * float(lot_size)
    mult = pnl_multiplier(symbol=symbol, lot_size=float(lot_size), total_quantity=total_qty)

    win_pct = abs(float(target_points))
    loss_pct = abs(float(stop_points))

    charges = estimate_round_trip_charges(
        exchange=exchange,
        entry_price=entry_price,
        exit_price=entry_price + (win_pct if float(target_points) >= 0 else -win_pct),
        symbol=symbol,
        lot_size=float(lot_size),
        lots=float(lots),
    )
    cost = charges.total_charges

    expected_edge = win_pct * mult
    ratio = expected_edge / cost if cost > 0 else float("inf")

    net_if_win = expected_edge - cost
    net_if_loss = -(loss_pct * mult) - cost
    req_wr = required_win_rate(net_if_win=net_if_win, net_if_loss=net_if_loss)

    def _reject(reason: str, code: str) -> TradeEconomics:
        return TradeEconomics(
            tradable=False,
            reason=reason,
            expected_edge=expected_edge,
            round_trip_cost=cost,
            edge_to_cost_ratio=ratio,
            required_win_rate=req_wr,
            win_pct=win_pct,
            loss_pct=loss_pct,
            net_if_win=net_if_win,
            net_if_loss=net_if_loss,
            min_lots_required=0.0,
            block_reason_code=code,
        )

    if cost <= 0:
        return _reject("No cost model available for this instrument", BlockReason.EDGE_BELOW_MINIMUM)

    if expected_edge <= 0:
        return _reject("Non-positive expected edge", BlockReason.EDGE_BELOW_MINIMUM)

    if ratio < min_edge_multiple:
        needed = min_lots_for_viability(
            expected_edge_per_lot=expected_edge,
            round_trip_cost_at_one_lot=cost,
            min_edge_multiple=min_edge_multiple,
        )
        if needed <= 0 or needed > max_lots_allowed:
            return _reject(
                f"Edge/cost ratio {ratio:.2f}x below {min_edge_multiple:.1f}x minimum; "
                f"no viable lot size up to {max_lots_allowed:g} lots",
                BlockReason.LOT_SIZE_UNECONOMICAL,
            )

    # Even a generous win rate must produce positive expectancy.
    generous_wr = min(max(strategy_win_rate, 0.60), 0.95)
    expectancy = generous_wr * net_if_win + (1.0 - generous_wr) * net_if_loss
    if expectancy <= 0:
        return _reject(
            f"Negative expectancy (Rs.{expectancy:,.2f}/trade) even at "
            f"{generous_wr * 100:.0f}% win rate",
            BlockReason.NEGATIVE_EXPECTANCY,
        )

    if available_capital > 0 and margin_per_lot > 0:
        needed_margin = float(lots) * float(margin_per_lot)
        if needed_margin > available_capital:
            affordable = available_capital / float(margin_per_lot)
            if affordable <= 0:
                return _reject("Insufficient capital for margin", BlockReason.INSUFFICIENT_CAPITAL)

    return TradeEconomics(
        tradable=True,
        reason=f"Tradable: edge {ratio:.2f}x cost, requires {req_wr * 100:.1f}% win rate",
        expected_edge=expected_edge,
        round_trip_cost=cost,
        edge_to_cost_ratio=ratio,
        required_win_rate=req_wr,
        win_pct=win_pct,
        loss_pct=loss_pct,
        net_if_win=net_if_win,
        net_if_loss=net_if_loss,
        min_lots_required=round(float(lots), 3),
    )


@dataclass
class CostAwareSizer:
    """Find the largest affordable lot count that still clears the cost hurdle.

    Sizing up is the single most effective lever when per-trade cost has a large
    fixed component: the brokerage floor is amortised across more notional while
    the gross edge scales linearly.
    """

    max_lots: float
    max_risk_pct: float
    capital: float
    margin_per_lot: float
    min_edge_multiple: float = 3.0
    lot_step: float = 1.0
    _cache: dict[tuple[str, ...], float] = field(default_factory=dict, repr=False)

    def size_for(
        self,
        *,
        exchange: str,
        entry_price: float,
        symbol: str,
        lot_size: float,
        target_points: float,
        stop_points: float,
        strategy_win_rate: float,
        hard_ceiling: float | None = None,
    ) -> tuple[float, TradeEconomics]:
        """Return ``(lots, economics)`` for the best feasible size.

        Prefers the *largest* size that passes, because larger size improves the
        edge-to-cost ratio. Returns ``(0.0, economics)`` when nothing is viable.
        """
        ceiling = min(
            self.max_lots,
            hard_ceiling if hard_ceiling is not None else self.max_lots,
        )
        capital_ceiling = self.max_lots
        if self.margin_per_lot > 0 and self.capital > 0:
            capital_ceiling = self.capital / self.margin_per_lot
        ceiling = min(ceiling, capital_ceiling)
        if ceiling <= 0:
            ceiling = self.max_lots

        best_lots = 0.0
        best_econ: TradeEconomics | None = None
        steps = max(int(ceiling / self.lot_step), 1)

        for i in range(steps, 0, -1):
            lots = round(i * self.lot_step, 3)
            if lots <= 0:
                continue
            econ = assess_trade(
                exchange=exchange,
                entry_price=entry_price,
                symbol=symbol,
                lot_size=float(lot_size),
                lots=lots,
                target_points=target_points,
                stop_points=stop_points,
                strategy_win_rate=strategy_win_rate,
                min_edge_multiple=self.min_edge_multiple,
                max_lots_allowed=ceiling,
                available_capital=self.capital,
                margin_per_lot=self.margin_per_lot,
            )
            if econ.tradable:
                best_lots = lots
                best_econ = econ
                break

        if best_econ is None:
            # Report the best diagnostic we have: the largest affordable size.
            probe = round(ceiling, 3)
            best_econ = assess_trade(
                exchange=exchange,
                entry_price=entry_price,
                symbol=symbol,
                lot_size=float(lot_size),
                lots=max(probe, self.lot_step),
                target_points=target_points,
                stop_points=stop_points,
                strategy_win_rate=strategy_win_rate,
                min_edge_multiple=self.min_edge_multiple,
                max_lots_allowed=ceiling,
                available_capital=self.capital,
                margin_per_lot=self.margin_per_lot,
            )
            return 0.0, best_econ

        # Respect the per-trade risk budget: cap size so that stop distance stays
        # within max_risk_pct of capital.
        if self.max_risk_pct > 0 and stop_points > 0 and float(lot_size) > 0:
            total_qty = best_lots * float(lot_size)
            mult = pnl_multiplier(
                symbol=symbol, lot_size=float(lot_size), total_quantity=total_qty
            )
            risk_per_lot = abs(float(stop_points)) * mult
            risk_total = risk_per_lot * best_lots
            risk_budget = self.capital * self.max_risk_pct / 100.0
            if risk_budget > 0 and risk_total > risk_budget:
                affordable_risk_lots = risk_budget / risk_per_lot if risk_per_lot > 0 else 0.0
                capped = max(self.lot_step, (affordable_risk_lots // self.lot_step) * self.lot_step)
                capped = min(capped, best_lots)
                if capped < self.lot_step:
                    return 0.0, TradeEconomics(
                        tradable=False,
                        reason=(
                            f"Risk budget Rs.{risk_budget:,.0f} ({self.max_risk_pct}% of capital) "
                            f"cannot absorb a Rs.{risk_per_lot * self.lot_step:,.0f} stop"
                        ),
                        expected_edge=best_econ.expected_edge,
                        round_trip_cost=best_econ.round_trip_cost,
                        edge_to_cost_ratio=best_econ.edge_to_cost_ratio,
                        required_win_rate=best_econ.required_win_rate,
                        win_pct=best_econ.win_pct,
                        loss_pct=best_econ.loss_pct,
                        net_if_win=best_econ.net_if_win,
                        net_if_loss=best_econ.net_if_loss,
                        min_lots_required=0.0,
                        block_reason_code=BlockReason.RISK_BUDGET,
                    )
                best_lots = round(capped, 3)

        return best_lots, best_econ


__all__ = [
    "BlockReason",
    "BROKERAGE_PER_ORDER",
    "ChargeBreakdown",
    "CostAwareSizer",
    "ORDERS_PER_ROUND_TRIP",
    "TradeEconomics",
    "assess_trade",
    "calculate_charges",
    "estimate_round_trip_charges",
    "min_lots_for_viability",
    "pnl_multiplier",
    "required_win_rate",
]
