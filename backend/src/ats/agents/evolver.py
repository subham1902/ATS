"""Continuous validation loop: keep testing candidates against live behaviour.

The user requirement is that the playground must keep testing rather than
discovering an edge once and stopping. This module runs a bounded, repeated
revalidation cycle and records every verdict, so the system's belief about a
strategy can *change* in both directions.

Design
------
* **Bounded.** Each cycle is capped in duration and candidate count, so the
  loop cannot starve the trading loop or leak resources.
* **Non-destructive.** A cycle never mutates the roster or the deployment gate
  by itself. It produces evidence; a human or an explicit promote call applies it.
* **History-aware.** Verdicts are appended, so drift is visible: a strategy that
  degrades over time shows up as a declining expectancy trend even while each
  individual cycle looks acceptable.
* **Isolated.** Failures in one candidate never abort the cycle.

Everything here is opt-in via :meth:`ContinuousTester.start`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ats.agents.edge import StrategyEdgeRegistry

LOGGER = logging.getLogger(__name__)

#: Minimum trades in a cycle before a verdict is issued at all.
MIN_CYCLES_FOR_VERDICT = 3


@dataclass
class CycleResult:
    """One validation cycle's outcome."""

    started_at: str
    duration_seconds: float
    candidates_tested: int
    per_agent: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "duration_seconds": round(self.duration_seconds, 3),
            "candidates_tested": self.candidates_tested,
            "per_agent": self.per_agent,
            "errors": self.errors,
        }


class ContinuousTester:
    """Repeatedly re-evaluates the edge registry and the deployment gate.

    It is deliberately conservative. It watches, records, and reports. It does
    not promote a strategy on its own, because a background loop that silently
    starts funding a newly-"promising" strategy is exactly the failure mode this
    project has already paid for once.
    """

    def __init__(
        self,
        *,
        interval_seconds: float = 300.0,
        max_cycle_seconds: float = 30.0,
        history: int = 50,
    ) -> None:
        self._interval = max(10.0, interval_seconds)
        self._max_cycle = max(1.0, max_cycle_seconds)
        self._history: deque[CycleResult] = deque(maxlen=history)
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._cycle_count = 0
        self._started_at: str | None = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._started_at = datetime.now(UTC).isoformat()
        self._task = asyncio.create_task(self._loop())
        LOGGER.info("Continuous tester started (interval=%.0fs)", self._interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        LOGGER.info("Continuous tester stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                if not self._running:
                    break
                await self.run_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOGGER.error("Continuous tester cycle failed: %s", e, exc_info=True)

    # -- work --------------------------------------------------------------

    async def run_cycle(self) -> CycleResult:
        """Run one bounded validation cycle."""
        started = datetime.now(UTC).isoformat()
        t0 = time.time()
        deadline = t0 + self._max_cycle

        result = CycleResult(started_at=started, duration_seconds=0.0, candidates_tested=0)
        registry = _get_edge_registry()

        try:
            from ats.agents.roster import get_roster

            entries = get_roster().active_entries()
        except Exception as e:  # pragma: no cover - defensive
            result.errors.append(f"roster unavailable: {e}")
            entries = []

        for entry in entries:
            if time.time() > deadline:
                result.errors.append("cycle time budget exhausted")
                break
            result.candidates_tested += 1
            try:
                result.per_agent[entry.name] = self._evaluate(entry, registry)
            except Exception as e:
                result.errors.append(f"{entry.name}: {e}")

        result.duration_seconds = time.time() - t0
        self._history.append(result)
        self._cycle_count += 1
        return result

    def _evaluate(self, entry: Any, registry: StrategyEdgeRegistry) -> dict[str, Any]:
        """Evaluate one agent's live evidence against a notional geometry."""
        # Use a representative geometry so the break-even bar is meaningful even
        # before the agent has traded on a real signal.
        verdict = registry.evaluate(
            entry.signal_source,
            required_win_rate=0.45,
            net_if_win=2.0,
            net_if_loss=-1.0,
        )
        return verdict.as_dict()

    # -- reporting ---------------------------------------------------------

    def status(self) -> dict[str, Any]:
        latest = self._history[-1].as_dict() if self._history else None
        return {
            "running": self._running,
            "started_at": self._started_at,
            "cycle_count": self._cycle_count,
            "interval_seconds": self._interval,
            "max_cycle_seconds": self._max_cycle,
            "history_depth": len(self._history),
            "latest_cycle": latest,
            "recent_cycles": [c.as_dict() for c in list(self._history)[-5:]],
            "note": (
                "This loop records evidence only. It never promotes a strategy "
                "on its own - promotion requires an explicit decision against "
                "held-out validation."
            ),
        }

    def trend(self) -> dict[str, Any]:
        """Per-agent expectancy trend across cycles, to expose drift."""
        out: dict[str, list[float]] = {}
        for cycle in self._history:
            for agent, v in cycle.per_agent.items():
                out.setdefault(agent, []).append(float(v.get("expected_net_per_trade", 0.0)))
        summary: dict[str, Any] = {}
        for agent, series in out.items():
            if len(series) < 2:
                continue
            first, last = series[0], series[-1]
            summary[agent] = {
                "samples": len(series),
                "first": round(first, 4),
                "last": round(last, 4),
                "change": round(last - first, 4),
                "direction": "improving" if last > first else "degrading",
            }
        return summary


_TESTER: ContinuousTester | None = None


def get_continuous_tester() -> ContinuousTester:
    global _TESTER
    if _TESTER is None:
        _TESTER = ContinuousTester()
    return _TESTER


def _get_edge_registry() -> StrategyEdgeRegistry:
    from ats.agents.worker import get_edge_registry

    return get_edge_registry()


__all__ = ["ContinuousTester", "CycleResult", "MIN_CYCLES_FOR_VERDICT", "get_continuous_tester"]
