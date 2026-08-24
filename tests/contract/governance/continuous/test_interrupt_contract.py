"""The event dispatcher uses the typed advisory stream rather than financial events."""

from __future__ import annotations

from ats.governance.continuous import DispatchStatus


def test_dispatch_states_are_closed() -> None:
    assert {item.value for item in DispatchStatus} == {"DISPATCHED", "IGNORED"}
