from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from ats.intelligence.harness import (
    HarnessAgentType,
    HarnessRuntimeAdapter,
    HarnessRuntimeError,
    HarnessRuntimeState,
)


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 27, tzinfo=UTC)

    def now(self) -> datetime:
        self.value += timedelta(milliseconds=1)
        return self.value


class FakeSidecar:
    def __init__(self) -> None:
        self.running = False
        self.fail_start = False
        self.fail_prompt: Exception | None = None
        self.cancelled: list[str] = []

    def start(self) -> None:
        if self.fail_start:
            raise OSError("private raw startup detail")
        self.running = True

    def stop(self) -> None:
        self.running = False

    def healthy(self) -> bool:
        return self.running

    def create_session(self, *, cwd: str) -> str:
        assert Path(cwd).is_absolute()
        return "provider-session-1"

    def prompt(self, *, provider_session_id: str, prompt: str) -> str:
        assert provider_session_id == "provider-session-1"
        if self.fail_prompt is not None:
            raise self.fail_prompt
        return f"advisory:{prompt}"

    def cancel(self, *, provider_session_id: str) -> None:
        self.cancelled.append(provider_session_id)


def runtime(sidecar: FakeSidecar) -> HarnessRuntimeAdapter:
    return HarnessRuntimeAdapter(sidecar=sidecar, clock=Clock())


def test_start_health_session_resume_followup_cancel_and_stop(tmp_path: Path) -> None:
    sidecar = FakeSidecar()
    subject = runtime(sidecar)
    subject.start()
    assert subject.health().state is HarnessRuntimeState.HEALTHY

    session = subject.create_session(agent_type=HarnessAgentType.RESEARCH, cwd=str(tmp_path))
    assert subject.resume_session(session.session_id) == session
    answer = subject.fetch_advisory(session_id=session.session_id, question="explain")
    assert answer.content == "advisory:explain"
    assert answer.authority == "ADVISORY_ONLY"
    subject.cancel(session_id=session.session_id)
    assert sidecar.cancelled == ["provider-session-1"]

    subject.stop()
    assert subject.health().state is HarnessRuntimeState.STOPPED
    subject.start()
    with pytest.raises(HarnessRuntimeError, match="DURABLE_RESUME_UNSUPPORTED"):
        subject.resume_session(session.session_id)


def test_startup_failure_is_sanitized() -> None:
    sidecar = FakeSidecar()
    sidecar.fail_start = True
    subject = runtime(sidecar)
    with pytest.raises(HarnessRuntimeError) as error:
        subject.start()
    assert "private raw startup detail" not in str(error.value)
    assert subject.health().state is HarnessRuntimeState.DEGRADED


def test_timeout_and_malformed_response_fail_closed(tmp_path: Path) -> None:
    sidecar = FakeSidecar()
    subject = runtime(sidecar)
    subject.start()
    session = subject.create_session(agent_type=HarnessAgentType.POSITION, cwd=str(tmp_path))

    sidecar.fail_prompt = TimeoutError()
    with pytest.raises(HarnessRuntimeError, match="REQUEST_TIMEOUT"):
        subject.followup(session_id=session.session_id, prompt="check")

    sidecar.fail_prompt = None
    original = sidecar.prompt
    sidecar.prompt = lambda **_kwargs: ""
    with pytest.raises(HarnessRuntimeError, match="EMPTY_ADVISORY"):
        subject.followup(session_id=session.session_id, prompt="check")
    sidecar.prompt = original


def test_sidecar_crash_is_isolated_as_degraded(tmp_path: Path) -> None:
    sidecar = FakeSidecar()
    subject = runtime(sidecar)
    subject.start()
    subject.create_session(agent_type=HarnessAgentType.SESSION_MARKET, cwd=str(tmp_path))
    sidecar.running = False
    assert subject.health().state is HarnessRuntimeState.DEGRADED
    with pytest.raises(HarnessRuntimeError, match="SIDECAR_UNAVAILABLE"):
        subject.create_session(agent_type=HarnessAgentType.RESEARCH, cwd=str(tmp_path))
