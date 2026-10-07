"""Autonomous paper trading orchestration loop.

Connects the full pipeline end-to-end with no manual intervention:

market/replay event
→ TradingRuntime.process_event
→ actionable candidate
→ A04 authorization verification (candidate != authorization)
→ PaperBrokerAdapter.submit_order → canonical execution/paper fills
→ consume fills → TradingRuntime.handle_fill
→ position monitoring
→ authorized paper exit
→ TradingRuntime.handle_exit_fill
→ portfolio reconciliation

Design rules honored:
- the orchestrator coordinates existing domain components; it never reimplements
  the broker, execution engine, P&L engine, risk engine, or fill simulator
- paper fills and their cost (slippage, fees, taxes, partial fills, rejection)
  come from the canonical ``ats.execution.paper`` broker via PaperBrokerAdapter
- candidate does not imply authorization: no order is auto-submitted unless an
  injected A04 authorization provider returns ALLOW
- idempotency mandatory; duplicate events/orders cannot create duplicate positions
- failures fail closed; the orchestrator never invokes a live broker
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4

from ats.contracts.common import SystemClock, UTCDateTime
from ats.contracts.domain.models import Fill
from ats.contracts.domain.types import (
    ExitReason,
)
from ats.execution.paper.models import (
    PaperExecutionPolicy,
    PaperMarketFacts,
)
from ats.kernel.types import GateCode, KernelOutcome, KernelResult
from ats.market.calendar.models import SessionCalendar
from ats.market.domain import InstrumentMetadata, require_xauusd
from ats.trading_runtime.broker import (
    MarketDataFeed,
    OrderIntentBinding,
    OrderRequest,
    PaperBrokerAdapter,
)
from ats.trading_runtime.engine import (
    RuntimeConfig,
    RuntimeEvent,
    RuntimeEventKind,
    RuntimeState,
    TradingRuntime,
)
from ats.trading_runtime.exit_authorization import (
    ExitAuthorizationProvider,
    ExitAuthorizationRequest,
    ExitAuthorizationResult,
    UnavailableExitAuthorization,
)
from ats.trading_runtime.position_monitor import (
    MonitoredPosition,
    evaluate_position,
)
from ats.trading_runtime.reconciliation import (
    SessionReconciliation,
    build_session_reconciliation,
)


class OrchestrationPhase(StrEnum):
    IDLE = "IDLE"
    WARMUP = "WARMUP"
    ACTIVE = "ACTIVE"
    EXITING = "EXITING"
    FLATTENING = "FLATTENING"
    CLOSED = "CLOSED"
    HALTED = "HALTED"


class OrchestrationDecision(StrEnum):
    PASS = "PASS"
    CANDIDATE = "CANDIDATE"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    FILL = "FILL"
    EXIT = "EXIT"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


@dataclass
class OrchestrationCounters:
    """Autonomous-session counters fed into reconciliation."""

    submitted_orders: int = 0
    rejected_orders: int = 0
    risk_rejected_candidates: int = 0
    emergency_exits: int = 0
    # Reductions refused because no authorized ExitIntent/Position could be
    # obtained. Non-zero here means positions stayed open deliberately.
    exit_authorization_refused: int = 0
    fees: Decimal = Decimal("0")
    taxes: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")


class OrchestrationListener(Protocol):
    def on_decision(self, decision: OrchestrationDecision, **kwargs: Any) -> None: ...
    def on_fill(
        self, order_id: str, instrument_id: str, quantity: Decimal, price: Decimal
    ) -> None: ...
    def on_exit(self, position_id: str, reason: str) -> None: ...
    def on_session_end(self, report: SessionReconciliation) -> None: ...


class _NoopListener:
    def on_decision(self, decision: OrchestrationDecision, **kwargs: Any) -> None:
        pass

    def on_fill(self, order_id: str, instrument_id: str, quantity: Decimal, price: Decimal) -> None:
        pass

    def on_exit(self, position_id: str, reason: str) -> None:
        pass

    def on_session_end(self, report: SessionReconciliation) -> None:
        pass


MarketFactsProvider = Callable[[str, UTCDateTime], PaperMarketFacts | None]
AuthorizationProvider = Callable[[dict[str, Any]], KernelResult]
IntentBindingProvider = Callable[[dict[str, Any]], OrderIntentBinding | None]


def _default_authorization(result: dict[str, Any]) -> KernelResult:
    """Fail-closed default: candidates are never authorized without evidence.

    A real integration supplies an ``authorization_provider`` that runs A04 and
    returns ALLOW only when the kernel grants it. This default preserves the
    invariant ``candidate != authorization`` when no provider is wired.
    """
    _ = result
    return KernelResult(outcome=KernelOutcome.DENY, reason_codes=(GateCode.TOKEN_INVALID,))


class AutonomousPaperOrchestrator:
    """Fully autonomous paper trading orchestration loop."""

    def __init__(
        self,
        *,
        config: RuntimeConfig | None = None,
        calendar: SessionCalendar | None = None,
        market_feed: MarketDataFeed,
        broker: PaperBrokerAdapter,
        policy: PaperExecutionPolicy,
        instrument: InstrumentMetadata,
        market_facts_provider: MarketFactsProvider,
        authorization_provider: AuthorizationProvider = _default_authorization,
        intent_binding_provider: IntentBindingProvider | None = None,
        exit_authorization_provider: ExitAuthorizationProvider | None = None,
        opening_capital: Decimal = Decimal("100000"),
        listener: OrchestrationListener | None = None,
    ) -> None:
        if config is None and calendar is None:
            raise ValueError("provide either config or calendar to build the runtime")
        self.config = config or RuntimeConfig(calendar=calendar)  # type: ignore[arg-type]
        self.broker = broker
        self.policy = policy
        self.instrument = instrument
        self._market_facts_provider = market_facts_provider
        self._authorization_provider = authorization_provider
        # No binding provider means no order can be bound to real evidence, so
        # every candidate is refused by the broker instead of being dressed up
        # with invented policy/forecast/risk-decision identities.
        self._intent_binding_provider = intent_binding_provider
        # Exit authority defaults to *absent*, which resolves to UNKNOWN and
        # yields no artifacts. There is no implicit permit here: wiring a real
        # provider is the only way to make an exit executable.
        self._exit_authorization = exit_authorization_provider or UnavailableExitAuthorization()
        self.listener = listener or _NoopListener()
        self.state = RuntimeState(
            session_start_equity=opening_capital,
            current_equity=opening_capital,
            peak_equity=opening_capital,
        )
        self.runtime = TradingRuntime(
            config=self.config,
            market_feed=market_feed,
            broker=self.broker,
            state=self.state,
        )
        self.opening_capital = opening_capital
        self.counters = OrchestrationCounters()
        self.started_at: UTCDateTime | None = None
        self.closed_at: UTCDateTime | None = None
        self._seen_order_keys: set[str] = set()
        self._shutting_down = False
        self._paused = False
        self._phase = OrchestrationPhase.IDLE
        self._last_fill_prices: dict[str, Decimal] = {}

    # ------------------------------------------------------------------ events

    def tick(
        self,
        instrument_id: str = "XAUUSD",
        mark: Decimal = Decimal("100"),
        at: UTCDateTime | None = None,
    ) -> dict[str, Any] | None:
        require_xauusd(instrument_id)
        return self._process_event(
            RuntimeEventKind.TICK,
            instrument_id,
            payload={"mark": str(mark)},
            at=at or SystemClock().now(),
        )

    def bar(
        self,
        instrument_id: str = "XAUUSD",
        close: Decimal = Decimal("100"),
        previous_close: Decimal | None = None,
        at: UTCDateTime | None = None,
    ) -> dict[str, Any] | None:
        payload: dict[str, Any] = {"close": str(close)}
        if previous_close is not None:
            payload["previous_close"] = str(previous_close)
        require_xauusd(instrument_id)
        return self._process_event(
            RuntimeEventKind.BAR,
            instrument_id,
            payload=payload,
            at=at or SystemClock().now(),
        )

    def start(self, at: UTCDateTime | None = None) -> None:
        self.started_at = at or SystemClock().now()
        self._phase = OrchestrationPhase.ACTIVE

    # ------------------------------------------------------------------ core

    def _process_event(
        self,
        kind: RuntimeEventKind,
        instrument_id: str,
        payload: dict[str, Any],
        at: UTCDateTime,
    ) -> dict[str, Any] | None:
        if self._shutting_down or self._paused:
            return None
        event = RuntimeEvent(kind=kind, instrument_id=instrument_id, payload=payload, at=at)
        result = self.runtime.process_event(event)
        self._reconcile_unrealized()

        candidate = result.get("candidate")
        if candidate is None or not isinstance(candidate, dict):
            return result

        try:
            from ats.observability.jev_telemetry import invoke_jev_shadow_async

            invoke_jev_shadow_async(candidate, at)
        except Exception:
            pass  # Fail safe completely

        authorization = self._authorization_provider(result)
        if authorization.outcome is not KernelOutcome.ALLOW:
            self.counters.risk_rejected_candidates += 1
            self.listener.on_decision(OrchestrationDecision.BLOCKED, instrument_id=instrument_id)
            return result

        self._submit_candidate(candidate, at, authorization)
        self._flush_exits(at)
        self._reconcile_unrealized()
        return result

    def _submit_candidate(
        self, candidate: dict[str, Any], at: UTCDateTime, authorization: KernelResult
    ) -> None:
        direction = str(candidate.get("direction", "BULLISH"))
        full_instrument = self.instrument.instrument_id

        facts = self._market_facts_provider(full_instrument, at)
        if facts is None:
            self.counters.risk_rejected_candidates += 1
            self.listener.on_decision(
                OrchestrationDecision.BLOCKED, instrument_id=self.instrument.instrument_id
            )
            return

        # Size exactly one instrument lot (the canonical contract quantity); no
        # hardcoded lot counts or duplicated sizing logic live in the orchestrator.
        quantity = Decimal(self.instrument.lot_size)

        self.listener.on_decision(
            OrchestrationDecision.CANDIDATE,
            instrument_id=self.instrument.instrument_id,
            direction=direction,
        )
        order_key = f"{full_instrument}:{at.isoformat()}:{direction}"
        if order_key in self._seen_order_keys:
            return
        self._seen_order_keys.add(order_key)

        request = OrderRequest(
            instrument_id=full_instrument,
            side="BUY" if direction.upper() in ("BULLISH", "BUY") else "SELL",
            quantity=quantity,
            order_type="MARKET",
            limit_price=None,
            idempotency_key=order_key,
            intent_id=str(uuid4()),
            binding=self._intent_binding_provider(candidate)
            if self._intent_binding_provider is not None
            else None,
        )

        status = self.broker.submit_order(
            request, now=at, market_facts=facts, authorization=authorization
        )
        if status is None:
            self.counters.risk_rejected_candidates += 1
            return
        self.counters.submitted_orders += 1
        if status.status == "REJECTED":
            self.counters.rejected_orders += 1
            self.listener.on_decision(
                OrchestrationDecision.REJECTED, instrument_id=self.instrument.instrument_id
            )
            return

        fills = self.broker.consume_fills(status.order_id)
        for fill in fills:
            self._apply_entry_fill(fill, direction, at)

    def _apply_entry_fill(self, fill: Fill, direction: str, at: UTCDateTime) -> None:
        position_id = f"{fill.instrument_id}:{str(fill.fill_id)}"
        self.runtime.handle_fill(
            position_id=position_id,
            mark=fill.price,
            quantity=fill.quantity,
            at=at,
            lot_size=self.instrument.lot_size,
            direction="BULLISH" if direction.upper() in ("BULLISH", "BUY") else "BEARISH",
            expected_edge_r=0.0,
        )
        self.counters.fees += fill.fees
        self.counters.taxes += fill.taxes
        self.counters.slippage += fill.slippage
        self._last_fill_prices[position_id] = fill.price
        self.listener.on_decision(
            OrchestrationDecision.FILL,
            instrument_id=fill.instrument_id,
            quantity=fill.quantity,
            price=fill.price,
        )
        self.listener.on_fill(
            str(fill.paper_order_id), fill.instrument_id, fill.quantity, fill.price
        )

    # ------------------------------------------------------------------ exits

    def _flush_exits(self, at: UTCDateTime) -> None:
        for pid in list(self.runtime.state.open_positions.keys()):
            pos = self.runtime.state.open_positions[pid]
            decision = evaluate_position(
                config=self.config.position_monitor,
                position=pos,
                hwm=self.runtime.state.hwm_state,
                evaluation_time=at,
            )
            if not decision.should_exit_now:
                continue
            self._execute_exit(pid, pos, decision.reason_codes, at)

    def _execute_exit(
        self,
        position_id: str,
        position: MonitoredPosition,
        reason_codes: tuple[str, ...],
        at: UTCDateTime,
    ) -> None:
        listed = self.runtime.request_exit(
            position_id,
            at,
            reason_codes=reason_codes,
            source="ORCHESTRATOR",
        )
        if not listed.get("accepted", False):
            return
        # Only count the exit once it is actually authorized and submitted. A
        # refused reduction is recorded below and must never be reported as a
        # completed emergency exit.
        facts = self._market_facts_provider(position.instrument_id, at)
        if facts is None:
            return

        authorization_request = ExitAuthorizationRequest(
            position_key=position_id,
            exit_intent_id=uuid4(),
            instrument_id=position.instrument_id,
            quantity=position.quantity,
            reason=_exit_reason(reason_codes[0] if reason_codes else "EXIT"),
            reason_codes=reason_codes,
            idempotency_key=f"EXIT:{position_id}:{at.isoformat()}",
            at=at,
            source="ORCHESTRATOR",
        )
        try:
            authorized = self._exit_authorization.authorize_exit(authorization_request)
        except Exception:
            # An authority that throws has not authorized anything. Map it onto
            # UNKNOWN so the shared refusal path records the blocked exit instead
            # of either escalating the exception into a failed shutdown or, far
            # worse, being read as permission.
            authorized = ExitAuthorizationResult(
                decision=KernelResult(
                    outcome=KernelOutcome.UNKNOWN,
                    reason_codes=(GateCode.RISK_UNKNOWN,),
                )
            )
        if not authorized.allows_exit():
            # Fail closed. No Artifacts means nothing safe to submit, and we
            # must not synthesise an ExitIntent or Position to satisfy Stage-2.
            self.counters.exit_authorization_refused += 1
            self.listener.on_decision(
                OrchestrationDecision.BLOCKED,
                instrument_id=position.instrument_id,
                position_id=position_id,
                reason_codes=tuple(code.value for code in authorized.refusal_reason()),
            )
            return

        assert authorized.exit_intent is not None  # guaranteed by allows_exit
        assert authorized.position is not None  # guaranteed by allows_exit
        exit_intent = authorized.exit_intent
        snapshot = authorized.position

        if (
            snapshot.instrument_id != position.instrument_id
            or snapshot.net_quantity != position.quantity
        ):
            # Stale identity. Reducing against a snapshot that no longer
            # describes this position would flatten the wrong thing, so it is a
            # refusal, not a partial success to be papered over.
            self.counters.exit_authorization_refused += 1
            self.listener.on_decision(
                OrchestrationDecision.BLOCKED,
                instrument_id=position.instrument_id,
                position_id=position_id,
                reason_codes=(GateCode.POSITION_BINDING.value,),
            )
            return

        self.counters.emergency_exits += 1
        reason = exit_intent.reason.value
        self.listener.on_exit(position_id, reason)

        request = OrderRequest(
            instrument_id=position.instrument_id,
            side="SELL",
            quantity=position.quantity,
            order_type="MARKET",
            limit_price=None,
            idempotency_key=exit_intent.idempotency_key,
            intent_id=str(exit_intent.exit_intent_id),
        )
        status = self.broker.submit_exit(
            request=request,
            intent=exit_intent,
            position=snapshot,
            now=at,
            market_facts=facts,
            authorization=authorized.decision,
        )
        if status is None or status.status == "REJECTED":
            return
        exit_fills = self.broker.consume_exit_fills(status.order_id)
        for exit_fill in exit_fills:
            self._apply_exit_fill(position_id, exit_fill, at)

    def _apply_exit_fill(self, position_id: str, fill: Fill, at: UTCDateTime) -> None:
        pos = self.runtime.state.open_positions.get(position_id)
        if pos is not None:
            self.counters.fees += fill.fees
            self.counters.taxes += fill.taxes
            self.counters.slippage += fill.slippage
        self.runtime.handle_exit_fill(position_id, at)

    # ------------------------------------------------------------------ shutdown

    def request_shutdown(
        self, at: UTCDateTime | None = None, *, timeout_bars: int = 3, timeout_seconds: int = 60
    ) -> dict[str, Any]:
        """PAUSE_NEW_ENTRIES → flatten → zero positions → reconcile → CLOSED.

        Idempotent, bounded, fail-closed: if positions cannot be flattened the
        orchestrator reports NOT_CLOSED rather than a false success.
        """
        timestamp = at or SystemClock().now()
        self._shutting_down = True
        self._paused = True
        self._phase = OrchestrationPhase.FLATTENING

        remaining = {pid: pos for pid, pos in self.runtime.state.open_positions.items()}
        for pid, pos in list(remaining.items()):
            self._execute_exit(pid, pos, ("SESSIONS_END_FLATTEN",), timestamp)

        flattened = not self.runtime.state.open_positions
        self._reconcile_unrealized()
        if flattened:
            self._phase = OrchestrationPhase.CLOSED
            self.closed_at = timestamp
            return self._finalize(timestamp)
        self._phase = OrchestrationPhase.HALTED
        return {
            "status": "NOT_CLOSED",
            "remaining_positions": len(self.runtime.state.open_positions),
        }

    def _finalize(self, closed_at: UTCDateTime) -> dict[str, Any]:
        report = build_session_reconciliation(
            opening_capital=self.opening_capital,
            current_equity=self.state.current_equity,
            fees=self.counters.fees,
            taxes=self.counters.taxes,
            slippage=self.counters.slippage,
            total_trades=self.counters.submitted_orders,
            rejected_orders=self.counters.rejected_orders,
            risk_rejected_candidates=self.counters.risk_rejected_candidates,
            emergency_exits=self.counters.emergency_exits,
            remaining_positions=len(self.runtime.state.open_positions),
            max_drawdown=self.opening_capital - self.state.peak_equity,
            started_at=self.started_at,
            closed_at=closed_at,
        )
        self.listener.on_session_end(report)
        return report.to_dict()

    @property
    def session_report(self) -> SessionReconciliation | None:
        return build_session_reconciliation(
            opening_capital=self.opening_capital,
            current_equity=self.state.current_equity,
            fees=self.counters.fees,
            taxes=self.counters.taxes,
            slippage=self.counters.slippage,
            total_trades=self.counters.submitted_orders,
            rejected_orders=self.counters.rejected_orders,
            risk_rejected_candidates=self.counters.risk_rejected_candidates,
            emergency_exits=self.counters.emergency_exits,
            remaining_positions=len(self.runtime.state.open_positions),
            max_drawdown=self.opening_capital - self.state.peak_equity,
            started_at=self.started_at,
            closed_at=self.closed_at,
        )

    def _reconcile_unrealized(self) -> None:
        total_unrealized = sum(
            pos.unrealized_pnl for pos in self.runtime.state.open_positions.values()
        )
        self.state.current_equity = (
            self.opening_capital + self.counters_fees_pnl() + total_unrealized
        )
        self.state.peak_equity = max(self.state.peak_equity, self.state.current_equity)

    def counters_fees_pnl(self) -> Decimal:
        return -(self.counters.fees + self.counters.taxes + self.counters.slippage)

    # ------------------------------------------------------------------ queries

    def get_open_positions(self) -> dict[str, MonitoredPosition]:
        return dict(self.runtime.state.open_positions)

    def get_phase(self) -> OrchestrationPhase:
        return self._phase

    def is_position_empty(self) -> bool:
        return not self.runtime.state.open_positions

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False


def _exit_reason(reason: str) -> ExitReason:
    mapping: dict[str, ExitReason] = {
        "HARD_LOSS_BREACH": ExitReason.STOP,
        "TRAILING_STOP_HIT": ExitReason.TRAILING,
        "TIME_EXIT": ExitReason.TIME,
        "THESIS_INVALIDATED": ExitReason.TARGET,
        "IV_COLLAPSE": ExitReason.RISK,
        "THETA_DECAY_EXCESSIVE": ExitReason.RISK,
        "HWM_PROFIT_PROTECTION": ExitReason.TARGET,
        "SESSIONS_END_FLATTEN": ExitReason.HALT,
    }
    return mapping.get(reason, ExitReason.RISK)


__all__ = [
    "AutonomousPaperOrchestrator",
    "MarketFactsProvider",
    "OrchestrationCounters",
    "OrchestrationDecision",
    "OrchestrationListener",
    "OrchestrationPhase",
]
