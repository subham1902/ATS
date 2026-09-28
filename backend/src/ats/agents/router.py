"""FastAPI router for Quantitative Agents Playground, Dynamic Configurations, and Upstox Live Trade Ledger."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from ats.agents.config import get_agents_config_manager
from ats.agents.costs import assess_trade
from ats.agents.custom import StrategyValidationError, get_custom_registry
from ats.agents.deployment import from_report, get_deployment_gate
from ats.agents.deployment import load as load_gate
from ats.agents.evolver import get_continuous_tester
from ats.agents.families import FAMILY_DESCRIPTIONS
from ats.agents.portfolio import MANDATES, validate_mandates
from ats.agents.risk import GLOBAL_KILL_SWITCH
from ats.agents.roster import RosterError, get_roster
from ats.agents.strategies import STRATEGY_REGISTRY, ensure_diverse_families_loaded
from ats.agents.trade_ledger import get_upstox_trade_ledger
from ats.agents.worker import (
    CONTRACT_SPECS,
    agents_state,
    get_edge_registry,
    get_execution_model,
    get_portfolio_builder,
    get_risk_manager,
    init_agents,
)

router = APIRouter(prefix="/v1/agents", tags=["agents"])


def sync_roster_to_state() -> None:
    """Re-initialise agent state from the roster after a membership change."""
    init_agents()


class UpdateAgentPrincipalRequest(BaseModel):
    agent_name: str | None = None
    max_principal: float | None = Field(
        None, gt=0, description="Max principal in INR (e.g. 100000 or 200000)"
    )
    max_risk_pct_per_trade: float | None = Field(None, gt=0, le=100)
    max_lots: int | None = Field(None, gt=0)
    # Support bulk dictionary updates as well: {"Alpha": 100000, "Echo": 200000}
    principals: dict[str, float] | None = None


class MarketSelectionRequest(BaseModel):
    target_market: str = Field(
        ...,
        description="Target market: 'AUTO', 'MCX_GOLDM' (Mini 100g), 'MCX_GOLD' (1kg Big Contract), or 'GLOBAL_XAU' (XAU/USD 24/7)",
    )


class UpdateAgentGuidelinesRequest(BaseModel):
    mode: str | None = Field(None, description="'AUTO' (Autonomous) or 'CUSTOM'")
    strategy_id: str | None = Field(None, description="Strategy ID or 'AUTO'")
    strategy_name: str | None = None
    target_market: str | None = Field(None, description="'AUTO', 'MCX_GOLDM', 'MCX_GOLD', 'GLOBAL_XAU'")
    max_principal: float | None = Field(None, gt=0, description="Max principal in INR")
    allowed_lot_size: float | None = Field(None, gt=0, description="Allowed lot size ceiling (e.g. 0.1, 0.2, 1.0)")
    lots: float | None = Field(None, ge=0, description="0 = AUTO sizing, or fixed lot size")
    direction_bias: str | None = Field(None, description="'BOTH', 'LONG_ONLY', or 'SHORT_ONLY'")
    profit_target_pts: float | None = Field(None, ge=0, description="Profit target points (0 = AUTO)")
    stop_loss_pts: float | None = Field(None, ge=0, description="Stop loss points (0 = AUTO)")
    max_risk_pct_per_trade: float | None = Field(None, gt=0, le=100)
    goal: str | None = Field(None, description="'MAX_NET_PNL_INCREMENT' or custom goal")
    horizon: str | None = Field(None, description="'TACTICAL_INTRADAY' or 'LONG_TERM_SWING'")
    target_net_pnl_increment: float | None = Field(None, gt=0, description="Target net PnL increment in INR")
    retest_winning_strategies: bool | None = None
    condition_gated_entry: bool | None = None
    min_edge_multiple: float | None = Field(
        None, ge=1.0, description="Required edge-to-cost multiple (default 3.0)"
    )
    min_signal_confidence: float | None = Field(
        None, ge=0, le=1, description="Minimum signal confidence to act (default 0.45)"
    )
    max_trades_per_day: int | None = Field(None, ge=0)
    min_seconds_between_entries: float | None = Field(None, ge=0)


class BulkUpdateGuidelinesRequest(BaseModel):
    allowed_lot_size: float | None = Field(None, gt=0, description="Allowed lot size ceiling")
    mode: str | None = Field(None, description="'AUTO' or 'CUSTOM'")
    target_market: str | None = None
    direction_bias: str | None = None
    goal: str | None = None
    horizon: str | None = None
    target_net_pnl_increment: float | None = None
    retest_winning_strategies: bool | None = None
    condition_gated_entry: bool | None = None
    min_edge_multiple: float | None = Field(None, ge=1.0)
    min_signal_confidence: float | None = Field(None, ge=0, le=1)
    max_trades_per_day: int | None = Field(None, ge=0)


class KillSwitchRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Why trading is being enabled or halted")


class RiskLimitsRequest(BaseModel):
    max_portfolio_drawdown_pct: float | None = Field(None, gt=0, le=100)
    max_daily_loss_pct: float | None = Field(None, gt=0, le=100)
    max_consecutive_losses: int | None = Field(None, gt=0)
    max_total_loss_pct: float | None = Field(None, gt=0, le=100)
    max_trades_per_day: int | None = Field(None, gt=0)
    max_concurrent_positions: int | None = Field(None, gt=0)
    max_margin_utilisation_pct: float | None = Field(None, gt=0, le=100)
    max_gross_leverage: float | None = Field(None, gt=0)
    max_pair_correlation: float | None = Field(None, gt=0, le=1)
    portfolio_daily_loss_pct: float | None = Field(None, gt=0, le=100)
    min_seconds_between_entries: float | None = Field(None, ge=0)


class TradeEconomicsRequest(BaseModel):
    """Pre-trade viability probe. Answers 'would this trade be worth taking?'."""

    exchange: str = "MCX"
    entry_price: float = Field(..., gt=0)
    symbol: str = "MCX:GOLDM FUT"
    lot_size: float = Field(100.0, gt=0)
    lots: float = Field(1.0, gt=0)
    target_points: float = Field(..., gt=0)
    stop_points: float = Field(..., gt=0)
    strategy_win_rate: float = Field(0.5, ge=0, le=1)
    min_edge_multiple: float = Field(3.0, ge=1.0)


@router.get("/status")
def get_agents_status() -> dict[str, Any]:
    """Return live playground status, agent states, risk, edge, and cost-aware ledger stats."""
    ledger = get_upstox_trade_ledger()
    agents_state["upstox_ledger_summary"] = ledger.get_summary_statistics()
    agents_state["risk"] = get_risk_manager().summary()
    agents_state["execution"] = get_execution_model().stats
    agents_state["deployment"] = get_deployment_gate().summary()
    return cast("dict[str, Any]", jsonable_encoder(agents_state))


class AddAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=32, description="Unique agent name")
    family: str = Field(..., min_length=1, description="Signal family (must be unique in fleet)")
    signal_source: str = Field(..., min_length=1, description="Registered strategy id")
    description: str = ""
    instrument_bias: list[str] | None = None
    horizon: str = "TACTICAL_INTRADAY"
    bar_seconds: float = Field(300.0, gt=0)
    principal: float = Field(100_000.0, gt=0)


class AssignStrategyRequest(BaseModel):
    signal_source: str = Field(..., min_length=1, description="Registered strategy id")


class RegisterStrategyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    source: str = Field(..., min_length=1, description="Python defining a function of `name`")
    description: str = ""
    params: dict[str, Any] | None = None


class SetPrincipalRequest(BaseModel):
    principal: float = Field(..., gt=0)


# ---------------------------------------------------------------------------
# Roster: add and remove agents
# ---------------------------------------------------------------------------


@router.get("/roster")
def get_roster_status() -> dict[str, Any]:
    """Return the live agent roster: who is running and on what."""
    r = get_roster()
    return {
        **r.as_dict(),
        "registered_strategies": sorted(STRATEGY_REGISTRY.keys()),
        "diverse_families": sorted(FAMILY_DESCRIPTIONS),
    }


@router.post("/roster/agents")
def add_roster_agent(body: AddAgentRequest) -> dict[str, Any]:
    """Add an agent to the fleet, validating diversification first."""
    try:
        entry = get_roster().add(
            name=body.name,
            family=body.family,
            signal_source=body.signal_source,
            description=body.description,
            instrument_bias=body.instrument_bias,
            horizon=body.horizon,
            bar_seconds=body.bar_seconds,
            principal=body.principal,
        )
    except RosterError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    sync_roster_to_state()
    return {"message": f"Agent {entry.name} added", "agent": entry.as_dict()}


@router.delete("/roster/agents/{agent_name}")
def remove_roster_agent(agent_name: str) -> dict[str, Any]:
    """Remove an agent from the fleet and release its resources."""
    try:
        entry = get_roster().remove(agent_name)
    except RosterError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    sync_roster_to_state()
    get_risk_manager().reset_agent(entry.name, principal=entry.principal)
    get_portfolio_builder().remove_exposure(entry.name)
    return {"message": f"Agent {entry.name} removed", "agent": entry.as_dict()}


@router.post("/roster/agents/{agent_name}/strategy")
def assign_roster_strategy(agent_name: str, body: AssignStrategyRequest) -> dict[str, Any]:
    """Point an agent at a different registered strategy.

    This is how you run your own strategy: register it, then assign it here.
    """
    try:
        entry = get_roster().assign_strategy(agent_name, body.signal_source)
    except RosterError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    sync_roster_to_state()
    return {
        "message": f"Agent {agent_name} now runs {body.signal_source}",
        "agent": entry.as_dict(),
    }


@router.put("/roster/agents/{agent_name}/principal")
def set_roster_principal(agent_name: str, body: SetPrincipalRequest) -> dict[str, Any]:
    """Set an agent's principal."""
    try:
        entry = get_roster().set_principal(agent_name, body.principal)
    except RosterError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    get_risk_manager().register_principal(agent_name, body.principal)
    return {"message": f"Agent {agent_name} principal set", "agent": entry.as_dict()}


@router.post("/roster/reset")
def reset_roster() -> dict[str, Any]:
    """Restore the default four-agent fleet."""
    get_roster().reset_to_default()
    sync_roster_to_state()
    return {"message": "Roster reset to default four-agent fleet", "roster": get_roster().as_dict()}


# ---------------------------------------------------------------------------
# Custom strategies
# ---------------------------------------------------------------------------


@router.get("/strategies")
def list_strategies() -> dict[str, Any]:
    """List every registered strategy: built-in, diverse, and custom."""
    ensure_diverse_families_loaded()
    return {
        "builtin": sorted(k for k in STRATEGY_REGISTRY if k not in FAMILY_DESCRIPTIONS),
        "diverse": FAMILY_DESCRIPTIONS,
        "custom": get_custom_registry().list(),
    }


@router.post("/strategies")
def register_custom_strategy(body: RegisterStrategyRequest) -> dict[str, Any]:
    """Register your own strategy.

    Submit Python defining a function named ``name`` that takes ``bars`` and
    returns a ``StrategySignal`` (or ``None`` to abstain). The source is
    statically checked and smoke-tested, but it stays sandboxed from live
    trading until it clears validation and the deployment gate.
    """
    try:
        strategy = get_custom_registry().register(
            name=body.name,
            source=body.source,
            description=body.description,
            params=body.params,
        )
    except StrategyValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"message": f"Strategy {strategy.name} registered", "strategy": strategy.as_dict()}


@router.delete("/strategies/{name}")
def remove_custom_strategy(name: str) -> dict[str, Any]:
    """Unregister a custom strategy."""
    if not get_custom_registry().remove(name):
        raise HTTPException(status_code=404, detail=f"Custom strategy '{name}' not found")
    return {"message": f"Strategy {name} removed"}


@router.post("/strategies/{name}/validate")
async def validate_custom_strategy(name: str) -> dict[str, Any]:
    """Backtest a registered custom strategy on real history.

    Reports the same honest IS/OOS verdict the built-in gate uses. A strategy
    that does not hold up here cannot be funded, regardless of how it looks
    in-sample.
    """
    strategy = get_custom_registry().get(name)
    if strategy is None:
        raise HTTPException(status_code=404, detail=f"Custom strategy '{name}' not found")

    def _run() -> dict[str, Any]:
        from scripts.validate_strategies import (
            _mandate_params,
            load_bars,
            resolve_data_path,
            simulate,
        )

        bars = load_bars(resolve_data_path(), limit=120_000, bar_seconds=300.0)
        if len(bars) < 200:
            return {"error": "insufficient historical data"}
        split = int(len(bars) * 0.7)
        params = _mandate_params("TACTICAL_INTRADAY")
        oos = simulate(
            bars[split:],
            agent=name,
            family=name,
            signal_source=name,
            **params,
            seed=11,
        )
        result = oos.as_dict()
        strategy.validation = result
        strategy.status = oos.verdict
        return result

    try:
        result = await asyncio.to_thread(_run)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation failed: {e}") from e
    return {
        "strategy": name,
        "result": result,
        "note": (
            "Only positive out-of-sample expectancy can be deployed. "
            "The deployment gate enforces this automatically."
        ),
    }


# ---------------------------------------------------------------------------
# Continuous testing
# ---------------------------------------------------------------------------


@router.get("/evolver")
def get_evolver_status() -> dict[str, Any]:
    """Return continuous-tester status, recent cycles, and drift trends."""
    t = get_continuous_tester()
    return {**t.status(), "trend": t.trend()}


@router.post("/evolver/start")
async def start_evolver(interval_seconds: float = 300.0) -> dict[str, Any]:
    """Start the continuous testing loop."""
    t = get_continuous_tester()
    t._interval = max(10.0, interval_seconds)  # noqa: SLF001
    t.start()
    return {"message": "Continuous tester started", "status": t.status()}


@router.post("/evolver/stop")
async def stop_evolver() -> dict[str, Any]:
    """Stop the continuous testing loop."""
    t = get_continuous_tester()
    await t.stop()
    return {"message": "Continuous tester stopped", "status": t.status()}


@router.post("/evolver/cycle")
async def run_evolver_cycle() -> dict[str, Any]:
    """Run one validation cycle immediately."""
    result = await get_continuous_tester().run_cycle()
    return {"message": "Cycle complete", "cycle": result.as_dict()}


# ---------------------------------------------------------------------------
# Deployment gate (validated-evidence gate)
# ---------------------------------------------------------------------------


@router.get("/deployment")
def get_deployment_status() -> dict[str, Any]:
    """Return which mandates are cleared to trade, and why the rest are held."""
    return cast("dict[str, Any]", jsonable_encoder(get_deployment_gate().summary()))


@router.get("/deployment/{agent_name}")
def get_agent_deployment(agent_name: str) -> dict[str, Any]:
    """Return one agent's deployment verdict with the reasoning."""
    gate = get_deployment_gate()
    allowed, reason = gate.allows_with_reason(agent_name)
    verdict = gate.verdicts.get(agent_name)
    return {
        "agent": agent_name,
        "deployable": allowed,
        "reason": reason,
        "verdict": verdict.as_dict() if verdict else None,
    }


@router.post("/deployment/load")
def load_deployment_gate(body: dict[str, Any]) -> dict[str, Any]:
    """Load a validation report file and install it as the active deployment gate.

    Only out-of-sample evidence can deploy a mandate. Loading a report that
    shows no OOS edge will hold the whole fleet, which is the correct outcome.
    """
    path = str(body.get("path", ""))
    if not path:
        raise HTTPException(status_code=400, detail="Provide 'path' to a validation report")
    gate = load_gate(path)
    return {
        "message": "Deployment gate loaded from validation report",
        "gate": gate.summary(),
    }


@router.post("/deployment/report")
def load_deployment_report(report: dict[str, Any]) -> dict[str, Any]:
    """Install a validation report directly (no file path required)."""
    gate = from_report(report)
    return {
        "message": "Deployment gate updated from submitted report",
        "gate": gate.summary(),
    }


# ---------------------------------------------------------------------------
# Risk control (Tier 0)
# ---------------------------------------------------------------------------


@router.get("/risk")
def get_risk_status() -> dict[str, Any]:
    """Return circuit-breaker state, per-agent risk, and blocked-signal audit trail."""
    return cast("dict[str, Any]", jsonable_encoder(get_risk_manager().summary()))


@router.get("/risk/kill-switch")
def get_kill_switch() -> dict[str, Any]:
    """Return whether trading is globally permitted. Disabled by default."""
    return cast("dict[str, Any]", jsonable_encoder(GLOBAL_KILL_SWITCH.as_dict()))


@router.post("/risk/kill-switch/engage")
def engage_kill_switch(body: KillSwitchRequest) -> dict[str, Any]:
    """HALT all trading immediately. Existing positions are left unmanaged."""
    return cast("dict[str, Any]", jsonable_encoder(GLOBAL_KILL_SWITCH.engage(body.reason)))


@router.post("/risk/kill-switch/release")
def release_kill_switch(body: KillSwitchRequest) -> dict[str, Any]:
    """PERMIT trading. Read the cost-aware ledger summary first."""
    return cast("dict[str, Any]", jsonable_encoder(GLOBAL_KILL_SWITCH.release(body.reason)))


@router.get("/risk/limits")
def get_risk_limits() -> dict[str, Any]:
    """Return the enforced risk limit set."""
    return cast("dict[str, Any]", jsonable_encoder(get_risk_manager().limits.as_dict()))


@router.put("/risk/limits")
def update_risk_limits(body: RiskLimitsRequest) -> dict[str, Any]:
    """Tighten risk limits at runtime. Applies to every agent immediately."""
    mgr = get_risk_manager()
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(mgr.limits, key, value)
    return {
        "message": "Risk limits updated and enforced immediately",
        "limits": mgr.limits.as_dict(),
    }


# ---------------------------------------------------------------------------
# Cost awareness
# ---------------------------------------------------------------------------


@router.post("/economics/check")
def check_trade_economics(body: TradeEconomicsRequest) -> dict[str, Any]:
    """Probe whether a hypothetical trade is economically viable after charges.

    This is the pre-trade gate exposed to operators, so a rejection is
    explainable rather than mysterious.
    """
    econ = assess_trade(
        exchange=body.exchange,
        entry_price=body.entry_price,
        symbol=body.symbol,
        lot_size=body.lot_size,
        lots=body.lots,
        target_points=body.target_points,
        stop_points=body.stop_points,
        strategy_win_rate=body.strategy_win_rate,
        min_edge_multiple=body.min_edge_multiple,
    )
    return {
        "tradable": econ.tradable,
        "economics": econ.as_dict(),
        "note": (
            "Blocked trades cost nothing. The most common block is "
            "LOT_SIZE_UNECONOMICAL: transaction cost exceeds the edge."
        ),
    }


@router.get("/economics/cost-drag")
def get_cost_drag() -> dict[str, Any]:
    """Return charge-aware profitability: gross vs net win rate and required break-even."""
    ledger = get_upstox_trade_ledger()
    return {
        "summary": ledger.get_summary_statistics(),
        "per_agent": [
            ledger.get_agent_cost_report(name)
            for name in sorted(agents_state.get("agents", {}).keys())
        ],
    }


# ---------------------------------------------------------------------------
# Strategy evidence and portfolio
# ---------------------------------------------------------------------------


@router.get("/edge")
def get_edge_evidence() -> dict[str, Any]:
    """Return per-strategy statistical evidence and promotion status."""
    return cast("dict[str, Any]", jsonable_encoder(get_edge_registry().summary()))


@router.get("/portfolio")
def get_portfolio_status() -> dict[str, Any]:
    """Return mandate map, open exposure, and correlation-cap compliance."""
    return cast(
        "dict[str, Any]",
        jsonable_encoder(
            {
                "mandates": [m.as_dict() for m in MANDATES],
                "mandate_health": {
                    "problems": validate_mandates(),
                    "healthy": not validate_mandates(),
                    "distinct_families": len({m.family for m in MANDATES}),
                    "instruments": sorted({i for m in MANDATES for i in m.instrument_bias}),
                    "horizons": sorted({m.horizon for m in MANDATES}),
                },
                "exposure": get_portfolio_builder().concentration_summary(),
            }
        ),
    )


@router.get("/contracts")
def get_contract_specs() -> dict[str, Any]:
    """Return tradable contract specs, including lot size, margin, and tick size."""
    return {"contracts": CONTRACT_SPECS}


@router.get("/market")
def get_target_market() -> dict[str, Any]:
    """Get currently active playground market, active session info, and available markets."""
    cfg_mgr = get_agents_config_manager()
    current_market = cfg_mgr.get_target_market()
    return {
        "target_market": current_market,
        "active_session": agents_state.get("active_session", {}),
        "available_markets": [
            {
                "id": "AUTO",
                "name": "Auto Session Routing",
                "badge": "24/7 Smart Route",
                "description": "MCX Gold Mini during regular hours (09:00-23:30 IST), Global Spot Gold (XAU/USD) 24/7 during off-hours.",
                "currency": "INR / USD",
                "contract_type": "DYNAMIC",
            },
            {
                "id": "MCX_GOLDM",
                "name": "MCX Gold Mini (100g)",
                "badge": "MCX Live",
                "description": "100 grams lot size, quoted per 10 grams in INR. Upstox live tick feed with off-session spot parity.",
                "currency": "INR",
                "contract_type": "MCX_GOLDM",
            },
            {
                "id": "MCX_GOLD",
                "name": "MCX Gold (1kg Big Contract)",
                "badge": "MCX 1kg",
                "description": "1,000 grams (1kg) lot size, quoted per 10 grams in INR with 100x multiplier. Professional institutional contract.",
                "currency": "INR",
                "contract_type": "MCX_GOLD",
            },
            {
                "id": "GLOBAL_XAU",
                "name": "Global Spot Gold (XAU/USD)",
                "badge": "24/7 Spot",
                "description": "Continuous 24/7 international spot gold price in USD per troy ounce (PAXG/USDT institutional feed).",
                "currency": "USD",
                "contract_type": "GLOBAL_XAU",
            },
        ],
    }


@router.put("/market")
def set_target_market(body: MarketSelectionRequest) -> dict[str, Any]:
    """Set the playground active market target ('AUTO', 'MCX_GOLDM', 'MCX_GOLD', 'GLOBAL_XAU')."""
    cfg_mgr = get_agents_config_manager()
    valid_markets = {"AUTO", "MCX_GOLDM", "MCX_GOLD", "GLOBAL_XAU"}
    if body.target_market not in valid_markets:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid market '{body.target_market}'. Must be one of {valid_markets}",
        )
    target = cfg_mgr.set_target_market(body.target_market)
    agents_state["target_market"] = target
    return {
        "message": f"Playground target market updated to {target}",
        "target_market": target,
    }


@router.get("/guidelines")
def get_all_agent_guidelines() -> dict[str, Any]:
    """Retrieve full trading guidelines for all 10 playground agents."""
    cfg_mgr = get_agents_config_manager()
    return {
        "guidelines": cfg_mgr.get_all(),
        "summary": "10 Quantitative Agents with dynamic guidelines (8 @ ₹1 Lac, 2 @ ₹2 Lac: Echo and Juliet).",
    }


@router.get("/{agent_name}/guidelines")
def get_agent_guidelines(agent_name: str) -> dict[str, Any]:
    """Retrieve specific trading guidelines for an agent."""
    cfg_mgr = get_agents_config_manager()
    guidelines = cfg_mgr.get_guidelines(agent_name)
    return guidelines.to_dict()


@router.put("/{agent_name}/guidelines")
def update_agent_guidelines(agent_name: str, body: UpdateAgentGuidelinesRequest) -> dict[str, Any]:
    """Update execution guidelines, strategy directive, lot size, or principal for an agent."""
    cfg_mgr = get_agents_config_manager()
    updated = cfg_mgr.update_agent_guidelines(
        agent_name=agent_name,
        max_principal=body.max_principal,
        mode=body.mode,
        strategy_id=body.strategy_id,
        strategy_name=body.strategy_name,
        target_market=body.target_market,
        allowed_lot_size=body.allowed_lot_size,
        lots=body.lots,
        direction_bias=body.direction_bias,
        profit_target_pts=body.profit_target_pts,
        stop_loss_pts=body.stop_loss_pts,
        max_risk_pct=body.max_risk_pct_per_trade,
        goal=body.goal,
        horizon=body.horizon,
        target_net_pnl_increment=body.target_net_pnl_increment,
        retest_winning_strategies=body.retest_winning_strategies,
        condition_gated_entry=body.condition_gated_entry,
        min_edge_multiple=body.min_edge_multiple,
        min_signal_confidence=body.min_signal_confidence,
        max_trades_per_day=body.max_trades_per_day,
        min_seconds_between_entries=body.min_seconds_between_entries,
    )
    # Sync with live in-memory state
    if agent_name in agents_state["agents"]:
        agents_state["agents"][agent_name]["guidelines"] = updated.to_dict()
        if body.max_principal is not None:
            agents_state["agents"][agent_name]["max_principal"] = body.max_principal
        if body.strategy_id is not None and body.strategy_id != "AUTO":
            agents_state["agents"][agent_name]["active_strategy"] = body.strategy_id
        if body.strategy_name is not None:
            agents_state["agents"][agent_name]["active_strategy_name"] = body.strategy_name
        if body.goal is not None:
            agents_state["agents"][agent_name]["goal"] = body.goal
        if body.horizon is not None:
            agents_state["agents"][agent_name]["horizon"] = body.horizon

    return {
        "message": f"Updated guidelines for Agent {agent_name}",
        "guidelines": updated.to_dict(),
    }


@router.post("/{agent_name}/guidelines/reset")
def reset_agent_guidelines(agent_name: str) -> dict[str, Any]:
    """Reset a specific agent's guidelines to default AUTO autonomous mode."""
    cfg_mgr = get_agents_config_manager()
    reset_cfg = cfg_mgr.reset_agent_guidelines(agent_name)
    if agent_name in agents_state["agents"]:
        agents_state["agents"][agent_name]["guidelines"] = reset_cfg.to_dict()
        agents_state["agents"][agent_name]["max_principal"] = reset_cfg.max_principal
        agents_state["agents"][agent_name]["goal"] = reset_cfg.goal
        agents_state["agents"][agent_name]["horizon"] = reset_cfg.horizon
    return {
        "message": f"Reset Agent {agent_name} to default AUTO autonomous mode",
        "guidelines": reset_cfg.to_dict(),
    }


@router.post("/guidelines/bulk")
def update_bulk_guidelines(body: BulkUpdateGuidelinesRequest) -> dict[str, Any]:
    """Bulk update guidelines for all agents (e.g. setting lot size ceiling or mode)."""
    cfg_mgr = get_agents_config_manager()
    results = {}
    for name in list(agents_state.get("agents", {}).keys()):
        updated = cfg_mgr.update_agent_guidelines(
            agent_name=name,
            allowed_lot_size=body.allowed_lot_size,
            mode=body.mode,
            target_market=body.target_market,
            direction_bias=body.direction_bias,
            goal=body.goal,
            horizon=body.horizon,
            target_net_pnl_increment=body.target_net_pnl_increment,
            retest_winning_strategies=body.retest_winning_strategies,
            condition_gated_entry=body.condition_gated_entry,
            min_edge_multiple=body.min_edge_multiple,
            min_signal_confidence=body.min_signal_confidence,
            max_trades_per_day=body.max_trades_per_day,
        )
        if name in agents_state["agents"]:
            agents_state["agents"][name]["guidelines"] = updated.to_dict()
            if body.goal is not None:
                agents_state["agents"][name]["goal"] = body.goal
            if body.horizon is not None:
                agents_state["agents"][name]["horizon"] = body.horizon
        results[name] = updated.to_dict()
    return {"message": "Bulk guidelines updated successfully", "guidelines": results}


@router.post("/goals/set-success")
def set_all_agents_goals_to_success() -> dict[str, Any]:
    """Configure all agents with the unified success goal: finding winning strategies, retesting in right conditions, and maximizing net P&L."""
    cfg_mgr = get_agents_config_manager()
    results = {}
    for name in list(agents_state.get("agents", {}).keys()):
        is_long_term = (name in ("Echo", "Juliet"))
        horizon = "LONG_TERM_SWING" if is_long_term else "TACTICAL_INTRADAY"
        target_inc = 50000.0 if is_long_term else 25000.0
        updated = cfg_mgr.update_agent_guidelines(
            agent_name=name,
            goal="MAX_NET_PNL_INCREMENT",
            horizon=horizon,
            target_net_pnl_increment=target_inc,
            retest_winning_strategies=True,
            condition_gated_entry=True,
        )
        if name in agents_state["agents"]:
            agents_state["agents"][name]["guidelines"] = updated.to_dict()
            agents_state["agents"][name]["goal"] = updated.goal
            agents_state["agents"][name]["horizon"] = updated.horizon
            agents_state["agents"][name]["target_net_pnl_increment"] = updated.target_net_pnl_increment
            agents_state["agents"][name]["retest_winning_strategies"] = True
            agents_state["agents"][name]["condition_gated_entry"] = True
        results[name] = updated.to_dict()
    return {
        "status": "success",
        "message": "All agents' goals set to Success: Finding winning strategies, retesting in right conditions, and maximizing Net P&L increment.",
        "long_term_agents": ["Echo", "Juliet"],
        "tactical_intraday_agents": ["Alpha", "Bravo", "Charlie", "Delta", "Foxtrot", "Golf", "Hotel", "India"],
        "guidelines": results,
    }


@router.get("/config")
def get_agents_configuration() -> dict[str, Any]:
    """Get dynamic principal and risk configurations for all agents."""
    cfg_mgr = get_agents_config_manager()
    return {
        "configurations": cfg_mgr.get_all(),
        "summary": "10 Agents: 8 @ ₹1 Lac (₹100,000), 2 @ ₹2 Lac (₹200,000: Echo and Juliet).",
    }


@router.put("/config")
def update_agents_configuration(body: UpdateAgentPrincipalRequest) -> dict[str, Any]:
    """Dynamically update agent principal limits at runtime without server restart."""
    cfg_mgr = get_agents_config_manager()

    if body.principals:
        for name, amount in body.principals.items():
            if amount <= 0:
                raise HTTPException(
                    status_code=400, detail=f"Principal for {name} must be positive, got {amount}"
                )
            cfg_mgr.update_agent_principal(agent_name=name, max_principal=amount)
            if name in agents_state["agents"]:
                agents_state["agents"][name]["max_principal"] = amount

    elif body.agent_name and body.max_principal:
        cfg_mgr.update_agent_principal(
            agent_name=body.agent_name,
            max_principal=body.max_principal,
            max_risk_pct=body.max_risk_pct_per_trade,
            max_lots=body.max_lots,
        )
        if body.agent_name in agents_state["agents"]:
            agents_state["agents"][body.agent_name]["max_principal"] = body.max_principal
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either (agent_name and max_principal) or a principals map: {'Alpha': 100000, 'Echo': 200000}",
        )

    return {
        "message": "Agent principal configuration updated successfully",
        "configurations": cfg_mgr.get_all(),
    }


@router.post("/config/reset")
def reset_agents_configuration() -> dict[str, Any]:
    """Reset all 10 agent principals to 8 @ 1 Lac (₹100,000) and 2 @ 2 Lac (₹200,000)."""
    cfg_mgr = get_agents_config_manager()
    configs = cfg_mgr.reset_to_defaults()
    for name, cfg in configs.items():
        if name in agents_state["agents"]:
            agents_state["agents"][name]["max_principal"] = cfg["max_principal"]
            agents_state["agents"][name]["guidelines"] = cfg
    return {
        "message": "Reset all 10 agent principals to defaults (8 @ 1 Lac, 2 @ 2 Lac)",
        "configurations": configs,
    }


@router.get("/upstox-trades")
def get_upstox_live_trades(
    limit: int = Query(
        50, ge=1, le=1000, description="Max trades to retrieve (up to 1,000 capacity)"
    ),
    offset: int = Query(0, ge=0),
    agent_name: str | None = Query(None, description="Filter by agent name (e.g. Alpha, Echo)"),
    symbol: str | None = Query(None, description="Filter by symbol (e.g. GOLDM)"),
    direction: str | None = Query(None, description="Filter by direction (LONG, SHORT)"),
) -> dict[str, Any]:
    """Retrieve dedicated Upstox live market trade history with complete lot details (up to 1,000 trades)."""
    ledger = get_upstox_trade_ledger()
    result = ledger.get_trades(
        limit=limit,
        offset=offset,
        agent_name=agent_name,
        symbol=symbol,
        direction=direction,
    )
    result["summary_statistics"] = ledger.get_summary_statistics()
    return result


@router.get("/upstox-trades/export")
def export_upstox_live_trades() -> Response:
    """Export the full 1,000 trades Upstox Live Market Ledger as CSV with all lot details."""
    ledger = get_upstox_trade_ledger()
    csv_data = ledger.export_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=upstox_live_market_trades_ledger_1000.csv"
        },
    )


@router.delete("/upstox-trades")
def clear_upstox_live_trades() -> dict[str, str]:
    """Reset the Upstox live trades buffer."""
    ledger = get_upstox_trade_ledger()
    ledger.clear()
    return {"message": "Upstox live trade ledger cleared"}


@router.post("/reset")
@router.post("/history/reset")
@router.delete("/history")
def reset_all_agents_history() -> dict[str, Any]:
    """Reset all 10 agents to 0 numbers, clear all positions, histories, and the Upstox ledger, starting fresh."""
    init_agents()
    ledger = get_upstox_trade_ledger()
    agents_state["upstox_ledger_summary"] = ledger.get_summary_statistics()
    return {
        "status": "success",
        "message": "All 10 agents reset to 0 numbers and started fresh with ₹0 P&L and 0 trades.",
        "total_trades": 0,
        "agents": list(agents_state.get("agents", {}).keys()),
    }


@router.post("/{agent_name}/reset")
def reset_single_agent(agent_name: str) -> dict[str, Any]:
    """Reset an individual agent's performance numbers, positions, and history to 0."""
    cfg_mgr = get_agents_config_manager()
    if agent_name not in agents_state.get("agents", {}):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    guidelines = cfg_mgr.get_guidelines(agent_name)
    principal = guidelines.max_principal
    agent = agents_state["agents"][agent_name]
    agent["history"] = []
    agent["pnl"] = 0.0
    agent["win_rate"] = 0.0
    agent["winning_tests"] = 0
    agent["total_tests"] = 0
    agent["allocated_margin"] = 0.0
    agent["current_capital"] = principal
    agent["available_capital"] = principal
    agent["initial_capital"] = principal
    agent["position"] = None
    agent["learning_progress"] = 0.0
    agent["strategy_retests"] = 0
    agent["strategy_net_pnl"] = 0.0
    agent["strategy_wins"] = 0
    agent["strategy_losses"] = 0
    agent["strategy_edge_status"] = "TESTING_CANDIDATE"
    agent["net_pnl_increment"] = 0.0
    agent["goal_progress_pct"] = 0.0
    if "price_history" in agent and hasattr(agent["price_history"], "clear"):
        agent["price_history"].clear()
    agent["blocked_trades"] = 0
    agent["abstentions"] = 0
    agent["last_signal"] = None
    agent["last_economics"] = None

    # Reset this agent's risk state so breakers do not carry over.
    get_risk_manager().reset_agent(agent_name, principal=principal)
    get_portfolio_builder().remove_exposure(agent_name)

    return {
        "status": "success",
        "message": f"Agent {agent_name} reset to 0 numbers and started fresh.",
        "agent": agent_name,
    }

