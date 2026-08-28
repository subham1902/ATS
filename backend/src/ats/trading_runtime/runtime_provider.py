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
        self._state.can_enter = False

    def resume(self) -> None:
        self._state.paused = False
        self._state.can_enter = (
            self._state.phase == RuntimeSessionPhase.ENTRY_ALLOWED and not self._state.is_halted
        )

    def halt(self) -> None:
        self._state.is_halted = True
        self._state.can_enter = False
        self._state.phase = RuntimeSessionPhase.HALTED
        self._state.effective_mode = TradingMode.HALTED

    def update_from_engine(self, engine: object) -> None:
        if engine is None:
            return
        from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

        from ats.contracts.common import SystemClock

        if hasattr(engine, "state"):
            st = engine.state
            if hasattr(st, "open_positions"):
                pos_list: list[dict[str, object]] = []
                total_unrealized = Decimal("0")
                total_realized = Decimal("0")
                for pos in getattr(st, "open_positions", {}).values():
                    total_unrealized += getattr(pos, "unrealized_pnl", Decimal("0"))
                    total_realized += getattr(pos, "realized_pnl", Decimal("0"))
                    raw_pid = getattr(pos, "position_id", str(uuid4()))
                    try:
                        pid = UUID(str(raw_pid))
                    except (ValueError, TypeError):
                        pid = uuid5(NAMESPACE_DNS, str(raw_pid))
                    recommendation = "KEEP"
                    recommendation_reasons: tuple[str, ...] = ()
                    try:
                        from ats.trading_runtime.position_monitor import evaluate_position

                        decision = evaluate_position(
                            config=engine.config.position_monitor,
                            position=pos,
                            hwm=getattr(st, "hwm_state", None),
                            evaluation_time=SystemClock().now(),
                        )
                        recommendation = decision.action.value
                        recommendation_reasons = decision.reason_codes
                    except (AttributeError, TypeError, ValueError):
                        recommendation_reasons = ("POSITION_EVIDENCE_UNAVAILABLE",)
                    pos_list.append(
                        {
                            "position_id": pid,
                            "instrument_id": getattr(pos, "instrument_id", "UNKNOWN"),
                            "quantity": getattr(pos, "quantity", Decimal("0")),
                            "entry_price": getattr(pos, "entry_price", Decimal("0")),
                            "mark_price": getattr(pos, "current_mark", None),
                            "unrealized_pnl": getattr(pos, "unrealized_pnl", Decimal("0")),
                            "realized_pnl": getattr(pos, "realized_pnl", Decimal("0")),
                            "origin": getattr(
                                getattr(pos, "origin", None), "value", "ATS_AUTONOMOUS"
                            ),
                            "managed_exit_mode": getattr(
                                getattr(pos, "managed_exit_mode", None), "value", "ATS_MANAGED_EXIT"
                            ),
                            "capital_committed": getattr(pos, "capital_committed", Decimal("0")),
                            "current_stop": getattr(pos, "current_stop", None),
                            "target_price": None,
                            "trailing_stop": getattr(pos, "trailing_stop", None),
                            "time_held_minutes": getattr(pos, "time_held_minutes", 0),
                            "last_recommendation": recommendation,
                            "recommendation_reasons": recommendation_reasons,
                        }
                    )
                self._state.open_positions = pos_list
                self._state.unrealized = total_unrealized
                cum_realized = getattr(st, "cumulative_realized_pnl", Decimal("0"))
                self._state.realized = cum_realized + total_realized

            if hasattr(st, "peak_equity"):
                self._state.peak_equity = st.peak_equity
            if hasattr(st, "current_equity"):
                self._state.total = st.current_equity
                self._state.available = st.current_equity
            if hasattr(st, "hwm_state") and st.hwm_state is not None:
                hwm = st.hwm_state
                self._state.drawdown_fraction = getattr(hwm, "drawdown_fraction", Decimal("0"))
                self._state.hwm_state = hwm
            if hasattr(st, "kill_switch"):
                self._state.is_halted = st.kill_switch

        if hasattr(engine, "config"):
            cfg = engine.config
            if hasattr(cfg, "calendar") and hasattr(cfg, "session"):
                from ats.trading_runtime.session import resolve_session_status

                kill_switch = self._state.is_halted
                sess_status = resolve_session_status(
                    calendar=cfg.calendar,
                    config=cfg.session,
                    now=SystemClock().now(),
                    kill_switch_active=kill_switch,
                )
                self._state.phase = sess_status.phase
                self._state.can_enter = (
                    sess_status.can_enter and not self._state.paused and not self._state.is_halted
                )
                self._state.can_reduce = sess_status.can_reduce
                self._state.must_flatten = sess_status.must_flatten
                self._state.is_halted = sess_status.is_halted or self._state.is_halted

            if hasattr(cfg, "mode"):
                if (
                    hasattr(engine, "state")
                    and getattr(engine.state, "mode_state", None) is not None
                ):
                    ms = engine.state.mode_state
                    self._state.user_mode = ms.user_selected
                    self._state.effective_mode = ms.effective
                    self._state.deescalation_reason = ms.deescalation_reason
                elif self._state.user_mode == TradingMode.NORMAL and cfg.mode != TradingMode.NORMAL:
                    self._state.user_mode = cfg.mode
                    self._state.effective_mode = cfg.mode

        if hasattr(engine, "market_feed"):
            feed = engine.market_feed
            if hasattr(feed, "is_healthy"):
                self._state.feed_healthy = feed.is_healthy()

        if hasattr(engine, "broker"):
            broker = engine.broker
            if hasattr(broker, "is_healthy"):
                self._state.broker_healthy = broker.is_healthy()

        self._state.updated_at = SystemClock().now()

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
