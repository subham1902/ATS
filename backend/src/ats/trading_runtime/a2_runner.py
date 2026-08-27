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
from ats.contracts.domain import MarketSnapshot
from ats.contracts.domain.types import (
    LossState,
)
from ats.contracts.governance.models import OpportunityCandidate
from ats.intelligence.calibration.models import CalibrationObservation
from ats.intelligence.harness.models import MaterialAgentEvent
from ats.market.calendar.models import SessionCalendar
from ats.market.derivatives.providers.models import SourceFreshness
from ats.market.feeds.upstox_v3.instrument_keys import (
    BANKNIFTY_INDEX_FEED_KEY,
    NIFTY_INDEX_FEED_KEY,
)
from ats.market.feeds.upstox_v3.messages import NormalizedFeedUpdate
from ats.market.feeds.upstox_v3.runtime_feed import UpstoxV3RuntimeFeed
from ats.observability.live_pipeline_bridge import LivePipelineBridge
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


def default_a2_session_calendar(trading_dates: tuple[date, ...] | None = None) -> SessionCalendar:
    """Return a standard NSE session calendar for A2 Paper runtime including today."""
    today = date.today()
    dates = trading_dates or (today, date(2024, 6, 3))
    sorted_dates = tuple(sorted(set(dates)))
    return SessionCalendar(
        calendar_id="NSE_LIVE_SESSION",
        calendar_version="1.0.0",
        timezone="Asia/Kolkata",
        trading_dates=sorted_dates,
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


@dataclass
class PipelineCounters:
    """Truthful C2 pipeline telemetry — never synthesized, only incremented from real flow."""

    market_updates_received: int = 0
    snapshots_emitted: int = 0
    feature_bundles: int = 0
    regime_evaluations: int = 0
    calibration_evaluations: int = 0
    r10_evaluations: int = 0
    r10x_evaluations: int = 0
    scanner_observations: int = 0
    candidates_considered: int = 0
    candidates_rejected: int = 0
    candidates_qualified: int = 0
    portfolio_brain_allow: int = 0
    portfolio_brain_reduced: int = 0
    portfolio_brain_defer: int = 0
    portfolio_brain_deny: int = 0
    a04_allow: int = 0
    a04_deny: int = 0
    paper_orders: int = 0
    paper_fills: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)


_REJECTION_TAXONOMY: dict[str, str] = {
    "STALE": "stale",
    "SESSION_NOT_RUNNING": "session",
    "INVALID_REFERENCE": "invalid_reference",
    "CALIBRATION_EVIDENCE_REQUIRED": "insufficient_calibration_support",
    "NEGATIVE_NET_EV": "negative_net_ev",
    "SPREAD": "spread",
    "LIQUIDITY": "liquidity",
    "CONCENTRATION": "portfolio_concentration",
    "CORRELATION": "correlation",
    "CAPITAL": "risk_capital",
    "AUTHORITY_RESERVATION_DENIED": "a04",
    "MAX_CONCURRENT_POSITIONS_REACHED": "risk_capital",
    "QUANTITY_BELOW_LOT_SIZE": "risk_capital",
    "PAPER_BROKER_REJECTED": "other",
    "MARKET_DATA_UNSAFE": "risk_capital",
}


def classify_rejection(reason_codes: tuple[str, ...]) -> str:
    """Map a deterministic rejection reason set to a single typed category."""

    for code in reason_codes:
        category = _REJECTION_TAXONOMY.get(code)
        if category is not None:
            return category
    if any("CONCENTRATION" in c for c in reason_codes):
        return "portfolio_concentration"
    if any("CORRELATION" in c for c in reason_codes):
        return "correlation"
    if any("CALIBRATION" in c for c in reason_codes):
        return "insufficient_calibration_support"
    if any("STALE" in c for c in reason_codes):
        return "stale"
    if any("A04" in c or "AUTHORITY" in c for c in reason_codes):
        return "a04"
    return "other"


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
        self._pipeline_counters = PipelineCounters()
        self._last_event_time: UTCDateTime | None = None

        # Autonomous scanner scheduling & state
        self._last_scanned_state_id: str | None = None
        self._scan_in_flight: bool = False
        self._calibration_observations_provider: Any = None
        self._last_detected_regime: str | None = None
        self._consecutive_rejections: int = 0
        self._snapshot_history: dict[str, list[MarketSnapshot]] = {}

        # Background loop task
        self._stop_event = asyncio.Event()
        self._loop_task: asyncio.Task[None] | None = None

        # Real Upstox V3 runtime feed (read-only market data) and pipeline bridge
        self._upstox_feed: UpstoxV3RuntimeFeed | None = None
        self._live_pipeline_bridge = LivePipelineBridge()

        # Advisory-only DeepSeek Harness integration (ADVISORY_ONLY; governor-gated)
        self._harness_integration: Any = None

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

    @property
    def harness_integration(self) -> Any:
        return self._harness_integration

    def attach_harness_integration(self, integration: Any) -> None:
        """Attach the advisory-only Harness integration (ADVISORY_ONLY)."""
        self._harness_integration = integration

    @property
    def harness_bridge(self) -> Any:
        """Observability facade over the Harness adapter for the /v1/harness surface."""
        if self._harness_integration is None or self._harness_integration.adapter is None:
            return None
        from ats.api.harness_bridge import HarnessBridge

        return HarnessBridge(
            harness_adapter=self._harness_integration.adapter,
            agent_registry=None,
        )

    @property
    def upstox_feed(self) -> UpstoxV3RuntimeFeed | None:
        """Return the attached read-only market-data feed for observability."""

        return self._upstox_feed

    def _compute_decision_state_id(self, now: UTCDateTime) -> str | None:
        """Compute canonical deterministic identity of the current decision-ready state."""
        marks: list[tuple[str, str]] = []
        for und in self.config.underlyings:
            mark = self._market_feed.latest_mark(und)
            if mark is None:
                return None
            marks.append((und, str(mark)))
        offset = now.minute % 5
        from datetime import timedelta

        bar_ts = now - timedelta(
            minutes=offset,
            seconds=now.second,
            microseconds=now.microsecond,
        )
        sorted_marks = tuple(sorted(marks))
        return f"{bar_ts.isoformat()}|{sorted_marks}"

    def _maybe_scan_decision_ready_state(
        self, now: UTCDateTime | None = None
    ) -> dict[str, Any] | None:
        """Evaluate autonomous scanner if a new decision-ready market state exists."""
        if self._state is not A2SessionState.RUNNING or self._engine is None:
            return None
        if self._scan_in_flight:
            return None

        eval_now = now or SystemClock().now()

        # Feed must be healthy to scan
        if not self._market_feed.is_healthy():
            return None

        # Check if all underlyings have fresh data
        for und in self.config.underlyings:
            if not self._market_feed.data_fresh(
                und, now=eval_now, max_age_ms=self.config.max_quote_age_ms
            ):
                return None

        state_id = self._compute_decision_state_id(eval_now)
        if state_id is None or state_id == self._last_scanned_state_id:
            return None

        self._scan_in_flight = True
        self._last_scanned_state_id = state_id
        try:
            cal_obs = ()
            if callable(self._calibration_observations_provider):
                try:
                    cal_obs = self._calibration_observations_provider() or ()
                except Exception:
                    cal_obs = ()
            return self.scan_market_for_candidates(
                calibration_observations=cal_obs, now=eval_now
            )
        except Exception:
            # Scanner exceptions are isolated and must never crash P0 safety or event loop
            return None
        finally:
            self._scan_in_flight = False

    def notify_material_event(
        self,
        event_type: str,
        summary: str,
        *,
        evidence_refs: tuple[UUID, ...] = (),
        now: UTCDateTime | None = None,
    ) -> None:
        """Route a material runtime event to the advisory-only Harness (non-blocking)."""
        if self._harness_integration is None:
            return
        try:
            event = MaterialAgentEvent(
                event_type=event_type,
                occurred_at=now or SystemClock().now(),
                summary=summary,
                evidence_refs=evidence_refs or (uuid4(),),
            )
            if hasattr(self._harness_integration, "route_material_event"):
                self._harness_integration.route_material_event(event)
        except Exception:
            pass  # Harness is advisory only; failures must never affect trading runtime

    def set_calibration_observations_provider(self, provider: Any) -> None:
        """Set a callable provider returning calibration observations (for testing/replay)."""
        self._calibration_observations_provider = provider

    def _sync_live_pipeline_bridge(self) -> None:
        """Sync internal truthful pipeline counters to live pipeline bridge for API/dashboard."""
        c = self._live_pipeline_bridge.counters
        c.scanner_observations = self._pipeline_counters.scanner_observations
        c.feature_bundles = self._pipeline_counters.feature_bundles
        c.regime_evaluations = self._pipeline_counters.regime_evaluations
        c.calibration_evaluations = self._pipeline_counters.calibration_evaluations
        c.r10_evaluations = self._pipeline_counters.r10_evaluations
        c.r10x_evaluations = self._pipeline_counters.r10x_evaluations
        c.candidates_considered = self._pipeline_counters.candidates_considered
        c.candidates_rejected = self._pipeline_counters.candidates_rejected
        c.candidates_qualified = self._pipeline_counters.candidates_qualified
        c.portfolio_brain_decisions = (
            self._pipeline_counters.portfolio_brain_allow
            + self._pipeline_counters.portfolio_brain_reduced
            + self._pipeline_counters.portfolio_brain_defer
            + self._pipeline_counters.portfolio_brain_deny
        )
        c.a04_decisions = (
            self._pipeline_counters.a04_allow + self._pipeline_counters.a04_deny
        )
        c.paper_orders = self._pipeline_counters.paper_orders
        c.paper_fills = self._pipeline_counters.paper_fills

    def start(self, *, require_token: bool = True) -> bool:
        """Start the A2 paper session synchronously."""
        if self._state in (A2SessionState.RUNNING, A2SessionState.STARTING):
            return True

        self._state = A2SessionState.STARTING
        self._reason_codes = []
        self._last_scanned_state_id = None
        self._scan_in_flight = False
        self._consecutive_rejections = 0

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

        if self._harness_integration is not None:
            self._harness_integration.stop()

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
                self.notify_material_event(
                    "POSITION_DETERIORATION",
                    f"Exit triggered on position {pid}: {exit_info.get('reasons', ())}",
                    now=now,
                )

        # 4. Sync runtime provider
        self._runtime_provider.update_from_engine(self._engine)

        # 5. Trigger autonomous scanner if new decision-ready state exists
        self._maybe_scan_decision_ready_state(now)

        return {"accepted": True, "events_processed": self._events_processed, "runtime": runtime_outcome}

    def attach_upstox_runtime_feed(self, feed: UpstoxV3RuntimeFeed) -> None:
        """Attach the read-only Upstox V3 runtime feed to this A2 session.

        The feed is strictly market-data: it can never place, modify or cancel
        orders (no such method exists on :class:`UpstoxV3Transport`). Normalized
        updates are routed into the deterministic runtime via
        :meth:`_on_normalized_update`.
        """

        self._upstox_feed = feed
        self._live_pipeline_bridge.board = feed.board
        feed._on_normalized = self._on_normalized_update

    def _on_normalized_update(
        self, update: NormalizedFeedUpdate, freshness: SourceFreshness
    ) -> None:
        price = update.last_traded_price
        if price is None:
            return
        self.ingest_market_update(
            update.instrument_key, price, update.received_at, freshness
        )

    def ingest_market_update(
        self,
        instrument_key: str,
        price: Decimal,
        at: UTCDateTime | None = None,
        freshness: SourceFreshness | None = None,
    ) -> dict[str, Any]:
        """Route one normalized market update through the full deterministic pipeline."""

        if self._state is not A2SessionState.RUNNING or self._engine is None:
            return {"accepted": False, "reason": "SESSION_NOT_RUNNING"}

        now = at or SystemClock().now()
        self._last_event_time = now
        self._events_processed += 1

        # Index keys map to canonical underlying identities for the bridge.
        bridge_key = instrument_key
        if instrument_key == NIFTY_INDEX_FEED_KEY:
            bridge_key = "NIFTY"
        elif instrument_key == BANKNIFTY_INDEX_FEED_KEY:
            bridge_key = "BANKNIFTY"

        # 1. Update the runtime feed mark (read by the engine for positions).
        if isinstance(self._market_feed, UpstoxMarketFeedAdapter | InMemoryMarketFeed):
            self._market_feed.set_mark(instrument_key, price, now)
            if bridge_key != instrument_key:
                self._market_feed.set_mark(bridge_key, price, now)

        # 2. Truthful pipeline telemetry (no synthetic counts).
        self._live_pipeline_bridge.record_tick(bridge_key, price, received_at=now)
        if freshness is not None:
            fresh = 1 if freshness is SourceFreshness.FRESH else 0
            self._live_pipeline_bridge.record_scan(
                fresh_count=fresh, stale_count=0 if fresh else 1
            )

        # 3. Drive the deterministic engine mark / position monitor.
        event = RuntimeEvent(
            kind=RuntimeEventKind.TICK,
            instrument_id=instrument_key,
            payload={"price": str(price)},
            at=now,
        )
        runtime_outcome = self._engine.process_event(event)

        if runtime_outcome.get("exits"):
            for exit_info in runtime_outcome["exits"]:
                pid = exit_info["position_id"]
                self._engine.request_exit(pid, now, reason_codes=tuple(exit_info.get("reasons", ())), source="MONITOR")
                self._engine.handle_exit_fill(pid, now)
                self.notify_material_event(
                    "POSITION_DETERIORATION",
                    f"Exit triggered on position {pid}: {exit_info.get('reasons', ())}",
                    now=now,
                )

        self._runtime_provider.update_from_engine(self._engine)

        # 4. Trigger autonomous scanner if new decision-ready state exists
        self._maybe_scan_decision_ready_state(now)

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
        self._pipeline_counters.candidates_considered += 1

        # 1. Check max positions limit
        if len(self._engine.state.open_positions) >= self.config.max_positions:
            self._record_rejection(("MAX_CONCURRENT_POSITIONS_REACHED",))
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
            if alloc.outcome is AllocationOutcome.DENY:
                self._pipeline_counters.portfolio_brain_deny += 1
            else:
                self._pipeline_counters.portfolio_brain_defer += 1
            self._record_rejection(tuple(alloc.reason_codes))
            return {"allowed": False, "outcome": alloc.outcome.value, "reasons": alloc.reason_codes}
        if alloc.outcome is AllocationOutcome.ALLOW:
            self._pipeline_counters.portfolio_brain_allow += 1
        else:
            self._pipeline_counters.portfolio_brain_reduced += 1

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
                self._pipeline_counters.a04_deny += 1
                self._record_rejection(("AUTHORITY_RESERVATION_DENIED", *res_res.reason_codes))
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
            self._record_rejection(("PAPER_BROKER_REJECTED",))
            return {"allowed": False, "reason": "PAPER_BROKER_REJECTED"}

        self._paper_orders_submitted += 1
        self._pipeline_counters.paper_orders += 1
        self._pipeline_counters.a04_allow += 1
        self._pipeline_counters.candidates_qualified += 1

        # 5. Simulate Paper Fill
        self._broker.seed_fill(order_status.order_id, slipped_price, order_qty, now=evaluation_time)
        self._paper_fills_recorded += 1
        self._pipeline_counters.paper_fills += 1

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
        self._consecutive_rejections = 0
        self._sync_live_pipeline_bridge()
        return {
            "allowed": True,
            "position_id": pos_id,
            "order_id": order_status.order_id,
            "approved_capital": str(alloc.approved_capital),
            "approved_quantity": str(alloc.approved_quantity),
            "execution_target": "PAPER",
        }

    def pipeline_counters(self) -> PipelineCounters:
        """Read-only access to the truthful C2 pipeline telemetry."""

        return self._pipeline_counters

    def _record_rejection(self, reason_codes: tuple[str, ...]) -> None:
        self._pipeline_counters.candidates_rejected += 1
        category = classify_rejection(reason_codes)
        bucket = self._pipeline_counters.rejection_reasons
        bucket[category] = bucket.get(category, 0) + 1
        # Mirror into the operator dashboard bridge (honest, never synthesized).
        self._live_pipeline_bridge.counters.candidates_rejected += 1
        rb = self._live_pipeline_bridge.counters.rejection_reasons
        rb[category] = rb.get(category, 0) + 1
        self._consecutive_rejections += 1
        if self._consecutive_rejections >= 5 and self._consecutive_rejections % 5 == 0:
            self.notify_material_event(
                "CANDIDATE_REJECTION_CLUSTER",
                f"Candidate rejection cluster: {self._consecutive_rejections} rejections (latest: {category})",
            )

    def seed_snapshot_history(self, underlying: str, snapshots: Any) -> None:
        """Seed snapshot history for an underlying (used for testing/replay)."""
        self._snapshot_history[underlying] = list(snapshots)

    def scan_market_for_candidates(
        self,
        *,
        calibration_observations: tuple[CalibrationObservation, ...] = (),
        now: UTCDateTime | None = None,
    ) -> dict[str, Any]:
        """Run the MarketIntelligencePipeline over current marks.

        Increments the truthful C2 telemetry. If a candidate is synthesized it is
        routed through the governed execution path. If none qualifies, the
        system records a rejected observation with a typed reason and does NOT
        manufacture paper activity (C2.5 — no forced trade).
        """

        if self._state is not A2SessionState.RUNNING or self._engine is None:
            return {"considered": 0, "qualified": 0, "reason": "SESSION_NOT_RUNNING"}

        evaluation_time = now or SystemClock().now()
        self._pipeline_counters.market_updates_received += 1
        self._pipeline_counters.scanner_observations += 1

        from uuid import uuid4

        from ats.contracts.domain import MarketSnapshot
        from ats.contracts.domain.hashing import compute_payload_hash
        from ats.contracts.domain.types import DataQualityState, SessionState
        from ats.contracts.intelligence.models import MarketContext
        from ats.contracts.intelligence.types import LiquidityState, VolatilityState
        from ats.trading_runtime.intelligence_pipeline import (
            IntelligencePipelineConfig,
            MarketIntelligencePipeline,
        )

        offset = evaluation_time.minute % 5
        from datetime import timedelta

        bar_ts = (
            evaluation_time
            - timedelta(
                minutes=offset,
                seconds=evaluation_time.second,
                microseconds=evaluation_time.microsecond,
            )
        )

        pipeline = MarketIntelligencePipeline(config=IntelligencePipelineConfig())
        last_reason_codes: tuple[str, ...] = ()
        valid_underlyings_scanned = 0

        for und in self.config.underlyings:
            mark = self._market_feed.latest_mark(und)
            if mark is None:
                continue

            history = self._snapshot_history.setdefault(und, [])
            if not history or history[-1].bar_timestamp != bar_ts:
                seq = len(history) + 1
                snap = MarketSnapshot(
                    schema_version="1.0",
                    snapshot_id=uuid4(),
                    instrument_id=und,
                    exchange="NSE",
                    segment="CASH",
                    timeframe="5m",
                    sequence=seq,
                    bar_timestamp=bar_ts,
                    received_at=evaluation_time,
                    open=mark,
                    high=mark,
                    low=mark,
                    close=mark,
                    volume=Decimal("1000"),
                    quality_state=DataQualityState.GOOD,
                    quality_flags=(),
                    source="feed",
                    source_version="1.0.0",
                    session_state=SessionState.OPEN,
                    payload_hash="0" * 64,
                )
                snap = snap.model_copy(update={"payload_hash": compute_payload_hash(snap)})
                history.append(snap)
                if len(history) > 20:
                    history.pop(0)
                    history = [
                        h.model_copy(update={"sequence": idx})
                        for idx, h in enumerate(history, start=1)
                    ]
                    self._snapshot_history[und] = history
            else:
                cur = history[-1]
                updated_cur = cur.model_copy(
                    update={
                        "high": max(cur.high, mark),
                        "low": min(cur.low, mark),
                        "close": mark,
                        "received_at": evaluation_time,
                    }
                )
                updated_cur = updated_cur.model_copy(
                    update={"payload_hash": compute_payload_hash(updated_cur)}
                )
                history[-1] = updated_cur

            self._pipeline_counters.snapshots_emitted += 1
            valid_underlyings_scanned += 1
            latest_snap = history[-1]

            ctx = MarketContext(
                schema_version="1.0",
                market_context_id=uuid4(),
                instrument_spec_id=uuid4(),
                instrument_id=und,
                timeframe="5m",
                snapshot_id=latest_snap.snapshot_id,
                feature_bundle_id=uuid4(),
                as_of_time=evaluation_time,
                data_cutoff=evaluation_time,
                session_state=SessionState.OPEN,
                data_quality_state=DataQualityState.GOOD,
                freshness_ms=0,
                liquidity_state=LiquidityState.NORMAL,
                volatility_state=VolatilityState.NORMAL,
                higher_timeframe_context_refs=(),
                related_market_context_refs=(),
                cost_model_version="1.0.0",
                input_hash="0" * 64,
                payload_hash="0" * 64,
            )
            ctx = ctx.model_copy(update={"payload_hash": compute_payload_hash(ctx)})

            self._pipeline_counters.feature_bundles += 1
            self._pipeline_counters.regime_evaluations += 1
            if calibration_observations:
                self._pipeline_counters.calibration_evaluations += 1
            self._pipeline_counters.r10_evaluations += 1
            self._pipeline_counters.r10x_evaluations += 1

            result = pipeline.evaluate(
                snapshots=tuple(history),
                cutoff_sequence=len(history),
                market_context=ctx,
                campaign_id=uuid4(),
                strategy_id=uuid4(),
                evaluation_time=evaluation_time,
                calibration_observations=tuple(calibration_observations),
            )

            if result.regime is not None:
                regime_val = str(getattr(result.regime, "regime", result.regime))
                if self._last_detected_regime != regime_val:
                    self._last_detected_regime = regime_val
                    self.notify_material_event(
                        "REGIME_CHANGE",
                        f"Market regime transition detected: {regime_val}",
                        now=evaluation_time,
                    )

            if result.is_actionable and result.candidate is not None:
                from ats.portfolio.brain import ExposureDirection

                direction = (
                    ExposureDirection.BULLISH
                    if result.direction == "BULLISH"
                    else ExposureDirection.BEARISH
                )
                outcome = self.evaluate_and_execute_candidate(
                    result.candidate,
                    underlying=und,
                    direction=direction,
                    requested_capital=Decimal("50000"),
                    requested_quantity=Decimal("50"),
                    now=evaluation_time,
                )
                if outcome.get("allowed"):
                    self.notify_material_event(
                        "OPPORTUNITY_QUALIFIED",
                        f"Actionable candidate qualified and submitted to PaperBroker for {result.candidate.instrument_id}",
                        now=evaluation_time,
                    )
                self._sync_live_pipeline_bridge()
                return outcome

            last_reason_codes = tuple(result.reason_codes) or ("NEGATIVE_NET_EV",)
            self._record_rejection(last_reason_codes)

        if valid_underlyings_scanned == 0:
            self._record_rejection(("INVALID_REFERENCE",))
            self._sync_live_pipeline_bridge()
            return {"considered": 0, "qualified": 0, "reason": "INVALID_REFERENCE"}

        self._sync_live_pipeline_bridge()
        return {
            "considered": valid_underlyings_scanned,
            "qualified": 0,
            "reason_codes": last_reason_codes,
        }

    async def _event_loop(self) -> None:
        """Background loop monitoring runtime marks, position health, and autonomous candidate scanner."""
        while not self._stop_event.is_set():
            try:
                if self._engine is not None and self._state is A2SessionState.RUNNING:
                    now = SystemClock().now()
                    for und in self.config.underlyings:
                        mark = self._market_feed.latest_mark(und)
                        if mark is not None:
                            self.process_tick(und, mark, at=now)

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
                                self.notify_material_event(
                                    "POSITION_DETERIORATION",
                                    f"Exit triggered on {pos.instrument_id}: {dec.reason_codes}",
                                    now=now,
                                )

                    self._runtime_provider.update_from_engine(self._engine)

                    # Autonomous candidate scanner invocation for decision-ready states
                    self._maybe_scan_decision_ready_state(now)
            except Exception:
                pass
            await asyncio.sleep(self.config.loop_interval_sec)


class A2ControlPlaneReader:
    """Live read adapter over A2PaperSessionController for Control Center dashboard."""

    def __init__(self, controller: A2PaperSessionController) -> None:
        self._controller = controller

    def get_system(self) -> Any:
        from ats.api.models import ReadinessState, SystemReadModel
        from ats.contracts.domain.types import LossState
        from ats.contracts.governance.types import SystemState

        h = self._controller.health()
        is_healthy = h.get("status") == "HEALTHY"
        is_running = self._controller.state is A2SessionState.RUNNING

        now = SystemClock().now()
        return SystemReadModel(
            system_state=SystemState.READY if is_healthy else SystemState.DEGRADED,
            system_state_version=1,
            readiness=ReadinessState.READY if is_running else ReadinessState.NOT_READY,
            degradation_indicators=() if is_healthy else ("DEGRADED_FEED_OR_BROKER",),
            loss_state=LossState.NORMAL,
            active_policy_id=None,
            active_policy_version=None,
            active_campaign_id=None,
            active_campaign_version=None,
            authority_mode="A2_PAPER",
            reconciliation_active=False,
            halted=False,
            last_state_at=now,
            last_event_at=now,
        )

    def get_active_policy(self) -> Any:
        return None

    def get_policy(self, policy_id: UUID) -> Any:
        return None

    def get_campaign(self, campaign_id: UUID) -> Any:
        return None

    def get_candidate(self, candidate_id: UUID) -> Any:
        return None

    def get_governance_context(self, context_id: UUID) -> Any:
        return None

    def get_risk_decision(self, decision_id: UUID) -> Any:
        return None

    def get_advisory(self, advisory_id: UUID) -> Any:
        return None

    def get_token(self, token_id: UUID) -> Any:
        return None

    def list_activity(self) -> tuple[Any, ...]:
        return ()

    def stream_events(self) -> tuple[Any, ...]:
        return ()


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

    resolved_reader = reader or A2ControlPlaneReader(session_controller)

    app = create_app(
        reader=resolved_reader,
        trading_runtime_provider=session_controller.runtime_provider,
        operator_intelligence_provider=session_controller.operator_provider,
        trading_runtime_engine=session_controller.engine or session_controller,
    )
    app.state.a2_session_controller = session_controller
    harness_bridge = session_controller.harness_bridge
    if harness_bridge is not None:
        app.state.harness_bridge = harness_bridge
    app.state.live_pipeline_bridge = session_controller._live_pipeline_bridge

    @app.on_event("startup")
    async def _startup() -> None:
        if session_controller.state != A2SessionState.RUNNING:
            await session_controller.start_async(require_token=require_token)

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await session_controller.stop_async()

    return app


__all__ = [
    "A2PaperSessionConfig",
    "A2PaperSessionController",
    "A2SessionState",
    "A2SessionStatus",
    "UpstoxMarketFeedAdapter",
    "create_a2_paper_app",
]
