"""Session-end P&L reconciliation — a typed immutable session report.

Produced from deterministic Decimal accounting. Never introduces float money
or NaN/Infinity: profit factor and win rate guard against division by zero and
zero-winner/zero-loser cases explicitly.

HARD INVARIANT: ``remaining_positions == 0`` is required for a successful
``CLOSED`` reconciliation. A session with open positions cannot report success.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ats.contracts.common import UTCDateTime


@dataclass(frozen=True)
class SessionReconciliation:
    """Immutable session-end reconciliation report."""

    opening_capital: Decimal
    closing_equity: Decimal
    gross_realized_pnl: Decimal
    net_realized_pnl: Decimal
    unrealized_pnl: Decimal
    fees: Decimal
    taxes: Decimal
    slippage_cost: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal | None
    profit_factor: Decimal | None
    max_drawdown: Decimal
    largest_winner: Decimal
    largest_loser: Decimal
    rejected_orders: int
    risk_rejected_candidates: int
    emergency_exits: int
    remaining_positions: int
    started_at: UTCDateTime | None
    closed_at: UTCDateTime | None
    status: str

    @property
    def balanced(self) -> bool:
        # net_realized_pnl is already net of fees/taxes/slippage, so the equity
        # identity adds it back directly without re-subtracting the costs.
        expected = (
            self.closing_equity
            == self.opening_capital + self.net_realized_pnl + self.unrealized_pnl
        )
        return expected

    @property
    def closed_successfully(self) -> bool:
        return self.status == "CLOSED" and self.remaining_positions == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "opening_capital": str(self.opening_capital),
            "closing_equity": str(self.closing_equity),
            "gross_realized_pnl": str(self.gross_realized_pnl),
            "net_realized_pnl": str(self.net_realized_pnl),
            "unrealized_pnl": str(self.unrealized_pnl),
            "fees": str(self.fees),
            "taxes": str(self.taxes),
            "slippage_cost": str(self.slippage_cost),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": str(self.win_rate) if self.win_rate is not None else None,
            "profit_factor": str(self.profit_factor) if self.profit_factor is not None else None,
            "max_drawdown": str(self.max_drawdown),
            "largest_winner": str(self.largest_winner),
            "largest_loser": str(self.largest_loser),
            "rejected_orders": self.rejected_orders,
            "risk_rejected_candidates": self.risk_rejected_candidates,
            "emergency_exits": self.emergency_exits,
            "remaining_positions": self.remaining_positions,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "status": self.status,
        }


def build_session_reconciliation(
    *,
    opening_capital: Decimal,
    current_equity: Decimal,
    fees: Decimal,
    taxes: Decimal,
    slippage: Decimal,
    total_trades: int,
    rejected_orders: int,
    risk_rejected_candidates: int,
    emergency_exits: int,
    remaining_positions: int,
    max_drawdown: Decimal,
    started_at: UTCDateTime | None,
    closed_at: UTCDateTime | None,
    realized_pnl: Decimal | None = None,
    unrealized_pnl: Decimal = Decimal("0"),
    winners: int = 0,
    losers: int = 0,
    largest_winner: Decimal = Decimal("0"),
    largest_loser: Decimal = Decimal("0"),
    gross_realized_pnl: Decimal | None = None,
) -> SessionReconciliation:
    """Compute a safe, balanced session report from Decimal accounting inputs.

    ``net_realized_pnl`` defaults to realized P&L net of costs (approximation);
    callers may pass ``realized_pnl``/``gross_realized_pnl`` explicitly.
    Win rate and profit factor are ``None`` (never NaN/Inf) when the input
    counts are zero.
    """
    if gross_realized_pnl is None:
        gross_realized_pnl = realized_pnl if realized_pnl is not None else Decimal("0")
    # net_realized_pnl is ALWAYS net of trading costs (fees/taxes/slippage),
    # regardless of whether the caller supplied gross or realized P&L.
    realized_pnl = gross_realized_pnl - fees - taxes - slippage

    win_rate: Decimal | None = None
    if total_trades > 0:
        win_rate = (Decimal(winners) / Decimal(total_trades)) * Decimal("100")

    profit_factor: Decimal | None = None
    if losers > 0 and largest_loser > 0:
        gross_losses = largest_loser * Decimal(losers)
        gross_profits = largest_winner * Decimal(winners)
        profit_factor = gross_profits / gross_losses
    elif total_trades > 0 and gross_realized_pnl > 0 and losers == 0:
        # No losses: profit factor is undefined/infinite; report the realized
        # gross as a positive finite proxy rather than NaN/Inf.
        profit_factor = Decimal(gross_realized_pnl)

    status = "CLOSED" if remaining_positions == 0 else "NOT_CLOSED"
    return SessionReconciliation(
        opening_capital=opening_capital,
        closing_equity=current_equity,
        gross_realized_pnl=gross_realized_pnl,
        net_realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        fees=fees,
        taxes=taxes,
        slippage_cost=slippage,
        total_trades=total_trades,
        winning_trades=winners,
        losing_trades=losers,
        win_rate=win_rate,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
        largest_winner=largest_winner,
        largest_loser=largest_loser,
        rejected_orders=rejected_orders,
        risk_rejected_candidates=risk_rejected_candidates,
        emergency_exits=emergency_exits,
        remaining_positions=remaining_positions,
        started_at=started_at,
        closed_at=closed_at,
        status=status,
    )


__all__ = ["SessionReconciliation", "build_session_reconciliation"]
