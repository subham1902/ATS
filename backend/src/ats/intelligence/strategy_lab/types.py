"""Minimal immutable research structures."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

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


class ResearchTrade(ATSBaseModel):
    """Paired entry+exit fills (or open)."""

    trade_id: UUID
    instrument_id: InstrumentId
    entry_fill: ResearchFill
    exit_fill: ResearchFill | None
    entry_time: UTCDateTime
    exit_time: UTCDateTime | None
    pnl_fraction: Decimal | None
    pnl_r: Decimal | None


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
        for i in range(1, len(self.windows)):
            prev = self.windows[i - 1]
            cur = self.windows[i]
            # test windows must be chronological and non-overlapping
            prev_end = prev.test_end
            if prev_end is not None and cur.test_start <= prev_end:
                raise ValueError("walk-forward test windows overlap or not chronological")


__all__ = [
    "BacktestResult",
    "FillAssumption",
    "ResearchFill",
    "ResearchSignal",
    "ResearchTrade",
    "WalkForwardPlan",
    "WalkForwardWindow",
]
