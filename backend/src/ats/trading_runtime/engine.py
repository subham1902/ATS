# ruff: noqa: E501
"""Minimal orchestration layer connecting existing ATS components.

Event arrives -> market state -> P0 safety -> P1 monitor -> opportunity trigger ->
deterministic strategy -> candidate -> anti-churn -> portfolio reservation -> A04 ->
execution FSM -> PaperBroker -> fills -> portfolio/positions -> async audit.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.types import LossState
from ats.market.calendar.models import SessionCalendar
from ats.trading_runtime.anti_churn import AntiChurnConfig, ChurnFacts, evaluate_churn
from ats.trading_runtime.authority_service import (
    NoopAuthorityService,
    TradingAuthorityService,
)
from ats.trading_runtime.broker import ExecutionBroker, MarketDataFeed
from ats.trading_runtime.candidate_factory import build_opportunity_candidate
from ats.trading_runtime.hwm import HWMConfig, HWMState, evaluate_hwm
from ats.trading_runtime.modes import (
    DEFAULT_MODE_ENVELOPES,
    ModeEnvelope,
    ModeState,
    TradingMode,
    is_entry_blocked_by_mode,
    resolve_effective_mode,
)
from ats.trading_runtime.position_authority import PositionAuthorityStore
from ats.trading_runtime.position_monitor import (
    ManagedExitMode,
    MonitoredPosition,
    PositionMonitorConfig,
    PositionOrigin,
    evaluate_position,
    update_mark,
)
from ats.trading_runtime.reduction_authority import (
    BeginReductionRequest,
    ReductionAuthorityService,
)
from ats.trading_runtime.runtime_checkpoint import (
    RuntimeCheckpointStore,
    deserialize_position,
    serialize_position,
)
from ats.trading_runtime.safety import SafetyFacts, evaluate_p0_safety
from ats.trading_runtime.session import SessionRuntimeConfig, resolve_session_status
from ats.trading_runtime.strategy import BarFeatures, StrategyConfig, StrategySignal, evaluate_bar


class RuntimeEventKind(StrEnum):
    BAR = "BAR"
    TICK = "TICK"
    FILL = "FILL"
    PRICE_SHOCK = "PRICE_SHOCK"
    DATA_STALE = "DATA_STALE"
    POSITION_RISK_CHANGE = "POSITION_RISK_CHANGE"
    THESIS_INVALIDATED = "THESIS_INVALIDATED"
    PARTIAL_FILL = "PARTIAL_FILL"
    SESSION_EXIT_APPROACHING = "SESSION_EXIT_APPROACHING"
    FLATTEN = "FLATTEN"
    HALT = "HALT"


@dataclass(frozen=True)
class RuntimeEvent:
    kind: RuntimeEventKind
    instrument_id: str | None
    payload: dict[str, Any]
    at: UTCDateTime


@dataclass
class LatencySample:
    stage: str
    duration_ms: float


@dataclass
class EngineMetrics:
    samples: list[LatencySample] = field(default_factory=list)

    def record(self, stage: str, start_ns: int) -> None:
        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        self.samples.append(LatencySample(stage=stage, duration_ms=elapsed_ms))

    def summary(self) -> dict[str, dict[str, float]]:
        from collections import defaultdict

        grouped: dict[str, list[float]] = defaultdict(list)
        for s in self.samples:
            grouped[s.stage].append(s.duration_ms)
        out: dict[str, dict[str, float]] = {}
        for stage, values in grouped.items():
            values_sorted = sorted(values)
            n = len(values_sorted)
            p50 = values_sorted[n // 2]
            p95 = values_sorted[int(n * 0.95)] if n >= 20 else values_sorted[-1]
            p99 = values_sorted[int(n * 0.99)] if n >= 100 else values_sorted[-1]
            out[stage] = {"count": float(n), "p50": p50, "p95": p95, "p99": p99}
        return out


@dataclass
class RuntimeConfig:
    calendar: SessionCalendar
    session: SessionRuntimeConfig = field(default_factory=SessionRuntimeConfig)
    hwm: HWMConfig = field(default_factory=HWMConfig)
    position_monitor: PositionMonitorConfig = field(default_factory=PositionMonitorConfig)
    anti_churn: AntiChurnConfig = field(default_factory=AntiChurnConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    max_quote_age_ms: int = 2000
    mode: TradingMode = TradingMode.NORMAL
    mode_envelopes: dict[TradingMode, ModeEnvelope] = field(
        default_factory=lambda: dict(DEFAULT_MODE_ENVELOPES)
    )
    default_lot_size: int = 25
    authority_reservation_amount: Decimal = Decimal("50000")


@dataclass
class RuntimeState:
    hwm_state: HWMState | None = None
    session_start_equity: Decimal = Decimal("100000")
    current_equity: Decimal = Decimal("100000")
    peak_equity: Decimal = Decimal("100000")
    cumulative_realized_pnl: Decimal = Decimal("0")
    closed_positions: list[dict[str, Any]] = field(default_factory=list)
    mode_state: ModeState | None = None
    open_positions: dict[str, MonitoredPosition] = field(default_factory=dict)
    kill_switch: bool = False
    last_exit_at: dict[str, UTCDateTime] = field(default_factory=dict)
    last_thesis: dict[str, str] = field(default_factory=dict)
    pending_exits: dict[str, PendingExit] = field(default_factory=dict)
    last_exit_direction: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PendingExit:
    """Idempotent reduction request; a fill is the only event that closes a position."""

    position_id: str
    requested_at: UTCDateTime
    reason_codes: tuple[str, ...]
    source: str
    authorized: bool
    reduction_id: str | None = None
    execution_state: str | None = None


class ReductionRequestFactory(Protocol):
    def __call__(
        self,
        position_id: str,
        at: UTCDateTime,
        reason_codes: tuple[str, ...],
        source: str,
    ) -> BeginReductionRequest: ...


class TradingRuntime:
    def __init__(
        self,
        *,
        config: RuntimeConfig,
        market_feed: MarketDataFeed,
        broker: ExecutionBroker,
        state: RuntimeState | None = None,
        authority: TradingAuthorityService | None = None,
        reduction_authority: ReductionAuthorityService | None = None,
        reduction_request_factory: ReductionRequestFactory | None = None,
        durable_positions: PositionAuthorityStore | None = None,
        runtime_checkpoint: RuntimeCheckpointStore | None = None,
    ) -> None:
        self.config = config
        self.market_feed = market_feed
        self.broker = broker
        self.authority: TradingAuthorityService = authority or NoopAuthorityService()
        self.reduction_authority = reduction_authority
        self.reduction_request_factory = reduction_request_factory
        self.durable_positions = durable_positions
        self.runtime_checkpoint = runtime_checkpoint
        self.state = state or RuntimeState()
        self.metrics = EngineMetrics()
        self._event_log: list[RuntimeEvent] = []
        self._decision_log: list[dict[str, Any]] = []
        self._recover_durable_runtime_state()

    def process_event(self, event: RuntimeEvent) -> dict[str, Any]:
        t0 = time.perf_counter_ns()
        self._event_log.append(event)

        # --- Live mark update: re-mark all open positions on every market event ---
        mark_kinds = (RuntimeEventKind.BAR, RuntimeEventKind.TICK, RuntimeEventKind.PRICE_SHOCK)
        if event.kind in mark_kinds:
            self._update_position_marks(event)

        session_status = resolve_session_status(
            calendar=self.config.calendar,
            config=self.config.session,
            now=event.at,
            kill_switch_active=self.state.kill_switch,
        )
        self.metrics.record("state_update", t0)

        t1 = time.perf_counter_ns()
        broker_healthy = self.broker.is_healthy()
        data_fresh = True
        if event.instrument_id is not None:
            data_fresh = self.market_feed.data_fresh(
                event.instrument_id, now=event.at, max_age_ms=self.config.max_quote_age_ms
            )
        safety_facts = SafetyFacts(
            session=session_status,
            kill_switch_active=self.state.kill_switch,
            data_fresh=data_fresh,
            broker_healthy=broker_healthy,
            capital_ok=True,
            clock_healthy=True,
            position_max_loss_breached=False,
            daily_loss_limit_breached=False,
            loss_state=self._current_loss_state(),
            open_positions=(),
            current_equity=self.state.current_equity,
            peak_equity=self.state.peak_equity,
        )
        safety = evaluate_p0_safety(facts=safety_facts, evaluation_time=event.at)
        self.metrics.record("p0_safety", t1)

        t2 = time.perf_counter_ns()
        exits: list[dict[str, Any]] = []
        for pid, pos in list(self.state.open_positions.items()):
            dec = evaluate_position(
                config=self.config.position_monitor,
                position=pos,
                hwm=self.state.hwm_state,
                evaluation_time=event.at,
            )
            if dec.should_exit_now and pos.managed_exit_mode is ManagedExitMode.ATS_MANAGED_EXIT:
                exits.append(
                    {"position_id": pid, "action": dec.action.value, "reasons": dec.reason_codes}
                )
        self.metrics.record("p1_position_check", t2)

        if safety.require_flatten and self.state.open_positions:
            for pid in list(self.state.open_positions.keys()):
                if not any(e["position_id"] == pid for e in exits):
                    exits.append(
                        {
                            "position_id": pid,
                            "action": "EXIT",
                            "reasons": ("RUNTIME_FLATTEN_REQUIRED",),
                        }
                    )

        if exits:
            for e in exits:
                self.request_exit(
                    e["position_id"],
                    event.at,
                    reason_codes=tuple(e["reasons"]),
                    source="AUTOMATIC",
                )
            self._decision_log.append({"at": event.at.isoformat(), "exits": exits})
            return {
                "verdict": safety.verdict.value,
                "session_phase": session_status.phase.value,
                "exits": exits,
                "safety": safety.reason_codes,
            }

        hwm_hint = self.state.hwm_state.mode_hint if self.state.hwm_state is not None else None
        effective_mode_state = resolve_effective_mode(
            user_selected=self.config.mode,
            hwm_deescalated=hwm_hint,
            safety_halted=safety.block_new_risk,
            previous_effective=self.state.mode_state.effective if self.state.mode_state else None,
        )
        self.state.mode_state = effective_mode_state

        if safety.block_new_risk or effective_mode_state.effective == TradingMode.HALTED:
            reasons = safety.reason_codes if safety.block_new_risk else ("MODE_HALTED",)
            self._decision_log.append({"at": event.at.isoformat(), "blocked": reasons})
            return {
                "verdict": safety.verdict.value,
                "session_phase": session_status.phase.value,
                "blocked": reasons,
            }

        t3 = time.perf_counter_ns()
        signal: StrategySignal | None = None
        bar_kinds = (RuntimeEventKind.BAR, RuntimeEventKind.TICK, RuntimeEventKind.PRICE_SHOCK)
        if event.kind in bar_kinds:
            instrument = event.instrument_id or "NIFTY"
            mark = self.market_feed.latest_mark(instrument)
            prev = event.payload.get("previous_close")
            bar = BarFeatures(
                instrument_id=instrument,
                close=Decimal(str(mark)) if mark is not None else Decimal("100"),
                previous_close=Decimal(str(prev)) if prev is not None else None,
                evaluation_time=event.at,
                data_fresh=data_fresh,
            )
            last_exit = self.state.last_exit_at.get(instrument)
            bars_since = None
            minutes_since = None
            if last_exit is not None:
                delta_s = (event.at - last_exit).total_seconds()
                minutes_since = int(delta_s // 60)
                bars_since = int(delta_s // 300)
            churn_facts = ChurnFacts(
                instrument_id=instrument,
                direction="BULLISH",
                thesis_id=None,
                expected_edge_r=0.0,
                spread_ticks=None,
                bars_since_exit_same_instrument=bars_since,
                minutes_since_exit_same_instrument=minutes_since,
                campaign_trades_started=len(self.state.open_positions),
                evaluation_time=event.at,
                last_exit_direction=self.state.last_exit_direction.get(instrument),
            )
            signal = evaluate_bar(
                config=self.config.strategy,
                anti_churn=self.config.anti_churn,
                bar=bar,
                churn_facts=churn_facts,
            )
        self.metrics.record("signal_evaluation", t3)

        if signal is not None and signal.is_actionable:
            envelope = self.config.mode_envelopes.get(effective_mode_state.effective)
            if envelope is not None:
                if is_entry_blocked_by_mode(
                    envelope=envelope, open_positions=len(self.state.open_positions)
                ):
                    self._decision_log.append(
                        {
                            "at": event.at.isoformat(),
                            "mode_blocked": ("MODE_MAX_CONCURRENT_POSITIONS",),
                        }
                    )
                    return {
                        "verdict": safety.verdict.value,
                        "session_phase": session_status.phase.value,
                        "mode_blocked": ("MODE_MAX_CONCURRENT_POSITIONS",),
                    }
                if signal.expected_edge_r < envelope.minimum_expected_edge_r:
                    self._decision_log.append(
                        {"at": event.at.isoformat(), "mode_blocked": ("MODE_MIN_EDGE_NOT_MET",)}
                    )
                    return {
                        "verdict": safety.verdict.value,
                        "session_phase": session_status.phase.value,
                        "mode_blocked": ("MODE_MIN_EDGE_NOT_MET",),
                    }

            last_exit = self.state.last_exit_at.get(signal.instrument_id)
            bars_since = None
            minutes_since = None
            if last_exit is not None:
                delta_s = (event.at - last_exit).total_seconds()
                minutes_since = int(delta_s // 60)
                bars_since = int(delta_s // 300)

            anti = evaluate_churn(
                config=self.config.anti_churn,
                facts=ChurnFacts(
                    instrument_id=signal.instrument_id,
                    direction=signal.direction,
                    thesis_id=signal.thesis_id,
                    expected_edge_r=signal.expected_edge_r,
                    spread_ticks=None,
                    bars_since_exit_same_instrument=bars_since,
                    minutes_since_exit_same_instrument=minutes_since,
                    campaign_trades_started=len(self.state.open_positions),
                    evaluation_time=event.at,
                    last_exit_direction=self.state.last_exit_direction.get(signal.instrument_id),
                ),
            )
            if not anti.allowed:
                self._decision_log.append(
                    {"at": event.at.isoformat(), "churn_blocked": anti.reason_codes}
                )
                return {
                    "verdict": safety.verdict.value,
                    "session_phase": session_status.phase.value,
                    "churn_blocked": anti.reason_codes,
                }

            auth_result = self._try_authority_for_signal(signal=signal, at=event.at)
            if auth_result is not None and not auth_result.get("allowed", True):
                self._decision_log.append(
                    {"at": event.at.isoformat(), "authority_blocked": auth_result["reasons"]}
                )
                return {
                    "verdict": safety.verdict.value,
                    "session_phase": session_status.phase.value,
                    "authority_blocked": auth_result["reasons"],
                }

            hwm_hint = None
            if self.state.hwm_state is not None:
                hwm_hint = self.state.hwm_state.mode_hint
            self._decision_log.append(
                {
                    "at": event.at.isoformat(),
                    "candidate": {
                        "instrument": signal.instrument_id,
                        "option": signal.option_type,
                        "edge_r": signal.expected_edge_r,
                        "hwm_hint": hwm_hint,
                        "authority": auth_result,
                    },
                }
            )
            return {
                "verdict": safety.verdict.value,
                "session_phase": session_status.phase.value,
                "candidate": {
                    "instrument": signal.instrument_id,
                    "option": signal.option_type,
                    "edge_r": signal.expected_edge_r,
                },
                "authority": auth_result,
            }

        return {
            "verdict": safety.verdict.value,
            "session_phase": session_status.phase.value,
            "no_action": True,
        }

    def handle_fill(
        self,
        position_id: str,
        mark: Decimal,
        quantity: Decimal,
        at: UTCDateTime,
        *,
        instrument_id: str | None = None,
        lot_size: int | None = None,
        direction: str = "BULLISH",
        expected_edge_r: float = 0.0,
        entry_iv: float | None = None,
        origin: PositionOrigin = PositionOrigin.ATS_AUTONOMOUS,
        managed_exit_mode: ManagedExitMode = ManagedExitMode.ATS_MANAGED_EXIT,
        operator_action_id: str | None = None,
    ) -> None:
        from ats.trading_runtime.risk_terms import derive_position_risk_terms

        effective_lot = lot_size if lot_size is not None else self.config.default_lot_size
        risk_terms = derive_position_risk_terms(
            entry_price=mark,
            quantity=quantity,
            risk_fraction=self.config.position_monitor.hard_loss_fraction,
        )
        self.state.open_positions[position_id] = MonitoredPosition(
            position_id=position_id,
            instrument_id=instrument_id
            or (position_id.split(":")[0] if ":" in position_id else position_id),
            entry_price=mark,
            current_mark=mark,
            quantity=quantity,
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            peak_pnl=Decimal("0"),
            current_stop=None,
            trailing_stop=None,
            time_held_minutes=0,
            entry_thesis_ref=None,
            thesis_healthy=True,
            data_fresh=True,
            last_event="FILL",
            capital_at_risk=risk_terms.capital_committed,
            capital_committed=risk_terms.capital_committed,
            risk_budget=risk_terms.risk_budget,
            maximum_loss_per_unit=risk_terms.maximum_loss_per_unit,
            entry_iv=entry_iv,
            entry_at=at,
            lot_size=effective_lot,
            expected_edge_r=expected_edge_r,
            direction=direction,
            origin=origin,
            managed_exit_mode=managed_exit_mode,
            operator_action_id=operator_action_id,
        )
        self._persist_runtime_checkpoint()

    def set_managed_exit_mode(self, position_id: str, mode: ManagedExitMode) -> bool:
        """Persist the operator-selected mode in canonical position state."""
        position = self.state.open_positions.get(position_id)
        if position is None:
            return False
        from dataclasses import replace

        self.state.open_positions[position_id] = replace(position, managed_exit_mode=mode)
        self._persist_runtime_checkpoint()
        return True

    def request_exit(
        self,
        position_id: str,
        at: UTCDateTime,
        *,
        reason_codes: tuple[str, ...] = ("MANUAL_EXIT_REQUESTED",),
        source: str = "MANUAL",
    ) -> dict[str, Any]:
        """Start or return one durable authorized reduction without closing the position."""
        if position_id not in self.state.open_positions:
            return {"accepted": False, "reasons": ("POSITION_NOT_FOUND",)}
        existing = self.state.pending_exits.get(position_id)
        if existing is not None:
            return {
                "accepted": True,
                "idempotent": True,
                "authorized": existing.authorized,
                "reasons": existing.reason_codes,
                "reduction_id": existing.reduction_id,
                "execution_state": existing.execution_state,
            }
        reduction_id: str | None = None
        execution_state: str | None = None
        if self.reduction_authority is not None and self.reduction_request_factory is not None:
            try:
                request = self.reduction_request_factory(position_id, at, reason_codes, source)
                authorized_reduction = self.reduction_authority.begin_reduction(request)
                execution = self.reduction_authority.submit(
                    authorized_reduction, broker=self.broker, submitted_at=at
                )
                authorized = True
                reasons = reason_codes + ("REDUCTION_AUTHORIZED",)
                reduction_id = str(authorized_reduction.reduction_id)
                execution_state = execution.state.value
            except Exception as exc:
                return {
                    "accepted": False,
                    "authorized": False,
                    "reasons": reason_codes + (type(exc).__name__,),
                }
        else:
            authorized = isinstance(self.authority, NoopAuthorityService)
            reasons = reason_codes if authorized else reason_codes + ("EXIT_EVIDENCE_REQUIRED",)
        self.state.pending_exits[position_id] = PendingExit(
            position_id=position_id,
            requested_at=at,
            reason_codes=reasons,
            source=source,
            authorized=authorized,
            reduction_id=reduction_id,
            execution_state=execution_state,
        )
        self._persist_runtime_checkpoint()
        return {
            "accepted": True,
            "idempotent": False,
            "authorized": authorized,
            "reasons": reasons,
            "reduction_id": reduction_id,
            "execution_state": execution_state,
        }

    def request_flatten(
        self, at: UTCDateTime, *, reason_code: str = "FLATTEN_REQUESTED", source: str = "MANUAL"
    ) -> tuple[dict[str, Any], ...]:
        return tuple(
            self.request_exit(pid, at, reason_codes=(reason_code,), source=source)
            for pid in tuple(self.state.open_positions)
        )

    def handle_exit_fill(self, position_id: str, at: UTCDateTime) -> None:
        """Apply a terminal broker fill; requests/commands must never call this directly."""
        exited = self.state.open_positions.pop(position_id, None)
        self.state.pending_exits.pop(position_id, None)
        instrument = position_id.split(":")[0] if ":" in position_id else position_id
        self.state.last_exit_at[instrument] = at
        self.state.last_thesis.pop(instrument, None)
        if exited is not None:
            self.state.last_exit_direction[instrument] = exited.direction
            # Compute trade economics
            exit_mark = exited.current_mark or exited.entry_price
            gross_pnl = (exit_mark - exited.entry_price) * exited.quantity
            # Slipped execution costs: 5 bps entry + 5 bps exit
            costs = (exited.entry_price + exit_mark) * exited.quantity * Decimal("0.0005")
            net_pnl = gross_pnl - costs
            self.state.cumulative_realized_pnl += net_pnl
            self.state.current_equity += net_pnl
            if self.state.current_equity > self.state.peak_equity:
                self.state.peak_equity = self.state.current_equity
            self.state.closed_positions.append(
                {
                    "position_id": position_id,
                    "instrument_id": exited.instrument_id,
                    "direction": exited.direction,
                    "entry_price": exited.entry_price,
                    "exit_price": exit_mark,
                    "quantity": exited.quantity,
                    "gross_pnl": gross_pnl,
                    "costs": costs,
                    "net_pnl": net_pnl,
                    "exited_at": at,
                }
            )
        self._persist_runtime_checkpoint()

    def handle_exit(self, position_id: str, at: UTCDateTime) -> None:
        """Backward-compatible terminal fill hook. Prefer ``handle_exit_fill``."""
        self.handle_exit_fill(position_id, at)

    def reconcile_exit(self, position_id: str, at: UTCDateTime) -> dict[str, Any]:
        pending = self.state.pending_exits.get(position_id)
        if pending is None or pending.reduction_id is None or self.reduction_authority is None:
            return {"reconciled": False, "reasons": ("REDUCTION_NOT_FOUND",)}
        execution = self.reduction_authority.reconcile(
            UUID(pending.reduction_id), broker=self.broker, reconciled_at=at
        )
        self.state.pending_exits[position_id] = PendingExit(
            position_id=pending.position_id,
            requested_at=pending.requested_at,
            reason_codes=pending.reason_codes,
            source=pending.source,
            authorized=pending.authorized,
            reduction_id=pending.reduction_id,
            execution_state=execution.state.value,
        )
        if execution.state.value == "CLOSED":
            self.handle_exit_fill(position_id, at)
        return {"reconciled": True, "execution_state": execution.state.value}

    def _recover_durable_runtime_state(self) -> None:
        if self.runtime_checkpoint is not None:
            checkpoint = self.runtime_checkpoint.load()
            if checkpoint is not None:
                self.state.open_positions = {
                    item["position_id"]: deserialize_position(item)
                    for item in checkpoint.get("open_positions", [])
                }
                self.state.current_equity = Decimal(
                    str(checkpoint.get("current_equity", self.state.current_equity))
                )
                self.state.peak_equity = Decimal(
                    str(checkpoint.get("peak_equity", self.state.peak_equity))
                )
                self.state.cumulative_realized_pnl = Decimal(
                    str(checkpoint.get("cumulative_realized_pnl", self.state.cumulative_realized_pnl))
                )
        if self.durable_positions is not None:
            for record in self.durable_positions.recover_open():
                position = record.position
                self.state.open_positions[str(position.position_id)] = MonitoredPosition(
                    position_id=str(position.position_id),
                    instrument_id=position.instrument_id,
                    entry_price=position.average_entry_price,
                    current_mark=position.mark_price,
                    quantity=abs(position.net_quantity),
                    realized_pnl=position.realized_pnl,
                    unrealized_pnl=position.unrealized_pnl,
                    peak_pnl=max(position.unrealized_pnl, Decimal("0")),
                    current_stop=None,
                    trailing_stop=None,
                    time_held_minutes=0,
                    entry_thesis_ref=None,
                    thesis_healthy=True,
                    data_fresh=True,
                    last_event="RECOVERED",
                )
        if self.reduction_authority is not None:
            for recovered in self.reduction_authority.recover_pending():
                position_id = str(recovered.exit_intent.position_id)
                self.state.pending_exits[position_id] = PendingExit(
                    position_id=position_id,
                    requested_at=recovered.exit_intent.created_at,
                    reason_codes=("REDUCTION_RECOVERED",),
                    source="RECOVERY",
                    authorized=True,
                    reduction_id=str(recovered.reduction_id),
                    execution_state=recovered.execution.state.value,
                )

    def _persist_runtime_checkpoint(self) -> None:
        if self.runtime_checkpoint is None:
            return
        self.runtime_checkpoint.save(
            {
                "schema_version": 1,
                "open_positions": [
                    serialize_position(position) for position in self.state.open_positions.values()
                ],
                "current_equity": str(self.state.current_equity),
                "peak_equity": str(self.state.peak_equity),
                "cumulative_realized_pnl": str(self.state.cumulative_realized_pnl),
            }
        )

    def update_equity(self, current_equity: Decimal) -> None:
        self.state.current_equity = current_equity
        self.state.peak_equity = max(self.state.peak_equity, current_equity)
        self.state.hwm_state = evaluate_hwm(
            config=self.config.hwm,
            previous=self.state.hwm_state,
            session_start_equity=self.state.session_start_equity,
            current_equity=current_equity,
        )

    def _try_authority_for_signal(
        self, *, signal: StrategySignal, at: UTCDateTime
    ) -> dict[str, Any] | None:
        if isinstance(self.authority, NoopAuthorityService):
            return None
        from uuid import uuid4

        try:
            from ats.portfolio.runtime import ReservationPartition
            from ats.trading_runtime.authority_service import ReservationRequest

            candidate = build_opportunity_candidate(
                instrument_id=signal.instrument_id,
                campaign_id=uuid4(),
                campaign_version=1,
                strategy_id=uuid4(),
                strategy_version=1,
                market_context_id=uuid4(),
                thesis_id=uuid4(),
                thesis_version=1,
                distribution_id=uuid4(),
                created_at=at,
                expires_at=at + __import__("datetime").timedelta(hours=1),
            )
            req = ReservationRequest(
                candidate=candidate,
                amount=self.config.authority_reservation_amount,
                partition=ReservationPartition(market=signal.instrument_id[:7], strategy="ENGINE"),
                reservation_id=uuid4(),
                portfolio_id=uuid4(),
                campaign_id=uuid4(),
            )
            result = self.authority.try_reserve_for_candidate(req, evaluation_time=at)
            if result.outcome.value != "ALLOW":
                return {"allowed": False, "reasons": result.reason_codes}
            rid = result.reservation_id
            return {
                "allowed": True,
                "reservation_id": str(rid) if rid else None,
                "candidate_id": str(candidate.candidate_id),
            }
        except Exception as exc:
            return {"allowed": False, "reasons": (type(exc).__name__,)}

    def _update_position_marks(self, event: RuntimeEvent) -> None:
        """Re-mark all open positions from the market feed on every tick/bar.

        This is the critical fix: without this, MonitoredPosition.current_mark
        remains at entry price and all stop-loss/trailing-stop/PnL monitoring
        operates on stale data.
        """
        for pid in list(self.state.open_positions):
            pos = self.state.open_positions[pid]
            feed_mark = self.market_feed.latest_mark(pos.instrument_id)
            if feed_mark is not None:
                data_fresh = self.market_feed.data_fresh(
                    pos.instrument_id, now=event.at, max_age_ms=self.config.max_quote_age_ms
                )
                self.state.open_positions[pid] = update_mark(
                    pos,
                    mark=feed_mark,
                    at=event.at,
                    data_fresh=data_fresh,
                )

    def halt(self) -> None:
        self.state.kill_switch = True

    def resume(self) -> None:
        self.state.kill_switch = False

    def _current_loss_state(self) -> LossState:
        if self.state.kill_switch:
            return LossState.HALTED
        return LossState.NORMAL


__all__ = [
    "EngineMetrics",
    "PendingExit",
    "RuntimeConfig",
    "RuntimeEvent",
    "RuntimeEventKind",
    "RuntimeState",
    "TradingRuntime",
]
