"""Managed research agents: durable, versioned, proposal-only configuration.

This domain configures LLM/research agents (provider, model, instructions,
capabilities, data scopes, runtime limits). It is deliberately separate from
the strategy-persona playground in :mod:`ats.agents.roster`: those agents
carry principals and trade, these agents only ever inspect, analyze, and
propose.

Proposal-only is structural, not a flag. The capability vocabulary below has
no member for financial authority, the store has no reference to brokers,
portfolios, tokens, or orders, and editing an agent appends an immutable
config version instead of rewriting history. Every run records the exact
config version that produced it, and deletion archives by default: research
outputs, runs, and configuration history survive the agent.

Persistence follows the roster convention (a JSON document under
``data/agents/``), written atomically. Audit events flow through an injected
``announce`` callback so this module stays free of console imports; the router
wires it to the unified activity log.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

LOGGER = logging.getLogger(__name__)

MANAGED_FILE_PATH = Path("data/agents/managed.json")

#: What a managed agent is allowed to do. This is the whole vocabulary:
#: anything not listed here is rejected at the boundary, and financial
#: authority (authorize, order, token, portfolio, live execution) has no
#: member at all, so it cannot be selected, stored, or served.
CAPABILITY_ALLOWLIST = frozenset(
    {
        "READ_MARKET_DATA",
        "READ_HISTORICAL_DATA",
        "READ_DATASETS",
        "RUN_RESEARCH",
        "RUN_BACKTEST",
        "RUN_SIMULATION",
        "ANALYZE_STRATEGY",
        "PROPOSE_STRATEGY",
        "RISK_RESEARCH",
        "DATA_QUALITY_ANALYSIS",
        "GENERATE_REPORT",
    }
)

#: Data the agent may inspect. Closed for the same reason as capabilities.
DATA_SCOPE_ALLOWLIST = frozenset(
    {
        "MARKET_DATA",
        "HISTORICAL_DATA",
        "DATASETS",
        "STRATEGIES",
        "RESEARCH_OUTPUTS",
        "RISK_STATE",
    }
)

#: Research areas the agent may work in. Closed likewise.
RESEARCH_SCOPE_ALLOWLIST = frozenset(
    {
        "REGIME",
        "CALIBRATION",
        "ENSEMBLE",
        "COSTS",
        "RISK",
        "DATA_QUALITY",
        "STRATEGY_DESIGN",
    }
)

_CREDENTIAL_REF_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _\-]{0,63}$")


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ManagedAgentError(ValueError):
    """Raised when a managed-agent mutation is invalid or forbidden."""


def _require_name(name: str) -> str:
    clean = name.strip()
    if not _NAME_RE.match(clean):
        raise ManagedAgentError(
            "Agent name must be 1-64 chars: letters, digits, space, _ or -"
        )
    return clean


def _require_subset(values: tuple[str, ...] | list[str], allowed: frozenset[str], field: str) -> tuple[str, ...]:
    items = tuple(values or ())
    unknown = [v for v in items if v not in allowed]
    if unknown:
        raise ManagedAgentError(
            f"Unknown {field}: {unknown}. Allowed: {sorted(allowed)}"
        )
    if len(set(items)) != len(items):
        raise ManagedAgentError(f"Duplicate entries in {field}")
    return items


def _require_credential_ref(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    if not _CREDENTIAL_REF_RE.match(clean):
        raise ManagedAgentError(
            "credential_ref must be an environment variable NAME (A-Z, 0-9, _); "
            "never a secret value"
        )
    return clean


@dataclass
class ManagedAgent:
    """One managed research agent. Proposal-only by construction."""

    agent_id: str
    name: str
    description: str
    agent_type: str
    provider: str
    model: str
    system_instructions: str
    capabilities: tuple[str, ...]
    data_scopes: tuple[str, ...]
    research_scopes: tuple[str, ...]
    timeout_s: float
    max_concurrency: int
    credential_ref: str | None
    enabled: bool
    status: str
    current_config_version: int
    created_at: str
    updated_at: str
    archived_at: str | None = None
    last_run_at: str | None = None
    last_error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentConfigVersion:
    """One immutable configuration snapshot. History is append-only."""

    agent_id: str
    version: int
    snapshot: dict[str, Any]
    reason: str
    created_at: str = field(default_factory=_now)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentRun:
    """One recorded run, bound to the exact config version that produced it."""

    run_id: str
    agent_id: str
    config_version: int
    status: str  # STARTED | COMPLETED | FAILED
    started_at: str = field(default_factory=_now)
    finished_at: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


AGENT_TYPES = ("RESEARCH", "ANALYSIS", "BACKTEST", "SIMULATION", "REPORT")
AGENT_STATUSES = ("DISABLED", "IDLE", "RUNNING", "ERROR", "ARCHIVED")
RUN_STATUSES = ("STARTED", "COMPLETED", "FAILED")

#: Fields whose change defines a new configuration version. Status flips
#: (enable/disable/archive) and run bookkeeping never bump the version.
VERSIONED_FIELDS = (
    "name",
    "description",
    "agent_type",
    "provider",
    "model",
    "system_instructions",
    "capabilities",
    "data_scopes",
    "research_scopes",
    "timeout_s",
    "max_concurrency",
    "credential_ref",
)


class ManagedAgentStore:
    """Durable store for managed agents, versions, and runs."""

    def __init__(
        self,
        *,
        path: Path | None = None,
        announce: Callable[[str, str], None] | None = None,
    ) -> None:
        self._path = path or MANAGED_FILE_PATH
        self._announce = announce or (lambda _kind, _summary: None)
        self._agents: dict[str, ManagedAgent] = {}
        self._versions: dict[str, list[AgentConfigVersion]] = {}
        self._runs: dict[str, list[AgentRun]] = {}
        self._load()

    # -- reads ----------------------------------------------------------

    def list_agents(self, *, include_archived: bool = False) -> list[ManagedAgent]:
        agents = list(self._agents.values())
        if not include_archived:
            agents = [a for a in agents if a.archived_at is None]
        return sorted(agents, key=lambda a: a.created_at)

    def get(self, agent_id: str) -> ManagedAgent | None:
        return self._agents.get(agent_id)

    def require(self, agent_id: str) -> ManagedAgent:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise ManagedAgentError(f"Unknown agent '{agent_id}'")
        return agent

    def versions(self, agent_id: str) -> list[AgentConfigVersion]:
        self.require(agent_id)
        return list(self._versions.get(agent_id, []))

    def runs(self, agent_id: str, *, limit: int = 50) -> list[AgentRun]:
        self.require(agent_id)
        return list(reversed(self._runs.get(agent_id, [])))[:limit]

    # -- mutations ------------------------------------------------------

    def create(
        self,
        *,
        name: str,
        description: str = "",
        agent_type: str = "RESEARCH",
        provider: str = "",
        model: str = "",
        system_instructions: str = "",
        capabilities: tuple[str, ...] | list[str] = (),
        data_scopes: tuple[str, ...] | list[str] = (),
        research_scopes: tuple[str, ...] | list[str] = (),
        timeout_s: float = 300.0,
        max_concurrency: int = 1,
        credential_ref: str | None = None,
    ) -> ManagedAgent:
        """Create an agent. New agents are always DISABLED: activation is an
        explicit operator act, never a side effect of creation."""
        clean_name = _require_name(name)
        if any(a.name.lower() == clean_name.lower() for a in self._agents.values()):
            raise ManagedAgentError(f"Agent name '{clean_name}' is already taken")
        if agent_type not in AGENT_TYPES:
            raise ManagedAgentError(
                f"Unknown agent_type '{agent_type}'. Allowed: {list(AGENT_TYPES)}"
            )
        if timeout_s <= 0:
            raise ManagedAgentError("timeout_s must be positive")
        if max_concurrency < 1:
            raise ManagedAgentError("max_concurrency must be at least 1")
        agent = ManagedAgent(
            agent_id=uuid4().hex,
            name=clean_name,
            description=description.strip(),
            agent_type=agent_type,
            provider=provider.strip(),
            model=model.strip(),
            system_instructions=system_instructions,
            capabilities=_require_subset(capabilities, CAPABILITY_ALLOWLIST, "capabilities"),
            data_scopes=_require_subset(data_scopes, DATA_SCOPE_ALLOWLIST, "data_scopes"),
            research_scopes=_require_subset(research_scopes, RESEARCH_SCOPE_ALLOWLIST, "research_scopes"),
            timeout_s=timeout_s,
            max_concurrency=max_concurrency,
            credential_ref=_require_credential_ref(credential_ref),
            enabled=False,
            status="DISABLED",
            current_config_version=1,
            created_at=_now(),
            updated_at=_now(),
        )
        self._agents[agent.agent_id] = agent
        self._versions[agent.agent_id] = [
            AgentConfigVersion(
                agent_id=agent.agent_id,
                version=1,
                snapshot=_config_snapshot(agent),
                reason="created",
            )
        ]
        self._runs[agent.agent_id] = []
        self._save()
        self._announce("MANAGED_AGENT_CREATED", f"Managed agent '{clean_name}' created (disabled)")
        return agent

    def update(self, agent_id: str, *, reason: str = "edited", **fields: Any) -> ManagedAgent:
        """Edit an agent. Config changes append a version; history is never rewritten."""
        agent = self.require_active(agent_id)
        unknown = [k for k in fields if k not in VERSIONED_FIELDS]
        if unknown:
            raise ManagedAgentError(f"Cannot edit {unknown}: not versioned agent fields")
        if "name" in fields:
            clean = _require_name(str(fields["name"]))
            if any(
                a.agent_id != agent_id and a.name.lower() == clean.lower()
                for a in self._agents.values()
            ):
                raise ManagedAgentError(f"Agent name '{clean}' is already taken")
            fields["name"] = clean
        if "capabilities" in fields:
            fields["capabilities"] = _require_subset(
                fields["capabilities"], CAPABILITY_ALLOWLIST, "capabilities"
            )
        if "data_scopes" in fields:
            fields["data_scopes"] = _require_subset(
                fields["data_scopes"], DATA_SCOPE_ALLOWLIST, "data_scopes"
            )
        if "research_scopes" in fields:
            fields["research_scopes"] = _require_subset(
                fields["research_scopes"], RESEARCH_SCOPE_ALLOWLIST, "research_scopes"
            )
        if "credential_ref" in fields:
            fields["credential_ref"] = _require_credential_ref(fields["credential_ref"])
        if "agent_type" in fields and fields["agent_type"] not in AGENT_TYPES:
            raise ManagedAgentError(f"Unknown agent_type '{fields['agent_type']}'")
        if "timeout_s" in fields and not fields["timeout_s"] > 0:
            raise ManagedAgentError("timeout_s must be positive")
        if "max_concurrency" in fields and not fields["max_concurrency"] >= 1:
            raise ManagedAgentError("max_concurrency must be at least 1")
        changed = False
        for key, value in fields.items():
            current = getattr(agent, key)
            normalized = tuple(value) if isinstance(current, tuple) else value
            if normalized != current:
                setattr(agent, key, normalized)
                changed = True
        agent.updated_at = _now()
        if changed:
            agent.current_config_version += 1
            self._versions[agent.agent_id].append(
                AgentConfigVersion(
                    agent_id=agent.agent_id,
                    version=agent.current_config_version,
                    snapshot=_config_snapshot(agent),
                    reason=reason,
                )
            )
        self._save()
        self._announce(
            "MANAGED_AGENT_UPDATED",
            f"Managed agent '{agent.name}' edited (v{agent.current_config_version})",
        )
        return agent

    def set_enabled(self, agent_id: str, enabled: bool) -> ManagedAgent:
        agent = self.require_active(agent_id)
        agent.enabled = enabled
        agent.status = "IDLE" if enabled else "DISABLED"
        if enabled:
            agent.last_error = None
        agent.updated_at = _now()
        self._save()
        self._announce(
            "MANAGED_AGENT_ENABLED" if enabled else "MANAGED_AGENT_DISABLED",
            f"Managed agent '{agent.name}' {'enabled' if enabled else 'disabled'}",
        )
        return agent

    def duplicate(self, agent_id: str, *, name: str) -> ManagedAgent:
        """Clone safe configuration under a new id. The clone starts DISABLED
        with a fresh v1 history: runs and evidence stay with the original."""
        source = self.require(agent_id)
        if source.archived_at is not None:
            raise ManagedAgentError("Cannot duplicate an archived agent; restore it first")
        return self.create(
            name=name,
            description=f"Copy of {source.name}. {source.description}".strip(),
            agent_type=source.agent_type,
            provider=source.provider,
            model=source.model,
            system_instructions=source.system_instructions,
            capabilities=source.capabilities,
            data_scopes=source.data_scopes,
            research_scopes=source.research_scopes,
            timeout_s=source.timeout_s,
            max_concurrency=source.max_concurrency,
            credential_ref=source.credential_ref,
        )

    def archive(self, agent_id: str) -> ManagedAgent:
        """Soft-delete: the agent disappears from the roster but every run,
        version, and proposal stays queryable."""
        agent = self.require(agent_id)
        if agent.archived_at is not None:
            raise ManagedAgentError(f"Agent '{agent.name}' is already archived")
        agent.archived_at = _now()
        agent.enabled = False
        agent.status = "ARCHIVED"
        agent.updated_at = _now()
        self._save()
        self._announce("MANAGED_AGENT_ARCHIVED", f"Managed agent '{agent.name}' archived")
        return agent

    def hard_delete(self, agent_id: str, *, confirm: bool = False) -> str:
        """Destroy an agent and all its history. Only permitted when there is
        no history to preserve: never run, a single v1 config, and an explicit
        confirmation. Everything else must be archived, not deleted."""
        agent = self.require(agent_id)
        if not confirm:
            raise ManagedAgentError(
                f"Hard delete of '{agent.name}' requires explicit confirmation"
            )
        if self._runs.get(agent_id):
            raise ManagedAgentError(
                f"Cannot hard-delete '{agent.name}': run history exists; archive instead"
            )
        if len(self._versions.get(agent_id, [])) > 1:
            raise ManagedAgentError(
                f"Cannot hard-delete '{agent.name}': configuration history exists; "
                "archive instead"
            )
        name = agent.name
        del self._agents[agent_id]
        self._versions.pop(agent_id, None)
        self._runs.pop(agent_id, None)
        self._save()
        self._announce("MANAGED_AGENT_DELETED", f"Managed agent '{name}' hard-deleted")
        return name

    def require_active(self, agent_id: str) -> ManagedAgent:
        agent = self.require(agent_id)
        if agent.archived_at is not None:
            raise ManagedAgentError(f"Agent '{agent.name}' is archived")
        return agent

    # -- runs -----------------------------------------------------------

    def record_run_start(self, agent_id: str) -> AgentRun:
        """Record a run. Disabled or archived agents cannot start new work;
        an in-flight run is never disturbed — disabling only stops new starts."""
        agent = self.require_active(agent_id)
        if not agent.enabled:
            raise ManagedAgentError(f"Agent '{agent.name}' is disabled")
        run = AgentRun(
            run_id=uuid4().hex,
            agent_id=agent_id,
            config_version=agent.current_config_version,
            status="STARTED",
        )
        self._runs.setdefault(agent_id, []).append(run)
        agent.status = "RUNNING"
        agent.last_run_at = run.started_at
        agent.updated_at = _now()
        self._save()
        self._announce(
            "MANAGED_AGENT_RUN_STARTED",
            f"Managed agent '{agent.name}' run started (v{run.config_version})",
        )
        return run

    def record_run_finish(self, run_id: str, *, ok: bool, error: str | None = None) -> AgentRun:
        for agent_id, runs in self._runs.items():
            for run in runs:
                if run.run_id == run_id:
                    if run.status != "STARTED":
                        raise ManagedAgentError(f"Run '{run_id}' is already finished")
                    run.status = "COMPLETED" if ok else "FAILED"
                    run.finished_at = _now()
                    run.error = None if ok else (error or "unknown error")
                    agent = self._agents[agent_id]
                    agent.status = "IDLE" if ok else "ERROR"
                    agent.last_error = run.error
                    agent.updated_at = _now()
                    self._save()
                    self._announce(
                        "MANAGED_AGENT_RUN_FINISHED",
                        f"Managed agent '{agent.name}' run {run.status.lower()}",
                    )
                    return run
        raise ManagedAgentError(f"Unknown run '{run_id}'")

    # -- persistence ----------------------------------------------------

    def as_dict(self) -> dict[str, Any]:
        return {
            "agents": [a.as_dict() for a in self._agents.values()],
            "versions": [v.as_dict() for vs in self._versions.values() for v in vs],
            "runs": [r.as_dict() for rs in self._runs.values() for r in rs],
        }

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(self.as_dict(), indent=2, default=list)
            tmp_fd, tmp_name = tempfile.mkstemp(
                dir=str(self._path.parent), prefix=self._path.name + ".", suffix=".tmp"
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                os.replace(tmp_name, self._path)
            except OSError:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
        except OSError as exc:
            LOGGER.warning("Could not persist managed agents to %s: %s", self._path, exc)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            LOGGER.warning("Could not read managed agents %s: %s", self._path, exc)
            return
        try:
            for raw in data.get("agents", []):
                agent = ManagedAgent(
                    **{**raw, "capabilities": tuple(raw.get("capabilities", ())),
                       "data_scopes": tuple(raw.get("data_scopes", ())),
                       "research_scopes": tuple(raw.get("research_scopes", ()))},
                )
                self._agents[agent.agent_id] = agent
            for raw in data.get("versions", []):
                self._versions.setdefault(raw["agent_id"], []).append(
                    AgentConfigVersion(**raw)
                )
            for raw in data.get("runs", []):
                self._runs.setdefault(raw["agent_id"], []).append(AgentRun(**raw))
        except (TypeError, KeyError) as exc:
            LOGGER.warning("Could not parse managed agents %s: %s", self._path, exc)
            self._agents = {}
            self._versions = {}
            self._runs = {}


def _config_snapshot(agent: ManagedAgent) -> dict[str, Any]:
    full = agent.as_dict()
    return {key: full[key] for key in VERSIONED_FIELDS}


__all__ = [
    "AGENT_STATUSES",
    "AGENT_TYPES",
    "CAPABILITY_ALLOWLIST",
    "DATA_SCOPE_ALLOWLIST",
    "MANAGED_FILE_PATH",
    "RESEARCH_SCOPE_ALLOWLIST",
    "VERSIONED_FIELDS",
    "AgentConfigVersion",
    "AgentRun",
    "ManagedAgent",
    "ManagedAgentError",
    "ManagedAgentStore",
]
