"""Explicit provider connection state machine for ATS market data feeds."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

LOGGER = logging.getLogger(__name__)


class ConnectionState(StrEnum):
    """Explicit lifecycle states for upstream market data provider connections."""

    DISCONNECTED = "DISCONNECTED"
    AUTHORIZING = "AUTHORIZING"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    SNAPSHOT_PENDING = "SNAPSHOT_PENDING"
    STREAMING = "STREAMING"
    DEGRADED = "DEGRADED"
    RECONNECTING = "RECONNECTING"
    STALE = "STALE"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


@dataclass(frozen=True, slots=True)
class StateTransition:
    """Immutable audit record of one state transition."""

    from_state: ConnectionState
    to_state: ConnectionState
    timestamp: datetime
    reason: str
    provider: str
    connection_id: str
    attempt_count: int


# Legal state transition graph enforcing deterministic progression
_LEGAL_TRANSITIONS: dict[ConnectionState, set[ConnectionState]] = {
    ConnectionState.DISCONNECTED: {
        ConnectionState.AUTHORIZING,
        ConnectionState.STOPPED,
    },
    ConnectionState.AUTHORIZING: {
        ConnectionState.CONNECTING,
        ConnectionState.FAILED,
        ConnectionState.RECONNECTING,
        ConnectionState.STOPPED,
    },
    ConnectionState.CONNECTING: {
        ConnectionState.CONNECTED,
        ConnectionState.FAILED,
        ConnectionState.RECONNECTING,
        ConnectionState.STOPPED,
    },
    ConnectionState.CONNECTED: {
        ConnectionState.SNAPSHOT_PENDING,
        ConnectionState.STREAMING,
        ConnectionState.DEGRADED,
        ConnectionState.RECONNECTING,
        ConnectionState.STOPPED,
    },
    ConnectionState.SNAPSHOT_PENDING: {
        ConnectionState.STREAMING,
        ConnectionState.DEGRADED,
        ConnectionState.RECONNECTING,
        ConnectionState.STOPPED,
    },
    ConnectionState.STREAMING: {
        ConnectionState.DEGRADED,
        ConnectionState.STALE,
        ConnectionState.RECONNECTING,
        ConnectionState.STOPPED,
    },
    ConnectionState.DEGRADED: {
        ConnectionState.RECONNECTING,
        ConnectionState.STREAMING,
        ConnectionState.STALE,
        ConnectionState.STOPPED,
    },
    ConnectionState.STALE: {
        ConnectionState.STREAMING,
        ConnectionState.DEGRADED,
        ConnectionState.RECONNECTING,
        ConnectionState.STOPPED,
    },
    ConnectionState.RECONNECTING: {
        ConnectionState.AUTHORIZING,
        ConnectionState.CONNECTING,
        ConnectionState.FAILED,
        ConnectionState.STOPPED,
    },
    ConnectionState.FAILED: {
        ConnectionState.AUTHORIZING,
        ConnectionState.RECONNECTING,
        ConnectionState.STOPPED,
    },
    ConnectionState.STOPPED: {
        ConnectionState.DISCONNECTED,
        ConnectionState.AUTHORIZING,
    },
}


class ConnectionStateMachine:
    """Deterministic, observable provider connection state machine."""

    def __init__(
        self,
        provider: str = "upstox",
        initial_state: ConnectionState = ConnectionState.DISCONNECTED,
    ) -> None:
        self.provider = provider
        self._current_state = initial_state
        self._history: list[StateTransition] = []
        self._generation_id = 1
        self._attempt_count = 0
        self._listeners: list[Callable[[StateTransition], None]] = []

    @property
    def current_state(self) -> ConnectionState:
        return self._current_state

    @property
    def state(self) -> ConnectionState:
        return self._current_state

    @property
    def is_terminal(self) -> bool:
        return self._current_state in (ConnectionState.STOPPED, ConnectionState.FAILED)

    @property
    def generation_id(self) -> int:
        return self._generation_id

    @property
    def attempt_count(self) -> int:
        return self._attempt_count

    @property
    def history(self) -> tuple[StateTransition, ...]:
        return tuple(self._history)

    def add_listener(self, callback: Callable[[StateTransition], None]) -> None:
        self._listeners.append(callback)

    def transition(self, to_state: ConnectionState, reason: str) -> StateTransition:
        """Execute a state transition if valid, updating generation and listeners."""
        allowed = _LEGAL_TRANSITIONS.get(self._current_state, set())
        if to_state not in allowed:
            error_msg = (
                f"Illegal state transition from {self._current_state} to {to_state} "
                f"for provider {self.provider} (reason: {reason})"
            )
            LOGGER.error(error_msg)
            raise ValueError(error_msg)

        if to_state == ConnectionState.CONNECTING:
            self._attempt_count += 1
        elif to_state == ConnectionState.STREAMING:
            self._attempt_count = 0
        elif to_state == ConnectionState.RECONNECTING:
            self._generation_id += 1

        transition_record = StateTransition(
            from_state=self._current_state,
            to_state=to_state,
            timestamp=datetime.now(UTC),
            reason=reason,
            provider=self.provider,
            connection_id=f"conn-gen-{self._generation_id}",
            attempt_count=self._attempt_count,
        )

        LOGGER.info(
            "Provider [%s] transitioned: %s -> %s (reason: %s, gen: %d, attempt: %d)",
            self.provider,
            self._current_state,
            to_state,
            reason,
            self._generation_id,
            self._attempt_count,
        )

        self._current_state = to_state
        self._history.append(transition_record)
        if len(self._history) > 1000:
            self._history = self._history[-500:]

        for listener in self._listeners:
            try:
                listener(transition_record)
            except Exception as e:
                LOGGER.warning("State listener failed: %s", e)

        return transition_record


ProviderState = ConnectionState
ProviderStateMachine = ConnectionStateMachine

__all__ = [
    "ConnectionState",
    "ConnectionStateMachine",
    "ProviderState",
    "ProviderStateMachine",
    "StateTransition",
]
