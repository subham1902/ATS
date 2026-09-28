"""Portfolio construction: de-duplicated mandates, allocation, and correlation caps.

The pre-audit configuration created four duplicate pairs by archetype
(Alpha/Golf/Hotel/India, Bravo/Charlie, Echo/Juliet, Foxtrot/Delta). The audit
confirmed the consequence: agents in the same pair produced *identical* trade
signatures and correlation ~1.0. Ten nominally diversified agents were
effectively four highly correlated positions, which is concentrated risk
carrying a diversification cost.

This module assigns each agent a distinct mandate so the fleet actually spans
different signal families, and enforces a correlation cap across concurrently
open risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ats.agents.risk import correlation

# ---------------------------------------------------------------------------
# Mandates
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Mandate:
    """A distinct, non-overlapping trading mandate for one agent."""

    agent: str
    family: str
    signal_source: str
    instrument_bias: tuple[str, ...]
    horizon: str
    bar_seconds: float
    description: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "family": self.family,
            "signal_source": self.signal_source,
            "instrument_bias": list(self.instrument_bias),
            "horizon": self.horizon,
            "bar_seconds": self.bar_seconds,
            "description": self.description,
        }


#: Ten distinct mandates. No two share a signal family, and the horizons are
#: spread across intraday and swing so the fleet is not uniformly exposed to one
#: time horizon either.
MANDATES: tuple[Mandate, ...] = (
    Mandate(
        agent="Alpha",
        family="Trend",
        signal_source="donchian",
        instrument_bias=("GOLDM",),
        horizon="TACTICAL_INTRADAY",
        bar_seconds=300.0,
        description="Donchian channel breakout with trend-strength confirmation",
    ),
    Mandate(
        agent="Bravo",
        family="Volatility",
        signal_source="atr_expansion",
        instrument_bias=("GOLDM",),
        horizon="TACTICAL_INTRADAY",
        bar_seconds=300.0,
        description="Volatility expansion/contraction on ATR and realised vol",
    ),
    Mandate(
        agent="Charlie",
        family="MeanReversion",
        signal_source="zscore",
        instrument_bias=("GOLDM",),
        horizon="TACTICAL_INTRADAY",
        bar_seconds=300.0,
        description="Z-score reversion from statistically extended levels",
    ),
    Mandate(
        agent="Delta",
        family="OrderFlow",
        signal_source="oi_volume",
        instrument_bias=("GOLDM", "GOLD"),
        horizon="TACTICAL_INTRADAY",
        bar_seconds=300.0,
        description="Open-interest and volume confirmation state machine",
    ),
    Mandate(
        agent="Echo",
        family="Macro",
        signal_source="vwap_trend",
        instrument_bias=("GOLD", "XAU"),
        horizon="LONG_TERM_SWING",
        bar_seconds=1800.0,
        description="VWAP-anchored swing trend capture on the 1kg contract and spot",
    ),
    Mandate(
        agent="Foxtrot",
        family="Microstructure",
        signal_source="tick_velocity",
        instrument_bias=("XAU",),
        horizon="TACTICAL_INTRADAY",
        bar_seconds=300.0,
        description="Bar-internal tick velocity and volume imbalance on 24/7 spot",
    ),
    Mandate(
        agent="Golf",
        family="Auction",
        signal_source="gap_fill",
        instrument_bias=("GOLDM", "GOLD"),
        horizon="TACTICAL_INTRADAY",
        bar_seconds=900.0,
        description="Session open auction gap and 15-minute range fill",
    ),
    Mandate(
        agent="Hotel",
        family="RegimeFilter",
        signal_source="regime_gate",
        instrument_bias=("XAU", "GOLDM"),
        horizon="LONG_TERM_SWING",
        bar_seconds=1800.0,
        description="Regime classifier gating swing entries by volatility state",
    ),
    Mandate(
        agent="India",
        family="Momentum",
        signal_source="tsmom",
        instrument_bias=("GOLDM",),
        horizon="TACTICAL_INTRADAY",
        bar_seconds=600.0,
        description="Time-series momentum across stacked bar horizons",
    ),
    Mandate(
        agent="Juliet",
        family="CounterTrend",
        signal_source="fade_extreme",
        instrument_bias=("GOLDM",),
        horizon="LONG_TERM_SWING",
        bar_seconds=1800.0,
        description="Counter-trend fade of statistically extreme swing dislocations",
    ),
)


def mandate_for(agent: str) -> Mandate | None:
    for m in MANDATES:
        if m.agent == agent:
            return m
    return None


def validate_mandates(mandates: tuple[Mandate, ...] = MANDATES) -> list[str]:
    """Return a list of portfolio-construction problems. Empty means healthy."""
    problems: list[str] = []

    families = [m.family for m in mandates]
    dupes = {f for f in families if families.count(f) > 1}
    if dupes:
        problems.append(f"Duplicate signal families across agents: {sorted(dupes)}")

    agents = [m.agent for m in mandates]
    agent_dupes = {a for a in agents if agents.count(a) > 1}
    if agent_dupes:
        problems.append(f"Duplicate agent mandates: {sorted(agent_dupes)}")

    if len(set(agents)) < 2:
        problems.append("Fewer than 2 distinct agents - portfolio is too concentrated")

    if len({m.bar_seconds for m in mandates}) < 2:
        problems.append("All mandates share one bar size - no horizon diversification")

    if len({m.instrument_bias[0] for m in mandates}) < 2:
        problems.append("All mandates trade the same instrument - single-factor exposure")

    return problems


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------


@dataclass
class Allocation:
    """Capital allocation outcome for the fleet."""

    total_capital: float
    per_agent_capital: dict[str, float]
    method: str
    diversification_note: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_capital": round(self.total_capital, 2),
            "per_agent_capital": {
                k: round(v, 2) for k, v in self.per_agent_capital.items()
            },
            "method": self.method,
            "diversification_note": self.diversification_note,
        }


def allocate_capital(
    principals: dict[str, float],
    *,
    edge_scores: dict[str, float] | None = None,
    respect_proven_edge: bool = True,
) -> Allocation:
    """Allocate capital across agents, tilting toward validated edge.

    Agents with a proven edge may draw more than their nominal share; agents
    without evidence are held at or below it. Capital is never allocated to an
    agent that would exceed its own principal.
    """
    total = sum(principals.values())
    scores = edge_scores or {}

    if not respect_proven_edge or not scores:
        return Allocation(
            total_capital=total,
            per_agent_capital=dict(principals),
            method="EQUAL_TO_PRINCIPAL",
            diversification_note="No validated edge; each agent limited to its principal.",
        )

    positive = {k: max(v, 0.0) for k, v in scores.items() if k in principals}
    pool = sum(positive.values())
    if pool <= 0:
        return Allocation(
            total_capital=total,
            per_agent_capital=dict(principals),
            method="EQUAL_TO_PRINCIPAL",
            diversification_note="No agent has positive expected edge.",
        )

    allocated: dict[str, float] = {}
    for name, principal in principals.items():
        share = (positive.get(name, 0.0) / pool) * total
        allocated[name] = round(min(principal, max(principal * 0.5, share)), 2)

    return Allocation(
        total_capital=round(sum(allocated.values()), 2),
        per_agent_capital=allocated,
        method="EDGE_TILTED",
        diversification_note=(
            "Allocation tilted to validated edge, floored at 50% and capped at principal."
        ),
    )


# ---------------------------------------------------------------------------
# Correlation cap across the fleet
# ---------------------------------------------------------------------------


@dataclass
class OpenExposure:
    """One agent's open directional risk."""

    agent: str
    family: str
    instrument: str
    direction: str
    notional: float
    recent_returns: list[float] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "family": self.family,
            "instrument": self.instrument,
            "direction": self.direction,
            "notional": round(self.notional, 2),
        }


@dataclass(frozen=True, slots=True)
class PortfolioCheck:
    """Verdict on whether a proposed trade fits the portfolio."""

    allowed: bool
    reason: str
    worst_correlation: float
    worst_peer: str
    same_family_peers: list[str]
    same_instrument_peers: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "worst_correlation": round(self.worst_correlation, 3),
            "worst_peer": self.worst_peer,
            "same_family_peers": self.same_family_peers,
            "same_instrument_peers": self.same_instrument_peers,
        }


class PortfolioBuilder:
    """Enforce diversification and correlation limits across open agent risk."""

    def __init__(self, *, max_pair_correlation: float = 0.60) -> None:
        self._max_corr = max_pair_correlation
        self._open: list[OpenExposure] = []

    @property
    def max_pair_correlation(self) -> float:
        return self._max_corr

    def open_exposure(self) -> list[OpenExposure]:
        return list(self._open)

    def add_exposure(self, exposure: OpenExposure) -> None:
        self._open.append(exposure)

    def remove_exposure(self, agent: str) -> None:
        self._open = [e for e in self._open if e.agent != agent]

    def clear(self) -> None:
        self._open.clear()

    def check(
        self,
        *,
        agent: str,
        family: str,
        instrument: str,
        direction: str,
        proposed_returns: list[float],
        allow_same_family: bool = False,
    ) -> PortfolioCheck:
        """Decide whether a proposed trade concentrates the portfolio too far.

        Two guards:

        1. **Correlation cap** - reject if the proposed return series correlates
           above the limit with an open position.
        2. **Family cap** - reject a second simultaneous position in the same
           signal family unless explicitly allowed. This is the structural fix
           for the duplicate-archetype problem, which correlation alone will
           not catch while the sample is short.
        """
        same_family = [e.agent for e in self._open if e.family == family and e.agent != agent]
        same_instrument = [
            e.agent for e in self._open if e.instrument == instrument and e.agent != agent
        ]

        if same_family and not allow_same_family:
            return PortfolioCheck(
                allowed=False,
                reason=(
                    f"Signal family '{family}' already has open risk via "
                    f"{', '.join(same_family)} - avoids duplicate-mandate concentration"
                ),
                worst_correlation=0.0,
                worst_peer="",
                same_family_peers=same_family,
                same_instrument_peers=same_instrument,
            )

        worst = 0.0
        worst_peer = ""
        for e in self._open:
            if e.agent == agent:
                continue
            if e.direction != direction:
                continue
            rho = correlation(proposed_returns, e.recent_returns)
            if abs(rho) > abs(worst):
                worst = rho
                worst_peer = e.agent

        if abs(worst) > self._max_corr:
            return PortfolioCheck(
                allowed=False,
                reason=(
                    f"Correlation {worst:+.2f} with open {worst_peer} exceeds "
                    f"{self._max_corr:.2f} cap"
                ),
                worst_correlation=worst,
                worst_peer=worst_peer,
                same_family_peers=same_family,
                same_instrument_peers=same_instrument,
            )

        return PortfolioCheck(
            allowed=True,
            reason="Diversification limits satisfied",
            worst_correlation=worst,
            worst_peer=worst_peer,
            same_family_peers=same_family,
            same_instrument_peers=same_instrument,
        )

    def concentration_summary(self) -> dict[str, Any]:
        by_family: dict[str, list[str]] = {}
        by_instrument: dict[str, list[str]] = {}
        for e in self._open:
            by_family.setdefault(e.family, []).append(e.agent)
            by_instrument.setdefault(e.instrument, []).append(e.agent)

        pair_corr: list[dict[str, Any]] = []
        for i in range(len(self._open)):
            for j in range(i + 1, len(self._open)):
                a, b = self._open[i], self._open[j]
                rho = correlation(a.recent_returns, b.recent_returns)
                pair_corr.append({"a": a.agent, "b": b.agent, "correlation": round(rho, 3)})

        max_pair = max((abs(p["correlation"]) for p in pair_corr), default=0.0)
        return {
            "open_positions": len(self._open),
            "by_family": {k: v for k, v in by_family.items() if len(v) > 1},
            "by_instrument": {k: v for k, v in by_instrument.items() if len(v) > 1},
            "pair_correlations": pair_corr,
            "max_pair_correlation": round(max_pair, 3),
            "correlation_cap": self._max_corr,
            "within_limits": max_pair <= self._max_corr,
            "duplicate_family_exposure": bool(
                any(len(v) > 1 for v in by_family.values())
            ),
        }


__all__ = [
    "Allocation",
    "MANDATES",
    "Mandate",
    "OpenExposure",
    "PortfolioBuilder",
    "PortfolioCheck",
    "allocate_capital",
    "mandate_for",
    "validate_mandates",
]
