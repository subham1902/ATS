from __future__ import annotations

from ats.api.app import create_app
from ats.api.models import (
    ActivityReadModel,
    AutonomyTokenReadModel,
    ReadinessState,
    StreamEvent,
    SystemReadModel,
)
from ats.api.providers import ControlPlaneSnapshot, SnapshotControlPlaneReader
from ats.contracts.domain.types import LossState
from ats.contracts.governance.types import SystemState
from fastapi.testclient import TestClient

from tests.unit.contracts.domain.fixtures import make_contracts as make_a02
from tests.unit.kernel.fixtures import T0, make_kernel_fixture, uid


def make_api_fixture() -> dict[str, object]:
    kernel = make_kernel_fixture()
    token = make_a02()["AutonomyToken"]
    token_view = AutonomyTokenReadModel.from_contract(
        token,
        evaluation_time=token.issued_at,
    )
    system = SystemReadModel(
        system_state=SystemState.READY,
        system_state_version=1,
        readiness=ReadinessState.READY,
        degradation_indicators=(),
        loss_state=LossState.NORMAL,
        active_policy_id=kernel["policy"].policy_id,
        active_policy_version=kernel["policy"].policy_version,
        active_campaign_id=kernel["campaign"].campaign_id,
        active_campaign_version=kernel["campaign"].campaign_version,
        authority_mode="A2_PAPER",
        reconciliation_active=False,
        halted=False,
        last_state_at=T0,
        last_event_at=T0,
    )
    activity = ActivityReadModel(
        activity_id=uid(100),
        event_kind="RISK_EVALUATED",
        occurred_at=T0,
        correlation_id=uid(101),
        trace_id="1" * 32,
        aggregate_id=kernel["candidate"].candidate_id,
        aggregate_version=kernel["candidate"].candidate_version,
        summary="Risk decision available",
    )
    stream_event = StreamEvent(
        stream_event_id=uid(102),
        event_kind="RISK_EVALUATED",
        occurred_at=T0,
        correlation_id=uid(101),
        payload={"decision": "ALLOW", "candidate_id": str(kernel["candidate"].candidate_id)},
    )
    snapshot = ControlPlaneSnapshot(
        system=system,
        policies=(kernel["policy"],),
        active_policy_id=kernel["policy"].policy_id,
        campaigns=(kernel["campaign"],),
        candidates=(kernel["candidate"],),
        governance_contexts=(kernel["context"],),
        risk_decisions=(kernel["risk_decision"],),
        advisories=(kernel["advisory"],),
        tokens=(token_view,),
        activity=(activity,),
        stream=(stream_event,),
    )
    reader = SnapshotControlPlaneReader(snapshot)
    app = create_app(reader)
    return {
        **kernel,
        "token_contract": token,
        "token_view": token_view,
        "system_view": system,
        "activity": activity,
        "stream_event": stream_event,
        "snapshot": snapshot,
        "reader": reader,
        "app": app,
        "client": TestClient(app),
    }


__all__ = ["make_api_fixture"]
