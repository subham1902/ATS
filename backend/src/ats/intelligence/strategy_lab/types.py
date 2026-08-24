"""Minimal immutable research structures."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import InstrumentId


class ResearchSignal(ATSBaseModel):
    """Signal from completed bar T, evaluated via R13."""

    signal_id: UUID
    instrument_id: InstrumentId
    bar_timestamp: UTCDateTime
    bar_sequence: int
    is_entry: bool
    is_exit: bool
    strength: float | None = None


class ResearchFill(ATSBaseModel):
    """Fill at next eligible bar OPEN (conservative v1)."""

    fill_id: UUID
    signal_id: UUID
    instrument_id: InstrumentId
    side: str
    price: Decimal
    quantity: Decimal
    bar_timestamp: UTCDateTime
    bar_sequence: int
    cost: Decimal

    @model_validator(mode="after")
    def validate_fill(self) -> ResearchFill:
        if not self.price.is_finite() or not self.quantity.is_finite() or not self.cost.is_finite():
            raise ValueError("fill numeric values must be finite")
        if self.price <= 0 or self.quantity <= 0 or self.cost < 0:
            raise ValueError("fill price/quantity must be positive and cost non-negative")
        if self.side not in ("BUY", "SELL"):
            raise ValueError("fill side must be BUY or SELL")
        return self


class ResearchTrade(ATSBaseModel):
    """Paired entry+exit fills (or open). NET economics: pnl_fraction is net.

    Gross cash PnL = (exit_price - entry_price) * quantity
    Net cash PnL = gross - entry_cost - exit_cost
    Net return fraction = net_cash / (entry_price * quantity)  # denominator = entry notional
    If gross retained, named explicitly as gross_pnl_fraction.
    """

    trade_id: UUID
    instrument_id: InstrumentId
    entry_fill: ResearchFill
    exit_fill: ResearchFill | None
    entry_time: UTCDateTime
    exit_time: UTCDateTime | None
    pnl_fraction: Decimal | None  # NET
    pnl_r: Decimal | None  # NET
    gross_pnl_fraction: Decimal | None = None
    gross_pnl_r: Decimal | None = None
    gross_cash_pnl: Decimal | None = None
    net_cash_pnl: Decimal | None = None
    entry_notional: Decimal | None = None

    @model_validator(mode="after")
    def validate_economics(self) -> ResearchTrade:
        values = (
            self.pnl_fraction,
            self.pnl_r,
            self.gross_pnl_fraction,
            self.gross_pnl_r,
            self.gross_cash_pnl,
            self.net_cash_pnl,
            self.entry_notional,
        )
        if any(value is not None and not value.is_finite() for value in values):
            raise ValueError("trade economics must be finite")
        if self.entry_notional is not None and self.entry_notional <= 0:
            raise ValueError("entry_notional must be positive")
        return self


class BacktestResult(ATSBaseModel):
    """Result of deterministic backtest run."""

    result_id: UUID
    experiment_id: UUID
    trades: tuple[ResearchTrade, ...]
    fills: tuple[ResearchFill, ...]
    signals: tuple[ResearchSignal, ...]
    start_time: UTCDateTime
    end_time: UTCDateTime
    seed: int
    cost_model_version: str | None = None
    cost_model_authoritative: bool | None = None

    @model_validator(mode="after")
    def validate_result(self) -> BacktestResult:
        if self.end_time < self.start_time:
            raise ValueError("end_time must be >= start_time")
        if self.cost_model_authoritative is True and not self.cost_model_version:
            raise ValueError("authoritative result requires cost_model_version")
        return self


class FillAssumption(ATSBaseModel):
    """Frozen v1 fill assumption doc."""

    model_version: str
    description: str
    entry_at_next_open: bool = True
    exit_at_next_open: bool = True
    same_bar_exit_conservative: str = "next_open_stop_before_target"


# Walk-forward plan types
class WalkForwardWindow(ATSBaseModel):
    """Single train/test window."""

    window_id: UUID
    train_start: UTCDateTime | None
    train_end: UTCDateTime | None
    test_start: UTCDateTime
    test_end: UTCDateTime | None
    purge_bars: int
    embargo_bars: int


class WalkForwardPlan(ATSBaseModel):
    """Deterministic time-series plan."""

    plan_id: UUID
    windows: tuple[WalkForwardWindow, ...]
    mode: str  # rolling | expanding

    def validate_chronology(self) -> None:
        if self.mode != "rolling":
            raise ValueError("only rolling walk-forward mode is implemented in v1")
        if not self.windows:
            raise ValueError("walk-forward plan must contain at least one window")
        for window in self.windows:
            if window.purge_bars < 0 or window.embargo_bars < 0:
                raise ValueError("purge_bars and embargo_bars must be >=0")
            if window.train_start is None or window.train_end is None:
                if window.train_start is not None or window.train_end is not None:
                    raise ValueError("train range must be all-or-none")
            elif window.train_end >= window.test_start:
                raise ValueError("train must precede test")
        for i in range(1, len(self.windows)):
            prev = self.windows[i - 1]
            cur = self.windows[i]
            # test windows must be chronological and non-overlapping
            prev_end = prev.test_end
            if prev_end is not None and cur.test_start <= prev_end:
                raise ValueError("walk-forward test windows overlap or not chronological")
            if prev_end is not None and cur.train_start is not None:
                if cur.train_start <= prev_end:
                    raise ValueError("embargo window overlaps previous test")


__all__ = [
    "BacktestResult",
    "FillAssumption",
    "ResearchFill",
    "ResearchSignal",
    "ResearchTrade",
    "WalkForwardPlan",
    "WalkForwardWindow",
]
