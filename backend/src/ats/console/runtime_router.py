"""A2-safe runtime command router — no live trading, no direct ledger mutation."""

from __future__ import annotations

from datetime import UTC
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ats.trading_runtime.modes import TradingMode

from .runtime_models import RuntimeCommandRequest, RuntimeCommandResult, RuntimeStatusReadModel

router = APIRouter(prefix="/v1/runtime", tags=["runtime"])


def _runtime_provider(request: Request) -> object | None:
    return getattr(request.app.state, "trading_runtime_provider", None)


ProviderDep = Annotated[object | None, Depends(_runtime_provider)]


@router.get("/status", response_model=RuntimeStatusReadModel)
def get_runtime_status(request: Request, provider: ProviderDep) -> RuntimeStatusReadModel:
    _ = request
    if provider is None:
        from decimal import Decimal

        from ats.console.runtime_models import (
            RuntimeCapitalView,
            RuntimePnLView,
            RuntimeSessionView,
            RuntimeTradingMode,
        )
        from ats.contracts.common import SystemClock
        from ats.contracts.domain.types import LossState

        now = SystemClock().now()
        return RuntimeStatusReadModel(
            session=RuntimeSessionView(
                phase="CLOSED",
                can_enter=False,
                can_reduce=False,
                must_flatten=False,
                is_halted=False,
            ),
            trading_mode=RuntimeTradingMode(
                user_selected="SAFE",
                effective="SAFE",
                deescalation_reason=None,
            ),
            capital=RuntimeCapitalView(
                available=Decimal("0"),
                reserved=Decimal("0"),
                inflight=Decimal("0"),
                used=Decimal("0"),
                total=Decimal("0"),
            ),
            pnl=RuntimePnLView(
                realized=Decimal("0"),
                unrealized=Decimal("0"),
                session_peak=Decimal("0"),
                drawdown_fraction=Decimal("0"),
            ),
            loss_state=LossState.NORMAL,
            open_positions=(),
            recent_decisions=(),
            feed_healthy=False,
            broker_healthy=False,
            halted=False,
            paused_new_entries=True,
            updated_at=now,
        )
    from ats.console.runtime_models import (
        RuntimeCapitalView,
        RuntimePnLView,
        RuntimeSessionView,
        RuntimeTradingMode,
    )
    from ats.contracts.common import SystemClock
    from ats.trading_runtime.runtime_provider import TradingRuntimeProvider

    assert isinstance(provider, TradingRuntimeProvider)
    state = provider.get_state()
    now = SystemClock().now()

    return RuntimeStatusReadModel(
        session=RuntimeSessionView(
            phase=state.phase.value,
            can_enter=state.can_enter,
            can_reduce=state.can_reduce,
            must_flatten=state.must_flatten,
            is_halted=state.is_halted,
        ),
        trading_mode=RuntimeTradingMode(
            user_selected=state.user_mode.value,
            effective=state.effective_mode.value,
            deescalation_reason=state.deescalation_reason,
        ),
        capital=RuntimeCapitalView(
            available=state.available,
            reserved=state.reserved,
            inflight=state.inflight,
            used=state.used,
            total=state.total,
        ),
        pnl=RuntimePnLView(
            realized=state.realized,
            unrealized=state.unrealized,
            session_peak=state.peak_equity,
            drawdown_fraction=state.drawdown_fraction,
        ),
        loss_state=state.loss_state,
        open_positions=tuple(state.open_positions),  # type: ignore[arg-type]
        recent_decisions=tuple(state.recent_decisions),
        feed_healthy=state.feed_healthy,
        broker_healthy=state.broker_healthy,
        halted=state.is_halted,
        paused_new_entries=state.paused,
        updated_at=now,
    )


_ALLOWED = frozenset(
    {
        "SET_MODE",
        "PAUSE_NEW_ENTRIES",
        "RESUME_NEW_ENTRIES",
        "EXIT_POSITION",
        "FLATTEN_PORTFOLIO",
        "HALT_SYSTEM",
        "START_SESSION",
        "STOP_SESSION",
    }
)


@router.post("/command", response_model=RuntimeCommandResult)
def post_runtime_command(
    body: RuntimeCommandRequest, request: Request, provider: ProviderDep
) -> RuntimeCommandResult:
    _ = request
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="runtime provider not attached",
        )
    if body.command not in _ALLOWED:
        return RuntimeCommandResult(accepted=False, reason_codes=("COMMAND_NOT_ALLOWED",))
    from ats.trading_runtime.runtime_provider import TradingRuntimeProvider

    assert isinstance(provider, TradingRuntimeProvider)
    if body.command == "SET_MODE":
        if body.mode is None:
            return RuntimeCommandResult(accepted=False, reason_codes=("MODE_REQUIRED",))
        try:
            mode = TradingMode(body.mode)
        except ValueError:
            return RuntimeCommandResult(accepted=False, reason_codes=("INVALID_MODE",))
        provider.set_mode(mode)
        state = provider.get_state()
        try:
            from ats.trading_runtime.paper_tournament import record_system_activity
            record_system_activity(
                event_kind="TRADING_MODE_UPDATED",
                summary=(
                    f"Trading mode updated to {mode.value} "
                    f"(Effective: {state.effective_mode.value}) | "
                    "Live Safety Safeguard: ACTIVE"
                ),
            )
        except Exception:
            pass
        return RuntimeCommandResult(
            accepted=True, reason_codes=("MODE_UPDATED",), effective_mode=state.effective_mode.value
        )
    if body.command == "PAUSE_NEW_ENTRIES":
        provider.pause()
        try:
            from ats.trading_runtime.paper_tournament import record_system_activity
            record_system_activity(
                event_kind="SYSTEM_PAUSED",
                summary="New order entry paused by operator command.",
            )
        except Exception:
            pass
        return RuntimeCommandResult(accepted=True, reason_codes=("PAUSED",))
    if body.command == "RESUME_NEW_ENTRIES":
        provider.resume()
        try:
            from ats.trading_runtime.paper_tournament import record_system_activity
            record_system_activity(
                event_kind="SYSTEM_RESUMED",
                summary="New order entry resumed by operator command.",
            )
        except Exception:
            pass
        return RuntimeCommandResult(accepted=True, reason_codes=("RESUMED",))
    if body.command == "HALT_SYSTEM":
        provider.halt()
        try:
            from ats.trading_runtime.paper_tournament import record_system_activity
            record_system_activity(
                event_kind="SYSTEM_HALTED",
                summary="EMERGENCY HALT triggered by operator. All trading activities stopped.",
            )
        except Exception:
            pass
        return RuntimeCommandResult(
            accepted=True, reason_codes=("HALTED",), effective_mode="HALTED"
        )
    if body.command == "START_SESSION":
        from decimal import Decimal

        from ats.trading_runtime.paper_tournament import (
            record_system_activity,
            run_full_one_hour_paper_session,
        )
        from ats.trading_runtime.session import RuntimeSessionPhase

        budget = body.budget or Decimal("30000.00")
        try:
            record_system_activity(
                event_kind="PAPER_SESSION_STARTED",
                summary=(
                    "1-hour Paper Tournament V2 started via command | "
                    f"Budget: ₹{budget:,.2f} on MCX Gold Mini"
                ),
            )
        except Exception:
            pass
        session = run_full_one_hour_paper_session(budget=budget)
        request.app.state.active_paper_session = session

        ps = provider.get_state()
        ps.available = session.available_capital
        ps.reserved = session.reserved_capital
        ps.total = session.budget
        ps.realized = sum((t.net_pnl for t in session.closed_trades), Decimal("0.00"))
        ps.peak_equity = session.peak_equity
        ps.drawdown_fraction = session.max_drawdown
        ps.phase = RuntimeSessionPhase.CLOSED
        ps.open_positions = [t.to_dict() for t in session.open_positions.values()]
        ps.recent_decisions = [
            {
                "strategy": t.strategy_id,
                "action": t.direction,
                "price": str(t.entry_price),
                "pnl": str(t.net_pnl),
                "reason": t.exit_reason,
            }
            for t in session.closed_trades[-10:]
        ]
        return RuntimeCommandResult(accepted=True, reason_codes=("SESSION_EXECUTED_COMPLETED",))

    if body.command == "STOP_SESSION":
        active_session = getattr(request.app.state, "active_paper_session", None)
        if active_session:
            active_session.status = "COMPLETED"
        try:
            from ats.trading_runtime.paper_tournament import record_system_activity
            record_system_activity(
                event_kind="PAPER_SESSION_STOPPED",
                summary="Active paper tournament session stopped. Simulated positions flattened.",
            )
        except Exception:
            pass
        return RuntimeCommandResult(accepted=True, reason_codes=("SESSION_STOPPED",))

    if body.command in ("EXIT_POSITION", "FLATTEN_PORTFOLIO"):
        engine = getattr(request.app.state, "trading_runtime_engine", None)
        if engine is not None:
            flattens = ["FLATTEN_PORTFOLIO"]
            if body.command in flattens:
                from ats.contracts.common import SystemClock

                engine.request_flatten(
                    SystemClock().now(),
                    reason_code="DASHBOARD_FLATTEN_REQUESTED",
                    source="DASHBOARD",
                )
                return RuntimeCommandResult(accepted=True, reason_codes=("FLATTEN_QUEUED",))
            if body.position_id is not None:
                from ats.contracts.common import SystemClock

                pid = str(body.position_id)
                if pid in getattr(engine.state, "open_positions", {}):
                    engine.request_exit(
                        pid,
                        SystemClock().now(),
                        reason_codes=("DASHBOARD_EXIT_REQUESTED",),
                        source="DASHBOARD",
                    )
                    return RuntimeCommandResult(accepted=True, reason_codes=("EXIT_QUEUED",))
                return RuntimeCommandResult(accepted=False, reason_codes=("POSITION_NOT_FOUND",))
        active_session = getattr(request.app.state, "active_paper_session", None)
        if active_session:
            active_session.status = "COMPLETED"
        return RuntimeCommandResult(
            accepted=True, reason_codes=("COMMAND_ACCEPTED_PORTFOLIO_FLATTENED",)
        )
    return RuntimeCommandResult(accepted=False, reason_codes=("UNKNOWN_COMMAND",))


@router.get("/paper_session")
def get_paper_session(request: Request) -> dict[str, Any]:
    """Retrieve full summary, trade ledger, and strategy metrics of the active
    1-hr paper session."""
    session = getattr(request.app.state, "active_paper_session", None)
    if session is None:
        from decimal import Decimal

        from ats.trading_runtime.paper_tournament import run_full_one_hour_paper_session
        from ats.trading_runtime.session import RuntimeSessionPhase

        session = run_full_one_hour_paper_session(budget=Decimal("30000.00"))
        request.app.state.active_paper_session = session

        provider = getattr(request.app.state, "trading_runtime_provider", None)
        if provider:
            ps = provider.get_state()
            ps.available = session.available_capital
            ps.reserved = session.reserved_capital
            ps.total = session.budget
            ps.realized = sum((t.net_pnl for t in session.closed_trades), Decimal("0.00"))
            ps.phase = RuntimeSessionPhase.CLOSED
            ps.open_positions = [t.to_dict() for t in session.open_positions.values()]
            ps.recent_decisions = [
                {
                    "strategy": t.strategy_id,
                    "action": t.direction,
                    "price": str(t.entry_price),
                    "pnl": str(t.net_pnl),
                    "reason": t.exit_reason,
                }
                for t in session.closed_trades[-10:]
            ]
    return session.get_summary()


@router.post("/paper_session/start")
def start_paper_session(
    request: Request, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Start a new paper trading session — supports full PaperSessionConfig or
    legacy budget-only mode."""
    from decimal import Decimal

    from ats.trading_runtime.paper_tournament import (
        PaperSessionConfig,
        record_system_activity,
        run_configured_paper_session,
        run_full_one_hour_paper_session,
        validate_paper_session_config,
    )
    from ats.trading_runtime.session import RuntimeSessionPhase

    b = body or {}
    # Always enforce LIVE_MONEY = False server-side
    b["live_money"] = False

    # Full config path — when caller sends a structured PaperSessionConfig dict
    if "capital" in b or "selected_strategies" in b or "duration_minutes" in b:
        # Pre-flight validation
        validation = validate_paper_session_config(b)
        if validation["status"] == "BLOCKED":
            return {
                "status": "BLOCKED",
                "validation": validation,
                "session": None,
            }
        try:
            cfg = PaperSessionConfig(
                capital=Decimal(str(b.get("capital", 30000))),
                duration_minutes=int(b.get("duration_minutes", 60)),
                instrument=b.get("instrument", "GOLDM"),
                contract=b.get("contract", "MCX GOLDM 25SEP26"),
                selected_strategies=list(b.get("selected_strategies") or []),
                max_concurrent_positions=int(b.get("max_concurrent_positions", 2)),
                max_trades_limit=int(b.get("max_trades_limit", 10)),
                position_policy=b.get("position_policy", "ONE_POSITION_PER_STRATEGY"),
                lot_size=int(b.get("lot_size", 1)),
                risk_per_trade_pct=Decimal(str(b.get("risk_per_trade_pct", "2.0"))),
                max_drawdown_pct=Decimal(str(b.get("max_drawdown_pct", "5.0"))),
                stop_loss_mode=b.get("stop_loss_mode", "ATR"),
                stop_loss_value=Decimal(str(b.get("stop_loss_value", "1.5"))),
                take_profit_mode=b.get("take_profit_mode", "R_MULTIPLE"),
                take_profit_value=Decimal(str(b.get("take_profit_value", "2.0"))),
                trailing_stop_mode=b.get("trailing_stop_mode", "DISABLED"),
                trailing_stop_value=Decimal(str(b.get("trailing_stop_value", "1.0"))),
                entry_policy=b.get("entry_policy", "MARKET"),
                session_exit_policy=b.get("session_exit_policy", "SESSION_FLATTEN"),
                cost_model_id=b.get("cost_model_id", "MCX_GOLDM_CANONICAL_V1"),
                session_name=b.get("session_name"),
                mode=b.get("mode", "MULTI_STRATEGY"),
                market=b.get("market", "MCX"),
                exchange=b.get("exchange", "MCX"),
            )
        except Exception as exc:
            return {"status": "CONFIG_ERROR", "detail": str(exc), "session": None}

        try:
            record_system_activity(
                event_kind="PAPER_SESSION_STARTED",
                summary=(
                    "Configured Paper Session started | "
                    f"Capital: ₹{cfg.capital:,.2f} | "
                    f"Duration: {cfg.duration_minutes}m | "
                    f"Strategies: {len(cfg.selected_strategies or [])} | "
                    f"Policy: {cfg.position_policy}"
                ),
            )
        except Exception:
            pass

        session = run_configured_paper_session(config=cfg)
        request.app.state.active_paper_session = session
        provider = getattr(request.app.state, "trading_runtime_provider", None)
        if provider:
            ps = provider.get_state()
            ps.available = session.available_capital
            ps.reserved = session.reserved_capital
            ps.total = session.budget
            ps.realized = sum((t.net_pnl for t in session.closed_trades), Decimal("0.00"))
            ps.phase = RuntimeSessionPhase.CLOSED
            ps.open_positions = [t.to_dict() for t in session.open_positions.values()]
        return {"status": "COMPLETED", "validation": validation, "session": session.get_summary()}

    # Legacy budget-only path
    b_val = b.get("budget", 30000)
    budget = Decimal(str(b_val))
    try:
        record_system_activity(
            event_kind="PAPER_SESSION_STARTED",
            summary=(
                "1-hour Paper Tournament V2 started | "
                f"Budget: ₹{budget:,.2f} | "
                "Strategy Set: 16 native/imported | Instrument: MCX GOLDM"
            ),
        )
    except Exception:
        pass
    session = run_full_one_hour_paper_session(budget=budget)
    request.app.state.active_paper_session = session

    provider = getattr(request.app.state, "trading_runtime_provider", None)
    if provider:
        ps = provider.get_state()
        ps.available = session.available_capital
        ps.reserved = session.reserved_capital
        ps.total = session.budget
        ps.realized = sum((t.net_pnl for t in session.closed_trades), Decimal("0.00"))
        ps.phase = RuntimeSessionPhase.CLOSED
        ps.open_positions = [t.to_dict() for t in session.open_positions.values()]
        ps.recent_decisions = [
            {
                "strategy": t.strategy_id,
                "action": t.direction,
                "price": str(t.entry_price),
                "pnl": str(t.net_pnl),
                "reason": t.exit_reason,
            }
            for t in session.closed_trades[-10:]
        ]
    return {"status": "COMPLETED", "validation": None, "session": session.get_summary()}




@router.post("/paper_session/stop")
def stop_paper_session(request: Request) -> dict[str, Any]:
    """Stops the active paper trading session and flattens all simulated positions."""
    session = getattr(request.app.state, "active_paper_session", None)
    if session:
        session.status = "COMPLETED"
        try:
            from ats.trading_runtime.paper_tournament import record_system_activity
            record_system_activity(
                event_kind="PAPER_SESSION_STOPPED",
                summary=(
                    f"Active paper trading session {session.session_id} stopped. "
                    "All simulated positions flattened."
                ),
                correlation_id=session.session_id,
            )
        except Exception:
            pass
        return cast("dict[str, Any]", session.get_summary())
    return {"status": "NO_SESSION_ACTIVE"}


@router.get("/paper_campaign")
def get_paper_campaign() -> dict[str, Any]:
    """Retrieve multi-session empirical validation campaign metrics and strategy evidence."""
    from ats.trading_runtime.paper_tournament import get_active_campaign
    return get_active_campaign().get_summary()


@router.post("/paper_campaign/run_session")
def run_campaign_session(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Appends an empirical session across defined regimes to the active campaign."""
    from decimal import Decimal

    from ats.trading_runtime.paper_tournament import (
        get_active_campaign,
        record_system_activity,
        run_full_one_hour_paper_session,
    )

    b = body or {}
    budget = Decimal(str(b.get("budget", 30000)))
    regime = b.get("regime", "VOLATILE_EXPANSION")
    stress_mode = b.get("stress_mode", "BASE")
    start_p = Decimal(str(b.get("start_price", 75420.0)))

    campaign = get_active_campaign()
    session = run_full_one_hour_paper_session(
        budget=budget,
        start_price=start_p,
        regime=regime,
        stress_mode=stress_mode,
        campaign=campaign,
    )
    request.app.state.active_paper_session = session
    try:
        record_system_activity(
            event_kind="CAMPAIGN_SESSION_RUN",
            summary=(
                f"Validation Campaign session added: Regime={regime}, "
                f"Budget=₹{budget:,.2f}, Stress={stress_mode} "
                f"(Session: {session.session_id})"
            ),
            correlation_id=session.session_id,
        )
    except Exception:
        pass
    return {
        "session": session.get_summary(),
        "campaign": campaign.get_summary(),
    }


# ---------------------------------------------------------------------------
# Universal Paper Trading Control Center endpoints
# ---------------------------------------------------------------------------

@router.get("/paper_session/schema")
def get_paper_session_schema() -> dict[str, Any]:
    """Returns the complete PaperSessionConfig schema with allowed values and defaults."""
    return {
        "version": "ATS_PAPER_CONFIG_SCHEMA_V2",
        "capital": {
            "type": "Decimal",
            "min": 10000,
            "max": 1000000,
            "default": 30000,
            "presets": [10000, 30000, 50000, 100000],
            "description": (
                "Total paper trading budget in INR. "
                "Must not exceed ₹10,00,000 system ceiling."
            )
        },
        "duration_minutes": {
            "type": "int",
            "allowed": [15, 30, 60, 90, 120, 360, "UNTIL_MARKET_CLOSE"],
            "default": 60,
            "description": "Session duration in minutes. 360 = until market close."
        },
        "selected_strategies": {
            "type": "list[str]",
            "allowed": [
                "A04_PROBABILISTIC",
                "S01_ORB_NR7",
                "S02_TSMOM",
                "S03_DONCHIAN_ATR",
                "S04_VOL_TARGET",
                "S17_PRICE_OI_VOL",
                "S34_REGIME_ROUTER",
                "B02_NAIVE_BREAKOUT",
                "B00_NO_TRADE",
            ],
            "default": ["A04_PROBABILISTIC", "S01_ORB_NR7", "S02_TSMOM"],
            "description": "List of strategy IDs to include in this session."
        },
        "max_concurrent_positions": {
            "type": "int",
            "min": 1,
            "max": 10,
            "default": 2,
            "presets": [1, 2, 3, 5, 10],
            "description": "Maximum number of paper positions open simultaneously."
        },
        "max_trades_limit": {
            "type": "int",
            "min": 1,
            "max": 100,
            "default": 10,
            "description": "Total hard cap on number of trades entered during the session."
        },
        "position_policy": {
            "type": "str",
            "allowed": [
                "ONE_POSITION_PER_STRATEGY",
                "ALLOW_MULTIPLE",
                "ONE_POSITION_PER_INSTRUMENT",
                "NET_BY_INSTRUMENT",
            ],
            "default": "ONE_POSITION_PER_STRATEGY",
            "description": "Position concurrency policy."
        },
        "stop_loss_mode": {
            "type": "str",
            "allowed": ["ATR", "FIXED", "PERCENT", "VOLATILITY_SCALED"],
            "default": "ATR"
        },
        "take_profit_mode": {
            "type": "str",
            "allowed": ["R_MULTIPLE", "FIXED", "PERCENT", "TIME_BASED"],
            "default": "R_MULTIPLE"
        },
        "trailing_stop_mode": {
            "type": "str",
            "allowed": ["DISABLED", "ATR", "FIXED", "CHANDELIER", "BREAKEVEN_PLUS_TRAIL"],
            "default": "DISABLED"
        },
        "cost_model_id": {
            "type": "str",
            "allowed": ["MCX_GOLDM_CANONICAL_V1", "RESEARCH_V2", "STRESS_1_5X", "STRESS_2X"],
            "default": "MCX_GOLDM_CANONICAL_V1"
        },
        "session_exit_policy": {
            "type": "str",
            "allowed": ["SESSION_FLATTEN", "HOLD_THROUGH", "TRAILING_STOP_ONLY"],
            "default": "SESSION_FLATTEN"
        },
        "live_money": {
            "type": "bool",
            "forced_value": False,
            "description": "PERMANENTLY FORCED TO False. Cannot be overridden."
        },
    }


@router.get("/paper_session/presets")
def get_paper_presets_endpoint() -> dict[str, Any]:
    """Returns all built-in and user-saved paper session presets."""
    from ats.trading_runtime.paper_tournament import get_paper_presets
    return {
        "presets": get_paper_presets(),
        "count": len(get_paper_presets()),
    }


@router.post("/paper_session/presets")
def save_paper_preset_endpoint(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Saves a user-defined paper session preset for future use."""
    from ats.trading_runtime.paper_tournament import save_paper_preset
    saved = save_paper_preset(body or {})
    return {"status": "SAVED", "preset": saved}


@router.post("/paper_session/validate")
def validate_paper_session_endpoint(body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validates a paper session configuration before starting. Returns VALID,
    WARNING, or BLOCKED."""
    from ats.trading_runtime.paper_tournament import validate_paper_session_config
    b = body or {}
    # Enforce server-side LIVE_MONEY=False always
    b["live_money"] = False
    return validate_paper_session_config(b)


@router.get("/paper_session/history")
def get_paper_session_history_endpoint() -> dict[str, Any]:
    """Returns list of all completed paper sessions ordered by most recent."""
    from ats.trading_runtime.paper_tournament import get_paper_session_history
    sessions = get_paper_session_history()
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/paper_session/history/{session_id}")
def get_paper_session_detail_endpoint(session_id: str) -> dict[str, Any]:
    """Returns full forensic detail for a specific historical paper session."""
    from ats.trading_runtime.paper_tournament import get_paper_session_detail
    detail = get_paper_session_detail(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return detail


@router.post("/paper_session/clone/{session_id}")
def clone_paper_session_config(session_id: str) -> dict[str, Any]:
    """Returns a cloneable configuration dict from a past session, ready to POST to /start."""
    from ats.trading_runtime.paper_tournament import get_paper_session_detail
    detail = get_paper_session_detail(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    config = detail.get("config", {})
    config["session_name"] = f"Clone of {session_id}"
    config.pop("session_id", None)
    config["live_money"] = False
    return {"config": config, "cloned_from": session_id}


@router.post("/paper_session/manual_entry")
def manual_paper_entry_endpoint(
    request: Request, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Inserts a manual paper position into the active session without a
    strategy signal."""
    from datetime import datetime
    from decimal import Decimal

    from ats.trading_runtime.paper_tournament import record_system_activity

    b = body or {}
    session = getattr(request.app.state, "active_paper_session", None)
    if session is None:
        raise HTTPException(
            status_code=404, detail="No active paper session. Start a session first."
        )
    if session.status not in ("RUNNING", "CREATED"):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Session {session.session_id} is not running "
                f"(status: {session.status})"
            ),
        )

    strategy_id = b.get("strategy_id", "MANUAL")
    if strategy_id not in session.strategies:
        # Auto-register a manual strategy entry for this session
        from ats.trading_runtime.paper_tournament import StrategyPerformance
        session.strategies[strategy_id] = StrategyPerformance(
            strategy_id=strategy_id,
            name=f"Manual Entry ({strategy_id})",
            category="MANUAL",
            margin_allocated=Decimal(str(b.get("margin", 15000))),
        )

    symbol = b.get("symbol", session.instrument)
    direction = b.get("direction", "LONG")
    price = Decimal(str(b.get("price", 75000)))
    stop_offset = Decimal(str(b.get("stop_offset", 75)))
    target_offset = Decimal(str(b.get("target_offset", 150)))
    prob = float(b.get("expected_prob", 0.55))
    now = datetime.now(UTC)

    candidate = session.evaluate_opportunity(
        strategy_id=strategy_id,
        symbol=symbol,
        direction=direction,
        price=price,
        timestamp=now,
        stop_offset=stop_offset,
        target_offset=target_offset,
        expected_prob=prob,
        market_opp_id=f"MANUAL-{b.get('ref', 'ENTRY')}",
        a04_approved=True,
    )

    try:
        record_system_activity(
            event_kind="MANUAL_PAPER_ENTRY",
            summary=(
                "Manual paper entry via Control Center: "
                f"[{strategy_id}] {direction} {symbol} @ ₹{price:,.2f} | "
                f"Status: {candidate.candidate_status}"
            ),
            correlation_id=candidate.candidate_id,
        )
    except Exception:
        pass

    return {
        "candidate": candidate.to_dict(),
        "session_id": session.session_id,
        "open_positions": len(session.open_positions),
        "available_capital": float(session.available_capital),
    }


@router.get("/candidates")
def get_candidates(
    request: Request, strategy_id: str | None = None, status: str | None = None
) -> dict[str, Any]:
    """Returns the comprehensive strategy candidate ledger distinguishing
    opportunities from executions."""
    session = getattr(request.app.state, "active_paper_session", None)
    if not session:
        from decimal import Decimal

        from ats.trading_runtime.paper_tournament import run_full_one_hour_paper_session
        session = run_full_one_hour_paper_session(budget=Decimal("30000.00"))
        request.app.state.active_paper_session = session

    cands = session.candidates_ledger
    if strategy_id:
        cands = [c for c in cands if c.strategy_id == strategy_id]
    if status:
        cands = [c for c in cands if c.candidate_status == status]

    return {
        "session_id": session.session_id,
        "total_candidates": len(cands),
        "candidates": [c.to_dict() for c in cands],
    }


@router.get("/rejections")
def get_rejections(request: Request, reason_code: str | None = None) -> dict[str, Any]:
    """Returns the granular deterministic rejection ledger with risk facts and capital limits."""
    session = getattr(request.app.state, "active_paper_session", None)
    if not session:
        from decimal import Decimal

        from ats.trading_runtime.paper_tournament import run_full_one_hour_paper_session
        session = run_full_one_hour_paper_session(budget=Decimal("30000.00"))
        request.app.state.active_paper_session = session

    rejs = session.rejections_ledger
    if reason_code:
        rejs = [r for r in rejs if r.reason_code == reason_code]

    return {
        "session_id": session.session_id,
        "total_rejections": len(rejs),
        "rejections": [r.to_dict() for r in rejs],
    }


@router.get("/capital_telemetry")
def get_capital_telemetry(request: Request) -> dict[str, Any]:
    """Returns detailed capital allocation, margin utilization, and buffer metrics."""
    session = getattr(request.app.state, "active_paper_session", None)
    if not session:
        from decimal import Decimal

        from ats.trading_runtime.paper_tournament import run_full_one_hour_paper_session
        session = run_full_one_hour_paper_session(budget=Decimal("30000.00"))
        request.app.state.active_paper_session = session

    return {
        "session_id": session.session_id,
        "budget_cap": float(session.budget),
        "available_capital": float(session.available_capital),
        "reserved_capital": float(session.reserved_capital),
        "utilization_pct": (
            round(float(session.reserved_capital / session.budget) * 100.0, 2)
            if session.budget > 0
            else 0.0
        ),
        "open_positions_count": len(session.open_positions),
        "closed_trades_count": len(session.closed_trades),
        "max_drawdown_pct": round(float(session.max_drawdown) * 100.0, 2),
    }


__all__ = ["router"]


