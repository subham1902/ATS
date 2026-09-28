"""Operator-surface read providers.

The operator console may present a *live-looking* system panel, but it must not
claim READY when no runtime is actually attached. :class:`LiveControlPlaneReader`
therefore derives its state from the trading runtime provider when one is bound
and reports NOT_READY otherwise -- ``UNKNOWN`` must never be rendered as healthy.
"""

from __future__ import annotations

from ats.api.models import SystemReadModel
from ats.api.providers import ControlPlaneSnapshot, SnapshotControlPlaneReader
from ats.contracts.common import ClockProtocol, SystemClock


class LiveControlPlaneReader(SnapshotControlPlaneReader):
    """Operational reader: mirrors a bound runtime, otherwise reports NOT_READY."""

    def __init__(
        self,
        runtime_provider: object | None = None,
        clock: ClockProtocol | None = None,
    ) -> None:
        self._clock: ClockProtocol = clock or SystemClock()
        snapshot_system = self._derive_system(runtime_provider)
        super().__init__(
            ControlPlaneSnapshot(
                system=snapshot_system,
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

    def _derive_system(self, runtime_provider: object | None) -> SystemReadModel | None:
        from ats.api.models import ReadinessState
        from ats.contracts.domain.types import LossState
        from ats.contracts.governance.types import SystemState

        now = self._clock.now()
        attached = runtime_provider is not None
        ready = bool(attached and getattr(runtime_provider, "is_ready", False))
        return SystemReadModel(
            system_state=SystemState.READY if ready else SystemState.DEGRADED,
            system_state_version=1,
            readiness=ReadinessState.READY if ready else ReadinessState.DEGRADED,
            degradation_indicators=() if ready else ("RUNTIME_NOT_ATTACHED",),
            loss_state=LossState.NORMAL,
            active_policy_id=None,
            active_policy_version=None,
            active_campaign_id=None,
            active_campaign_version=None,
            authority_mode="A2_PAPER",
            reconciliation_active=bool(attached),
            halted=False,
            last_state_at=now,
            last_event_at=now,
        )


__all__ = ["LiveControlPlaneReader"]
