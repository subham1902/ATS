"""Typed runtime models for A2 paper dashboard controls and status."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import LossState


class RuntimeTradingMode(ATSBaseModel):
    user_selected: str
    effective: str
    deescalation_reason: str | None


class RuntimeCapitalView(ATSBaseModel):
    available: Decimal
    reserved: Decimal
    inflight: Decimal
    used: Decimal
    total: Decimal


class RuntimePnLView(ATSBaseModel):
    realized: Decimal
    unrealized: Decimal
    session_peak: Decimal
    drawdown_fraction: Decimal


class RuntimePositionView(ATSBaseModel):
    position_id: UUID
    instrument_id: str
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal | None
    unrealized_pnl: Decimal


class RuntimeSessionView(ATSBaseModel):
    phase: str
    can_enter: bool
    can_reduce: bool
    must_flatten: bool
    is_halted: bool


class RuntimeStatusReadModel(ATSBaseModel):
    session: RuntimeSessionView
    trading_mode: RuntimeTradingMode
    capital: RuntimeCapitalView
    pnl: RuntimePnLView
    loss_state: LossState
    open_positions: tuple[RuntimePositionView, ...]
    recent_decisions: tuple[dict[str, object], ...]
    feed_healthy: bool
    broker_healthy: bool
    halted: bool
    paused_new_entries: bool
    updated_at: UTCDateTime


class RuntimeCommandRequest(ATSBaseModel):
    command: Literal[
        "SET_MODE",
        "PAUSE_NEW_ENTRIES",
        "RESUME_NEW_ENTRIES",
        "EXIT_POSITION",
        "FLATTEN_PORTFOLIO",
        "HALT_SYSTEM",
    ]
    mode: Literal["SAFE", "NORMAL", "AGGRESSIVE"] | None = None
    position_id: UUID | None = None


class RuntimeCommandResult(ATSBaseModel):
    accepted: bool
    reason_codes: tuple[str, ...]
    effective_mode: str | None = None


__all__ = [
    "RuntimeCapitalView",
    "RuntimeCommandRequest",
    "RuntimeCommandResult",
    "RuntimePnLView",
    "RuntimePositionView",
    "RuntimeSessionView",
    "RuntimeStatusReadModel",
    "RuntimeTradingMode",
]
