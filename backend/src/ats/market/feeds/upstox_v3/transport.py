"""Bounded synchronous WebSocket transport for Upstox Market Data Feed V3."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Protocol
from urllib.parse import urlparse

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection
from websockets.sync.client import connect as websocket_connect

from .config import (
    MARKET_DATA_AUTHORIZE_URL,
    FeedMode,
    UpstoxFeedAuthorization,
    UpstoxFeedConfiguration,
)
from .errors import UpstoxFeedError, UpstoxFeedErrorCode
from .frames import subscribe_frame, unsubscribe_frame

_USER_AGENT = "ATS-Market-Data-V3/1.0"


class FeedAuthorizer(Protocol):
    def authorize_feed(self) -> str: ...


class UpstoxV3FeedAuthorizer:
    """Exchange a bearer secret for a single-use provider WebSocket URI."""

    def __init__(self, authorization: UpstoxFeedAuthorization) -> None:
        self._authorization = authorization

    def authorize_feed(self) -> str:
        try:
            token = self._authorization.require_token().get_secret_value()
        except ValueError as error:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.AUTHORIZATION_REQUIRED,
                "market-data authorization was not injected",
            ) from error
        request = urllib.request.Request(
            MARKET_DATA_AUTHORIZE_URL,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": _USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=10.0) as response:
                document = json.loads(response.read())
        except (OSError, ValueError, urllib.error.HTTPError) as error:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.AUTHORIZATION_FAILED,
                "Upstox V3 feed authorization failed",
            ) from error
        uri = document.get("data", {}).get("authorized_redirect_uri")
        if not isinstance(uri, str) or not _approved_socket_uri(uri):
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.AUTHORIZATION_FAILED,
                "authorization response did not contain an approved WSS endpoint",
            )
        return uri


class UpstoxV3WebSocketConnection:
    """D08 connection seam backed by one bounded websockets client."""

    def __init__(self, socket: ClientConnection) -> None:
        self._socket = socket

    def send_text(self, payload: str) -> None:
        """Send control JSON as a binary UTF-8 frame, as V3 requires."""

        self._socket.send(payload.encode("utf-8"))

    def receive(self, timeout_seconds: float) -> bytes | str:
        try:
            return self._socket.recv(timeout=timeout_seconds)
        except TimeoutError as error:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.RECEIVE_TIMEOUT, "market-data receive timed out"
            ) from error
        except ConnectionClosed as error:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.CONNECTION_CLOSED,
                "market-data WebSocket closed",
            ) from error

    def close(self) -> None:
        self._socket.close()


SocketFactory = Callable[..., ClientConnection]


class UpstoxV3Transport:
    """Authorize, connect and operate one bounded read-only V3 feed session."""

    def __init__(
        self,
        *,
        configuration: UpstoxFeedConfiguration,
        authorizer: FeedAuthorizer,
        socket_factory: SocketFactory = websocket_connect,
    ) -> None:
        self._configuration = configuration
        self._authorizer = authorizer
        self._socket_factory = socket_factory
        self._connection: UpstoxV3WebSocketConnection | None = None

    @property
    def connection(self) -> UpstoxV3WebSocketConnection | None:
        return self._connection

    def authorize_feed(self) -> None:
        """Validate authorization without retaining or exposing its one-time URI."""

        self._authorizer.authorize_feed()

    def connect(self) -> UpstoxV3WebSocketConnection:
        if self._connection is not None:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.ALREADY_CONNECTED, "transport already connected"
            )
        uri = self._authorizer.authorize_feed()
        limits = self._configuration.limits
        try:
            socket = self._socket_factory(
                uri,
                open_timeout=limits.connect_timeout_ms / 1000,
                close_timeout=2,
                ping_interval=20,
                ping_timeout=20,
                max_queue=limits.maximum_buffered_frames,
            )
        except Exception as error:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.CONNECTION_FAILED,
                "Upstox V3 WebSocket connection failed",
            ) from error
        self._connection = UpstoxV3WebSocketConnection(socket)
        return self._connection

    def subscribe(
        self, *, guid: str, mode: FeedMode, instrument_keys: tuple[str, ...]
    ) -> None:
        self._require_connection().send_text(
            subscribe_frame(guid=guid, mode=mode, instrument_keys=instrument_keys)
        )

    def unsubscribe(self, *, guid: str, instrument_keys: tuple[str, ...]) -> None:
        self._require_connection().send_text(
            unsubscribe_frame(guid=guid, instrument_keys=instrument_keys)
        )

    def receive(self) -> bytes | str:
        timeout = self._configuration.limits.receive_timeout_ms / 1000
        return self._require_connection().receive(timeout)

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def reconnect(self) -> UpstoxV3WebSocketConnection:
        self.close()
        return self.connect()

    def _require_connection(self) -> UpstoxV3WebSocketConnection:
        if self._connection is None:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.NOT_CONNECTED, "transport is not connected"
            )
        return self._connection


def _approved_socket_uri(uri: str) -> bool:
    parsed = urlparse(uri)
    host = parsed.hostname or ""
    return parsed.scheme == "wss" and (host == "upstox.com" or host.endswith(".upstox.com"))


__all__ = [
    "FeedAuthorizer",
    "UpstoxV3FeedAuthorizer",
    "UpstoxV3Transport",
    "UpstoxV3WebSocketConnection",
]
