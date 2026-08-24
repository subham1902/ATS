"""Narrow read-only provider boundary for the A05 control surface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain.models import RiskDecision, StrategyPolicy, SupervisorAdvisory
from ats.contracts.governance.models import GovernanceContext, OpportunityCandidate, TradingCampaign

from .models import ActivityReadModel, AutonomyTokenReadModel, StreamEvent, SystemReadModel


@runtime_checkable
class ControlPlaneReader(Protocol):
    """Read-only application-facing seam; implementations own no API authority."""

    def get_system(self) -> SystemReadModel | None: ...

    def get_active_policy(self) -> StrategyPolicy | None: ...

    def get_policy(self, policy_id: UUID) -> StrategyPolicy | None: ...

    def get_campaign(self, campaign_id: UUID) -> TradingCampaign | None: ...

    def get_candidate(self, candidate_id: UUID) -> OpportunityCandidate | None: ...

    def get_governance_context(self, context_id: UUID) -> GovernanceContext | None: ...

    def get_risk_decision(self, decision_id: UUID) -> RiskDecision | None: ...

    def get_advisory(self, advisory_id: UUID) -> SupervisorAdvisory | None: ...

    def get_token(self, token_id: UUID) -> AutonomyTokenReadModel | None: ...

    def list_activity(self) -> tuple[ActivityReadModel, ...]: ...

    def stream_events(self) -> tuple[StreamEvent, ...]: ...


class ControlPlaneSnapshot(ATSBaseModel):
    """Explicit immutable snapshot adapter suitable for composition and tests."""

    system: SystemReadModel | None
    policies: tuple[StrategyPolicy, ...]
    active_policy_id: UUID | None
    campaigns: tuple[TradingCampaign, ...]
    candidates: tuple[OpportunityCandidate, ...]
    governance_contexts: tuple[GovernanceContext, ...]
    risk_decisions: tuple[RiskDecision, ...]
    advisories: tuple[SupervisorAdvisory, ...]
    tokens: tuple[AutonomyTokenReadModel, ...]
    activity: tuple[ActivityReadModel, ...]
    stream: tuple[StreamEvent, ...]


class SnapshotControlPlaneReader:
    """Read-only adapter over a caller-supplied immutable snapshot."""

    def __init__(self, snapshot: ControlPlaneSnapshot) -> None:
        self._snapshot = snapshot

    def get_system(self) -> SystemReadModel | None:
        return self._snapshot.system

    def get_active_policy(self) -> StrategyPolicy | None:
        if self._snapshot.active_policy_id is None:
            return None
        return self.get_policy(self._snapshot.active_policy_id)

    def get_policy(self, policy_id: UUID) -> StrategyPolicy | None:
        return next((item for item in self._snapshot.policies if item.policy_id == policy_id), None)

    def get_campaign(self, campaign_id: UUID) -> TradingCampaign | None:
        return next(
            (item for item in self._snapshot.campaigns if item.campaign_id == campaign_id),
            None,
        )

    def get_candidate(self, candidate_id: UUID) -> OpportunityCandidate | None:
        return next(
            (item for item in self._snapshot.candidates if item.candidate_id == candidate_id),
            None,
        )

    def get_governance_context(self, context_id: UUID) -> GovernanceContext | None:
        return next(
            (
                item
                for item in self._snapshot.governance_contexts
                if item.governance_context_id == context_id
            ),
            None,
        )

    def get_risk_decision(self, decision_id: UUID) -> RiskDecision | None:
        return next(
            (
                item
                for item in self._snapshot.risk_decisions
                if item.risk_decision_id == decision_id
            ),
            None,
        )

    def get_advisory(self, advisory_id: UUID) -> SupervisorAdvisory | None:
        return next(
            (item for item in self._snapshot.advisories if item.advisory_id == advisory_id),
            None,
        )

    def get_token(self, token_id: UUID) -> AutonomyTokenReadModel | None:
        return next((item for item in self._snapshot.tokens if item.token_id == token_id), None)

    def list_activity(self) -> tuple[ActivityReadModel, ...]:
        return self._snapshot.activity

    def stream_events(self) -> tuple[StreamEvent, ...]:
        return self._snapshot.stream


class EmptyControlPlaneReader(SnapshotControlPlaneReader):
    """Truthful default: live process, no attached runtime state and not ready."""

    def __init__(self) -> None:
        super().__init__(
            ControlPlaneSnapshot(
                system=None,
                policies=(),
                active_policy_id=None,
                campaigns=(),
                candidates=(),
                governance_contexts=(),
                risk_decisions=(),
                advisories=(),
                tokens=(),
                activity=(),
                stream=(),
            )
        )


__all__ = [
    "ControlPlaneReader",
    "ControlPlaneSnapshot",
    "EmptyControlPlaneReader",
    "SnapshotControlPlaneReader",
]
