"""Deployment gate: which mandates are allowed to trade, based on validated evidence.

This is the bridge between offline research and live capital. The 2026-09-28
historical validation found that **no** mandate had positive out-of-sample
expectancy on real gold data, so on load the system correctly holds the entire
fleet.

That is not a bug and not a disappointing result - it is the gate working. Two
mandates (Echo, Hotel) showed strongly positive in-sample expectancy and then
went negative out-of-sample. That is the signature of curve-fitting, and it is
exactly the failure the gate exists to prevent.

A mandate becomes deployable only when a *fresh* out-of-sample run says so. The
verdict is not sticky: re-running validation can withdraw a mandate, because
evidence that no longer holds should stop trading.

Usage
-----
    from ats.agents.deployment import DeploymentGate
    gate = DeploymentGate.load("strategy_validation.json")
    gate.allows("Alpha")   # -> False, with a reason
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

#: Verdicts that permit live deployment.
DEPLOYABLE_VERDICTS = frozenset({"GRADUATED"})


@dataclass
class MandateVerdict:
    """One mandate's validated deployment status."""

    agent: str
    verdict: str
    deployable: bool
    trades: int
    win_rate: float
    net_points: float
    expectancy: float
    profit_factor: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "verdict": self.verdict,
            "deployable": self.deployable,
            "trades": self.trades,
            "win_rate": self.win_rate,
            "net_points": self.net_points,
            "expectancy": self.expectancy,
            "profit_factor": self.profit_factor,
            "reason": self.reason,
        }


@dataclass
class DeploymentGate:
    """Authoritative allow/deny list derived from out-of-sample evidence."""

    verdicts: dict[str, MandateVerdict] = field(default_factory=dict)
    generated_at: str = ""
    data_source: str = ""
    oos_fraction: float = 0.0
    evidence_present: bool = False
    notes: str = ""

    # -- queries ----------------------------------------------------------

    def allows(self, agent: str) -> bool:
        """May this agent trade?"""
        return self.allows_with_reason(agent)[0]

    def allows_with_reason(self, agent: str) -> tuple[bool, str]:
        """``(allowed, reason)`` for an agent."""
        v = self.verdicts.get(agent)
        if v is None:
            return (
                False,
                "No validated evidence for this mandate. Absence of evidence is "
                "not evidence of edge.",
            )
        return (True, v.reason) if v.deployable else (False, v.reason)

    @property
    def deployable_agents(self) -> list[str]:
        return sorted(a for a, v in self.verdicts.items() if v.deployable)

    @property
    def held_agents(self) -> list[str]:
        return sorted(a for a, v in self.verdicts.items() if not v.deployable)

    def is_fleet_wide_hold(self) -> bool:
        return not self.deployable_agents

    # -- reporting --------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "data_source": self.data_source,
            "oos_fraction": self.oos_fraction,
            "evidence_present": self.evidence_present,
            "fleet_wide_hold": self.is_fleet_wide_hold(),
            "deployable_agents": self.deployable_agents,
            "held_agents": self.held_agents,
            "verdicts": {a: v.as_dict() for a, v in self.verdicts.items()},
            "notes": self.notes,
        }


#: Reason text keyed by verdict, so operators get an explanation not a code.
_REASONS = {
    "GRADUATED": "Out-of-sample evidence clears the deployment bar.",
    "PROMISING": "Held: positive but sample or profit factor below the bar.",
    "INSUFFICIENT_SAMPLE": "Held: too few out-of-sample trades to judge.",
    "NEGATIVE_EXPECTANCY": "Held: negative out-of-sample expectancy after costs.",
    "NO_SIGNAL": "Held: never fired on validation data - no evidence of edge.",
}


def _reason_for(verdict: str, r: dict[str, Any], is_oos_negative: bool) -> str:
    base = _REASONS.get(verdict, f"Held: verdict {verdict}.")
    if is_oos_negative and verdict != "NEGATIVE_EXPECTANCY":
        return (
            f"{base} Note: in-sample was positive but out-of-sample is negative "
            f"- classic overfit, so it is held."
        )
    return base


def from_report(report: dict[str, Any]) -> DeploymentGate:
    """Build a gate from a :mod:`scripts.validate_strategies` report."""
    oos = report.get("oos") or {}
    is_seg = report.get("is") or {}

    verdicts: dict[str, MandateVerdict] = {}
    for agent, r in oos.items():
        verdict = str(r.get("verdict", "NO_SIGNAL"))
        deployable = bool(r.get("deployable", False)) and verdict in DEPLOYABLE_VERDICTS
        in_sample_net = float(is_seg.get(agent, {}).get("net_points", 0.0))
        oos_net = float(r.get("net_points", 0.0))
        is_oos_negative = in_sample_net > 0 and oos_net <= 0

        verdicts[agent] = MandateVerdict(
            agent=agent,
            verdict=verdict,
            deployable=deployable,
            trades=int(r.get("trades", 0)),
            win_rate=float(r.get("win_rate", 0.0)),
            net_points=oos_net,
            expectancy=float(r.get("expectancy", 0.0)),
            profit_factor=float(r.get("profit_factor", 0.0)),
            reason=_reason_for(verdict, r, is_oos_negative),
        )

    gate = DeploymentGate(
        verdicts=verdicts,
        generated_at=datetime.now(UTC).isoformat(),
        data_source=str(report.get("data_source", "")),
        oos_fraction=float(report.get("oos_fraction", 0.0)),
        evidence_present=bool(verdicts),
    )

    if not verdicts:
        gate.notes = (
            "No validation evidence loaded. Every mandate is held, because an "
            "unvalidated strategy must never be pointed at capital."
        )
    elif gate.is_fleet_wide_hold():
        overfit = [
            a for a, v in verdicts.items()
            if float(is_seg.get(a, {}).get("net_points", 0.0)) > 0
            and v.net_points <= 0
        ]
        gate.notes = (
            "Fleet-wide hold: no mandate showed positive out-of-sample "
            "expectancy after costs."
            + (
                f" Overfit-detected (positive in-sample, negative OOS): {', '.join(overfit)}."
                if overfit
                else ""
            )
        )
    else:
        gate.notes = (
            f"Deployable: {', '.join(gate.deployable_agents)}. "
            f"All others held."
        )
    return gate


#: Fleet-wide hold. There is no validated evidence at import time, and the
#: correct default for a system that lost money is to not trade.
_DEFAULT_GATE = DeploymentGate(
    verdicts={},
    evidence_present=False,
    notes=(
        "DEFAULT: no validation evidence loaded, so every mandate is held. "
        "Run 'python -m scripts.validate_strategies' and load the result via "
        "DeploymentGate.load() before releasing the kill switch."
    ),
)


def get_deployment_gate() -> DeploymentGate:
    """Return the process-wide deployment gate."""
    return _DEFAULT_GATE


def set_deployment_gate(gate: DeploymentGate) -> DeploymentGate:
    """Install a validated gate as the process-wide gate."""
    global _DEFAULT_GATE
    _DEFAULT_GATE = gate
    LOGGER.info(
        "Deployment gate updated: deployable=%s held=%s",
        gate.deployable_agents or "none",
        gate.held_agents or "none",
    )
    return gate


def load(path: Path | str) -> DeploymentGate:
    """Load and install a validation report as the active gate."""
    p = Path(path)
    if not p.exists():
        LOGGER.warning("Validation report not found at %s; keeping default hold", p)
        return get_deployment_gate()
    try:
        report = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        LOGGER.warning("Could not read validation report %s: %s", p, e)
        return get_deployment_gate()
    return set_deployment_gate(from_report(report))


__all__ = [
    "DEPLOYABLE_VERDICTS",
    "DeploymentGate",
    "MandateVerdict",
    "from_report",
    "get_deployment_gate",
    "load",
    "set_deployment_gate",
]
