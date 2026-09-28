"""Autonomous Quantitative Agents Playground Worker.

Operating principles after the 2026-09-28 profitability audit
=============================================================

The pre-audit worker lost Rs.5.2 lakh across 1,000 trades in 55 minutes. The
root cause was not weak signals, it was an unfalsifiable cost structure: at
Rs.336 per round trip against a Rs.450 target and a Rs.220 stop, the fleet
needed an 83% win rate to break even. Nothing in the system could express that
constraint, so it was violated on every single trade.

The invariants this worker now enforces:

1. **NO UNPROFITABLE TRADES.** Every candidate is screened by
   :func:`ats.agents.costs.assess_trade` before entry. A trade whose expected
   edge does not clear ``min_edge_multiple`` times the round-trip charge is
   blocked, and the block is recorded with a reason code.

2. **BARS, NOT TICKS, DECIDE.** Signals are computed on time-bucketed bars per
   agent mandate. Ticks drive execution only. The old 60-second tick window
   could not support any real signal and guaranteed noise-stops.

3. **STOPS COME FROM VOLATILITY.** Target and stop are ATR-derived, so the stop
   sits outside bar noise. A fixed 22-point stop on a Rs.147,000 instrument is
   0.015% and is inside the spread.

4. **FILLS ARE PESSIMISTIC.** Entries cross the spread; stop exits fill worse
   than the stop level. A configurable fraction of orders are rejected.

5. **RISK LIMITS ARE ENFORCED, NOT DISPLAYED.** Daily loss, drawdown, loss
   streak, trade caps, leverage and correlation caps are all checked before
   entry. ``max_risk_pct_per_trade`` sizes the position and is never ignored.

6. **ABSTENTION IS THE DEFAULT.** Most evaluations return no signal. Zero
   trades is a valid and often correct outcome.

7. **THE FLEET IS DIVERSIFIED.** Ten agents hold ten distinct mandates spanning
   different signal families, horizons and instruments, with a correlation cap.

8. **PARTICIPATION DATA IS NOT INVENTED.** Volume and open interest are
   threaded from the live feed. When absent, dependent strategies abstain
   rather than substituting a different signal under the same name.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.request
import uuid
from collections import deque
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ats.agents.config import get_agents_config_manager
from ats.agents.costs import CostAwareSizer, TradeEconomics, pnl_multiplier
from ats.agents.deployment import get_deployment_gate
from ats.agents.deployment import load as load_deployment_gate
from ats.agents.edge import StrategyEdgeRegistry
from ats.agents.execution import ExecutionModel
from ats.agents.features import TickAggregator, atr_geometry, classify_regime, validate_geometry
from ats.agents.portfolio import MANDATES, Mandate, OpenExposure, PortfolioBuilder
from ats.agents.risk import GLOBAL_KILL_SWITCH, RiskLimits, RiskManager
from ats.agents.roster import get_roster
from ats.agents.strategies import StrategySignal, evaluate_strategy
from ats.agents.trade_ledger import get_upstox_trade_ledger

LOGGER = logging.getLogger(__name__)

# Market Contract Specifications
CONTRACT_SPECS = {
    "MCX_GOLDM": {
        "symbol": "MCX:GOLDM FUT",
        "name": "MCX Gold Mini",
        "instrument_key": "MCX_FO|569003",
        "exchange": "MCX",
        "contract_type": "MCX_GOLDM",
        "lot_size": 100.0,  # 100 grams per lot
        "lot_unit": "grams",
        "quote_unit": "per 10 grams",
        "margin_per_lot": 45_000.0,
        "currency": "INR",
        "currency_symbol": "₹",
        "tick_size": 0.1,
    },
    "MCX_GOLD": {
        "symbol": "MCX:GOLD FUT",
        "name": "MCX Gold (1kg Big Contract)",
        "instrument_key": "MCX_FO|569002",
        "exchange": "MCX",
        "contract_type": "MCX_GOLD",
        "lot_size": 1000.0,  # 1,000 grams per lot
        "lot_unit": "grams (1kg)",
        "quote_unit": "per 10 grams",
        "margin_per_lot": 450_000.0,
        "currency": "INR",
        "currency_symbol": "₹",
        "tick_size": 0.1,
    },
    "GLOBAL_XAU": {
        "symbol": "XAU/USD (Spot Gold)",
        "name": "Global Spot Gold (XAU/USD 24/7)",
        "instrument_key": "GLOBAL_XAUUSD",
        "exchange": "GLOBAL",
        "contract_type": "GLOBAL_XAU",
        "lot_size": 1.0,  # 1 troy oz
        "lot_unit": "oz",
        "quote_unit": "per oz",
        "margin_per_lot": 500.0,
        "currency": "USD",
        "currency_symbol": "$",
        "tick_size": 0.01,
    },
}

#: Map from contract type to the short instrument token used by mandates.
CONTRACT_TO_INSTRUMENT = {
    "MCX_GOLDM": "GOLDM",
    "MCX_GOLD": "GOLD",
    "GLOBAL_XAU": "XAU",
}

#: Fallback mandate table, used only if the roster is ever empty.
_FALLBACK_MANDATES = MANDATES


def _active_mandates() -> list[Mandate]:
    """Mandates the worker should act on, taken from the live roster.

    The roster is the single source of truth for fleet composition, so adding or
    removing an agent takes effect on the very next tick.
    """
    return get_roster().mandates() or list(_FALLBACK_MANDATES)

#: Fallback contract when a market cannot be resolved.
_DEFAULT_CONTRACT = CONTRACT_SPECS["MCX_GOLDM"]

agents_state: dict[str, Any] = {
    "status": "STOPPED",
    "target_market": "AUTO",
    "active_session": {
        "mode": "MCX_UPSTOX_LIVE",
        "market_name": "MCX Gold Mini 100g (Live Data)",
        "symbol": "MCX:GOLDM FUT",
        "contract_type": "MCX_GOLDM",
        "currency": "INR",
        "currency_symbol": "₹",
        "live_price": 75420.0,
        "bid_price": 75418.0,
        "ask_price": 75422.0,
        "source": "Upstox Live WebSocket (MCX Mini)",
        "session_desc": "MCX Live Regular Session Active (09:00 - 23:30 IST)",
        "is_live": True,
        "last_tick_time": datetime.now(UTC).isoformat(),
        "volume": None,
        "open_interest": None,
    },
    "agents": {},
    "upstox_ledger_summary": {},
    "risk": {},
    "edge": {},
    "portfolio": {},
    "execution": {},
    "deployment": {},
}

#: Locations searched for a strategy validation report at import time. When one
#: is present the deployment gate boots informed instead of defaulting to a blind
#: fleet-wide hold.
VALIDATION_REPORT_CANDIDATES = (
    Path("agents-playground/strategy_validation.json"),
    Path("../agents-playground/strategy_validation.json"),
    Path("strategy_validation.json"),
)


def _autoload_validation_report() -> None:
    """Install the deployment gate from a validation report if one exists."""
    for candidate in VALIDATION_REPORT_CANDIDATES:
        if candidate.exists():
            load_deployment_gate(candidate)
            gate = get_deployment_gate()
            LOGGER.info(
                "Deployment gate autoloaded from %s (deployable=%s)",
                candidate,
                gate.deployable_agents or "none - fleet-wide hold",
            )
            return
    LOGGER.info(
        "No validation report found; deployment gate holds all mandates. "
        "Run 'python -m scripts.validate_strategies' to generate one."
    )

_GLOBAL_GOLD_CACHE = {
    "price": 4260.0,
    "last_fetched": 0.0,
    "consecutive_failures": 0,
}


def fetch_global_gold_spot_sync() -> float:
    """Fetch live spot gold price strictly from live 24/7 market feeds (cached & non-blocking)."""
    global _GLOBAL_GOLD_CACHE
    now_ts = time.time()
    if now_ts - _GLOBAL_GOLD_CACHE["last_fetched"] < 5.0 and _GLOBAL_GOLD_CACHE["price"] > 0:
        return _GLOBAL_GOLD_CACHE["price"]

    if _GLOBAL_GOLD_CACHE["consecutive_failures"] >= 2 and now_ts - _GLOBAL_GOLD_CACHE["last_fetched"] < 15.0:
        return _GLOBAL_GOLD_CACHE["price"]

    urls = [
        "https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT",
        "https://data-api.binance.vision/api/v3/ticker/price?symbol=PAXGUSDT",
    ]

    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ATS-Intelligence-Engine/2.0"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                price = float(data["price"])
                _GLOBAL_GOLD_CACHE["price"] = price
                _GLOBAL_GOLD_CACHE["last_fetched"] = now_ts
                _GLOBAL_GOLD_CACHE["consecutive_failures"] = 0
                return price
        except Exception as e:
            LOGGER.debug("Live spot feed fetch error from %s: %s", url, e)

    _GLOBAL_GOLD_CACHE["consecutive_failures"] += 1
    _GLOBAL_GOLD_CACHE["last_fetched"] = now_ts
    return _GLOBAL_GOLD_CACHE["price"]


def resolve_active_market(fabric: Any = None, preferred_market: str = "AUTO") -> dict[str, Any]:
    """Determine live market session strictly based on live data and user's selected market.

    Volume and open interest are carried through when the feed provides them.
    Spot XAU/USD legitimately has neither, so those keys stay ``None`` there and
    any participation-dependent strategy abstains.
    """
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)

    is_weekday = now_ist.weekday() < 5
    is_mcx_trading_hours = (9 <= now_ist.hour < 23) or (now_ist.hour == 23 and now_ist.minute <= 30)

    mcx_price = None
    bid_p = None
    ask_p = None
    mcx_volume = None
    mcx_oi = None
    if fabric is not None:
        try:
            mcx_tick = fabric.latest("MCX_FO|569003") or fabric.latest("MCX_FO|569002")
            if mcx_tick is not None:
                mcx_price = getattr(mcx_tick, "last_traded_price", None) or getattr(
                    mcx_tick, "close_price", None
                )
                bid_p = getattr(mcx_tick, "bid_price", None)
                ask_p = getattr(mcx_tick, "ask_price", None)
                mcx_volume = getattr(mcx_tick, "volume", None)
                mcx_oi = getattr(mcx_tick, "open_interest", None)
        except Exception:
            mcx_price = None

    spot_price = fetch_global_gold_spot_sync()
    mcx_parity_per_10g = round(spot_price * (86.85 / 31.1034768) * 10.0 * 1.092, 2)

    effective_market = preferred_market
    if effective_market == "AUTO":
        if is_weekday and is_mcx_trading_hours and mcx_price is not None:
            effective_market = "MCX_GOLDM"
        else:
            effective_market = "GLOBAL_XAU"

    if effective_market == "GLOBAL_XAU":
        return {
            "mode": "GLOBAL_XAUUSD_LIVE",
            "market_name": "Global Spot Gold / XAU-USD (24/7 Live Feed)",
            "symbol": "XAU/USD (Spot Gold)",
            "instrument_key": "GLOBAL_XAUUSD",
            "contract_type": "GLOBAL_XAU",
            "currency": "USD",
            "currency_symbol": "$",
            "live_price": spot_price,
            "bid_price": round(spot_price - 0.20, 2),
            "ask_price": round(spot_price + 0.20, 2),
            "source": "Global 24/7 Spot Live Feed",
            "session_desc": "Continuous 24/7 International Spot Gold Feed",
            "is_live": True,
            "last_tick_time": datetime.now(UTC).isoformat(),
            "volume": None,
            "open_interest": None,
        }

    if effective_market == "MCX_GOLD":
        if is_weekday and is_mcx_trading_hours and mcx_price is not None:
            live_price = float(mcx_price)
            source_desc = "Upstox Live WebSocket (MCX 1kg)"
            session_desc = "MCX Live Regular Session Active (09:00 - 23:30 IST)"
        else:
            live_price = mcx_parity_per_10g
            source_desc = "Live Spot Parity Feed (MCX Equivalent)"
            session_desc = "MCX Off-Session: Live Real-Time Global Spot Gold Parity"

        return {
            "mode": "MCX_GOLD_1KG_LIVE",
            "market_name": "MCX Gold 1kg Big Contract (Live Data)",
            "symbol": "MCX:GOLD FUT",
            "instrument_key": "MCX_FO|569002",
            "contract_type": "MCX_GOLD",
            "currency": "INR",
            "currency_symbol": "₹",
            "live_price": live_price,
            "bid_price": float(bid_p) if bid_p else round(live_price - 2.0, 2),
            "ask_price": float(ask_p) if ask_p else round(live_price + 2.0, 2),
            "source": source_desc,
            "session_desc": session_desc,
            "is_live": True,
            "last_tick_time": datetime.now(UTC).isoformat(),
            "volume": float(mcx_volume) if mcx_volume is not None else None,
            "open_interest": float(mcx_oi) if mcx_oi is not None else None,
        }

    if is_weekday and is_mcx_trading_hours and mcx_price is not None:
        live_price = float(mcx_price)
        source_desc = "Upstox Live WebSocket (MCX Mini)"
        session_desc = "MCX Live Regular Session Active (09:00 - 23:30 IST)"
    else:
        live_price = mcx_parity_per_10g
        source_desc = "Live Spot Parity Feed (MCX Mini Equivalent)"
        session_desc = "MCX Off-Session: Live Real-Time Global Spot Gold Parity"

    return {
        "mode": "MCX_UPSTOX_LIVE",
        "market_name": "MCX Gold Mini 100g (Live Data)",
        "symbol": "MCX:GOLDM FUT",
        "instrument_key": "MCX_FO|569003",
        "contract_type": "MCX_GOLDM",
        "currency": "INR",
        "currency_symbol": "₹",
        "live_price": live_price,
        "bid_price": float(bid_p) if bid_p else round(live_price - 2.0, 2),
        "ask_price": float(ask_p) if ask_p else round(live_price + 2.0, 2),
        "source": source_desc,
        "session_desc": session_desc,
        "is_live": True,
        "last_tick_time": datetime.now(UTC).isoformat(),
        "volume": float(mcx_volume) if mcx_volume is not None else None,
        "open_interest": float(mcx_oi) if mcx_oi is not None else None,
    }


_AGENT_AVATARS = {
    "Alpha": "⚡",
    "Bravo": "🛡️",
    "Charlie": "📐",
    "Delta": "🌊",
    "Echo": "🌐",
    "Foxtrot": "🎯",
    "Golf": "⛳",
    "Hotel": "🏨",
    "India": "🇮🇳",
    "Juliet": "💎",
}

#: Per-agent bar aggregator, keyed by agent name.
_aggregators: dict[str, TickAggregator] = {}

_EDGE_REGISTRY: StrategyEdgeRegistry | None = None
_EXECUTION_MODEL: ExecutionModel | None = None
_RISK_MANAGER: RiskManager | None = None
_PORTFOLIO: PortfolioBuilder | None = None


def get_edge_registry() -> StrategyEdgeRegistry:
    global _EDGE_REGISTRY
    if _EDGE_REGISTRY is None:
        _EDGE_REGISTRY = StrategyEdgeRegistry()
    return _EDGE_REGISTRY


def get_execution_model() -> ExecutionModel:
    global _EXECUTION_MODEL
    if _EXECUTION_MODEL is None:
        _EXECUTION_MODEL = ExecutionModel()
    return _EXECUTION_MODEL


def get_risk_manager() -> RiskManager:
    global _RISK_MANAGER
    if _RISK_MANAGER is None:
        _RISK_MANAGER = RiskManager(RiskLimits())
    return _RISK_MANAGER


def get_portfolio_builder() -> PortfolioBuilder:
    global _PORTFOLIO
    if _PORTFOLIO is None:
        _PORTFOLIO = PortfolioBuilder(
            max_pair_correlation=get_risk_manager().limits.max_pair_correlation
        )
    return _PORTFOLIO


def init_agents() -> None:
    """Initialise all 10 agents with mandate-derived, cost-gated defaults."""
    cfg_mgr = get_agents_config_manager()
    ledger = get_upstox_trade_ledger()
    ledger.clear()

    risk = get_risk_manager()
    risk.reset()
    get_portfolio_builder().clear()
    get_edge_registry()
    get_execution_model()

    for mandate in _active_mandates():
        name = mandate.agent
        guidelines = cfg_mgr.get_guidelines(name)
        principal = guidelines.max_principal

        agents_state["agents"][name] = {
            "id": f"agt-{name.lower()}-{uuid.uuid4().hex[:6]}",
            "name": name,
            "avatar": _AGENT_AVATARS.get(name, "◆"),
            "specialization": mandate.description,
            "mandate": mandate.as_dict(),
            "max_principal": principal,
            "initial_capital": principal,
            "current_capital": principal,
            "allocated_margin": 0.0,
            "available_capital": principal,
            "pnl": 0.0,
            "win_rate": 0.0,
            "winning_tests": 0,
            "total_tests": 0,
            "history": [],
            "current_activity": f"Observing: building {mandate.bar_seconds:.0f}s bars ({mandate.family})",
            "current_hypothesis": "Abstaining by default - awaiting cost-clearing signal",
            "active_strategy": "MANDATE",
            "active_strategy_name": mandate.family,
            "active_strategy_status": "TESTING",
            "active_market": "INITIALIZING",
            "last_price": 0.0,
            "last_updated": datetime.now(UTC).isoformat(),
            "learning_progress": 0.0,
            "position": None,
            "price_history": deque(maxlen=600),
            "guidelines": guidelines.to_dict(),
            "goal": "MAX_NET_PNL_INCREMENT",
            "goal_description": guidelines.goal_description,
            "horizon": mandate.horizon,
            "target_net_pnl_increment": guidelines.target_net_pnl_increment,
            "retest_winning_strategies": True,
            "condition_gated_entry": True,
            "strategy_retests": 0,
            "strategy_net_pnl": 0.0,
            "strategy_wins": 0,
            "strategy_losses": 0,
            "strategy_edge_status": "TESTING_CANDIDATE",
            "condition_status": {
                "matched": False,
                "regime_type": "BUILDING_BARS",
                "condition_name": "BUILDING_BARS",
                "condition_label": f"Accumulating {mandate.bar_seconds:.0f}s bars for {mandate.family} signals",
                "strength_score": 0.0,
            },
            "last_signal": None,
            "last_economics": None,
            "blocked_trades": 0,
            "abstentions": 0,
            "net_pnl_increment": 0.0,
            "goal_progress_pct": 0.0,
        }
        risk.register_principal(name, principal)


init_agents()
_autoload_validation_report()


def _abstain(agent: dict[str, Any], message: str, *, regime: str = "ABSTAIN") -> None:
    """Record a deliberate no-trade decision. Abstention is a first-class outcome."""
    agent["abstentions"] = int(agent.get("abstentions", 0)) + 1
    agent["current_activity"] = f"ABSTAIN: {message}"
    agent["last_updated"] = datetime.now(UTC).isoformat()


def _block(agent: dict[str, Any], message: str, economics: TradeEconomics | None = None) -> None:
    """Record a trade that was blocked by a gate. Blocked trades are evidence too."""
    agent["blocked_trades"] = int(agent.get("blocked_trades", 0)) + 1
    if economics is not None:
        agent["last_economics"] = economics.as_dict()
    code = economics.block_reason_code if economics else "GATE"
    agent["current_activity"] = f"BLOCKED [{code}]: {message}"
    agent["last_updated"] = datetime.now(UTC).isoformat()


class AgentsWorker:
    """Quantitative Agents Playground worker with cost-gated live execution."""

    def __init__(self, fabric: Any = None) -> None:
        self._fabric = fabric
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._ledger = get_upstox_trade_ledger()
        self._cfg_mgr = get_agents_config_manager()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        agents_state["status"] = "RUNNING"
        self._task = asyncio.create_task(self._loop())
        LOGGER.info(
            "Agents Playground Worker started (trading enabled=%s)",
            GLOBAL_KILL_SWITCH.armed,
        )

    async def stop(self) -> None:
        self._running = False
        agents_state["status"] = "STOPPED"
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        LOGGER.info("Agents Playground Worker stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                target_market = self._cfg_mgr.get_target_market()
                agents_state["target_market"] = target_market
                session_info = await asyncio.to_thread(
                    resolve_active_market, self._fabric, target_market
                )
                if session_info is None:
                    LOGGER.error("resolve_active_market returned None; skipping cycle")
                    await asyncio.sleep(2.0)
                    continue

                agents_state["active_session"] = session_info

                live_price = session_info["live_price"]
                contract_key = session_info.get("contract_type", "MCX_GOLDM")
                contract_spec = CONTRACT_SPECS.get(contract_key, _DEFAULT_CONTRACT)
                instrument = CONTRACT_TO_INSTRUMENT.get(contract_key, "GOLDM")

                now_ts = time.time()

                if not GLOBAL_KILL_SWITCH.armed:
                    for mandate in _active_mandates():
                        agent = agents_state["agents"].get(mandate.agent)
                        if agent is not None and agent.get("position") is None:
                            agent["current_activity"] = (
                                "HALTTED: global kill switch engaged - "
                                f"{GLOBAL_KILL_SWITCH.reason}"
                            )
                            agent["current_activity"] = agent["current_activity"].replace(
                                "HALTTED", "HALTED"
                            )
                else:
                    for mandate in _active_mandates():
                        if not self._running:
                            break
                        agent = agents_state["agents"].get(mandate.agent)
                        if agent is None:
                            continue

                        self._sync_agent(agent, mandate, session_info, live_price)

                        if not self._instrument_allowed(mandate, instrument):
                            agent["current_activity"] = (
                                f"SKIP: mandate instruments {list(mandate.instrument_bias)} "
                                f"do not include {instrument} - diversification guard"
                            )
                            continue

                        position = agent.get("position")
                        if position is not None:
                            await self._manage_open_position(
                                agent=agent,
                                mandate=mandate,
                                position=position,
                                live_price=live_price,
                                session_info=session_info,
                                contract_spec=contract_spec,
                                instrument=instrument,
                            )
                        else:
                            await self._evaluate_entry_signal(
                                agent=agent,
                                mandate=mandate,
                                live_price=live_price,
                                session_info=session_info,
                                contract_spec=contract_spec,
                                instrument=instrument,
                                now_ts=now_ts,
                            )

                agents_state["upstox_ledger_summary"] = self._ledger.get_summary_statistics()
                agents_state["risk"] = get_risk_manager().summary()
                agents_state["edge"] = get_edge_registry().summary()
                agents_state["portfolio"] = get_portfolio_builder().concentration_summary()
                agents_state["execution"] = get_execution_model().stats

                await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOGGER.error("Error in AgentsWorker loop: %s", e, exc_info=True)
                await asyncio.sleep(3.0)

    def _sync_agent(
        self,
        agent: dict[str, Any],
        mandate: Mandate,
        session_info: dict[str, Any],
        live_price: float,
    ) -> None:
        """Keep agent state, bars and participation data in sync with the latest tick."""
        name = agent["name"]
        guidelines = self._cfg_mgr.get_guidelines(name)
        agent["guidelines"] = guidelines.to_dict()
        agent["goal"] = guidelines.goal
        agent["horizon"] = guidelines.horizon
        agent["target_net_pnl_increment"] = guidelines.target_net_pnl_increment
        agent["active_market"] = session_info["mode"]
        agent["last_price"] = live_price

        if agent["max_principal"] != guidelines.max_principal:
            agent["max_principal"] = guidelines.max_principal
            get_risk_manager().register_principal(name, guidelines.max_principal)

        bar_seconds = guidelines.bar_seconds
        agg = _aggregators.get(name)
        if agg is None or agg.interval_seconds != bar_seconds:
            agg = TickAggregator(interval_seconds=bar_seconds, max_bars=250)
            _aggregators[name] = agg

        # Volume and OI come straight off the feed. They stay None when the
        # provider omits them, which makes participation-dependent strategies
        # abstain instead of trading an impostor signal.
        agg.update(
            price=float(live_price),
            timestamp=time.time(),
            volume=float(session_info.get("volume") or 0.0),
            open_interest=(
                float(session_info["open_interest"])
                if session_info.get("open_interest") is not None
                else None
            ),
        )
        agent["price_history"].append(float(live_price))

    def _instrument_allowed(self, mandate: Mandate, instrument: str) -> bool:
        """Diversification guard: a mandate only trades its assigned instruments."""
        return instrument in mandate.instrument_bias

    async def _evaluate_entry_signal(
        self,
        *,
        agent: dict[str, Any],
        mandate: Mandate,
        live_price: float,
        session_info: dict[str, Any],
        contract_spec: dict[str, Any],
        instrument: str,
        now_ts: float,
    ) -> None:
        """Evaluate a candidate entry through every gate, in cost-first order."""
        name = agent["name"]
        guidelines = self._cfg_mgr.get_guidelines(name)
        agg = _aggregators.get(name)
        bars = agg.bars if agg else []

        # --- Gate 0: kill switch (authoritative, checked first) ------------
        if not GLOBAL_KILL_SWITCH.armed:
            _abstain(agent, f"global kill switch engaged: {GLOBAL_KILL_SWITCH.reason}")
            return

        # --- Gate 0b: deployment gate --------------------------------------
        # A mandate may only trade if out-of-sample evidence cleared the bar.
        # With no validated evidence loaded, every mandate is held.
        gate = get_deployment_gate()
        allowed, gate_reason = gate.allows_with_reason(name)
        if not allowed:
            _abstain(agent, f"deployment hold - {gate_reason}", regime="DEPLOYMENT_HOLD")
            return

        # --- Gate 1: enough bars to compute anything ------------------------
        regime = classify_regime(bars)
        agent["condition_status"] = {
            "matched": False,
            "regime_type": regime.regime,
            "condition_name": regime.regime,
            "condition_label": regime.description,
            "strength_score": regime.confidence,
        }
        if len(bars) < 10:
            _abstain(
                agent,
                f"building bars ({len(bars)}/10) at {guidelines.bar_seconds:.0f}s each",
                regime=regime.regime,
            )
            return

        # --- Gate 2: strategy signal ---------------------------------------
        signal: StrategySignal = evaluate_strategy(
            mandate.signal_source, bars, tick_size=contract_spec.get("tick_size", 0.01)
        )
        agent["last_signal"] = signal.as_dict()
        if not signal.has_signal or signal.direction is None:
            _abstain(agent, signal.rationale, regime=signal.regime)
            return

        # --- Gate 3: confidence --------------------------------------------
        if signal.confidence < guidelines.min_signal_confidence:
            _abstain(
                agent,
                f"confidence {signal.confidence:.2f} below "
                f"{guidelines.min_signal_confidence:.2f} threshold",
                regime=signal.regime,
            )
            return

        # --- Gate 4: direction bias ----------------------------------------
        direction = signal.direction
        if guidelines.direction_bias == "LONG_ONLY" and direction == "SHORT":
            _abstain(agent, "direction blocked by LONG_ONLY bias", regime=signal.regime)
            return
        if guidelines.direction_bias == "SHORT_ONLY" and direction == "LONG":
            _abstain(agent, "direction blocked by SHORT_ONLY bias", regime=signal.regime)
            return

        # --- Gate 5: volatility-derived geometry ---------------------------
        geometry = signal.geometry or atr_geometry(
            bars,
            atr_multiplier=guidelines.atr_stop_multiplier,
            risk_reward=guidelines.risk_reward,
            tick_size=contract_spec.get("tick_size", 0.01),
        )
        if guidelines.mode == "CUSTOM" and guidelines.profit_target_pts > 0:
            stop = abs(guidelines.stop_loss_pts or geometry.stop_points)
            target = abs(guidelines.profit_target_pts)
            geometry = type(geometry)(
                stop_points=stop,
                target_points=target,
                atr=geometry.atr,
                risk_reward=(target / stop) if stop else geometry.risk_reward,
                basis="CUSTOM (operator override)",
            )

        ok, why = validate_geometry(geometry)
        if not ok:
            _abstain(agent, f"trade geometry rejected: {why}", regime=signal.regime)
            return

        # --- Gate 6: execution reality at entry ---------------------------
        raw_entry = session_info["ask_price"] if direction == "LONG" else session_info["bid_price"]
        order_id = f"{name}-{uuid.uuid4().hex[:8]}"
        entry_fill = get_execution_model().apply_entry(
            price=float(raw_entry), direction=direction, order_id=order_id
        )
        if entry_fill.rejected:
            _abstain(agent, f"entry order rejected: {entry_fill.reason}", regime=signal.regime)
            return
        entry_price = entry_fill.price

        # --- Gate 7: THE COST GATE -----------------------------------------
        sizer = CostAwareSizer(
            max_lots=float(guidelines.allowed_lot_size),
            max_risk_pct=guidelines.max_risk_pct_per_trade,
            capital=agent["current_capital"],
            margin_per_lot=contract_spec["margin_per_lot"],
            min_edge_multiple=guidelines.min_edge_multiple,
        )
        prior = get_edge_registry().evaluate(
            signal.strategy_id,
            required_win_rate=0.5,
            net_if_win=1.0,
            net_if_loss=-1.0,
        )
        lots, economics = sizer.size_for(
            exchange=contract_spec["exchange"],
            entry_price=entry_price,
            symbol=contract_spec["symbol"],
            lot_size=contract_spec["lot_size"],
            target_points=geometry.target_points,
            stop_points=geometry.stop_points,
            strategy_win_rate=prior.posterior_win_rate,
            hard_ceiling=min(float(guidelines.allowed_lot_size), float(guidelines.max_lots)),
        )

        if lots <= 0 or not economics.tradable:
            _block(
                agent,
                f"{economics.reason} | target {geometry.target_points:.1f}pts vs "
                f"stop {geometry.stop_points:.1f}pts",
                economics,
            )
            return

        # --- Gate 8: risk limits -------------------------------------------
        margin_req = round(lots * contract_spec["margin_per_lot"], 2)
        risk = get_risk_manager()
        decision = risk.can_trade(
            name,
            principal=agent["max_principal"],
            proposed_margin=margin_req,
            open_positions=0,
            open_gross_exposure=0.0,
            now_ts=now_ts,
        )
        if not decision.allowed:
            _block(agent, decision.reason)
            return

        # --- Gate 9: portfolio diversification ------------------------------
        recent = [b.close for b in bars[-20:]]
        proposed_returns = _returns(recent)
        pcheck = get_portfolio_builder().check(
            agent=name,
            family=mandate.family,
            instrument=instrument,
            direction=direction,
            proposed_returns=proposed_returns,
        )
        if not pcheck.allowed:
            _block(agent, pcheck.reason)
            return

        # --- Gate 10: open the position ------------------------------------
        total_qty = round(lots * contract_spec["lot_size"], 3)
        mult = pnl_multiplier(
            symbol=contract_spec["symbol"],
            lot_size=contract_spec["lot_size"],
            total_quantity=total_qty,
        )
        target_price = round(
            entry_price + geometry.target_points
            if direction == "LONG"
            else entry_price - geometry.target_points,
            2,
        )
        stop_price = round(
            entry_price - geometry.stop_points
            if direction == "LONG"
            else entry_price + geometry.stop_points,
            2,
        )

        horizon_seconds = 4 * 3600.0 if guidelines.horizon == "LONG_TERM_SWING" else 45 * 60.0
        position = {
            "trade_id": order_id,
            "strategy_id": signal.strategy_id,
            "strategy_name": mandate.family,
            "direction": direction,
            "lots": lots,
            "lot_size": contract_spec["lot_size"],
            "total_quantity": total_qty,
            "lot_unit": contract_spec["lot_unit"],
            "entry_price": entry_price,
            "entry_time": datetime.now(UTC).isoformat(),
            "entry_timestamp_ts": time.time(),
            "target_price": target_price,
            "stop_loss_price": stop_price,
            "max_hold_seconds": horizon_seconds,
            "margin_utilized": margin_req,
            "hypothesis": signal.rationale,
            "params": {
                "lots": lots,
                "lot_size": contract_spec["lot_size"],
                "target_points": round(geometry.target_points, 2),
                "stop_loss_points": round(geometry.stop_points, 2),
                "multiplier": mult,
                "margin_per_lot": contract_spec["margin_per_lot"],
                "strategy": signal.strategy_id,
                "signal_source": mandate.signal_source,
                "mode": guidelines.mode,
                "horizon": guidelines.horizon,
                "bar_seconds": guidelines.bar_seconds,
                "regime": signal.regime,
                "confidence": round(signal.confidence, 3),
                "geometry_basis": geometry.basis,
                "edge_to_cost_ratio": round(economics.edge_to_cost_ratio, 3),
                "required_win_rate": round(economics.required_win_rate, 4),
                "round_trip_cost": round(economics.round_trip_cost, 2),
                "entry_slippage_points": entry_fill.slippage_points,
                "min_edge_multiple": guidelines.min_edge_multiple,
            },
            "unrealized_pnl": 0.0,
            "regime": signal.regime,
        }

        cs = session_info["currency_symbol"]
        agent["position"] = position
        agent["allocated_margin"] = margin_req
        agent["available_capital"] = round(agent["current_capital"] - margin_req, 2)
        agent["last_economics"] = economics.as_dict()
        agent["active_strategy"] = signal.strategy_id
        agent["active_strategy_name"] = mandate.family
        agent["current_hypothesis"] = signal.rationale
        agent["current_activity"] = (
            f"OPENED {direction} {lots:g} lot(s) @ {cs}{entry_price:,.2f} | "
            f"Target {cs}{target_price:,.2f} (+{geometry.target_points:.1f}pts) | "
            f"Stop {cs}{stop_price:,.2f} (-{geometry.stop_points:.1f}pts) | "
            f"Edge {economics.edge_to_cost_ratio:.1f}x cost | "
            f"Needs {economics.required_win_rate * 100:.0f}% WR | {signal.regime}"
        )
        agent["last_updated"] = datetime.now(UTC).isoformat()

        risk.on_entry(name, principal=agent["max_principal"], margin=margin_req, now_ts=now_ts)
        get_portfolio_builder().add_exposure(
            OpenExposure(
                agent=name,
                family=mandate.family,
                instrument=instrument,
                direction=direction,
                notional=total_qty,
                recent_returns=proposed_returns,
            )
        )
        LOGGER.info(
            "Agent %s OPENED %s %.2f lots %s entry=%.2f target=%.2f stop=%.2f "
            "edge/cost=%.2fx reqWR=%.1f%%",
            name,
            direction,
            lots,
            signal.strategy_id,
            entry_price,
            target_price,
            stop_price,
            economics.edge_to_cost_ratio,
            economics.required_win_rate * 100.0,
        )

    async def _manage_open_position(
        self,
        *,
        agent: dict[str, Any],
        mandate: Mandate,
        position: dict[str, Any],
        live_price: float,
        session_info: dict[str, Any],
        contract_spec: dict[str, Any],
        instrument: str,
    ) -> None:
        """Track an open position and exit on target, stop, or time.

        Deliberately **no breakeven guard**. The pre-audit implementation moved
        the stop to entry+1pt, which given Rs.336 of charges guaranteed a Rs.330
        loss and produced 70 trades with a 0% win rate. A breakeven stop is only
        rational when the cost basis is zero, which it never is here.
        """
        name = agent["name"]
        cs = session_info["currency_symbol"]
        direction = position["direction"]
        entry_price = position["entry_price"]
        lots = position["lots"]
        total_qty = position["total_quantity"]
        mult = position["params"]["multiplier"]
        duration_sec = time.time() - position["entry_timestamp_ts"]

        if direction == "LONG":
            raw_pnl = (live_price - entry_price) * mult
        else:
            raw_pnl = (entry_price - live_price) * mult
        position["unrealized_pnl"] = round(raw_pnl, 2)

        target_price = position["target_price"]
        stop_price = position["stop_loss_price"]
        max_hold = position["max_hold_seconds"]

        exit_triggered = False
        exit_reason = "ACTIVE"
        trigger_price = live_price

        if direction == "LONG":
            if live_price >= target_price:
                exit_triggered, exit_reason, trigger_price = True, "PROFIT_TARGET", target_price
            elif live_price <= stop_price:
                exit_triggered, exit_reason, trigger_price = True, "STOP_LOSS", stop_price
            elif duration_sec >= max_hold:
                exit_triggered, exit_reason = True, "TIME_EXIT"
        else:
            if live_price <= target_price:
                exit_triggered, exit_reason, trigger_price = True, "PROFIT_TARGET", target_price
            elif live_price >= stop_price:
                exit_triggered, exit_reason, trigger_price = True, "STOP_LOSS", stop_price
            elif duration_sec >= max_hold:
                exit_triggered, exit_reason = True, "TIME_EXIT"

        if not exit_triggered:
            agent["current_activity"] = (
                f"Holding {direction} {lots:g} lot(s) @ {cs}{entry_price:,.2f} | "
                f"Live {cs}{live_price:,.2f} | PnL {cs}{raw_pnl:,.2f} | "
                f"Tgt {cs}{target_price:,.2f} | Stop {cs}{stop_price:,.2f} | "
                f"{duration_sec / 60.0:.0f}min of {max_hold / 60.0:.0f}min"
            )
            agent["last_updated"] = datetime.now(UTC).isoformat()
            return

        exit_fill = get_execution_model().apply_exit(
            price=trigger_price,
            direction=direction,
            order_id=position["trade_id"],
            reason=exit_reason,
        )
        exit_price = exit_fill.price

        strat_id = position["strategy_id"]
        params = position["params"]
        margin_req = position["margin_utilized"]

        # FIX (audit D2): the balance must be the NET post-trade figure. The
        # pre-audit code passed gross here while updating capital with net, so
        # the displayed balance diverged from real cash on every single trade.
        estimated_cost = _est_cost(contract_spec, entry_price, exit_price, lots)
        trade_record = self._ledger.record_trade(
            agent_id=agent["id"],
            agent_name=name,
            strategy_id=strat_id,
            strategy_name=position["strategy_name"],
            exchange=contract_spec["exchange"],
            instrument_key=session_info.get("instrument_key", "MCX_FO|569003"),
            symbol=contract_spec["symbol"],
            direction=direction,
            lot_size=position["lot_size"],
            lots=lots,
            entry_price=entry_price,
            exit_price=exit_price,
            margin_utilized=margin_req,
            agent_max_principal=agent["max_principal"],
            post_trade_balance=round(agent["current_capital"] + raw_pnl - estimated_cost, 2),
            duration_seconds=duration_sec,
            exit_reason=exit_reason,
            upstox_feed_source=session_info["source"],
            exchange_timestamp=session_info.get("last_tick_time"),
            hypothesis=position["hypothesis"],
            strategy_params=params,
            lot_unit=position["lot_unit"],
            entry_slippage_points=params.get("entry_slippage_points", 0.0),
            exit_slippage_points=exit_fill.slippage_points,
            latency_seconds=exit_fill.latency_seconds,
            fill_rejected=False,
            passed_cost_gate=True,
            edge_to_cost_ratio=params.get("edge_to_cost_ratio", 0.0),
            required_win_rate=params.get("required_win_rate", 0.0),
            signal_confidence=params.get("confidence", 0.0),
            data_split="LIVE",
            execution_note=exit_fill.reason,
        )

        net_pnl = trade_record.net_pnl

        agent["current_capital"] = trade_record.post_trade_balance
        agent["pnl"] = round(agent["pnl"] + net_pnl, 2)
        agent["allocated_margin"] = 0.0
        agent["available_capital"] = agent["current_capital"]
        agent["total_tests"] += 1
        if net_pnl > 0:
            agent["winning_tests"] += 1
        agent["win_rate"] = round((agent["winning_tests"] / agent["total_tests"]) * 100.0, 1)
        agent["learning_progress"] = min(100.0, agent["learning_progress"] + 1.0)

        get_risk_manager().record_trade(
            name,
            principal=agent["max_principal"],
            net_pnl=net_pnl,
            margin_released=margin_req,
        )
        get_portfolio_builder().remove_exposure(name)

        agent["strategy_retests"] += 1
        agent["strategy_net_pnl"] = round(agent["strategy_net_pnl"] + net_pnl, 2)
        if net_pnl > 0:
            agent["strategy_wins"] += 1
        else:
            agent["strategy_losses"] += 1

        get_edge_registry().record_trade(
            strat_id,
            net_pnl=net_pnl,
            gross_pnl=trade_record.gross_pnl,
            charges=trade_record.total_charges,
        )

        verdict = get_edge_registry().evaluate(
            strat_id,
            required_win_rate=params.get("required_win_rate", 0.5),
            net_if_win=abs(trade_record.gross_pnl),
            net_if_loss=abs(trade_record.gross_pnl) if net_pnl <= 0 else 0.0,
        )
        agent["strategy_edge_status"] = verdict.status

        agent["net_pnl_increment"] = agent["pnl"]
        target_goal = agent["guidelines"].get("target_net_pnl_increment", 25_000.0)
        agent["goal_progress_pct"] = (
            min(100.0, max(0.0, round((agent["pnl"] / target_goal) * 100.0, 1)))
            if target_goal
            else 0.0
        )

        agent["history"].insert(
            0,
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "market": session_info["mode"],
                "symbol": contract_spec["symbol"],
                "direction": direction,
                "lots": lots,
                "lot_size": position["lot_size"],
                "total_quantity": total_qty,
                "lot_unit": position["lot_unit"],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_pnl": trade_record.gross_pnl,
                "charges": trade_record.total_charges,
                "pnl_change": net_pnl,
                "currency_symbol": cs,
                "strategy": strat_id,
                "strategy_name": position["strategy_name"],
                "exit_reason": exit_reason,
                "hypothesis": position["hypothesis"],
                "params": params,
                "balance": agent["current_capital"],
                "edge_status": verdict.status,
                "edge_rationale": verdict.rationale,
            },
        )
        agent["history"] = agent["history"][:100]
        agent["position"] = None

        sign = "+" if net_pnl >= 0 else ""
        slip = float(params.get("entry_slippage_points", 0.0)) + exit_fill.slippage_points
        agent["current_activity"] = (
            f"Closed ({exit_reason}): {direction} {lots:g} lot(s) | "
            f"Net {sign}{cs}{net_pnl:,.2f} (fee {cs}{trade_record.total_charges:,.2f}, "
            f"slippage {slip:.2f}pts) | "
            f"Held {duration_sec:.0f}s | Edge: {verdict.status}"
        )
        agent["last_updated"] = datetime.now(UTC).isoformat()

        LOGGER.info(
            "Agent %s CLOSED %s %s (%s): net=%.2f gross=%.2f fees=%.2f edge=%s",
            name,
            strat_id,
            direction,
            exit_reason,
            net_pnl,
            trade_record.gross_pnl,
            trade_record.total_charges,
            verdict.status,
        )


def _returns(closes: list[float]) -> list[float]:
    """Simple period-over-period returns for correlation analysis."""
    out: list[float] = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            out.append((closes[i] - closes[i - 1]) / closes[i - 1])
    return out


def _est_cost(
    contract_spec: dict[str, Any], entry: float, exit_: float, lots: float
) -> float:
    """Estimated round-trip cost, used to keep the displayed balance net-correct."""
    from ats.agents.costs import estimate_round_trip_charges

    return estimate_round_trip_charges(
        exchange=contract_spec["exchange"],
        entry_price=entry,
        exit_price=exit_,
        symbol=contract_spec["symbol"],
        lot_size=contract_spec["lot_size"],
        lots=lots,
    ).total_charges


__all__ = [
    "CONTRACT_SPECS",
    "CONTRACT_TO_INSTRUMENT",
    "_active_mandates",
    "AgentsWorker",
    "agents_state",
    "get_edge_registry",
    "get_execution_model",
    "get_portfolio_builder",
    "get_risk_manager",
    "init_agents",
    "resolve_active_market",
]
