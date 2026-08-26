"""ATS-owned Harness lifecycle; no method can mutate financial state."""

from __future__ import annotations

from uuid import UUID, uuid4

from ats.contracts.common import ClockProtocol

from .models import (
    HarnessAdvisory,
    HarnessAgentType,
    HarnessHealth,
    HarnessRuntimeError,
    HarnessRuntimeState,
    HarnessSession,
    MaterialAgentEvent,
)
from .protocols import HarnessSidecar


class HarnessRuntimeAdapter:
    def __init__(self, *, sidecar: HarnessSidecar, clock: ClockProtocol) -> None:
        self._sidecar = sidecar
        self._clock = clock
        self._state = HarnessRuntimeState.STOPPED
        self._sessions: dict[UUID, HarnessSession] = {}

    def start(self) -> None:
        self._state = HarnessRuntimeState.STARTING
        try:
            self._sidecar.start()
        except Exception as error:
            self._state = HarnessRuntimeState.DEGRADED
            raise HarnessRuntimeError("STARTUP_FAILED") from error
        self._state = (
            HarnessRuntimeState.HEALTHY if self._sidecar.healthy() else HarnessRuntimeState.DEGRADED
        )
        if self._state is not HarnessRuntimeState.HEALTHY:
            raise HarnessRuntimeError("HEALTH_CHECK_FAILED")

    def stop(self) -> None:
        try:
            self._sidecar.stop()
        finally:
            stamp = self._clock.now()
            self._sessions = {
                key: value.model_copy(update={"active": False, "last_activity_at": stamp})
                for key, value in self._sessions.items()
            }
            self._state = HarnessRuntimeState.STOPPED

    def health(self) -> HarnessHealth:
        running = self._sidecar.healthy() if self._state is HarnessRuntimeState.HEALTHY else False
        state = (
            self._state
            if running or self._state is HarnessRuntimeState.STOPPED
            else HarnessRuntimeState.DEGRADED
        )
        reasons = () if state is HarnessRuntimeState.HEALTHY else (state.value,)
        return HarnessHealth(
            state=state,
            checked_at=self._clock.now(),
            version="0.1.1-rc.2",
            active_sessions=sum(item.active for item in self._sessions.values()),
            reason_codes=reasons,
        )

    def create_session(self, *, agent_type: HarnessAgentType, cwd: str) -> HarnessSession:
        self._require_healthy()
        try:
            provider_id = self._sidecar.create_session(cwd=cwd)
        except Exception as error:
            raise HarnessRuntimeError("SESSION_CREATE_FAILED") from error
        stamp = self._clock.now()
        session = HarnessSession(
            session_id=uuid4(),
            provider_session_id=provider_id,
            agent_type=agent_type,
            created_at=stamp,
            last_activity_at=stamp,
            active=True,
        )
        self._sessions[session.session_id] = session
        return session

    def resume_session(self, session_id: UUID) -> HarnessSession:
        """Resume an adapter-owned live session; upstream has no durable reload API."""

        self._require_healthy()
        session = self._require_session(session_id)
        if not session.active:
            raise HarnessRuntimeError("DURABLE_RESUME_UNSUPPORTED")
        return session

    def followup(self, *, session_id: UUID, prompt: str) -> HarnessAdvisory:
        self._require_healthy()
        session = self._require_session(session_id)
        if not prompt.strip():
            raise ValueError("Harness prompt must not be empty")
        try:
            response = self._sidecar.prompt(
                provider_session_id=session.provider_session_id,
                prompt=prompt,
            )
        except TimeoutError as error:
            raise HarnessRuntimeError("REQUEST_TIMEOUT") from error
        except Exception as error:
            raise HarnessRuntimeError("MALFORMED_OR_FAILED_RESPONSE") from error
        if not response.strip():
            raise HarnessRuntimeError("EMPTY_ADVISORY")
        stamp = self._clock.now()
        self._sessions[session_id] = session.model_copy(update={"last_activity_at": stamp})
        return HarnessAdvisory(session_id=session_id, generated_at=stamp, content=response)

    def submit_material_event(
        self, *, session_id: UUID, event: MaterialAgentEvent
    ) -> HarnessAdvisory:
        evidence = ",".join(str(item) for item in event.evidence_refs)
        prompt = (
            f"MATERIAL_EVENT type={event.event_type} occurred_at={event.occurred_at.isoformat()} "
            f"evidence_refs=[{evidence}] summary={event.summary}"
        )
        return self.followup(session_id=session_id, prompt=prompt)

    def fetch_advisory(self, *, session_id: UUID, question: str) -> HarnessAdvisory:
        return self.followup(session_id=session_id, prompt=question)

    def cancel(self, *, session_id: UUID) -> None:
        session = self._require_session(session_id)
        try:
            self._sidecar.cancel(provider_session_id=session.provider_session_id)
        except Exception as error:
            raise HarnessRuntimeError("CANCEL_FAILED") from error

    def _require_healthy(self) -> None:
        if self._state is not HarnessRuntimeState.HEALTHY or not self._sidecar.healthy():
            self._state = HarnessRuntimeState.DEGRADED
            raise HarnessRuntimeError("SIDECAR_UNAVAILABLE")

    def _require_session(self, session_id: UUID) -> HarnessSession:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise HarnessRuntimeError("UNKNOWN_SESSION") from error


__all__ = ["HarnessRuntimeAdapter"]
