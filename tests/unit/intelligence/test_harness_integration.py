"""C3: DeepSeek Harness integration + governor-gated advisory wiring.

Covers:
* Pinned config builder fails fast on missing/unverified vendored build.
* Four scoped agent sessions register against the sidecar.
* MaterialAgentEvent routing reaches the responsible agent (advisory only).
* RuntimeChangeGovernor gate: safe de-escalation accepted; aggressive
  escalation, hard-risk increase, and direct order all rejected.
* /v1/harness/status reflects the real (active) harness state when wired.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from ats.contracts.common import SystemClock, UTCDateTime
from ats.intelligence.agent_governance import (
    RuntimeChangeCategory,
    RuntimeChangeGovernor,
    RuntimeChangeProposal,
    RuntimeChangeType,
)
from ats.intelligence.agent_governance.governor import RuntimeChangeOutcome
from ats.intelligence.harness.harness_integration import (
    A2HarnessIntegration,
    build_runtime_change_proposal,
)
from ats.intelligence.harness.models import (
    HarnessAgentType,
    MaterialAgentEvent,
)
from ats.intelligence.harness.runtime import HarnessRuntimeAdapter
from ats.trading_runtime.a2_runner import A2PaperSessionController, create_a2_paper_app
from ats.trading_runtime.modes import TradingMode
from fastapi.testclient import TestClient


class _FakeSidecar:
    """In-memory HarnessSidecar stub — no real subprocess is spawned."""

    def __init__(self) -> None:
        self.running = False
        self.sessions: list[str] = []
        self.prompts: list[tuple[str, str]] = []

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def healthy(self) -> bool:
        return self.running

    def create_session(self, *, cwd: str) -> str:
        sid = f"sid-{len(self.sessions) + 1}"
        self.sessions.append(sid)
        return sid

    def prompt(self, *, provider_session_id: str, prompt: str) -> str:
        self.prompts.append((provider_session_id, prompt))
        return f"ADVISORY[{provider_session_id}]: observed {prompt[:24]}"

    def cancel(self, *, provider_session_id: str) -> None:  # pragma: no cover
        return None


def _make_event(event_type: str) -> MaterialAgentEvent:
    return MaterialAgentEvent(
        event_type=event_type,
        occurred_at=SystemClock().now(),
        summary="material market event observed during paper session",
        evidence_refs=(uuid4(),),
    )


def _proposal(
    proposal_type: RuntimeChangeType,
    *,
    proposed_value: dict,
    current_value: dict | None = None,
    category: RuntimeChangeCategory = RuntimeChangeCategory.BOUNDED_RUNTIME_CONFIG,
) -> RuntimeChangeProposal:
    now: UTCDateTime = SystemClock().now()
    return build_runtime_change_proposal(
        agent_id="AGENT_X",
        session_id=uuid4(),
        proposal_type=proposal_type,
        category=category,
        target="system",
        requested_change={"action": proposal_type.value},
        current_value=current_value or {"mode": "PAPER"},
        proposed_value=proposed_value,
        reason="agent advisory",
        valid_until=now + timedelta(minutes=5),
        as_of=now,
        data_cutoff=now,
        created_at=now,
    )


def test_build_pinned_harness_configuration_fails_without_vendored_build(monkeypatch) -> None:
    # Simulate a vendored checkout whose commit does NOT match the pinned pin.
    import ats.intelligence.harness.harness_integration as mod

    class _FakeResult:
        stdout = "deadbeef00000000000000000000000000000000\n"

    def fake_run(*_args, **_kwargs):
        return _FakeResult()

    monkeypatch.setattr("subprocess.run", fake_run)
    try:
        mod.build_pinned_harness_configuration(harness_root="D:\\nonexistent\\harness")
    except RuntimeError as error:
        assert "HARNESS_COMMIT_MISMATCH" in str(error)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError for commit mismatch")


def test_harness_registers_four_agent_sessions_and_routes_events() -> None:
    sidecar = _FakeSidecar()
    adapter = HarnessRuntimeAdapter(sidecar=sidecar, clock=SystemClock())
    governor = RuntimeChangeGovernor(clock=SystemClock())
    integration = A2HarnessIntegration(governor=governor, adapter=adapter)
    integration.start()

    assert set(integration.agent_sessions) == {
        HarnessAgentType.SESSION_MARKET,
        HarnessAgentType.POSITION,
        HarnessAgentType.PORTFOLIO_ANALYST,
        HarnessAgentType.RESEARCH,
    }
    assert sidecar.healthy() is True

    # A market shock routes to SESSION_MARKET, not a financial mutation.
    advisories = integration.route_material_event(_make_event("PRICE_SHOCK_ON_NIFTY"))
    assert len(advisories) == 1
    agent_type, content = advisories[0]
    assert agent_type is HarnessAgentType.SESSION_MARKET
    assert content.startswith("ADVISORY[")


def test_governor_accepts_safe_deescalation_rejects_risk_broadening() -> None:
    governor = RuntimeChangeGovernor(clock=SystemClock())
    integration = A2HarnessIntegration(governor=governor)

    # 1) Safe de-escalation accepted.
    safe = integration.evaluate_proposal(
        _proposal(RuntimeChangeType.SET_SAFE_MODE, proposed_value={"mode": "SAFE"}),
        effective_mode=TradingMode.NORMAL,
    )
    assert safe.outcome is RuntimeChangeOutcome.APPLY

    # 2) Aggressive escalation rejected.
    aggressive = integration.evaluate_proposal(
        _proposal(RuntimeChangeType.SET_AGGRESSIVE_MODE, proposed_value={"mode": "AGGRESSIVE"}),
        effective_mode=TradingMode.NORMAL,
    )
    assert aggressive.outcome is RuntimeChangeOutcome.REJECT

    # 3) Hard-risk increase rejected.
    risk = integration.evaluate_proposal(
        _proposal(RuntimeChangeType.INCREASE_HARD_RISK, proposed_value={"risk": "HIGHER"}),
        effective_mode=TradingMode.NORMAL,
    )
    assert risk.outcome is RuntimeChangeOutcome.REJECT

    # 4) Direct order rejected (financial authority forbidden).
    order = integration.evaluate_proposal(
        _proposal(
            RuntimeChangeType.PLACE_ORDER,
            proposed_value={"symbol": "NIFTY", "qty": 10},
            category=RuntimeChangeCategory.FINANCIAL_AUTHORITY,
        ),
        effective_mode=TradingMode.NORMAL,
    )
    assert order.outcome is RuntimeChangeOutcome.REJECT


def test_harness_status_endpoint_reflects_real_active_state() -> None:
    sidecar = _FakeSidecar()
    adapter = HarnessRuntimeAdapter(sidecar=sidecar, clock=SystemClock())
    governor = RuntimeChangeGovernor(clock=SystemClock())
    integration = A2HarnessIntegration(governor=governor, adapter=adapter)
    integration.start()

    controller = A2PaperSessionController()
    controller.attach_harness_integration(integration)
    app = create_a2_paper_app(controller)
    client = TestClient(app)

    resp = client.get("/v1/harness/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["harness"]["state"] == "HEALTHY"
    assert data["harness"]["active_sessions"] == 4
    assert data["harness"]["live_money"] == "DISABLED"
    assert data["harness"]["execution_target"] == "PAPER"
    assert data["harness"]["real_orders_placed"] == 0
    assert len(data["agents"]) == 4
    assert all(agent["status"] == "ACTIVE" for agent in data["agents"])
    assert data["safety"]["REAL_ORDER_AUTHORITY"] == "NONE"
