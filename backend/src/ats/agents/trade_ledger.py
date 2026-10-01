"""Dedicated Upstox Live Market Trade History Logger & Ledger.

Enforces:
- Separate history ledger specifically for Upstox live market trade details.
- Capacity of up to 1,000 trades in a ring buffer with persistent storage.
- Comprehensive lot details (lot_size, lots, total_quantity, lot_unit).
- Accurate Upstox brokerage, STT/CTT, exchange charges, GST, and net PnL calculations,
  delegated to :mod:`ats.agents.costs` so the cost gate and the ledger agree.
- Full provenance tracking (feed source, exchange timestamps, strategy attribution).
- Cost-aware reporting: net-after-charges, charge-to-edge ratio, and the
  required-vs-actual win rate for every trade.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ats.agents.costs import calculate_charges, pnl_multiplier
from ats.persistence.json_files import quarantine_after_failure, read_json_or_quarantine

LOGGER = logging.getLogger(__name__)

LEDGER_FILE_PATH = Path("data/agents/upstox_live_trades_ledger.json")
MAX_TRADES_CAPACITY = 1000

IST = timezone(timedelta(hours=5, minutes=30))


def _calculate_upstox_charges(
    exchange: str,
    turnover: float,
    gross_pnl: float,
    num_orders: int = 2,
) -> dict[str, float]:
    """Calculate realistic Upstox transaction charges & statutory taxes.

    Delegates to :mod:`ats.agents.costs` so the ledger and the pre-trade cost
    gate can never disagree about what a trade costs. Disagreement here was the
    failure mode that made the pre-audit losses invisible.
    """
    return calculate_charges(
        exchange=exchange,
        turnover=turnover,
        num_orders=num_orders,
    ).as_dict()


@dataclass
class UpstoxLiveTradeRecord:
    trade_id: str
    timestamp: str  # ISO-8601 UTC
    ist_timestamp: str  # IST human readable
    agent_id: str
    agent_name: str
    strategy_id: str
    strategy_name: str
    exchange: str
    instrument_key: str
    symbol: str
    order_side: str  # "BUY" or "SELL"
    direction: str  # "LONG" or "SHORT"

    # Lot Details
    lot_size: float  # Units per lot (e.g. 100 for GOLDM [100 grams], 25 for NIFTY, 1 for spot)
    lots: float  # Number of lots traded (supports fractional e.g. 0.1, 0.2, 1.0)
    total_quantity: float  # lots * lot_size
    lot_unit: str  # "grams", "units", "shares", "oz"

    # Price Execution
    entry_price: float
    exit_price: float
    bid_price: float | None = None
    ask_price: float | None = None

    # Financials
    turnover: float = 0.0
    margin_utilized: float = 0.0
    agent_max_principal: float = 100_000.0
    gross_pnl: float = 0.0
    brokerage: float = 40.0
    stt_ctt: float = 0.0
    exchange_charges: float = 0.0
    gst: float = 0.0
    sebi_charges: float = 0.0
    stamp_duty: float = 0.0
    total_charges: float = 0.0
    net_pnl: float = 0.0
    net_roi_pct: float = 0.0
    post_trade_balance: float = 0.0

    # Execution Provenance
    order_type: str = "MARKET"
    duration_seconds: float = 0.0
    exit_reason: str = "PROFIT_TARGET"
    upstox_feed_source: str = "Upstox V3 Live Feed"
    exchange_timestamp: str | None = None
    feed_tick_sequence: int | None = None
    hypothesis: str = ""
    strategy_params: dict[str, Any] = field(default_factory=dict)
    status: str = "CLOSED"

    # Execution realism (added after the 2026-09-28 audit)
    #: Adverse slippage applied to the entry fill, in price points.
    entry_slippage_points: float = 0.0
    #: Adverse slippage applied to the exit fill, in price points.
    exit_slippage_points: float = 0.0
    #: Simulated round-trip latency in seconds.
    latency_seconds: float = 0.0
    #: Whether the fill was rejected by the simulated execution model.
    fill_rejected: bool = False
    #: Whether the trade passed the cost gate at entry (always True for a
    #: recorded trade, but recorded for auditability).
    passed_cost_gate: bool = True
    #: Edge-to-cost ratio the trade cleared at entry.
    edge_to_cost_ratio: float = 0.0
    #: Win rate the trade needed to break even at its own target/stop.
    required_win_rate: float = 0.0
    #: Signal confidence that authorised the entry.
    signal_confidence: float = 0.0
    #: Data split the trade belongs to, for anti-overfit separation.
    data_split: str = "LIVE"
    #: Execution realism note, e.g. "stop exit filled with adverse slippage".
    execution_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _empty_cost_awareness() -> dict[str, Any]:
    """Zeroed cost-awareness block, used when no trades exist."""
    return {
        "gross_win_rate": 0.0,
        "net_win_rate": 0.0,
        "cost_drag_pp": 0.0,
        "charges_pct_of_gross_edge": 0.0,
        "avg_charges_per_trade": 0.0,
        "avg_required_win_rate": 0.0,
        "profitability_gap_pp": 0.0,
        "gross_winners_became_net_losers": 0,
        "slippage_total_points": 0.0,
        "verdict": "No trades recorded",
    }


def _cost_awareness(
    trades: list[UpstoxLiveTradeRecord],
    gross_winning: list[UpstoxLiveTradeRecord],
) -> dict[str, Any]:
    """Quantify how much of the theoretical edge transaction costs consumed.

    The headline diagnostic: ``profitability_gap_pp`` is the gap between the win
    rate the trades required and the win rate they actually achieved. A large
    positive gap means the cost structure, not the signal, is the binding
    constraint - exactly the pre-audit failure mode.
    """
    n = len(trades)
    if n == 0:
        return _empty_cost_awareness()

    net_wins = [t for t in trades if t.net_pnl > 0]
    gross_pnl_total = sum(t.gross_pnl for t in trades)
    charges_total = sum(t.total_charges for t in trades)

    gross_wr = 100.0 * len(gross_winning) / n
    net_wr = 100.0 * len(net_wins) / n

    required = [t.required_win_rate for t in trades if t.required_win_rate > 0]
    avg_required = (100.0 * sum(required) / len(required)) if required else 0.0

    charges_pct_edge = (
        100.0 * charges_total / abs(gross_pnl_total) if abs(gross_pnl_total) > 0 else 0.0
    )

    # A trade that won on price but lost after charges is the clearest possible
    # evidence of a cost problem rather than a signal problem.
    flipped = [t for t in gross_winning if t.net_pnl <= 0]

    gap = avg_required - net_wr if avg_required > 0 else 0.0
    if not net_wins and n > 0:
        verdict = "CRITICAL: no trade closed profitable"
    elif gap > 20:
        verdict = f"CRITICAL: win rate {gap:.0f}pp below the cost-adjusted break-even"
    elif gap > 5:
        verdict = f"WARNING: win rate {gap:.0f}pp below cost-adjusted break-even"
    elif charges_pct_edge > 50:
        verdict = "WARNING: charges consume over half the gross edge"
    elif net_wr > avg_required and gross_pnl_total > 0:
        verdict = "HEALTHY: beating cost-adjusted break-even"
    else:
        verdict = "NEUTRAL: insufficient evidence to judge"

    return {
        "gross_win_rate": round(gross_wr, 1),
        "net_win_rate": round(net_wr, 1),
        "cost_drag_pp": round(gross_wr - net_wr, 1),
        "charges_pct_of_gross_edge": round(charges_pct_edge, 1),
        "avg_charges_per_trade": round(charges_total / n, 2),
        "avg_required_win_rate": round(avg_required, 1),
        "profitability_gap_pp": round(gap, 1),
        "gross_winners_became_net_losers": len(flipped),
        "slippage_total_points": round(
            sum(t.entry_slippage_points + t.exit_slippage_points for t in trades), 2
        ),
        "verdict": verdict,
    }


class UpstoxLiveTradeLedger:
    """Dedicated circular ledger maintaining up to 1,000 Upstox live market trades with full lot details."""

    def __init__(
        self,
        capacity: int = MAX_TRADES_CAPACITY,
        ledger_path: Path | None = None,
    ) -> None:
        self._capacity = capacity
        self._ledger_path = ledger_path or LEDGER_FILE_PATH
        self._trades: deque[UpstoxLiveTradeRecord] = deque(maxlen=capacity)
        self.degraded = False
        self.quarantined_to: Path | None = None
        self._save_blocked = False
        self._load_persisted_trades()

    def _load_persisted_trades(self) -> None:
        """Load trades from the JSON file. An unreadable file is preserved
        (never overwritten by an empty ledger) and the ledger starts degraded."""
        result = read_json_or_quarantine(self._ledger_path)
        self.degraded = result.degraded
        self.quarantined_to = result.quarantined_to
        self._save_blocked = result.blocked
        if result.degraded or result.data is None:
            return
        try:
            if not isinstance(result.data, list):
                raise TypeError("ledger root must be a list")
            records = [UpstoxLiveTradeRecord(**item) for item in result.data[-self._capacity :]]
        except (TypeError, ValueError, KeyError) as exc:
            failed = quarantine_after_failure(self._ledger_path, f"schema: {type(exc).__name__}")
            self.degraded = True
            self.quarantined_to = failed.quarantined_to
            self._save_blocked = failed.blocked
            return
        self._trades.extend(records)
        LOGGER.info(
            "Loaded %d Upstox live market trades from %s", len(self._trades), self._ledger_path
        )

    def _save_to_disk(self) -> None:
        """Persist current trades to file."""
        if self._save_blocked:
            LOGGER.error("Refusing to save the Upstox ledger: the existing file is unreadable and could not be preserved")
            return
        try:
            self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
            serializable = [t.to_dict() for t in self._trades]
            with open(self._ledger_path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2)
        except Exception as e:
            LOGGER.warning("Could not persist Upstox trade ledger: %s", e)

    def record_trade(
        self,
        agent_id: str,
        agent_name: str,
        strategy_id: str,
        strategy_name: str,
        exchange: str,
        instrument_key: str,
        symbol: str,
        direction: str,
        lot_size: float,
        lots: float,
        entry_price: float,
        exit_price: float,
        margin_utilized: float,
        agent_max_principal: float,
        post_trade_balance: float,
        duration_seconds: float = 0.0,
        exit_reason: str = "PROFIT_TARGET",
        upstox_feed_source: str = "Upstox V3 Live Feed",
        exchange_timestamp: str | None = None,
        feed_tick_sequence: int | None = None,
        hypothesis: str = "",
        strategy_params: dict[str, Any] | None = None,
        bid_price: float | None = None,
        ask_price: float | None = None,
        lot_unit: str = "grams",
        entry_slippage_points: float = 0.0,
        exit_slippage_points: float = 0.0,
        latency_seconds: float = 0.0,
        fill_rejected: bool = False,
        passed_cost_gate: bool = True,
        edge_to_cost_ratio: float = 0.0,
        required_win_rate: float = 0.0,
        signal_confidence: float = 0.0,
        data_split: str = "LIVE",
        execution_note: str = "",
    ) -> UpstoxLiveTradeRecord:
        """Record a market trade with precise lot calculation and Upstox statutory fees."""
        now_utc = datetime.now(UTC)
        now_ist = now_utc.astimezone(IST)
        ist_str = now_ist.strftime("%Y-%m-%d %H:%M:%S IST")

        total_qty = round(float(lots) * float(lot_size), 3)

        # Gross P&L: LONG = (exit - entry) * multiplier, SHORT = (entry - exit) * multiplier.
        # MCX gold is quoted per 10g while lots are in grams, so the multiplier
        # is notional-normalised via the shared cost module.
        multiplier = pnl_multiplier(
            symbol=symbol, lot_size=float(lot_size), total_quantity=total_qty
        )

        if direction.upper() == "LONG":
            gross_pnl = round((exit_price - entry_price) * multiplier, 2)
            order_side = "BUY"
        else:
            gross_pnl = round((entry_price - exit_price) * multiplier, 2)
            order_side = "SELL"

        turnover = round((entry_price + exit_price) * multiplier, 2)
        charges = _calculate_upstox_charges(
            exchange=exchange, turnover=turnover, gross_pnl=gross_pnl
        )

        net_pnl = round(gross_pnl - charges["total_charges"], 2)
        net_roi = round((net_pnl / margin_utilized * 100.0), 2) if margin_utilized > 0 else 0.0

        trade_record = UpstoxLiveTradeRecord(
            trade_id=str(uuid.uuid4())[:12],
            timestamp=now_utc.isoformat(),
            ist_timestamp=ist_str,
            agent_id=agent_id,
            agent_name=agent_name,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            exchange=exchange,
            instrument_key=instrument_key,
            symbol=symbol,
            order_side=order_side,
            direction=direction.upper(),
            lot_size=lot_size,
            lots=lots,
            total_quantity=total_qty,
            lot_unit=lot_unit,
            entry_price=round(entry_price, 2),
            exit_price=round(exit_price, 2),
            bid_price=bid_price,
            ask_price=ask_price,
            turnover=turnover,
            margin_utilized=round(margin_utilized, 2),
            agent_max_principal=round(agent_max_principal, 2),
            gross_pnl=gross_pnl,
            brokerage=charges["brokerage"],
            stt_ctt=charges["stt_ctt"],
            exchange_charges=charges["exchange_charges"],
            gst=charges["gst"],
            sebi_charges=charges["sebi_charges"],
            stamp_duty=charges["stamp_duty"],
            total_charges=charges["total_charges"],
            net_pnl=net_pnl,
            net_roi_pct=net_roi,
            post_trade_balance=round(post_trade_balance, 2),
            order_type="MARKET",
            duration_seconds=round(duration_seconds, 1),
            exit_reason=exit_reason,
            upstox_feed_source=upstox_feed_source,
            exchange_timestamp=exchange_timestamp,
            feed_tick_sequence=feed_tick_sequence,
            hypothesis=hypothesis,
            strategy_params=strategy_params or {},
            status="CLOSED",
            entry_slippage_points=round(entry_slippage_points, 3),
            exit_slippage_points=round(exit_slippage_points, 3),
            latency_seconds=round(latency_seconds, 3),
            fill_rejected=fill_rejected,
            passed_cost_gate=passed_cost_gate,
            edge_to_cost_ratio=round(edge_to_cost_ratio, 3),
            required_win_rate=round(required_win_rate, 4),
            signal_confidence=round(signal_confidence, 3),
            data_split=data_split,
            execution_note=execution_note,
        )

        self._trades.appendleft(trade_record)  # Newest trades at index 0
        self._save_to_disk()
        LOGGER.info(
            "Logged Upstox Live Trade [%s]: Agent=%s, Strategy=%s, %s %s lots (%s %s), Entry=₹%s, Exit=₹%s, Net PnL=₹%s",
            trade_record.trade_id,
            agent_name,
            strategy_id,
            direction,
            f"{lots:g}",
            f"{total_qty:g}",
            lot_unit,
            f"{entry_price:,.2f}",
            f"{exit_price:,.2f}",
            f"{net_pnl:,.2f}",
        )
        return trade_record

    def get_trades(
        self,
        limit: int = 50,
        offset: int = 0,
        agent_name: str | None = None,
        symbol: str | None = None,
        direction: str | None = None,
    ) -> dict[str, Any]:
        """Fetch trades from the 1,000 capacity buffer with filtering and pagination."""
        all_trades = list(self._trades)

        if agent_name:
            all_trades = [t for t in all_trades if t.agent_name.lower() == agent_name.lower()]
        if symbol:
            all_trades = [t for t in all_trades if symbol.lower() in t.symbol.lower()]
        if direction and direction.upper() != "ALL":
            all_trades = [t for t in all_trades if t.direction.upper() == direction.upper()]

        total_filtered = len(all_trades)
        paginated = all_trades[offset : offset + limit]

        return {
            "total_trades": total_filtered,
            "capacity": self._capacity,
            "buffer_count": len(self._trades),
            "offset": offset,
            "limit": limit,
            "trades": [t.to_dict() for t in paginated],
        }

    def get_summary_statistics(self) -> dict[str, Any]:
        """Charge-aware summary statistics.

        Every headline figure is net of statutory charges, and the cost drag is
        reported explicitly: gross win rate vs net win rate, charge-to-edge
        ratio, and the average break-even win rate the trades actually required.
        Pre-audit reporting was gross-only, which is why the bleed was invisible.
        """
        trades = list(self._trades)
        if not trades:
            return {
                "total_trades": 0,
                "capacity": self._capacity,
                "gross_pnl": 0.0,
                "net_pnl": 0.0,
                "total_lots_traded": 0,
                "total_turnover": 0.0,
                "total_upstox_charges": 0.0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "avg_trade_pnl": 0.0,
                "cost_awareness": _empty_cost_awareness(),
            }

        net_winning = [t for t in trades if t.net_pnl > 0]
        net_losing = [t for t in trades if t.net_pnl < 0]
        gross_winning = [t for t in trades if t.gross_pnl > 0]
        gross_profit = sum(t.net_pnl for t in net_winning)
        gross_loss = abs(sum(t.net_pnl for t in net_losing))

        profit_factor = (
            round(gross_profit / gross_loss, 2)
            if gross_loss > 0
            else (999.0 if gross_profit > 0 else 0.0)
        )
        win_rate = round(len(net_winning) / len(trades) * 100.0, 1)

        return {
            "total_trades": len(trades),
            "capacity": self._capacity,
            "gross_pnl": round(sum(t.gross_pnl for t in trades), 2),
            "net_pnl": round(sum(t.net_pnl for t in trades), 2),
            "total_lots_traded": round(sum(t.lots for t in trades), 2),
            "total_turnover": round(sum(t.turnover for t in trades), 2),
            "total_upstox_charges": round(sum(t.total_charges for t in trades), 2),
            "winning_trades": len(net_winning),
            "losing_trades": len(net_losing),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_trade_pnl": round(sum(t.net_pnl for t in trades) / len(trades), 2),
            "cost_awareness": _cost_awareness(trades, gross_winning),
        }

    def get_agent_cost_report(self, agent_name: str) -> dict[str, Any]:
        """Per-agent cost-drag report, so a bleed can be attributed to charges."""
        trades = [t for t in self._trades if t.agent_name.lower() == agent_name.lower()]
        if not trades:
            return {"agent": agent_name, "total_trades": 0, "cost_awareness": _empty_cost_awareness()}
        gross_winning = [t for t in trades if t.gross_pnl > 0]
        return {
            "agent": agent_name,
            "total_trades": len(trades),
            "net_pnl": round(sum(t.net_pnl for t in trades), 2),
            "gross_pnl": round(sum(t.gross_pnl for t in trades), 2),
            "total_charges": round(sum(t.total_charges for t in trades), 2),
            "cost_awareness": _cost_awareness(trades, gross_winning),
        }

    def export_csv(self) -> str:
        """Export all trades currently in the ledger buffer to a standard CSV string."""
        trades = list(self._trades)
        output = io.StringIO()
        fieldnames = [
            "trade_id",
            "timestamp_utc",
            "ist_timestamp",
            "agent_name",
            "strategy_id",
            "strategy_name",
            "exchange",
            "symbol",
            "direction",
            "order_side",
            "lots",
            "lot_size",
            "total_quantity",
            "lot_unit",
            "entry_price",
            "exit_price",
            "turnover",
            "margin_utilized",
            "agent_max_principal",
            "gross_pnl",
            "brokerage",
            "stt_ctt",
            "exchange_charges",
            "gst",
            "total_charges",
            "net_pnl",
            "net_roi_pct",
            "post_trade_balance",
            "duration_seconds",
            "exit_reason",
            "upstox_feed_source",
            "edge_to_cost_ratio",
            "required_win_rate",
            "signal_confidence",
            "entry_slippage_points",
            "exit_slippage_points",
            "latency_seconds",
            "fill_rejected",
            "passed_cost_gate",
            "data_split",
            "execution_note",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for t in trades:
            row = t.to_dict()
            row["timestamp_utc"] = row.pop("timestamp")
            writer.writerow({k: row.get(k, "") for k in fieldnames})
        return output.getvalue()

    def clear(self) -> None:
        """Reset the in-memory trade buffer."""
        self._trades.clear()
        self._save_to_disk()


# Global Singleton Ledger
_UPSTOX_LEDGER: UpstoxLiveTradeLedger | None = None


def get_upstox_trade_ledger() -> UpstoxLiveTradeLedger:
    global _UPSTOX_LEDGER
    if _UPSTOX_LEDGER is None:
        _UPSTOX_LEDGER = UpstoxLiveTradeLedger()
    return _UPSTOX_LEDGER
