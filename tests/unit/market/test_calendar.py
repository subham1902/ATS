from __future__ import annotations

from datetime import UTC, datetime

import pytest
from ats.contracts.domain.types import SessionState
from ats.market import SessionOverride, nse_cash_alpha_v1_calendar


def at(hour: int, minute: int) -> datetime:
    return datetime(2024, 6, 3, hour, minute, tzinfo=UTC)


def test_calendar_derives_preopen_open_and_closed_from_session_profile() -> None:
    calendar = nse_cash_alpha_v1_calendar()
    assert calendar.state_at(at(3, 45)) is SessionState.PREOPEN
    assert calendar.state_at(at(3, 50)) is SessionState.OPEN
    assert calendar.state_at(at(9, 55)) is SessionState.OPEN
    assert calendar.state_at(at(2, 0)) is SessionState.CLOSED


def test_alignment_is_anchored_to_session_and_declared_state() -> None:
    calendar = nse_cash_alpha_v1_calendar()
    calendar.validate_bar_close(at(3, 45), SessionState.PREOPEN)
    calendar.validate_bar_close(at(3, 50), SessionState.OPEN)
    with pytest.raises(ValueError, match="PREOPEN"):
        calendar.validate_bar_close(at(3, 45), SessionState.OPEN)
    with pytest.raises(ValueError, match="explicit"):
        calendar.validate_bar_close(at(2, 0), SessionState.CLOSED)
    with pytest.raises(ValueError, match="five-minute"):
        calendar.validate_bar_close(at(3, 52), SessionState.OPEN)


@pytest.mark.parametrize("state", [SessionState.HALTED, SessionState.CLOSED])
def test_halted_and_closed_fixture_states_require_explicit_override(
    state: SessionState,
) -> None:
    timestamp = at(3, 55)
    calendar = nse_cash_alpha_v1_calendar().model_copy(
        update={"overrides": (SessionOverride(timestamp=timestamp, state=state),)}
    )
    assert calendar.state_at(timestamp) is state
    calendar.validate_bar_close(timestamp, state)
