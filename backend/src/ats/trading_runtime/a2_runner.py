# ruff: noqa: E501
"""Production-safe autonomous PaperBroker session launcher and lifecycle controller (A2-RUNNER).

INVARIANTS:
1. Execution target is PaperBrokerAdapter ONLY — live-money execution is impossible.
2. Upstox is a READ-ONLY market data provider.
3. A04 remains the final deterministic authority; Portfolio Brain is the permitting/allocation layer.
4. Intelligence Harness remains ADVISORY_ONLY.
5. UNKNOWN state never creates new risk.
6. Real orders placed remains strictly 0.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from ats.contracts.common import SystemClock, UTCDateTime
from ats.contracts.domain.types import (
    LossState,
)
from ats.contracts.governance.models import OpportunityCandidate
from ats.market.calendar.models import SessionCalendar, nse_cash_alpha_v1_calendar
from ats.observability.operator_provider import OperatorIntelligenceProvider
from ats.portfolio.brain import (
    AllocationOutcome,
    CandidateAllocationRequest,
    ExposureDirection,
    PortfolioBrainContext,
    PortfolioManagerBrain,
    PositionExposure,
)
from ats.portfolio.persistence import PortfolioCapitalAccount
from ats.portfolio.runtime import (
    PortfolioAuthoritySnapshot,
    ReservationPartition,
)
from ats.trading_runtime.authority_service import (
    ReservationRequest,
    TradingAuthorityService,
)
from ats.trading_runtime.broker import (
    InMemoryMarketFeed,
    MarketDataFeed,
    OrderRequest,
    PaperBrokerAdapter,
)
from ats.trading_runtime.engine import (
    RuntimeConfig,
    RuntimeEvent,
    RuntimeEventKind,
    TradingRuntime,
)
from ats.trading_runtime.hwm import HWMState, ProfitProtectionState
from ats.trading_runtime.intelligence_pipeline import (
    IntelligencePipelineConfig,
    MarketIntelligencePipeline,
)
from ats.trading_runtime.lot_size import LotSizeRegistry
from ats.trading_runtime.modes import TradingMode
from ats.trading_runtime.position_monitor import (
    MonitoredPosition,
    evaluate_position,
    update_mark,
)
from ats.trading_runtime.runtime_provider import (
    TradingRuntimeProvider,
)
from ats.trading_runtime.session import SessionRuntimeConfig


def default_a2_session_calendar() -> SessionCalendar:
    """Return a standard NSE session calendar for A2 Paper runtime."""
    try:
        return nse_cash_alpha_v1_calendar()
    except Exception:
        return SessionCalendar(
            calendar_id="NSE_STANDARD",
            calendar_version="1.0.0",
            timezone="Asia/Kolkata",
            trading_dates=(date.today(),),
            preopen_start=time(9, 0),
            market_open=time(9, 15),
            market_close=time(15, 30),
            overrides=(),
        )


class A2SessionState(StrEnum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"


@dataclass
class A2PaperSessionConfig:
    execution_target: str = "PAPER"
    live_money: str = "DISABLED"
    underlyings: tuple[str, ...] = ("NIFTY", "BANKNIFTY")
    capital_budget: Decimal = Decimal("500000")
    max_positions: int = 4
    max_quote_age_ms: int = 2000
    loop_interval_sec: float = 1.0
    lot_sizes: dict[str, int] = field(
        default_factory=lambda: {
            "NIFTY": 25,
            "BANKNIFTY": 15,
            "NIFTY_CE": 25,
            "NIFTY_PE": 25,
            "BANKNIFTY_CE": 15,
            "BANKNIFTY_PE": 15,
        }
    )
    base_slippage_ticks: int = 1
    tick_size: Decimal = Decimal("0.05")
    mode: TradingMode = TradingMode.NORMAL


@dataclass(frozen=True)
class A2SessionStatus:
    state: A2SessionState
    execution_target: str = "PAPER"
    live_money: str = "DISABLED"
    real_orders_placed: int = 0
    events_processed: int = 0
    candidates_evaluated: int = 0
    paper_orders_submitted: int = 0
    paper_fills_recorded: int = 0
    open_paper_positions: int = 0
    realized_pnl: str = "0.00"
    unrealized_pnl: str = "0.00"
    last_event_time: UTCDateTime | None = None
    heartbeat: UTCDateTime = field(default_factory=lambda: SystemClock().now())
    reason_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "execution_target": self.execution_target,
            "live_money": self.live_money,
            "real_orders_placed": self.real_orders_placed,
            "events_processed": self.events_processed,
            "candidates_evaluated": self.candidates_evaluated,
            "paper_orders_submitted": self.paper_orders_submitted,
            "paper_fills_recorded": self.paper_fills_recorded,
            "open_paper_positions": self.open_paper_positions,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "last_event_time": self.last_event_time.isoformat() if self.last_event_time else None,
            "heartbeat": self.heartbeat.isoformat(),
            "reason_codes": list(self.reason_codes),
        }


class UpstoxMarketFeedAdapter(MarketDataFeed):
    """Adapter wrapping read-only market data feeds with freshness & health checking."""

    def __init__(self, *, clock: Any = None) -> None:
        self._clock = clock or SystemClock()
        self._marks: dict[str, tuple[Decimal, UTCDateTime]] = {}
        self._healthy = True

    def set_mark(self, instrument_id: str, price: Decimal, at: UTCDateTime | None = None) -> None:
        stamp = at or self._clock.now()
        self._marks[instrument_id] = (price, stamp)

    def latest_mark(self, instrument_id: str) -> Decimal | None:
        entry = self._marks.get(instrument_id)
        return None if entry is None else entry[0]

    def data_fresh(self, instrument_id: str, *, now: UTCDateTime, max_age_ms: int) -> bool:
        entry = self._marks.get(instrument_id)
        if entry is None:
            return False
        _, at = entry
        age_ms = int((now - at).total_seconds() * 1000)
        return 0 <= age_ms <= max_age_ms

    def is_healthy(self) -> bool:
        return self._healthy

    def set_healthy(self, healthy: bool) -> None:
        self._healthy = healthy


class A2PaperSessionController:
    """Production-safe A2 Paper Session lifecycle controller and orchestrator."""

    def __init__(
        self,
        config: A2PaperSessionConfig | None = None,
        *,
        market_feed: MarketDataFeed | None = None,
        broker: PaperBrokerAdapter | None = None,
        runtime_provider: TradingRuntimeProvider | None = None,
        operator_provider: OperatorIntelligenceProvider | None = None,
        authority: TradingAuthorityService | None = None,
        calendar: SessionCalendar | None = None,
    ) -> None:
        self.config = config or A2PaperSessionConfig()
        self._state = A2SessionState.STOPPED
        self._reason_codes: list[str] = []

        # Dependencies
        self._market_feed = market_feed or UpstoxMarketFeedAdapter()
        self._broker = broker or PaperBrokerAdapter(
            healthy=True,
            lot_size_registry=LotSizeRegistry(self.config.lot_sizes),
            base_slippage_ticks=self.config.base_slippage_ticks,
            tick_size=self.config.tick_size,
        )
        self._runtime_provider = runtime_provider or TradingRuntimeProvider()
        self._operator_provider = operator_provider or OperatorIntelligenceProvider()
        self._authority = authority
        self._calendar = calendar or default_a2_session_calendar()

        # Engine & Pipeline
        self._engine: TradingRuntime | None = None
        self._pipeline: MarketIntelligencePipeline | None = None
        self._portfolio_brain: PortfolioManagerBrain | None = None

        # Telemetry counters
        self._events_processed = 0
        self._candidates_evaluated = 0
        self._paper_orders_submitted = 0
        self._paper_fills_recorded = 0
        self._last_event_time: UTCDateTime | None = None

        # Background loop task
        self._stop_event = asyncio.Event()
        self._loop_task: asyncio.Task[None] | None = None

    @property
    def state(self) -> A2SessionState:
        return self._state

    @property
    def engine(self) -> TradingRuntime | None:
        return self._engine

    @property
    def broker(self) -> PaperBrokerAdapter:
        return self._broker

    @property
    def market_feed(self) -> MarketDataFeed:
        return self._market_feed

    @property
    def runtime_provider(self) -> TradingRuntimeProvider:
        return self._runtime_provider

    @property
    def operator_provider(self) -> OperatorIntelligenceProvider:
        return self._operator_provider

    def start(self, *, require_token: bool = True) -> bool:
        """Start the A2 paper session synchronously."""
        if self._state in (A2SessionState.RUNNING, A2SessionState.STARTING):
            return True

        self._state = A2SessionState.STARTING
        self._reason_codes = []

        # 1. Token check: verify presence without printing
        token = os.environ.get("ATS_UPSTOX_ACCESS_TOKEN", "").strip()
        if require_token and not token:
            self._state = A2SessionState.FAILED
            self._reason_codes = ["ACCESS_TOKEN_MISSING"]
            return False

        # 2. Invariant: live-money must be DISABLED
        if self.config.live_money != "DISABLED" or self.config.execution_target != "PAPER":
            self._state = A2SessionState.FAILED
            self._reason_codes = ["LIVE_MONEY_PROHIBITED"]
            return False

        # 3. Construct TradingRuntime & components
        runtime_config = RuntimeConfig(
            calendar=self._calendar,
            session=SessionRuntimeConfig(),
            max_quote_age_ms=self.config.max_quote_age_ms,
            mode=self.config.mode,
            authority_reservation_amount=Decimal("50000"),
        )
        self._engine = TradingRuntime(
            config=runtime_config,
            market_feed=self._market_feed,
            broker=self._broker,
            authority=self._authority,
        )
        self._pipeline = MarketIntelligencePipeline(config=IntelligencePipelineConfig())
        self._portfolio_brain = PortfolioManagerBrain()

        # Sync runtime provider
        self._runtime_provider.update_from_engine(self._engine)
        self._state = A2SessionState.RUNNING
        self._reason_codes = ["A2_PAPER_SESSION_ACTIVE"]
        return True

    async def start_async(self, *, require_token: bool = True) -> bool:
        """Start the A2 paper session and attach background async loop."""
        success = self.start(require_token=require_token)
        if not success:
            return False

        self._stop_event.clear()
        try:
            loop = asyncio.get_running_loop()
            self._loop_task = loop.create_task(self._event_loop())
        except RuntimeError:
            pass
        return True

    def stop(self) -> bool:
        """Stop the A2 paper session and flatten open paper positions."""
        if self._state is A2SessionState.STOPPED:
            return True

        self._state = A2SessionState.STOPPING
        self._stop_event.set()

        if self._loop_task is not None and not self._loop_task.done():
            self._loop_task.cancel()
            self._loop_task = None

        # Flatten open paper positions safely
        if self._engine is not None and self._engine.state.open_positions:
            now = SystemClock().now()
            self._engine.request_flatten(now, reason_code="A2_SESSION_STOP_FLATTEN", source="CONTROLLER")
            for pid in list(self._engine.state.open_positions.keys()):
                self._engine.handle_exit_fill(pid, now)

        if self._engine is not None:
            self._runtime_provider.update_from_engine(self._engine)

        self._state = A2SessionState.STOPPED
        self._reason_codes = ["A2_PAPER_SESSION_STOPPED"]
        return True

    async def stop_async(self) -> bool:
        """Stop the A2 paper session asynchronously."""
        return self.stop()

    def health(self) -> dict[str, Any]:
        """Diagnostic health summary."""
        feed_ok = self._market_feed.is_healthy()
        broker_ok = self._broker.is_healthy()
        runtime_ok = self._engine is not None and not self._engine.state.kill_switch
        is_healthy = feed_ok and broker_ok and runtime_ok and self._state is A2SessionState.RUNNING

        return {
            "status": "HEALTHY" if is_healthy else ("DEGRADED" if self._state is A2SessionState.RUNNING else "OFFLINE"),
            "session_state": self._state.value,
            "feed_healthy": feed_ok,
            "broker_healthy": broker_ok,
            "runtime_healthy": runtime_ok,
            "live_money": "DISABLED",
            "execution_target": "PAPER",
            "real_orders_placed": 0,
            "open_positions_count": len(self._engine.state.open_positions) if self._engine else 0,
            "reason_codes": list(self._reason_codes),
        }

    def status(self) -> A2SessionStatus:
        """Truthful A2 session status read model."""
        now = SystemClock().now()
        open_pos_count = len(self._engine.state.open_positions) if self._engine else 0
        realized_str = str(self._runtime_provider.get_state().realized)
        unrealized_str = str(self._runtime_provider.get_state().unrealized)

        return A2SessionStatus(
            state=self._state,
            execution_target="PAPER",
            live_money="DISABLED",
            real_orders_placed=0,
            events_processed=self._events_processed,
            candidates_evaluated=self._candidates_evaluated,
            paper_orders_submitted=self._paper_orders_submitted,
            paper_fills_recorded=self._paper_fills_recorded,
            open_paper_positions=open_pos_count,
            realized_pnl=realized_str,
            unrealized_pnl=unrealized_str,
            last_event_time=self._last_event_time,
            heartbeat=now,
            reason_codes=tuple(self._reason_codes),
        )

    def process_tick(
        self,
        instrument_id: str,
        price: Decimal,
        at: UTCDateTime | None = None,
    ) -> dict[str, Any]:
        """Process one market tick through the full deterministic pipeline."""
        if self._state is not A2SessionState.RUNNING or self._engine is None:
            return {"accepted": False, "reason": "SESSION_NOT_RUNNING"}

        now = at or SystemClock().now()
        self._last_event_time = now
        self._events_processed += 1

        # 1. Update mark in feed
        if isinstance(self._market_feed, UpstoxMarketFeedAdapter | InMemoryMarketFeed):
            self._market_feed.set_mark(instrument_id, price, now)

        # 2. Drive TradingRuntime process_event (updates marks, P0 safety, P1 monitor)
        event = RuntimeEvent(
            kind=RuntimeEventKind.TICK,
            instrument_id=instrument_id,
            payload={"price": str(price)},
            at=now,
        )
        runtime_outcome = self._engine.process_event(event)

        # 3. Check for exits triggered by position monitor
        if runtime_outcome.get("exits"):
            for exit_info in runtime_outcome["exits"]:
                pid = exit_info["position_id"]
                self._engine.request_exit(pid, now, reason_codes=tuple(exit_info.get("reasons", ())), source="MONITOR")
                self._engine.handle_exit_fill(pid, now)

        # 4. Sync runtime provider
        self._runtime_provider.update_from_engine(self._engine)
        return {"accepted": True, "events_processed": self._events_processed, "runtime": runtime_outcome}

    def evaluate_and_execute_candidate(
        self,
        candidate: OpportunityCandidate,
        *,
        underlying: str = "NIFTY",
        direction: ExposureDirection = ExposureDirection.BULLISH,
        requested_capital: Decimal = Decimal("50000"),
        requested_quantity: Decimal = Decimal("50"),
        maximum_loss: Decimal = Decimal("5000"),
        expected_net_value: Decimal = Decimal("50"),
        now: UTCDateTime | None = None,
    ) -> dict[str, Any]:
        """Execute candidate through canonical pipeline: Pipeline -> PortfolioBrain -> A04 -> Authority -> PaperBroker."""
        if self._state is not A2SessionState.RUNNING or self._engine is None or self._portfolio_brain is None:
            return {"allowed": False, "reason": "SESSION_NOT_RUNNING"}

        evaluation_time = now or SystemClock().now()
        self._candidates_evaluated += 1

        # 1. Check max positions limit
        if len(self._engine.state.open_positions) >= self.config.max_positions:
            return {"allowed": False, "reason": "MAX_CONCURRENT_POSITIONS_REACHED"}

        # 2. Portfolio Brain Allocation
        account = PortfolioCapitalAccount(
            portfolio_id=uuid4(),
            version=1,
            total_capital=self.config.capital_budget,
            deployable_capital=self.config.capital_budget,
            reserved_capital=Decimal("0"),
            used_capital=Decimal("0"),
            available_capital=self.config.capital_budget,
            realized_pnl=self._runtime_provider.get_state().realized,
            unrealized_pnl=self._runtime_provider.get_state().unrealized,
            daily_loss=Decimal("0"),
            maximum_drawdown=Decimal("0"),
            loss_state=LossState.NORMAL,
            updated_at=evaluation_time,
        )
        hwm = self._engine.state.hwm_state or HWMState(
            session_start_equity=self.config.capital_budget,
            peak_equity=self.config.capital_budget,
            current_equity=self.config.capital_budget,
            drawdown_fraction=Decimal("0"),
            peak_profit=Decimal("0"),
            giveback_from_peak=Decimal("0"),
            profit_protection=ProfitProtectionState.NONE,
            mode_hint=None,
        )
        from ats.contracts.domain.hashing import compute_payload_hash

        pos_exposures = []
        for pid, pos in self._engine.state.open_positions.items():
            try:
                p_uuid = UUID(pid)
            except Exception:
                p_uuid = uuid4()
            pos_exposures.append(
                PositionExposure(
                    position_id=p_uuid,
                    underlying=pos.instrument_id.split("_")[0],
                    direction=ExposureDirection.BULLISH if pos.direction == "BULLISH" else ExposureDirection.BEARISH,
                    strategy_id=uuid4(),
                    capital_at_risk=pos.capital_at_risk,
                )
            )

        ctx = PortfolioBrainContext(
            snapshot=PortfolioAuthoritySnapshot(
                account=account,
                active_reservations=(),
                partition_usage=(),
                inflight_capital=Decimal("0"),
                open_risk_capital=Decimal("0"),
                active_reservation_count=0,
            ),
            positions=tuple(pos_exposures),
            hwm=hwm,
            user_mode=self.config.mode,
            effective_mode=self.config.mode,
            feed_healthy=self._market_feed.is_healthy(),
            execution_healthy=self._broker.is_healthy(),
            calibration_healthy=True,
            loss_streak=0,
            remaining_session_risk=Decimal("50000"),
            as_of=evaluation_time,
            input_hash="0" * 64,
        )
        ctx = ctx.model_copy(update={"input_hash": compute_payload_hash(ctx, hash_field="input_hash")})

        req = CandidateAllocationRequest(
            candidate=candidate,
            underlying=underlying,
            direction=direction,
            requested_capital=requested_capital,
            requested_quantity=requested_quantity,
            maximum_loss=maximum_loss,
            expected_net_value=expected_net_value,
            spread_fraction=Decimal("0.01"),
            liquidity_score=Decimal("0.90"),
            quote_fresh=True,
        )
        alloc = self._portfolio_brain.allocate(req, ctx)
        if alloc.outcome not in (AllocationOutcome.ALLOW, AllocationOutcome.ALLOW_REDUCED):
            return {"allowed": False, "outcome": alloc.outcome.value, "reasons": alloc.reason_codes}

        # 3. Portfolio Authority Reservation
        if self._authority is not None:
            res_req = ReservationRequest(
                candidate=candidate,
                amount=alloc.approved_capital,
                partition=ReservationPartition(market=underlying, strategy="A2_RUNNER"),
                reservation_id=uuid4(),
                portfolio_id=uuid4(),
                campaign_id=candidate.campaign_id,
            )
            res_res = self._authority.try_reserve_for_candidate(res_req, evaluation_time=evaluation_time)
            if res_res.outcome.value != "ALLOW":
                return {"allowed": False, "reason": "AUTHORITY_RESERVATION_DENIED", "reasons": res_res.reason_codes}

        # 4. Submit to PaperBrokerAdapter ONLY (No real order placed)
        slipped_price = self._broker.apply_slippage(Decimal("100.00"), "BUY")
        order_qty = alloc.approved_quantity
        if self._broker._lot_size_registry is not None:
            try:
                lot = self._broker._lot_size_registry.lot_size_for(candidate.instrument_id)
                lots_count = int(order_qty) // lot
                if lots_count <= 0:
                    return {"allowed": False, "reason": "QUANTITY_BELOW_LOT_SIZE"}
                order_qty = Decimal(str(lots_count * lot))
            except Exception:
                pass

        order_req = OrderRequest(
            instrument_id=candidate.instrument_id,
            side="BUY",
            quantity=order_qty,
            order_type="LIMIT",
            limit_price=slipped_price,
            idempotency_key=str(uuid4()),
            intent_id=str(candidate.candidate_id),
        )
        order_status = self._broker.submit_order(order_req, now=evaluation_time)
        if order_status is None:
            return {"allowed": False, "reason": "PAPER_BROKER_REJECTED"}

        self._paper_orders_submitted += 1

        # 5. Simulate Paper Fill
        self._broker.seed_fill(order_status.order_id, slipped_price, order_qty, now=evaluation_time)
        self._paper_fills_recorded += 1

        # 6. Add to TradingRuntime open positions
        pos_id = str(uuid4())
        self._engine.state.open_positions[pos_id] = MonitoredPosition(
            position_id=pos_id,
            instrument_id=candidate.instrument_id,
            entry_price=slipped_price,
            current_mark=slipped_price,
            quantity=order_qty,
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            peak_pnl=Decimal("0"),
            current_stop=slipped_price * Decimal("0.95"),
            trailing_stop=None,
            time_held_minutes=0,
            entry_thesis_ref=str(candidate.thesis_id),
            thesis_healthy=True,
            data_fresh=True,
            last_event="PAPER_FILL",
            capital_at_risk=alloc.approved_capital,
            capital_committed=alloc.approved_capital,
            entry_at=evaluation_time,
            direction="BULLISH" if direction == ExposureDirection.BULLISH else "BEARISH",
        )

        self._runtime_provider.update_from_engine(self._engine)
        return {
            "allowed": True,
            "position_id": pos_id,
            "order_id": order_status.order_id,
            "approved_capital": str(alloc.approved_capital),
            "approved_quantity": str(alloc.approved_quantity),
            "execution_target": "PAPER",
        }

    async def _event_loop(self) -> None:
        """Background loop monitoring runtime marks and session health."""
        while not self._stop_event.is_set():
            try:
                if self._engine is not None:
                    now = SystemClock().now()
                    for pid, pos in list(self._engine.state.open_positions.items()):
                        mark = self._market_feed.latest_mark(pos.instrument_id)
                        if mark is not None:
                            self._engine.state.open_positions[pid] = update_mark(pos, mark=mark, at=now)
                            dec = evaluate_position(
                                config=self._engine.config.position_monitor,
                                position=self._engine.state.open_positions[pid],
                                hwm=self._engine.state.hwm_state,
                                evaluation_time=now,
                            )
                            if dec.should_exit_now:
                                self._engine.request_exit(pid, now, reason_codes=dec.reason_codes, source="MONITOR")
                                self._engine.handle_exit_fill(pid, now)

                    self._runtime_provider.update_from_engine(self._engine)
            except Exception:
                pass
            await asyncio.sleep(self.config.loop_interval_sec)


def create_a2_paper_app(
    controller: A2PaperSessionController | None = None,
    *,
    reader: Any | None = None,
    require_token: bool = False,
    start_immediately: bool = False,
) -> Any:
    """Create a production-safe A2 Paper FastAPI application over the given session controller.

    Enforces that execution target is PaperBrokerAdapter and live money is disabled.
    """
    from ats.api.app import create_app

    session_controller = controller or A2PaperSessionController(
        config=A2PaperSessionConfig(
            execution_target="PAPER",
            live_money="DISABLED",
        )
    )

    if session_controller.config.execution_target != "PAPER":
        raise ValueError("A2 Paper stack requires execution_target == 'PAPER'")
    if session_controller.config.live_money != "DISABLED":
        raise ValueError("A2 Paper stack requires live_money == 'DISABLED'")

    if start_immediately:
        session_controller.start(require_token=require_token)

    app = create_app(
        reader=reader,
        trading_runtime_provider=session_controller.runtime_provider,
        operator_intelligence_provider=session_controller.operator_provider,
        trading_runtime_engine=session_controller.engine or session_controller,
    )
    app.state.a2_session_controller = session_controller
    return app


__all__ = [
    "A2PaperSessionConfig",
    "A2PaperSessionController",
    "A2SessionState",
    "A2SessionStatus",
    "UpstoxMarketFeedAdapter",
    "create_a2_paper_app",
]
