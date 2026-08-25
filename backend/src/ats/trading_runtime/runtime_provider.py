"""Real runtime status provider — truthful A2 paper-only read model."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.types import LossState
from ats.trading_runtime.hwm import HWMState
from ats.trading_runtime.modes import TradingMode
from ats.trading_runtime.session import RuntimeSessionPhase


@dataclass
class RuntimeProviderState:
    phase: RuntimeSessionPhase = RuntimeSessionPhase.CLOSED
    can_enter: bool = False
    can_reduce: bool = False
    must_flatten: bool = False
    is_halted: bool = False
    user_mode: TradingMode = TradingMode.NORMAL
    effective_mode: TradingMode = TradingMode.NORMAL
    deescalation_reason: str | None = None
    available: Decimal = Decimal("100000")
    reserved: Decimal = Decimal("0")
    inflight: Decimal = Decimal("0")
    used: Decimal = Decimal("0")
    total: Decimal = Decimal("100000")
    realized: Decimal = Decimal("0")
    unrealized: Decimal = Decimal("0")
    peak_equity: Decimal = Decimal("100000")
    drawdown_fraction: Decimal = Decimal("0")
    hwm_state: HWMState | None = None
    loss_state: LossState = LossState.NORMAL
    open_positions: list[dict[str, object]] = field(default_factory=list)
    recent_decisions: list[dict[str, object]] = field(default_factory=list)
    feed_healthy: bool = True
    broker_healthy: bool = True
    paused: bool = False
    updated_at: UTCDateTime | None = None


class TradingRuntimeProvider:
    def __init__(self, state: RuntimeProviderState | None = None) -> None:
        self._state = state or RuntimeProviderState()

    def get_state(self) -> RuntimeProviderState:
        return self._state

    def set_mode(self, mode: TradingMode) -> None:
        self._state.user_mode = mode
        if mode == TradingMode.SAFE:
            self._state.effective_mode = TradingMode.SAFE
        elif mode == TradingMode.NORMAL:
            self._state.effective_mode = TradingMode.NORMAL
        elif mode == TradingMode.AGGRESSIVE:
            self._state.effective_mode = TradingMode.AGGRESSIVE

    def pause(self) -> None:
        self._state.paused = True

    def resume(self) -> None:
        self._state.paused = False

    def halt(self) -> None:
        self._state.is_halted = True
        self._state.effective_mode = TradingMode.HALTED

    def update_from_engine(self, engine: object) -> None:
        _ = engine

    def to_status_dict(self) -> dict[str, object]:
        s = self._state
        return {
            "session": {
                "phase": s.phase.value,
                "can_enter": s.can_enter,
                "can_reduce": s.can_reduce,
                "must_flatten": s.must_flatten,
                "is_halted": s.is_halted,
            },
            "trading_mode": {
                "user_selected": s.user_mode.value,
                "effective": s.effective_mode.value,
                "deescalation_reason": s.deescalation_reason,
            },
            "capital": {
                "available": str(s.available),
                "reserved": str(s.reserved),
                "inflight": str(s.inflight),
                "used": str(s.used),
                "total": str(s.total),
            },
            "pnl": {
                "realized": str(s.realized),
                "unrealized": str(s.unrealized),
                "session_peak": str(s.peak_equity),
                "drawdown_fraction": str(s.drawdown_fraction),
            },
            "loss_state": s.loss_state.value,
            "open_positions": s.open_positions,
            "recent_decisions": s.recent_decisions,
            "feed_healthy": s.feed_healthy,
            "broker_healthy": s.broker_healthy,
            "halted": s.is_halted,
            "paused_new_entries": s.paused,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }


__all__ = ["RuntimeProviderState", "TradingRuntimeProvider"]
