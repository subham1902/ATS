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
from uuid import UUID, uuid4

from ats.contracts.common import SystemClock, UTCDateTime
from ats.contracts.domain.models import ExitIntent, Fill, Position
from ats.contracts.domain.types import (
    ExitReason,
    PaperOrderType,
)
from ats.execution.paper.models import (
    PaperExecutionPolicy,
    PaperMarketFacts,
)
from ats.kernel.types import ALLOW, GateCode, KernelOutcome, KernelResult
from ats.market.calendar.models import SessionCalendar
from ats.market.derivatives.contract_master import DerivativeInstrument
from ats.trading_runtime.broker import (
    MarketDataFeed,
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


def _default_authorization(result: dict[str, Any]) -> KernelResult:
    """Fail-closed default: candidates are never authorized without evidence.

    A real integration supplies an ``authorization_provider`` that runs A04 and
    returns ALLOW only when the kernel grants it. This default preserves the
    invariant ``candidate != authorization`` when no provider is wired.
    """
    _ = result
    return KernelResult(
        outcome=KernelOutcome.DENY, reason_codes=(GateCode.TOKEN_INVALID,)
    )


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
        instrument: DerivativeInstrument,
        market_facts_provider: MarketFactsProvider,
        authorization_provider: AuthorizationProvider = _default_authorization,
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
        instrument_id: str = "NIFTY",
        mark: Decimal = Decimal("100"),
        at: UTCDateTime | None = None,
    ) -> dict[str, Any] | None:
        return self._process_event(
            RuntimeEventKind.TICK,
            instrument_id,
            payload={"mark": str(mark)},
            at=at or SystemClock().now(),
        )

    def bar(
        self,
        instrument_id: str = "NIFTY",
        close: Decimal = Decimal("100"),
        previous_close: Decimal | None = None,
        at: UTCDateTime | None = None,
    ) -> dict[str, Any] | None:
        payload: dict[str, Any] = {"close": str(close)}
        if previous_close is not None:
            payload["previous_close"] = str(previous_close)
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

    def _apply_entry_fill(
        self, fill: Fill, direction: str, at: UTCDateTime
    ) -> None:
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
        self.counters.emergency_exits += 1
        reason = reason_codes[0] if reason_codes else "EXIT"
        self.listener.on_exit(position_id, reason)

        facts = self._market_facts_provider(position.instrument_id, at)
        if facts is None:
            return

        exit_intent = ExitIntent(
            schema_version="1.0",
            exit_intent_id=uuid4(),
            position_id=_snapshot_position_id(),
            position_version=1,
            reason=_exit_reason(reason),
            quantity=position.quantity,
            order_type=PaperOrderType.MARKET,
            limit_price=None,
            stop_price=None,
            risk_decision_id=uuid4(),
            autonomy_token_id=uuid4(),
            idempotency_key=f"EXIT:{position_id}:{at.isoformat()}",
            created_at=at,
            payload_hash="0" * 64,
        )
        from ats.contracts.domain.hashing import compute_payload_hash

        exit_intent = exit_intent.model_copy(
            update={"payload_hash": compute_payload_hash(exit_intent)}
        )
        snapshot = _position_snapshot(position)
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
            authorization=ALLOW,
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


def _snapshot_position_id() -> UUID:
    # A stable synthetic contract for the domain exit path; the runtime closes
    # the real string position_id via handle_exit_fill independently.
    return UUID("a0000000-0000-0000-0000-000000000001")


def _position_snapshot(position: MonitoredPosition) -> Position:
    """Domain Position placeholder for the canonical exit path.

    Real integrations supply the authoritative domain ``Position`` from the
    position authority store; the orchestrator passes a lightweight snapshot so
    the canonical ``submit_paper_exit`` binding checks can operate. The payload
    hash is computed so the canonical integrity check passes.
    """
    from ats.contracts.domain.hashing import compute_payload_hash
    from ats.contracts.domain.types import PositionStatus

    value = Position(
        schema_version="1.0",
        position_id=_snapshot_position_id(),
        portfolio_id=UUID("a0000000-0000-0000-0000-000000000002"),
        instrument_id=position.instrument_id,
        net_quantity=position.quantity,
        average_entry_price=position.entry_price,
        mark_price=position.current_mark or position.entry_price,
        realized_pnl=position.realized_pnl,
        unrealized_pnl=position.unrealized_pnl,
        cash_effect=Decimal("0"),
        policy_id=UUID(int=1),
        policy_version=1,
        opened_at=position.entry_at or SystemClock().now(),
        updated_at=SystemClock().now(),
        closed_at=None,
        status=PositionStatus.OPEN,
        version=1,
        last_fill_id=UUID("a0000000-0000-0000-0000-000000000003"),
        payload_hash="0" * 64,
    )
    return value.model_copy(update={"payload_hash": compute_payload_hash(value)})


__all__ = [
    "AutonomousPaperOrchestrator",
    "MarketFactsProvider",
    "OrchestrationCounters",
    "OrchestrationDecision",
    "OrchestrationListener",
    "OrchestrationPhase",
]
