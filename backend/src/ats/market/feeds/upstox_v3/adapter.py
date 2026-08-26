"""Credential-injected Upstox V3 market-data feed adapter core.

This adapter owns the conservative no-sequence safety model required because
broker feeds do not expose an authoritative replay sequence:

* disconnects invalidate continuity — every latch enters
  ``RESYNC_REQUIRED`` and only an explicit full reconciliation clears it;
* reconnect always performs a **full** re-subscription from the registry;
* silence ages feeds out to STALE and is never read as ``price unchanged``;
* malformed frames, unknown instruments, duplicate messages, and timestamp
  regressions are surfaced explicitly instead of being silently absorbed.

No credentials are embedded here: the bearer token arrives through
:class:`UpstoxFeedAuthorization` and only ever leaves its SecretStr inside
:func:`build_handshake_headers`, which the future transport consumes.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from ats.contracts.common import ClockProtocol, UTCDateTime
from ats.market.derivatives.providers.models import SourceFreshness

from .codec import FeedPayloadDecoder
from .config import UpstoxFeedAuthorization, UpstoxFeedConfiguration
from .errors import UpstoxFeedError, UpstoxFeedErrorCode
from .frames import subscribe_frame
from .freshness import FeedFreshnessBoard, LatchDecision
from .messages import NormalizedFeedUpdate
from .subscription import SubscriptionRegistry


class ConnectionState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    LIVE = "LIVE"
    RESYNC_REQUIRED = "RESYNC_REQUIRED"


@runtime_checkable
class FeedConnection(Protocol):
    """Transport seam implemented later by the real websocket edge."""

    def send_text(self, payload: str) -> None: ...

    def close(self) -> None: ...


@runtime_checkable
class ReconciliationSource(Protocol):
    """REST reconciliation seam used to prove a post-reconnect snapshot."""

    def full_snapshot(
        self, instrument_keys: tuple[str, ...]
    ) -> tuple[NormalizedFeedUpdate, ...]: ...


class FeedDiagnostics(BaseModel):
    """Read-only counters for observability without payload exposure."""

    frames_handled: int
    malformed_frames: int
    unknown_updates: int
    duplicate_updates: int
    regression_updates: int
    reconciliations_completed: int


class FrameOutcome(BaseModel):
    """Deterministic result of one decoded frame."""

    applied_updates: tuple[str, ...]
    duplicate_keys: tuple[str, ...]
    regression_keys: tuple[str, ...]
    unknown_keys: tuple[str, ...]


def build_handshake_headers(authorization: UpstoxFeedAuthorization) -> dict[str, str]:
    """The sole credential-unwrapping point; consumed by the transport edge only."""

    token = authorization.require_token()
    return {"Authorization": f"Bearer {token.get_secret_value()}"}


class UpstoxV3FeedAdapter:
    """Synchronous deterministic core driven by an injected connection."""

    def __init__(
        self,
        *,
        configuration: UpstoxFeedConfiguration,
        authorization: UpstoxFeedAuthorization,
        registry: SubscriptionRegistry,
        freshness_board: FeedFreshnessBoard,
        decoder: FeedPayloadDecoder,
        clock: ClockProtocol,
    ) -> None:
        self._configuration = configuration
        self._authorization = authorization
        self._registry = registry
        self._board = freshness_board
        self._decoder = decoder
        self._clock = clock
        self._state = ConnectionState.DISCONNECTED
        self._connection: FeedConnection | None = None
        self._latest: dict[str, NormalizedFeedUpdate] = {}
        self._frames_handled = 0
        self._malformed_frames = 0
        self._unknown_updates = 0
        self._duplicate_updates = 0
        self._regression_updates = 0
        self._reconciliations_completed = 0
        self._last_receipt_at: UTCDateTime | None = None

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def diagnostics(self) -> FeedDiagnostics:
        return FeedDiagnostics(
            frames_handled=self._frames_handled,
            malformed_frames=self._malformed_frames,
            unknown_updates=self._unknown_updates,
            duplicate_updates=self._duplicate_updates,
            regression_updates=self._regression_updates,
            reconciliations_completed=self._reconciliations_completed,
        )

    def connect(self, connection: FeedConnection) -> None:
        if self._state is not ConnectionState.DISCONNECTED:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.ALREADY_CONNECTED, "adapter already holds a connection"
            )
        try:
            self._authorization.require_token()
        except ValueError as exc:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.AUTHORIZATION_REQUIRED,
                "no Upstox bearer token has been injected",
            ) from exc
        self._connection = connection
        self._send_subscriptions()
        self._state = ConnectionState.LIVE

    def disconnect(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        self._enter_resync()

    def handle_frame(
        self, payload: bytes | str, *, received_at: UTCDateTime | None = None
    ) -> FrameOutcome:
        if self._state is ConnectionState.DISCONNECTED:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.NOT_CONNECTED, "adapter has no live connection"
            )
        stamp = received_at or self._clock.now()
        try:
            updates = self._decoder.decode(payload, received_at=stamp)
        except UpstoxFeedError:
            self._malformed_frames += 1
            raise
        self._frames_handled += 1
        self._last_receipt_at = stamp
        applied: list[str] = []
        duplicated: list[str] = []
        regressed: list[str] = []
        unknown: list[str] = []
        for update in updates:
            if not self._registry.is_registered(update.instrument_key):
                self._unknown_updates += 1
                unknown.append(update.instrument_key)
                continue
            decision: LatchDecision = self._board.latch(update.instrument_key).record(update)
            if decision.duplicate:
                self._duplicate_updates += 1
                duplicated.append(update.instrument_key)
                continue
            if decision.regression:
                self._regression_updates += 1
                regressed.append(update.instrument_key)
            applied.append(update.instrument_key)
            self._latest[update.instrument_key] = update
        return FrameOutcome(
            applied_updates=tuple(applied),
            duplicate_keys=tuple(duplicated),
            regression_keys=tuple(regressed),
            unknown_keys=tuple(unknown),
        )

    def latest(self, instrument_key: str) -> NormalizedFeedUpdate | None:
        return self._latest.get(instrument_key)

    def evaluate_freshness(self, *, now: UTCDateTime | None = None) -> SourceFreshness:
        if self._state is ConnectionState.DISCONNECTED:
            return SourceFreshness.UNKNOWN
        if self._state is ConnectionState.RESYNC_REQUIRED:
            return SourceFreshness.RESYNC_REQUIRED
        stamp = now or self._clock.now()
        aggregate = self._board.aggregate(stamp)
        if aggregate is SourceFreshness.FRESH and self._silence_exceeded(stamp):
            return SourceFreshness.STALE
        return aggregate

    def reconnect(self, connection: FeedConnection) -> None:
        """Full re-subscription; continuity is claimed only after reconciliation."""

        if self._connection is not None:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.ALREADY_CONNECTED,
                "previous connection was never closed",
            )
        try:
            self._authorization.require_token()
        except ValueError as exc:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.AUTHORIZATION_REQUIRED,
                "no Upstox bearer token has been injected",
            ) from exc
        self._connection = connection
        self._send_subscriptions()
        if len(self._registry) == 0:
            self._state = ConnectionState.DISCONNECTED
        elif self._state is ConnectionState.DISCONNECTED:
            self._state = ConnectionState.RESYNC_REQUIRED

    def complete_resync(
        self, source: ReconciliationSource, *, now: UTCDateTime | None = None
    ) -> None:
        if self._state is not ConnectionState.RESYNC_REQUIRED:
            raise UpstoxFeedError(UpstoxFeedErrorCode.RESYNC_INCOMPLETE, "resync is not pending")
        stamp = now or self._clock.now()
        keys = self._registry.instrument_keys()
        updates = source.full_snapshot(keys)
        by_key = {update.instrument_key: update for update in updates}
        missing = [key for key in keys if key not in by_key]
        extra = sorted(set(by_key) - set(keys))
        if missing or extra:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.RECONCILIATION_GAP,
                f"snapshot mismatch; missing={len(missing)} unexpected={len(extra)}",
            )
        for key in keys:
            update = by_key[key].model_copy(update={"received_at": stamp})
            state = self._board.latch(key).reconcile(update, now=stamp)
            if state is not SourceFreshness.FRESH:
                raise UpstoxFeedError(
                    UpstoxFeedErrorCode.RESYNC_INCOMPLETE,
                    f"{key} is {state.value} after reconciliation",
                )
            self._latest[key] = update
        self._reconciliations_completed += 1
        self._last_receipt_at = stamp
        self._state = ConnectionState.LIVE

    def _send_subscriptions(self) -> None:
        assert self._connection is not None
        for mode, keys in self._registry.snapshot_by_mode():
            frame = subscribe_frame(
                guid=self._configuration.client_guid, mode=mode, instrument_keys=keys
            )
            self._connection.send_text(frame)

    def _enter_resync(self) -> None:
        self._board.mark_all_resync_required()
        if len(self._registry) == 0:
            self._state = ConnectionState.DISCONNECTED
        else:
            self._state = ConnectionState.RESYNC_REQUIRED

    def _silence_exceeded(self, now: UTCDateTime) -> bool:
        if self._last_receipt_at is None:
            return True
        silence_ms = (now - self._last_receipt_at).total_seconds() * 1000
        return silence_ms > self._configuration.limits.maximum_silence_ms


__all__ = [
    "ConnectionState",
    "FeedConnection",
    "FeedDiagnostics",
    "FrameOutcome",
    "ReconciliationSource",
    "UpstoxV3FeedAdapter",
    "build_handshake_headers",
]
