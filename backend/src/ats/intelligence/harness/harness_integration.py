"""Pinned DeepSeek Harness integration for the A2 paper trading session.

This module wires the advisory-only Harness sidecar (``HarnessRuntimeAdapter``)
into the A2 runtime: it attaches the four scoped agent sessions, routes
``MaterialAgentEvent`` triggers to the responsible agent, and forces every
agent-proposed runtime change through the deterministic ``RuntimeChangeGovernor``.

Hard rules enforced here:
* The Harness is ADVISORY_ONLY. No endpoint, session, or proposal can place
  orders, mutate risk, or bypass A04. The governor rejects financial-authority
  and risk-broadening proposals outright.
* The pinned configuration is verified against the vendored commit
  ``b150a551b8d465e31e418e1b2eaf5e79bbb7d28e`` (dsh-v0.1.1-rc.2) before any
  subprocess is spawned.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final
from uuid import UUID, uuid4

from ats.contracts.common import ClockProtocol, SystemClock
from ats.intelligence.agent_governance import RuntimeChangeProposal
from ats.intelligence.agent_governance.governor import RuntimeChangeGovernor
from ats.intelligence.harness.agent_registry import (
    HARNESS_AGENT_REGISTRY,
    HarnessAgentPolicy,
)
from ats.intelligence.harness.models import (
    HarnessAgentType,
    HarnessRuntimeConfiguration,
    HarnessSession,
)
from ats.intelligence.harness.runtime import HarnessRuntimeAdapter
from ats.trading_runtime.modes import TradingMode

from .models import MaterialAgentEvent

_HARNESS_COMMIT: Final = "b150a551b8d465e31e418e1b2eaf5e79bbb7d28e"
_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_HARNESS_ROOT = _REPO_ROOT / "tools" / "deepseek-harness"
_DEFAULT_NODE_EXE = _REPO_ROOT / "toolchains" / "node-v24.19.0-win-x64" / "node.exe"
# Canonical fallback when running from a worktree where tools is not linked
_FALLBACK_HARNESS_ROOT = Path(r"D:\Projects\ATS\tools\deepseek-harness")
_FALLBACK_NODE_EXE = Path(r"D:\Projects\ATS\toolchains\node-v24.19.0-win-x64\node.exe")

# Keyword -> agent routing for MaterialAgentEvent.event_type (case-insensitive,
# first match wins). Defaults keep the four agents wired without caller config.
_DEFAULT_EVENT_ROUTING: Mapping[str, HarnessAgentType] = {
    "MARKET": HarnessAgentType.SESSION_MARKET,
    "PRICE_SHOCK": HarnessAgentType.SESSION_MARKET,
    "IV_SHOCK": HarnessAgentType.SESSION_MARKET,
    "OI_SHIFT": HarnessAgentType.SESSION_MARKET,
    "REGIME_CHANGE": HarnessAgentType.SESSION_MARKET,
    "POSITION": HarnessAgentType.POSITION,
    "THESIS_INVALIDATED": HarnessAgentType.POSITION,
    "PORTFOLIO": HarnessAgentType.PORTFOLIO_ANALYST,
    "STRATEGY_DEGRADATION": HarnessAgentType.PORTFOLIO_ANALYST,
    "EXECUTION_ANOMALY": HarnessAgentType.PORTFOLIO_ANALYST,
    "RESEARCH": HarnessAgentType.RESEARCH,
    "EXPERIMENT": HarnessAgentType.RESEARCH,
    "MODEL_DISAGREEMENT": HarnessAgentType.RESEARCH,
}

_REQUIRED_AGENT_TYPES: tuple[HarnessAgentType, ...] = (
    HarnessAgentType.SESSION_MARKET,
    HarnessAgentType.POSITION,
    HarnessAgentType.PORTFOLIO_ANALYST,
    HarnessAgentType.RESEARCH,
)

_CLOCK = SystemClock()


def _resolve_harness_root(explicit: str | Path | None) -> Path:
    if explicit:
        return Path(explicit)
    import os

    env = os.environ.get("ATS_HARNESS_ROOT")
    if env and Path(env).exists():
        return Path(env)
    if _DEFAULT_HARNESS_ROOT.exists():
        return _DEFAULT_HARNESS_ROOT
    return _FALLBACK_HARNESS_ROOT


def _resolve_node_exe(explicit: str | Path | None) -> Path:
    if explicit:
        return Path(explicit)
    if _DEFAULT_NODE_EXE.exists():
        return _DEFAULT_NODE_EXE
    return _FALLBACK_NODE_EXE


def build_pinned_harness_configuration(
    *,
    node_exe: str | Path | None = None,
    harness_root: str | Path | None = None,
) -> HarnessRuntimeConfiguration:
    """Construct the pinned Harness configuration, verifying the vendored build.

    Raises ``RuntimeError`` with a descriptive code when the vendored commit or
    the built binary/config is missing, so production startup fails fast rather
    than spawning an unverified process.
    """
    root = _resolve_harness_root(harness_root)
    node = _resolve_node_exe(node_exe)

    actual = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if actual != _HARNESS_COMMIT:
        raise RuntimeError("HARNESS_COMMIT_MISMATCH")

    binary = root / "packages" / "examples" / "acp-demo" / "lib" / "bin.js"
    config = root / "examples" / "acp-agent" / "cordis.yml"
    if not binary.is_file() or not config.is_file():
        raise RuntimeError("HARNESS_BUILD_MISSING")

    return HarnessRuntimeConfiguration(
        source_url="https://github.com/deepseek-ai/deepseek-harness",
        source_tag="dsh-v0.1.1-rc.2",
        source_commit=_HARNESS_COMMIT,
        license="MIT",
        command=(str(node), str(binary), "--config", str(config)),
        cwd=str(root),
    )


class A2HarnessIntegration:
    """Owns the Harness lifecycle + agent routing + governor gate for A2."""

    def __init__(
        self,
        *,
        governor: RuntimeChangeGovernor,
        adapter: HarnessRuntimeAdapter | None = None,
        agent_registry: Mapping[HarnessAgentType, HarnessAgentPolicy] = HARNESS_AGENT_REGISTRY,
        clock: ClockProtocol = _CLOCK,
        event_routing: Mapping[str, HarnessAgentType] | None = None,
        cwd: str = ".",
    ) -> None:
        self._governor = governor
        self._adapter = adapter
        self._agent_registry = agent_registry
        self._clock = clock
        self._event_routing = dict(event_routing or _DEFAULT_EVENT_ROUTING)
        self._cwd = cwd
        self._agent_sessions: dict[HarnessAgentType, HarnessSession] = {}

    @property
    def adapter(self) -> HarnessRuntimeAdapter | None:
        return self._adapter

    @property
    def agent_sessions(self) -> Mapping[HarnessAgentType, HarnessSession]:
        return self._agent_sessions

    def attach(self, adapter: HarnessRuntimeAdapter) -> None:
        self._adapter = adapter

    def start(self, *, cwd: str | None = None) -> None:
        """Start the sidecar and register the four scoped agent sessions."""
        if self._adapter is None:
            raise RuntimeError("HARNESS_ADAPTER_NOT_ATTACHED")
        self._adapter.start()
        self.register_agent_sessions(cwd=cwd)

    def stop(self) -> None:
        if self._adapter is not None:
            self._adapter.stop()
        self._agent_sessions = {}

    def register_agent_sessions(
        self, *, cwd: str | None = None
    ) -> Mapping[HarnessAgentType, HarnessSession]:
        if self._adapter is None:
            raise RuntimeError("HARNESS_ADAPTER_NOT_ATTACHED")
        resolved_cwd = cwd if cwd is not None else self._cwd
        self._agent_sessions = {}
        for agent_type in _REQUIRED_AGENT_TYPES:
            session = self._adapter.create_session(agent_type=agent_type, cwd=resolved_cwd)
            self._agent_sessions[agent_type] = session
        return self._agent_sessions

    def route_material_event(
        self, event: MaterialAgentEvent, *, agent_type: HarnessAgentType | None = None
    ) -> list[tuple[HarnessAgentType, str]]:
        """Dispatch a material event to the responsible agent(s); return advisories.

        The advisory text is produced by the Harness only; it never mutates
        runtime state. Any resulting runtime change must go through
        ``evaluate_proposal`` before it can be applied.
        """
        if self._adapter is None:
            raise RuntimeError("HARNESS_ADAPTER_NOT_ATTACHED")
        target = agent_type or self._resolve_agent(event.event_type)
        session = self._agent_sessions.get(target)
        if session is None:
            session = self._adapter.create_session(agent_type=target, cwd=self._cwd)
            self._agent_sessions[target] = session
        advisory = self._adapter.submit_material_event(session_id=session.session_id, event=event)
        return [(target, advisory.content)]

    def _resolve_agent(self, event_type: str) -> HarnessAgentType:
        upper = event_type.upper()
        for key, agent in self._event_routing.items():
            if key in upper:
                return agent
        return HarnessAgentType.SESSION_MARKET

    def evaluate_proposal(
        self, proposal: RuntimeChangeProposal, *, effective_mode: TradingMode
    ) -> Any:
        """Force every agent proposal through the deterministic governor."""
        return self._governor.evaluate(proposal, effective_mode=effective_mode)


def build_runtime_change_proposal(
    *,
    agent_id: str,
    session_id: UUID,
    proposal_type: Any,
    category: Any,
    target: str,
    requested_change: dict[str, Any],
    current_value: dict[str, Any],
    proposed_value: dict[str, Any],
    reason: str,
    valid_until: Any,
    as_of: Any,
    data_cutoff: Any,
    created_at: Any,
    evidence_refs: tuple[UUID, ...] = (),
    input_hash: str = "0" * 64,
) -> RuntimeChangeProposal:
    """Construct a tamper-evident proposal with a correct payload hash."""
    from ats.contracts.domain.hashing import compute_payload_hash

    proposed = RuntimeChangeProposal(
        proposal_id=uuid4(),
        agent_id=agent_id,
        session_id=session_id,
        created_at=created_at,
        as_of=as_of,
        data_cutoff=data_cutoff,
        category=category,
        proposal_type=proposal_type,
        target=target,
        requested_change=requested_change,
        current_value=current_value,
        proposed_value=proposed_value,
        reason=reason,
        evidence_refs=evidence_refs,
        input_hash=input_hash,
        valid_until=valid_until,
        payload_hash="0" * 64,
    )
    return proposed.model_copy(update={"payload_hash": compute_payload_hash(proposed)})


def build_a2_harness_integration(
    *,
    node_exe: str | Path | None = None,
    harness_root: str | Path | None = None,
    clock: ClockProtocol = _CLOCK,
) -> A2HarnessIntegration:
    """Build a real (subprocess-backed) Harness integration with a fresh governor."""
    from ats.intelligence.harness.subprocess_sidecar import AcpSubprocessSidecar

    configuration = build_pinned_harness_configuration(node_exe=node_exe, harness_root=harness_root)
    sidecar = AcpSubprocessSidecar(configuration)
    adapter = HarnessRuntimeAdapter(sidecar=sidecar, clock=clock)
    governor = RuntimeChangeGovernor(clock=clock)
    return A2HarnessIntegration(
        governor=governor,
        adapter=adapter,
        clock=clock,
        cwd=str(configuration.cwd),
    )


def attach_and_start_a2_harness(
    controller: Any,
    *,
    node_exe: str | Path | None = None,
    harness_root: str | Path | None = None,
    clock: ClockProtocol = _CLOCK,
) -> A2HarnessIntegration:
    """Build, attach, and start the pinned Harness into an A2 paper controller.

    Raises on a missing/unverified vendored build so production startup fails
    fast rather than spawning an unverified process. The Harness remains
    ADVISORY_ONLY; every proposed runtime change is governor-gated.
    """
    integration = build_a2_harness_integration(
        node_exe=node_exe, harness_root=harness_root, clock=clock
    )
    controller.attach_harness_integration(integration)
    integration.start()
    return integration


__all__ = [
    "A2HarnessIntegration",
    "attach_and_start_a2_harness",
    "build_a2_harness_integration",
    "build_pinned_harness_configuration",
    "build_runtime_change_proposal",
]
