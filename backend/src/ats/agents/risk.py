"""Risk management: circuit breakers, position sizing, and exposure limits.

Nothing in the pre-audit system could stop a loss. There was no daily loss
limit, no drawdown halt, no consecutive-loss breaker, and no global kill switch.
``max_risk_pct_per_trade`` was configurable through the API and UI but never
read by the sizing path - a control that existed only in the UI.

This module makes risk controls authoritative. The worker's entry path must
consult :class:`RiskManager` and may not open a position it rejects.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ats.agents.costs import BlockReason

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class RiskLimits:
    """Hard risk limits. These are enforced, not advisory."""

    #: Stop trading for the whole portfolio beyond this loss vs peak equity.
    max_portfolio_drawdown_pct: float = 15.0
    #: Halt an individual agent for the day beyond this loss vs its start capital.
    max_daily_loss_pct: float = 5.0
    #: Halt an agent after this many consecutive losing trades.
    max_consecutive_losses: int = 5
    #: Ceiling on an agent's realised loss vs its principal, all-time.
    max_total_loss_pct: float = 40.0
    #: Ceiling on trades an agent may open per session day.
    max_trades_per_day: int = 20
    #: Ceiling on lots an agent may hold concurrently.
    max_concurrent_positions: int = 2
    #: Ceiling on total margin deployed as a fraction of principal.
    max_margin_utilisation_pct: float = 60.0
    #: Ceiling on notional exposure as a multiple of principal.
    max_gross_leverage: float = 4.0
    #: Ceiling on pairwise correlation between simultaneously-open agent trades.
    max_pair_correlation: float = 0.60
    #: Portfolio-level daily loss halt, in percent of aggregate principal.
    portfolio_daily_loss_pct: float = 6.0
    #: Minimum seconds between two entries by the same agent.
    min_seconds_between_entries: float = 900.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_portfolio_drawdown_pct": self.max_portfolio_drawdown_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_consecutive_losses": self.max_consecutive_losses,
            "max_total_loss_pct": self.max_total_loss_pct,
            "max_trades_per_day": self.max_trades_per_day,
            "max_concurrent_positions": self.max_concurrent_positions,
            "max_margin_utilisation_pct": self.max_margin_utilisation_pct,
            "max_gross_leverage": self.max_gross_leverage,
            "max_pair_correlation": self.max_pair_correlation,
            "portfolio_daily_loss_pct": self.portfolio_daily_loss_pct,
            "min_seconds_between_entries": self.min_seconds_between_entries,
        }


@dataclass
class RiskState:
    """Mutable per-session risk bookkeeping."""

    initial_capital: float
    current_capital: float
    peak_equity: float = 0.0
    daily_start_capital: float = 0.0
    consecutive_losses: int = 0
    trades_today: int = 0
    day_key: str = ""
    halted: bool = False
    halt_reason: str = ""
    halted_at: str | None = None
    realized_pnl_today: float = 0.0
    gross_exposure: float = 0.0
    recent_pnl: deque[float] = field(default_factory=lambda: deque(maxlen=50), repr=False)
    last_entry_ts: float = 0.0
    blocked_reasons: dict[str, int] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.peak_equity <= 0:
            self.peak_equity = self.initial_capital
        if self.daily_start_capital <= 0:
            self.daily_start_capital = self.initial_capital


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Verdict from a risk evaluation."""

    allowed: bool
    reason: str
    reason_code: str = ""
    drawdown_pct: float = 0.0
    daily_pnl_pct: float = 0.0
    consecutive_losses: int = 0
    trades_today: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "reason_code": self.reason_code,
            "drawdown_pct": round(self.drawdown_pct, 2),
            "daily_pnl_pct": round(self.daily_pnl_pct, 2),
            "consecutive_losses": self.consecutive_losses,
            "trades_today": self.trades_today,
        }


class KillSwitch:
    """Global, operator-controlled trading permission across the whole playground.

    ``armed=True`` means **trading is permitted**. The default is
    ``armed=False`` - the system refuses to open positions until an operator
    explicitly releases it. Enabling a system that structurally loses money
    must be a deliberate act, not a startup default.

    This is Tier 0.1 from the audit: stop the bleeding first, then reason about
    signal quality.
    """

    def __init__(self, *, armed: bool = False, reason: str | None = None) -> None:
        self._armed = bool(armed)
        self._reason = (
            reason
            if reason is not None
            else (
                ""
                if armed
                else "DEFAULT SAFE STATE: trading is disabled. Release the kill "
                "switch via POST /v1/agents/risk/kill-switch/release or set "
                "ATS_AGENTS_ARMED=1 once cost gates are understood."
            )
        )
        self._changed_at = datetime.now(UTC).isoformat()

    @property
    def armed(self) -> bool:
        """True when trading is permitted."""
        return self._armed

    @property
    def trading_enabled(self) -> bool:
        """Clear alias for readability at call sites."""
        return self._armed

    @property
    def reason(self) -> str:
        return self._reason

    def engage(self, reason: str) -> dict[str, Any]:
        """Disarm trading (the switch is 'engaged' = halted)."""
        self._armed = False
        self._reason = reason
        self._changed_at = datetime.now(UTC).isoformat()
        return self.as_dict()

    def release(self, reason: str) -> dict[str, Any]:
        """Permit trading."""
        self._armed = True
        self._reason = reason
        self._changed_at = datetime.now(UTC).isoformat()
        return self.as_dict()

    def as_dict(self) -> dict[str, Any]:
        return {
            "armed": self._armed,
            "trading_enabled": self._armed,
            "reason": self._reason,
            "changed_at": self._changed_at,
        }


#: Process-wide kill switch. Trading is DISABLED by default.
GLOBAL_KILL_SWITCH = KillSwitch(armed=False)


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------


def correlation(a: list[float], b: list[float]) -> float:
    """Pearson correlation of two return series, tolerant of short/flat inputs."""
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    xs = list(a[-n:])
    ys = list(b[-n:])
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 1e-18 or vy <= 1e-18:
        return 0.0
    rho: float = cov / ((vx**0.5) * (vy**0.5))
    return max(-1.0, min(1.0, rho))


# ---------------------------------------------------------------------------
# Risk manager
# ---------------------------------------------------------------------------


class RiskManager:
    """Central authority for whether an agent may trade, and how much.

    The worker must call :meth:`can_trade` before every entry and honour the
    verdict. :meth:`record_trade` keeps the state honest after every close.
    """

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self._limits = limits or RiskLimits()
        self._states: dict[str, RiskState] = {}
        self._portfolio_day_key = ""
        self._portfolio_day_start = 0.0
        self._portfolio_peak = 0.0
        self._portfolio_halt_reason = ""
        self._blocked_signals: list[dict[str, Any]] = []
        self._max_blocked_records = 500

    @property
    def limits(self) -> RiskLimits:
        return self._limits

    # -- state ------------------------------------------------------------

    def state_for(self, agent_name: str, *, principal: float) -> RiskState:
        st = self._states.get(agent_name)
        if st is None:
            st = RiskState(initial_capital=principal, current_capital=principal)
            self._states[agent_name] = st
        return st

    def register_principal(self, agent_name: str, principal: float) -> None:
        st = self.state_for(agent_name, principal=principal)
        st.initial_capital = principal
        if st.peak_equity <= 0 or st.peak_equity < principal:
            st.peak_equity = principal
        if st.daily_start_capital <= 0:
            st.daily_start_capital = principal

    def reset(self) -> None:
        self._states.clear()
        self._portfolio_day_key = ""
        self._portfolio_day_start = 0.0
        self._portfolio_peak = 0.0
        self._portfolio_halt_reason = ""
        self._blocked_signals.clear()

    def reset_agent(self, agent_name: str, *, principal: float) -> None:
        """Reset one agent's risk state, keeping the rest of the fleet intact."""
        self._states.pop(agent_name, None)
        self.register_principal(agent_name, principal)

    def _today(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def _roll_day_if_needed(self, st: RiskState) -> None:
        key = self._today()
        if st.day_key != key:
            st.day_key = key
            st.daily_start_capital = st.current_capital
            st.realized_pnl_today = 0.0
            st.trades_today = 0
            # A day boundary clears a *daily* halt, but never a structural halt.
            if st.halt_reason.startswith("DAILY_LOSS"):
                st.halted = False
                st.halt_reason = ""

    # -- evaluation -------------------------------------------------------

    def can_trade(
        self,
        agent_name: str,
        *,
        principal: float,
        proposed_margin: float = 0.0,
        open_positions: int = 0,
        open_gross_exposure: float = 0.0,
        now_ts: float | None = None,
    ) -> RiskDecision:
        """Evaluate every risk limit for a proposed entry."""
        if not GLOBAL_KILL_SWITCH.armed:
            return self._deny(
                agent_name,
                f"Global kill switch engaged: {GLOBAL_KILL_SWITCH.reason}",
                BlockReason.GLOBAL_KILL,
            )

        st = self.state_for(agent_name, principal=principal)
        self._roll_day_if_needed(st)

        ts = now_ts if now_ts is not None else time.time()
        elapsed = ts - st.last_entry_ts
        if st.last_entry_ts and elapsed < self._limits.min_seconds_between_entries:
            wait = self._limits.min_seconds_between_entries - elapsed
            return self._deny(
                agent_name,
                f"Cooldown: {wait:.0f}s remaining before this agent may trade again",
                BlockReason.FREQUENCY_CAP,
            )

        if st.halted:
            return self._deny(
                agent_name,
                f"Agent halted: {st.halt_reason}",
                BlockReason.DRAWDOWN_HALT if "HALT" in st.halt_reason else BlockReason.CIRCUIT_BREAKER,
            )

        if open_positions >= self._limits.max_concurrent_positions:
            return self._deny(
                agent_name,
                f"Concurrent position limit ({self._limits.max_concurrent_positions}) reached",
                BlockReason.CIRCUIT_BREAKER,
            )

        if st.trades_today >= self._limits.max_trades_per_day:
            return self._deny(
                agent_name,
                f"Daily trade cap ({self._limits.max_trades_per_day}) reached",
                BlockReason.FREQUENCY_CAP,
            )

        if st.consecutive_losses >= self._limits.max_consecutive_losses:
            return self._deny(
                agent_name,
                f"{st.consecutive_losses} consecutive losses - agent paused for the day",
                BlockReason.CIRCUIT_BREAKER,
            )

        drawdown_pct = self._drawdown_pct(st)
        if drawdown_pct >= self._limits.max_total_loss_pct:
            return self._deny(
                agent_name,
                f"Total loss {drawdown_pct:.1f}% exceeds "
                f"{self._limits.max_total_loss_pct:.1f}% ceiling",
                BlockReason.DRAWDOWN_HALT,
            )

        daily_pnl_pct = self._daily_pnl_pct(st)
        if daily_pnl_pct <= -abs(self._limits.max_daily_loss_pct):
            return self._deny(
                agent_name,
                f"Daily loss {daily_pnl_pct:.1f}% breaches "
                f"{self._limits.max_daily_loss_pct:.1f}% limit",
                BlockReason.CIRCUIT_BREAKER,
            )

        if proposed_margin > 0 and st.current_capital > 0:
            margin_after = st.gross_exposure + proposed_margin
            util = (margin_after / st.current_capital) * 100.0
            if util > self._limits.max_margin_utilisation_pct:
                return self._deny(
                    agent_name,
                    f"Margin utilisation {util:.0f}% exceeds "
                    f"{self._limits.max_margin_utilisation_pct:.0f}% cap",
                    BlockReason.RISK_BUDGET,
                )

        if st.current_capital > 0 and open_gross_exposure > 0:
            lev = (st.gross_exposure + open_gross_exposure) / st.current_capital
            if lev > self._limits.max_gross_leverage:
                return self._deny(
                    agent_name,
                    f"Gross leverage {lev:.2f}x exceeds "
                    f"{self._limits.max_gross_leverage:.2f}x cap",
                    BlockReason.RISK_BUDGET,
                )

        portfolio = self._portfolio_decision()
        if portfolio is not None:
            return self._deny(agent_name, portfolio, BlockReason.CIRCUIT_BREAKER)

        return RiskDecision(
            allowed=True,
            reason="Within all risk limits",
            drawdown_pct=drawdown_pct,
            daily_pnl_pct=daily_pnl_pct,
            consecutive_losses=st.consecutive_losses,
            trades_today=st.trades_today,
        )

    def _deny(self, agent_name: str, reason: str, code: str) -> RiskDecision:
        st = self._states.get(agent_name)
        if st is not None:
            st.blocked_reasons[code] = st.blocked_reasons.get(code, 0) + 1
        self._record_block(agent_name, reason, code)
        return RiskDecision(allowed=False, reason=reason, reason_code=code)

    def _record_block(self, agent_name: str, reason: str, code: str) -> None:
        self._blocked_signals.append(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "agent": agent_name,
                "reason": reason,
                "reason_code": code,
            }
        )
        if len(self._blocked_signals) > self._max_blocked_records:
            del self._blocked_signals[: -self._max_blocked_records]

    def correlation_allowed(
        self,
        *,
        proposed_returns: list[float],
        other_positions: list[tuple[str, list[float]]],
    ) -> tuple[bool, str, str]:
        """Reject a trade whose returns correlate with an already-open position.

        The pre-audit portfolio had correlation ~1.0 across agents - ten
        "diversified" agents were one leveraged position. This enforces the cap.
        """
        worst = 0.0
        worst_peer = ""
        for peer_name, peer_returns in other_positions:
            rho = correlation(proposed_returns, peer_returns)
            if abs(rho) > abs(worst):
                worst = rho
                worst_peer = peer_name
        if abs(worst) > self._limits.max_pair_correlation:
            return (
                False,
                f"Correlation {worst:+.2f} with open {worst_peer} exceeds "
                f"{self._limits.max_pair_correlation:.2f} cap",
                BlockReason.CORRELATED_EXPOSURE,
            )
        return True, "", ""

    # -- state updates ----------------------------------------------------

    def on_entry(
        self,
        agent_name: str,
        *,
        principal: float,
        margin: float,
        now_ts: float | None = None,
    ) -> None:
        st = self.state_for(agent_name, principal=principal)
        self._roll_day_if_needed(st)
        st.gross_exposure += margin
        st.last_entry_ts = now_ts if now_ts is not None else time.time()

    def record_trade(
        self,
        agent_name: str,
        *,
        principal: float,
        net_pnl: float,
        margin_released: float = 0.0,
    ) -> None:
        """Fold a closed trade into the risk state and trip breakers as needed."""
        st = self.state_for(agent_name, principal=principal)
        self._roll_day_if_needed(st)

        st.current_capital = round(st.current_capital + net_pnl, 2)
        st.gross_exposure = max(0.0, st.gross_exposure - margin_released)
        st.trades_today += 1
        st.realized_pnl_today = round(st.realized_pnl_today + net_pnl, 2)
        st.recent_pnl.append(net_pnl)

        if net_pnl > 0:
            st.consecutive_losses = 0
        else:
            st.consecutive_losses += 1

        st.peak_equity = max(st.peak_equity, st.current_capital)

        if st.consecutive_losses >= self._limits.max_consecutive_losses and not st.halted:
            st.halted = True
            st.halt_reason = (
                f"DAILY_LOSS: {st.consecutive_losses} consecutive losses"
            )
            st.halted_at = datetime.now(UTC).isoformat()

        daily_pnl_pct = self._daily_pnl_pct(st)
        if daily_pnl_pct <= -abs(self._limits.max_daily_loss_pct) and not st.halted:
            st.halted = True
            st.halt_reason = f"DAILY_LOSS: {daily_pnl_pct:.1f}% today"
            st.halted_at = datetime.now(UTC).isoformat()

        self._register_portfolio_day()

    def _register_portfolio_day(self) -> None:
        key = self._today()
        total = sum(s.current_capital for s in self._states.values())
        if key != self._portfolio_day_key:
            self._portfolio_day_key = key
            self._portfolio_day_start = total
            self._portfolio_peak = total
            self._portfolio_halt_reason = ""
        self._portfolio_peak = max(self._portfolio_peak, total)

    def _daily_pnl_pct(self, st: RiskState) -> float:
        if st.daily_start_capital <= 0:
            return 0.0
        return ((st.current_capital - st.daily_start_capital) / st.daily_start_capital) * 100.0

    def _drawdown_pct(self, st: RiskState) -> float:
        if st.peak_equity <= 0:
            return 0.0
        return ((st.current_capital - st.peak_equity) / st.peak_equity) * 100.0

    def _portfolio_decision(self) -> str | None:
        if self._portfolio_halt_reason:
            return f"Portfolio halted: {self._portfolio_halt_reason}"
        self._register_portfolio_day()
        if self._portfolio_peak <= 0:
            return None
        drawdown = ((sum(s.current_capital for s in self._states.values()) - self._portfolio_peak)
                    / self._portfolio_peak) * 100.0
        if drawdown <= -abs(self._limits.max_portfolio_drawdown_pct):
            self._portfolio_halt_reason = (
                f"drawdown {drawdown:.1f}% breached "
                f"{self._limits.max_portfolio_drawdown_pct:.1f}% limit"
            )
            return self._portfolio_halt_reason
        if self._portfolio_day_start > 0:
            day_pnl = (
                (sum(s.current_capital for s in self._states.values()) - self._portfolio_day_start)
                / self._portfolio_day_start
            ) * 100.0
            if day_pnl <= -abs(self._limits.portfolio_daily_loss_pct):
                self._portfolio_halt_reason = (
                    f"session loss {day_pnl:.1f}% breached "
                    f"{self._limits.portfolio_daily_loss_pct:.1f}% limit"
                )
                return self._portfolio_halt_reason
        return None

    # -- reporting --------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        total_capital = sum(s.current_capital for s in self._states.values())
        total_initial = sum(s.initial_capital for s in self._states.values())
        blocked_by_code: dict[str, int] = {}
        for st in self._states.values():
            for code, n in st.blocked_reasons.items():
                blocked_by_code[code] = blocked_by_code.get(code, 0) + n
        return {
            "kill_switch": GLOBAL_KILL_SWITCH.as_dict(),
            "limits": self._limits.as_dict(),
            "portfolio": {
                "initial_capital": round(total_initial, 2),
                "current_capital": round(total_capital, 2),
                "net_pnl": round(total_capital - total_initial, 2),
                "drawdown_pct": round(
                    ((total_capital - self._portfolio_peak) / self._portfolio_peak) * 100.0
                    if self._portfolio_peak > 0
                    else 0.0,
                    2,
                ),
                "halted": bool(self._portfolio_halt_reason),
                "halt_reason": self._portfolio_halt_reason,
            },
            "agents": {
                name: {
                    "current_capital": round(st.current_capital, 2),
                    "initial_capital": round(st.initial_capital, 2),
                    "peak_equity": round(st.peak_equity, 2),
                    "drawdown_pct": round(self._drawdown_pct(st), 2),
                    "daily_pnl_pct": round(self._daily_pnl_pct(st), 2),
                    "consecutive_losses": st.consecutive_losses,
                    "trades_today": st.trades_today,
                    "gross_exposure": round(st.gross_exposure, 2),
                    "halted": st.halted,
                    "halt_reason": st.halt_reason,
                    "blocked_reasons": dict(st.blocked_reasons),
                }
                for name, st in self._states.items()
            },
            "blocked_signals": {
                "total": len(self._blocked_signals),
                "by_code": blocked_by_code,
                "recent": self._blocked_signals[-20:],
            },
        }


__all__ = [
    "GLOBAL_KILL_SWITCH",
    "KillSwitch",
    "RiskDecision",
    "RiskLimits",
    "RiskManager",
    "RiskState",
    "correlation",
]
