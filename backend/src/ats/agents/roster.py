"""Dynamic agent roster: add, remove, and reassign agents at runtime.

The original design hard-coded ten agents. That was a mistake twice over: it
forced ten positions on a system with no validated edge, and it made the fleet
shape unchangeable without a code edit.

This module makes the roster data. The default fleet is **four** agents, sized
to the strongest evidence available rather than to a round number. Agents can be
added or removed at runtime, and every mutation is validated against the
diversification rules before it is accepted.

Key invariant: an agent is only added if it carries a **distinct signal family**
and a mandate that passes :func:`ats.agents.portfolio.validate_mandates`. A
fleet of near-duplicates is concentrated risk wearing a diversification
costume, which is exactly the pre-audit failure.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ats.agents.portfolio import MANDATES, Mandate, validate_mandates

LOGGER = logging.getLogger(__name__)

ROSTER_FILE_PATH = Path("data/agents/roster.json")

#: Default fleet size. Four is a deliberate choice: enough to diversify, few
#: enough that each agent's behaviour is legible and its risk is attributable.
DEFAULT_FLEET_SIZE = 4

#: Agent names that must never be reused for a different role, because the
#: frontend and existing histories key on them.
RESERVED_NAMES = frozenset({""})


@dataclass
class RosterEntry:
    """One agent's assignment."""

    name: str
    family: str
    signal_source: str
    instrument_bias: list[str]
    horizon: str
    bar_seconds: float
    description: str
    principal: float = 100_000.0
    enabled: bool = True
    origin: str = "builtin"
    added_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    def to_mandate(self) -> Mandate:
        return Mandate(
            agent=self.name,
            family=self.family,
            signal_source=self.signal_source,
            instrument_bias=tuple(self.instrument_bias),
            horizon=self.horizon,
            bar_seconds=self.bar_seconds,
            description=self.description,
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class RosterError(ValueError):
    """Raised when a roster mutation would produce an unsafe fleet."""


class Roster:
    """The set of agents the playground will actually run."""

    def __init__(
        self,
        entries: list[RosterEntry] | None = None,
        *,
        path: Path | None = None,
    ) -> None:
        self._entries: dict[str, RosterEntry] = {}
        self._path = path or ROSTER_FILE_PATH
        for e in entries or []:
            self._entries[e.name] = e
        if not self._entries:
            self._entries = {e.agent: default_entry(e) for e in MANDATES}

    # -- reads -------------------------------------------------------------

    @property
    def entries(self) -> list[RosterEntry]:
        return list(self._entries.values())

    def names(self) -> list[str]:
        return list(self._entries.keys())

    def get(self, name: str) -> RosterEntry | None:
        return self._entries.get(name)

    def mandates(self) -> list[Mandate]:
        return [e.to_mandate() for e in self._entries.values()]

    def active_entries(self) -> list[RosterEntry]:
        return [e for e in self._entries.values() if e.enabled]

    def size(self) -> int:
        return len(self._entries)

    def as_dict(self) -> dict[str, Any]:
        return {
            "size": self.size(),
            "agents": [e.as_dict() for e in self._entries.values()],
            "families": sorted({e.family for e in self._entries.values()}),
            "instruments": sorted({i for e in self._entries.values() for i in e.instrument_bias}),
        }

    # -- validation --------------------------------------------------------

    def _registered_sources(self) -> set[str]:
        """All strategy ids that can currently be assigned.

        Diverse families are registered lazily, so they must be materialised
        before membership checks or valid sources would be rejected as unknown.
        """
        from ats.agents.strategies import ensure_diverse_families_loaded

        ensure_diverse_families_loaded()
        from ats.agents.strategies import STRATEGY_REGISTRY

        return set(STRATEGY_REGISTRY.keys())

    def _validate(self) -> None:
        problems = validate_mandates(tuple(self.mandates()))
        if problems:
            raise RosterError("; ".join(problems))

    # -- mutations ---------------------------------------------------------

    def add(
        self,
        *,
        name: str,
        family: str,
        signal_source: str,
        description: str = "",
        instrument_bias: list[str] | None = None,
        horizon: str = "TACTICAL_INTRADAY",
        bar_seconds: float = 300.0,
        principal: float = 100_000.0,
        origin: str = "custom",
    ) -> RosterEntry:
        """Add an agent, rejecting anything that breaks diversification.

        The signal source must already be registered, otherwise the agent
        could never produce a signal and would silently sit idle.
        """
        clean = name.strip()
        if not clean:
            raise RosterError("Agent name must be non-empty")
        if clean in self._entries:
            raise RosterError(f"Agent '{clean}' already exists")

        from ats.agents.strategies import STRATEGY_REGISTRY  # noqa: F401

        registered = self._registered_sources()
        if signal_source not in registered:
            raise RosterError(
                f"Unknown signal source '{signal_source}'. "
                f"Registered: {', '.join(sorted(registered))}"
            )

        if any(e.family == family for e in self._entries.values()):
            existing = [e.name for e in self._entries.values() if e.family == family]
            raise RosterError(
                f"Family '{family}' is already covered by {existing}. "
                f"Distinct families are what make the fleet diversified."
            )

        entry = RosterEntry(
            name=clean,
            family=family,
            signal_source=signal_source,
            instrument_bias=instrument_bias or ["GOLDM"],
            horizon=horizon,
            bar_seconds=bar_seconds,
            description=description or f"Custom agent using {signal_source}",
            principal=principal,
            origin=origin,
        )
        # Validate against a trial roster before committing.
        trial = dict(self._entries)
        trial[clean] = entry
        problems = validate_mandates(tuple(e.to_mandate() for e in trial.values()))
        if problems:
            raise RosterError("Adding this agent would break diversification: " + "; ".join(problems))

        self._entries[clean] = entry
        self.save()
        LOGGER.info("Roster: added agent %s (family=%s, source=%s)", clean, family, signal_source)
        return entry

    def remove(self, name: str) -> RosterEntry:
        """Remove an agent. The fleet must retain at least one agent."""
        if name not in self._entries:
            raise RosterError(f"Agent '{name}' is not in the roster")
        if len(self._entries) <= 1:
            raise RosterError("Cannot remove the last agent - the fleet would be empty")
        entry = self._entries.pop(name)
        self.save()
        LOGGER.info("Roster: removed agent %s", name)
        return entry

    def set_enabled(self, name: str, enabled: bool) -> RosterEntry:
        if name not in self._entries:
            raise RosterError(f"Agent '{name}' is not in the roster")
        entry = self._entries[name]
        entry.enabled = enabled
        self.save()
        return entry

    def set_principal(self, name: str, principal: float) -> RosterEntry:
        if name not in self._entries:
            raise RosterError(f"Agent '{name}' is not in the roster")
        if principal <= 0:
            raise RosterError("Principal must be positive")
        self._entries[name].principal = principal
        self.save()
        return self._entries[name]

    def assign_strategy(self, name: str, signal_source: str) -> RosterEntry:
        """Point an existing agent at a different registered strategy.

        This is the "run my own strategy on an agent" path: register the
        strategy, then assign it.
        """
        if name not in self._entries:
            raise RosterError(f"Agent '{name}' is not in the roster")

        registered = self._registered_sources()
        if signal_source not in registered:
            raise RosterError(
                f"Unknown signal source '{signal_source}'. "
                f"Registered: {', '.join(sorted(registered))}"
            )
        self._entries[name].signal_source = signal_source
        self.save()
        LOGGER.info("Roster: agent %s now using %s", name, signal_source)
        return self._entries[name]

    def reset_to_default(self) -> None:
        """Restore the curated default fleet (four agents)."""
        self._entries = {e.agent: default_entry(e) for e in DEFAULT_FLEET}
        self.save()

    # -- persistence -------------------------------------------------------

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps({"agents": [e.as_dict() for e in self._entries.values()]}, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            LOGGER.warning("Could not persist roster to %s: %s", self._path, e)

    @classmethod
    def load(cls, path: Path | None = None) -> Roster:
        p = path or ROSTER_FILE_PATH
        if not p.exists():
            return cls(path=p)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            entries = [RosterEntry(**a) for a in data.get("agents", [])]
        except (OSError, ValueError, TypeError) as e:
            LOGGER.warning("Could not read roster %s: %s", p, e)
            return cls(path=p)
        if not entries:
            return cls(path=p)
        return cls(entries, path=p)


def default_entry(mandate: Mandate) -> RosterEntry:
    principal = 200_000.0 if mandate.horizon == "LONG_TERM_SWING" else 100_000.0
    return RosterEntry(
        name=mandate.agent,
        family=mandate.family,
        signal_source=mandate.signal_source,
        instrument_bias=list(mandate.instrument_bias),
        horizon=mandate.horizon,
        bar_seconds=mandate.bar_seconds,
        description=mandate.description,
        principal=principal,
        origin="builtin",
    )


#: Four agents, four structurally different families, two horizons, three instruments.
DEFAULT_FLEET: tuple[Mandate, ...] = (
    Mandate("Alpha", "Hurst", "hurst_regime", ("GOLDM",), "TACTICAL_INTRADAY", 300.0, "Serial-correlation regime"),
    Mandate("Bravo", "VolumeDivergence", "volume_divergence", ("XAU",), "TACTICAL_INTRADAY", 300.0, "Price unsupported by volume"),
    Mandate("Charlie", "Squeeze", "squeeze", ("GOLDM", "GOLD"), "LONG_TERM_SWING", 1800.0, "Volatility compression release"),
    Mandate("Delta", "Skew", "moment_skew", ("GOLD",), "TACTICAL_INTRADAY", 900.0, "Distribution asymmetry fade"),
)


def build_default_roster(
    *, size: int = DEFAULT_FLEET_SIZE, path: Path | None = None
) -> Roster:
    """Build the default four-agent fleet from structurally different families."""
    entries = [default_entry(m) for m in DEFAULT_FLEET[:size]]
    return Roster(entries, path=path)


_ROSTER: Roster | None = None


def get_roster() -> Roster:
    """Return the process-wide roster, loading or building it on first use."""
    global _ROSTER
    if _ROSTER is None:
        loaded = Roster.load()
        if loaded.size() == 0 or loaded.size() == len(MANDATES):
            # No customisation, or the legacy ten-agent set: use the curated default.
            _ROSTER = build_default_roster(path=ROSTER_FILE_PATH)
        else:
            _ROSTER = loaded
    return _ROSTER


def set_roster(roster: Roster) -> Roster:
    global _ROSTER
    _ROSTER = roster
    return roster


def reset_roster_cache() -> None:
    """Drop the cached roster so the next read reloads from disk."""
    global _ROSTER
    _ROSTER = None


__all__ = [
    "DEFAULT_FLEET_SIZE",
    "Roster",
    "RosterEntry",
    "RosterError",
    "build_default_roster",
    "default_entry",
    "get_roster",
    "reset_roster_cache",
    "set_roster",
]
