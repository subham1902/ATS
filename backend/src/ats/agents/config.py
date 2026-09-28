"""Dynamic and configurable principal, market, and execution guidelines for Agents Playground.

Supports:
- 10 Autonomous Agents with dynamic principals (8 @ ₹1 Lac, 2 @ ₹2 Lac).
- Specific Agent Guidelines: strategy selection, principal amount, lot size, direction bias, target/stop loss.
- Target Market Selection: MCX Gold Mini (100g), MCX Gold (1kg), Global Spot Gold (XAU/USD), and Auto.
- Default Mode: Fully autonomous evaluation on live market data.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ats.agents.portfolio import mandate_for

LOGGER = logging.getLogger(__name__)

# 10 Agents: 8 @ ₹1 Lac (100,000) and 2 @ ₹2 Lac (200,000)
DEFAULT_PRINCIPALS: dict[str, float] = {
    "Alpha": 100_000.0,    # ₹1 Lac - Trend & Momentum Specialist
    "Bravo": 100_000.0,    # ₹1 Lac - Mean Reversion AI
    "Charlie": 100_000.0,  # ₹1 Lac - Statistical Arbitrage & Volatility Control
    "Delta": 100_000.0,    # ₹1 Lac - Order Flow & Liquidity Hunter
    "Echo": 200_000.0,     # ₹2 Lac - Global Macro & Breakout Strategist
    "Foxtrot": 100_000.0,  # ₹1 Lac - Microstructure & Scalping Specialist
    "Golf": 100_000.0,     # ₹1 Lac - Auction Market & Opening Gap Specialist
    "Hotel": 100_000.0,    # ₹1 Lac - ML Regime Shift & Trend Filter
    "India": 100_000.0,    # ₹1 Lac - Multi-Timeframe Consolidation Breakout
    "Juliet": 200_000.0,   # ₹2 Lac - Institutional Hedging & Counter-Trend
}

CONFIG_FILE_PATH = Path("data/agents/agents_config.json")


@dataclass
class AgentGuidelinesConfig:
    name: str
    max_principal: float
    mode: str = "AUTO"  # "AUTO" (Default autonomous trading) or "CUSTOM"
    strategy_id: str = "AUTO"  # "AUTO" or specific strategy ID (e.g. "S17_OI_VOLUME_MACHINE")
    strategy_name: str = "Auto-Selected Strategy"
    target_market: str = "AUTO"  # "AUTO", "MCX_GOLDM", "MCX_GOLD", "GLOBAL_XAU"
    allowed_lot_size: float = 4.0  # Max allowed lot size ceiling. Cost amortisation needs size.
    lots: float = 0.0  # 0.0 = AUTO sizing bounded by allowed_lot_size, or fixed lot size
    direction_bias: str = "BOTH"  # "BOTH", "LONG_ONLY", "SHORT_ONLY"
    profit_target_pts: float = 0.0  # 0.0 = AUTO (ATR-derived), or custom target points
    stop_loss_pts: float = 0.0  # 0.0 = AUTO (ATR-derived), or custom stop points
    max_risk_pct_per_trade: float = 1.0  # Enforced by the RiskManager sizing path
    max_lots: int = 4
    is_active: bool = True
    goal: str = "MAX_NET_PNL_INCREMENT"
    goal_description: str = "Find winning strategies, retest in optimal conditions, and maximize net P&L increment"
    horizon: str = "TACTICAL_INTRADAY"  # "TACTICAL_INTRADAY" (intraday) or "LONG_TERM_SWING" (Echo, Juliet)
    target_net_pnl_increment: float = 25_000.0
    retest_winning_strategies: bool = True
    condition_gated_entry: bool = True

    # --- Cost-awareness (added after the 2026-09-28 profitability audit) ---
    #: Expected gross edge must be at least this multiple of round-trip charges.
    min_edge_multiple: float = 3.0
    #: Minimum signal confidence to act. Below this the agent abstains.
    min_signal_confidence: float = 0.45
    #: Bar size in seconds for this agent's decision layer.
    bar_seconds: float = 300.0
    #: ATR multiplier used to derive the stop distance.
    atr_stop_multiplier: float = 1.5
    #: Target-to-stop ratio used to derive the target distance.
    risk_reward: float = 2.0
    #: Ceiling on trades this agent may open per day.
    max_trades_per_day: int = 20
    #: Minimum signal confidence to act. Below this the agent abstains.
    min_seconds_between_entries: float = 900.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Backwards compatibility alias
AgentPrincipalConfig = AgentGuidelinesConfig


#: Fields that are always derived from the agent's mandate rather than
#: user-editable, because they define the agent's distinct role in the fleet.
MANDATE_LOCKED_FIELDS = ("bar_seconds", "risk_reward", "atr_stop_multiplier")


def build_default_config(name: str, principal: float) -> AgentGuidelinesConfig:
    """Construct the default guideline set for an agent from its mandate.

    Mandate-derived values (bar size, risk/reward, ATR stop) come from
    :mod:`ats.agents.portfolio` so the ten agents stay structurally distinct
    instead of collapsing into four duplicated archetypes.
    """
    mandate = mandate_for(name)
    is_long_term = name in ("Echo", "Juliet")
    horizon = mandate.horizon if mandate else (
        "LONG_TERM_SWING" if is_long_term else "TACTICAL_INTRADAY"
    )
    bar_seconds = mandate.bar_seconds if mandate else 300.0
    target_inc = 50_000.0 if horizon == "LONG_TERM_SWING" else 25_000.0

    # Swing mandates carry wider stops and better R:R because a swing target
    # must clear materially more transaction cost to be worth holding.
    if horizon == "LONG_TERM_SWING":
        atr_mult, rr = 2.0, 2.5
    else:
        atr_mult, rr = 1.5, 2.0

    max_lots = 6 if principal >= 200_000.0 else 4

    return AgentGuidelinesConfig(
        name=name,
        max_principal=principal,
        mode="AUTO",
        strategy_id="AUTO",
        strategy_name="Mandate-Driven (see signal family)",
        target_market="AUTO",
        allowed_lot_size=float(max_lots),
        lots=0.0,
        direction_bias="BOTH",
        profit_target_pts=0.0,
        stop_loss_pts=0.0,
        max_risk_pct_per_trade=1.0,
        max_lots=max_lots,
        is_active=True,
        goal="MAX_NET_PNL_INCREMENT",
        goal_description=(
            "Trade only when edge exceeds transaction cost by the required multiple; "
            "abstain by default; graduate strategies on validated out-of-sample evidence"
        ),
        horizon=horizon,
        target_net_pnl_increment=target_inc,
        retest_winning_strategies=True,
        condition_gated_entry=True,
        min_edge_multiple=3.0,
        min_signal_confidence=0.45,
        bar_seconds=bar_seconds,
        atr_stop_multiplier=atr_mult,
        risk_reward=rr,
        max_trades_per_day=20,
        min_seconds_between_entries=900.0,
    )


def apply_overrides(base: AgentGuidelinesConfig, item: dict[str, Any]) -> AgentGuidelinesConfig:
    """Overlay persisted values onto a mandate-derived default.

    Unknown keys are ignored and mandate-locked fields are re-asserted, so a
    stale config file cannot collapse the fleet back into duplicated agents.
    """
    cfg = replace(base)

    def _f(key: str, current: float) -> float:
        val = item.get(key)
        if val is None:
            return current
        try:
            return float(val)
        except (TypeError, ValueError):
            return current

    def _i(key: str, current: int) -> int:
        val = item.get(key)
        if val is None:
            return current
        try:
            return int(val)
        except (TypeError, ValueError):
            return current

    def _b(key: str, current: bool) -> bool:
        val = item.get(key)
        return current if val is None else bool(val)

    cfg.max_principal = _f("max_principal", cfg.max_principal)
    cfg.mode = str(item.get("mode", cfg.mode)).upper()
    cfg.strategy_id = str(item.get("strategy_id", cfg.strategy_id))
    cfg.strategy_name = str(item.get("strategy_name", cfg.strategy_name))
    cfg.target_market = str(item.get("target_market", cfg.target_market)).upper()
    cfg.allowed_lot_size = max(0.01, _f("allowed_lot_size", cfg.allowed_lot_size))
    cfg.lots = max(0.0, _f("lots", cfg.lots))
    cfg.direction_bias = str(item.get("direction_bias", cfg.direction_bias)).upper()
    cfg.profit_target_pts = max(0.0, _f("profit_target_pts", cfg.profit_target_pts))
    cfg.stop_loss_pts = max(0.0, _f("stop_loss_pts", cfg.stop_loss_pts))
    cfg.max_risk_pct_per_trade = max(0.01, _f("max_risk_pct_per_trade", cfg.max_risk_pct_per_trade))
    cfg.max_lots = max(1, _i("max_lots", cfg.max_lots))
    cfg.is_active = _b("is_active", cfg.is_active)
    cfg.goal = str(item.get("goal", cfg.goal)).upper()
    cfg.goal_description = str(item.get("goal_description", cfg.goal_description))
    cfg.horizon = str(item.get("horizon", cfg.horizon)).upper()
    cfg.target_net_pnl_increment = max(1000.0, _f("target_net_pnl_increment", cfg.target_net_pnl_increment))
    cfg.retest_winning_strategies = _b("retest_winning_strategies", cfg.retest_winning_strategies)
    cfg.condition_gated_entry = _b("condition_gated_entry", cfg.condition_gated_entry)
    cfg.min_edge_multiple = max(1.0, _f("min_edge_multiple", cfg.min_edge_multiple))
    cfg.min_signal_confidence = max(0.0, min(1.0, _f("min_signal_confidence", cfg.min_signal_confidence)))
    cfg.max_trades_per_day = max(0, _i("max_trades_per_day", cfg.max_trades_per_day))
    cfg.min_seconds_between_entries = max(0.0, _f("min_seconds_between_entries", cfg.min_seconds_between_entries))

    # Re-assert mandate-locked fields so the fleet cannot be re-duplicated by
    # a stale or hand-edited config file.
    mandate = mandate_for(cfg.name)
    if mandate is not None:
        cfg.bar_seconds = mandate.bar_seconds
        cfg.horizon = mandate.horizon
    return cfg


def replace(cfg: AgentGuidelinesConfig) -> AgentGuidelinesConfig:
    """Return a mutable copy of a guideline config."""
    return AgentGuidelinesConfig(**asdict(cfg))


class AgentsConfigManager:
    """Manages dynamic guidelines, principals, and market selection for all 10 playground agents."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or CONFIG_FILE_PATH
        self._configs: dict[str, AgentGuidelinesConfig] = {}
        self._target_market: str = "AUTO"
        self._load_configuration()

    def _load_configuration(self) -> None:
        """Load configuration with fallback priority: File -> Env Vars -> Defaults."""
        # 1. Start from mandate-derived defaults for all 10 agents
        configs: dict[str, AgentGuidelinesConfig] = {
            name: build_default_config(name, principal)
            for name, principal in DEFAULT_PRINCIPALS.items()
        }

        # 2. Overlay the persistent file, field by field, so new fields added
        #    later automatically fall back to their defaults on old config files.
        if self._config_path.exists():
            try:
                with open(self._config_path, encoding="utf-8") as f:
                    data = json.load(f)

                if "_target_market" in data:
                    self._target_market = str(data["_target_market"])

                for name, item in data.items():
                    if name.startswith("_"):
                        continue
                    if isinstance(item, dict):
                        base = configs.get(name) or build_default_config(
                            name, DEFAULT_PRINCIPALS.get(name, 100_000.0)
                        )
                        configs[name] = apply_overrides(base, item)
                    elif isinstance(item, int | float):
                        configs[name] = build_default_config(
                            name, float(item)
                        )
                LOGGER.info("Loaded %d-agent configurations from %s", len(configs), self._config_path)
            except Exception as e:
                LOGGER.warning("Could not read agent config file %s: %s", self._config_path, e)

        # 3. Check environment variable overrides
        env_json = os.environ.get("ATS_AGENT_PRINCIPALS")
        if env_json:
            try:
                env_data = json.loads(env_json)
                for name, val in env_data.items():
                    if name in configs:
                        configs[name].max_principal = float(val)
                        configs[name].max_lots = 6 if float(val) >= 200_000.0 else 4
                        configs[name].allowed_lot_size = float(configs[name].max_lots)
            except Exception as e:
                LOGGER.warning("Failed parsing ATS_AGENT_PRINCIPALS env var: %s", e)

        # Global kill switch env override, for operators who want a hard default.
        if os.environ.get("ATS_AGENTS_ARMED", "").strip().lower() in ("1", "true", "yes"):
            from ats.agents.risk import GLOBAL_KILL_SWITCH

            GLOBAL_KILL_SWITCH.release("Released via ATS_AGENTS_ARMED env var")

        for name in list(configs.keys()):
            env_key = f"ATS_PRINCIPAL_{name.upper()}"
            if env_key in os.environ:
                try:
                    val = float(os.environ[env_key])
                    configs[name].max_principal = val
                    configs[name].max_lots = 6 if val >= 200_000.0 else 4
                    configs[name].allowed_lot_size = float(configs[name].max_lots)
                except ValueError:
                    pass

        self._configs = configs
        self._ensure_saved()

    def _ensure_saved(self) -> None:
        """Persist current configuration to JSON file."""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            serializable: dict[str, Any] = {
                name: cfg.to_dict() for name, cfg in self._configs.items()
            }
            serializable["_target_market"] = self._target_market
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2)
        except Exception as e:
            LOGGER.warning("Could not save agent configuration to %s: %s", self._config_path, e)

    def get_target_market(self) -> str:
        """Return the global playground target market ('AUTO', 'MCX_GOLDM', 'MCX_GOLD', 'GLOBAL_XAU')."""
        return self._target_market

    def set_target_market(self, market: str) -> str:
        """Set the global playground target market."""
        valid_markets = {"AUTO", "MCX_GOLDM", "MCX_GOLD", "GLOBAL_XAU"}
        if market not in valid_markets:
            raise ValueError(f"Invalid market '{market}'. Must be one of {valid_markets}")
        self._target_market = market
        self._ensure_saved()
        LOGGER.info("Updated playground target market to %s", market)
        return self._target_market

    def get_all(self) -> dict[str, dict[str, Any]]:
        """Return dict of all agent configurations."""
        return {name: cfg.to_dict() for name, cfg in self._configs.items()}

    def get_principal(self, agent_name: str) -> float:
        """Get max principal for an agent in INR."""
        cfg = self._configs.get(agent_name)
        if cfg:
            return cfg.max_principal
        return DEFAULT_PRINCIPALS.get(agent_name, 100_000.0)

    def get_guidelines(self, agent_name: str) -> AgentGuidelinesConfig:
        """Get full trading guidelines for an agent."""
        if agent_name in self._configs:
            return self._configs[agent_name]
        return AgentGuidelinesConfig(
            name=agent_name,
            max_principal=DEFAULT_PRINCIPALS.get(agent_name, 100_000.0),
        )

    # Backwards compatible alias
    get_config = get_guidelines

    def update_agent_guidelines(
        self,
        agent_name: str,
        max_principal: float | None = None,
        mode: str | None = None,
        strategy_id: str | None = None,
        strategy_name: str | None = None,
        target_market: str | None = None,
        allowed_lot_size: float | None = None,
        lots: float | None = None,
        direction_bias: str | None = None,
        profit_target_pts: float | None = None,
        stop_loss_pts: float | None = None,
        max_risk_pct: float | None = None,
        max_lots: int | None = None,
        goal: str | None = None,
        horizon: str | None = None,
        target_net_pnl_increment: float | None = None,
        retest_winning_strategies: bool | None = None,
        condition_gated_entry: bool | None = None,
        min_edge_multiple: float | None = None,
        min_signal_confidence: float | None = None,
        max_trades_per_day: int | None = None,
        min_seconds_between_entries: float | None = None,
    ) -> AgentGuidelinesConfig:
        """Dynamically update an agent's complete trading guidelines."""
        if agent_name not in self._configs:
            self._configs[agent_name] = build_default_config(
                agent_name, DEFAULT_PRINCIPALS.get(agent_name, 100_000.0)
            )

        cfg = self._configs[agent_name]
        if max_principal is not None:
            if max_principal <= 0:
                raise ValueError(f"max_principal must be positive, got {max_principal}")
            cfg.max_principal = float(max_principal)
            cfg.max_lots = 6 if cfg.max_principal >= 200_000.0 else 4
            cfg.allowed_lot_size = float(cfg.max_lots)

        if mode is not None:
            cfg.mode = mode.upper()
        if strategy_id is not None:
            cfg.strategy_id = strategy_id
        if strategy_name is not None:
            cfg.strategy_name = strategy_name
        if target_market is not None:
            cfg.target_market = target_market.upper()
        if allowed_lot_size is not None:
            cfg.allowed_lot_size = max(0.01, float(allowed_lot_size))
        if lots is not None:
            cfg.lots = max(0.0, float(lots))
        if direction_bias is not None:
            cfg.direction_bias = direction_bias.upper()
        if profit_target_pts is not None:
            cfg.profit_target_pts = max(0.0, float(profit_target_pts))
        if stop_loss_pts is not None:
            cfg.stop_loss_pts = max(0.0, float(stop_loss_pts))
        if max_risk_pct is not None:
            cfg.max_risk_pct_per_trade = float(max_risk_pct)
        if max_lots is not None:
            cfg.max_lots = int(max_lots)
        if goal is not None:
            cfg.goal = goal.upper()
        if horizon is not None:
            cfg.horizon = horizon.upper()
        if target_net_pnl_increment is not None:
            cfg.target_net_pnl_increment = max(1000.0, float(target_net_pnl_increment))
        if retest_winning_strategies is not None:
            cfg.retest_winning_strategies = bool(retest_winning_strategies)
        if condition_gated_entry is not None:
            cfg.condition_gated_entry = bool(condition_gated_entry)
        if min_edge_multiple is not None:
            cfg.min_edge_multiple = max(1.0, float(min_edge_multiple))
        if min_signal_confidence is not None:
            cfg.min_signal_confidence = max(0.0, min(1.0, float(min_signal_confidence)))
        if max_trades_per_day is not None:
            cfg.max_trades_per_day = max(0, int(max_trades_per_day))
        if min_seconds_between_entries is not None:
            cfg.min_seconds_between_entries = max(0.0, float(min_seconds_between_entries))

        self._ensure_saved()
        LOGGER.info("Updated Agent %s guidelines: mode=%s, strat=%s, horizon=%s, goal=%s, princ=Rs.%s, allowed_lot=%.2f", agent_name, cfg.mode, cfg.strategy_id, cfg.horizon, cfg.goal, f"{cfg.max_principal:,.0f}", cfg.allowed_lot_size)
        return cfg

    def update_agent_principal(
        self,
        agent_name: str,
        max_principal: float,
        max_risk_pct: float | None = None,
        max_lots: int | None = None,
    ) -> AgentGuidelinesConfig:
        """Dynamically update an agent's principal configuration at runtime."""
        return self.update_agent_guidelines(
            agent_name=agent_name,
            max_principal=max_principal,
            max_risk_pct=max_risk_pct,
            max_lots=max_lots,
        )

    def update_multiple(self, updates: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Update multiple agents at once."""
        for name, val in updates.items():
            if isinstance(val, int | float):
                self.update_agent_principal(name, float(val))
            elif isinstance(val, dict):
                self.update_agent_guidelines(
                    agent_name=name,
                    max_principal=val.get("max_principal"),
                    mode=val.get("mode"),
                    strategy_id=val.get("strategy_id"),
                    strategy_name=val.get("strategy_name"),
                    target_market=val.get("target_market"),
                    allowed_lot_size=val.get("allowed_lot_size"),
                    lots=val.get("lots"),
                    direction_bias=val.get("direction_bias"),
                    profit_target_pts=val.get("profit_target_pts"),
                    stop_loss_pts=val.get("stop_loss_pts"),
                    max_risk_pct=val.get("max_risk_pct_per_trade"),
                    max_lots=val.get("max_lots"),
                    goal=val.get("goal"),
                    horizon=val.get("horizon"),
                    target_net_pnl_increment=val.get("target_net_pnl_increment"),
                    retest_winning_strategies=val.get("retest_winning_strategies"),
                    condition_gated_entry=val.get("condition_gated_entry"),
                    min_edge_multiple=val.get("min_edge_multiple"),
                    min_signal_confidence=val.get("min_signal_confidence"),
                    max_trades_per_day=val.get("max_trades_per_day"),
                    min_seconds_between_entries=val.get("min_seconds_between_entries"),
                )
        return self.get_all()

    def reset_agent_guidelines(self, agent_name: str) -> AgentGuidelinesConfig:
        """Reset a specific agent's guidelines to its mandate-derived defaults."""
        default_p = DEFAULT_PRINCIPALS.get(agent_name, 100_000.0)
        cfg = build_default_config(agent_name, default_p)
        self._configs[agent_name] = cfg
        self._ensure_saved()
        LOGGER.info("Reset Agent %s guidelines to mandate defaults (%s horizon)", agent_name, cfg.horizon)
        return cfg

    def reset_to_defaults(self) -> dict[str, dict[str, Any]]:
        """Reset all agents to mandate-derived defaults: 8 @ 1 Lac, 2 @ 2 Lac, cost-gated."""
        self._target_market = "AUTO"
        for name, principal in DEFAULT_PRINCIPALS.items():
            self._configs[name] = build_default_config(name, principal)
        self._ensure_saved()
        LOGGER.info("Reset all 10 agent configurations to mandate defaults")
        return self.get_all()


# Global Singleton Manager
_CONFIG_MANAGER: AgentsConfigManager | None = None


def get_agents_config_manager() -> AgentsConfigManager:
    global _CONFIG_MANAGER
    if _CONFIG_MANAGER is None:
        _CONFIG_MANAGER = AgentsConfigManager()
    return _CONFIG_MANAGER
