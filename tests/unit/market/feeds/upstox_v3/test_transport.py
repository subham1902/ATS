from __future__ import annotations

import json
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request

import pytest
from ats.market.feeds.upstox_v3 import (
    FeedMode,
    UpstoxFeedAuthorization,
    UpstoxFeedConfiguration,
    UpstoxFeedError,
    UpstoxFeedErrorCode,
    UpstoxFeedLimits,
    UpstoxV3FeedAuthorizer,
    UpstoxV3Transport,
    WireFormat,
)
from pydantic import SecretStr

from .helpers import INDEX_KEY


class FakeAuthorizer:
    def __init__(self) -> None:
        self.calls = 0

    def authorize_feed(self) -> str:
        self.calls += 1
        return "wss://wsfeeder-api.upstox.com/private-one-time-uri"


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.closed = False

    def send(self, payload: bytes) -> None:
        self.sent.append(payload)

    def recv(self, timeout: float) -> bytes:
        assert timeout == 1
        return b"provider-frame"

    def close(self) -> None:
        self.closed = True


class FakeAuthorizationResponse:
    def __enter__(self) -> FakeAuthorizationResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return BytesIO(
            b'{"data":{"authorized_redirect_uri":'
            b'"wss://wsfeeder-api.upstox.com/private-one-time-uri"}}'
        ).read()


def configuration() -> UpstoxFeedConfiguration:
    return UpstoxFeedConfiguration(
        wire_format=WireFormat.PROTOBUF_BINARY,
        client_guid="d10-test",
        limits=UpstoxFeedLimits(
            maximum_silence_ms=500,
            stale_after_ms=1000,
            maximum_buffered_frames=4,
            receive_timeout_ms=1000,
        ),
    )


def test_connect_subscribe_receive_close_and_reconnect_are_bounded() -> None:
    authorizer = FakeAuthorizer()
    sockets: list[FakeSocket] = []
    captured: list[dict[str, object]] = []

    def factory(uri: str, **options: object):
        assert uri.startswith("wss://wsfeeder-api.upstox.com/")
        captured.append(options)
        socket = FakeSocket()
        sockets.append(socket)
        return socket

    transport = UpstoxV3Transport(
        configuration=configuration(), authorizer=authorizer, socket_factory=factory
    )
    transport.connect()
    transport.subscribe(guid="g", mode=FeedMode.FULL, instrument_keys=(INDEX_KEY,))
    assert json.loads(sockets[0].sent[0])["method"] == "sub"
    assert transport.receive() == b"provider-frame"
    transport.reconnect()
    assert sockets[0].closed is True
    assert authorizer.calls == 2
    assert captured[0]["max_queue"] == 4
    transport.close()


def test_operations_without_connection_fail_closed() -> None:
    transport = UpstoxV3Transport(
        configuration=configuration(), authorizer=FakeAuthorizer()
    )
    with pytest.raises(UpstoxFeedError) as error:
        transport.receive()
    assert error.value.code is UpstoxFeedErrorCode.NOT_CONNECTED


def test_authorizer_uses_required_headers_without_exposing_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[Request] = []

    def fake_urlopen(request: Request, *, timeout: float) -> FakeAuthorizationResponse:
        assert timeout == 10.0
        captured.append(request)
        return FakeAuthorizationResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    subject = UpstoxV3FeedAuthorizer(
        UpstoxFeedAuthorization(bearer_token=SecretStr("test-only-secret"))
    )

    assert subject.authorize_feed().startswith("wss://wsfeeder-api.upstox.com/")
    headers = dict(captured[0].header_items())
    assert headers["Authorization"] == "Bearer test-only-secret"
    assert headers["User-agent"] == "ATS-Market-Data-V3/1.0"


def test_authorizer_sanitizes_provider_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_urlopen(_request: Request, *, timeout: float) -> FakeAuthorizationResponse:
        raise HTTPError("https://provider.invalid", 403, "forbidden", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fail_urlopen)
    subject = UpstoxV3FeedAuthorizer(
        UpstoxFeedAuthorization(bearer_token=SecretStr("test-only-secret"))
    )

    with pytest.raises(UpstoxFeedError) as error:
        subject.authorize_feed()
    assert error.value.code is UpstoxFeedErrorCode.AUTHORIZATION_FAILED
    assert "test-only-secret" not in str(error.value)


def test_authorization_validation_never_echoes_rejected_credential() -> None:
    secret = "test-only-rejected-credential"

    with pytest.raises(ValueError) as error:
        UpstoxFeedAuthorization.model_validate({"access_token": secret})

    assert secret not in str(error.value)
