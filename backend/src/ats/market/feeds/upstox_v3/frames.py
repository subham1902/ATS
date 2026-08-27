"""Deterministic outbound subscription-request construction.

Requests are plain JSON text frames matching the documented V3 control
grammar. Construction is a pure function of the registry state: identical
inputs always yield byte-identical frames, and no credential ever enters a
frame (authorization travels only in the injected handshake headers).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from .config import FeedMode
from .errors import UpstoxFeedError, UpstoxFeedErrorCode
from .instrument_keys import validate_feed_key


def subscribe_frame(
    *, guid: str, mode: FeedMode, instrument_keys: tuple[str, ...]
) -> str:
    return _control_frame(guid=guid, method="sub", mode=mode, instrument_keys=instrument_keys)


def unsubscribe_frame(*, guid: str, instrument_keys: tuple[str, ...]) -> str:
    if not instrument_keys:
        raise UpstoxFeedError(UpstoxFeedErrorCode.EMPTY_SUBSCRIPTION, "unsub requires keys")
    for key in instrument_keys:
        validate_feed_key(key)
    payload = _envelope(guid, "unsub")
    payload["data"] = {"instrumentKeys": _ordered_unique(instrument_keys)}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def change_mode_frame(
    *, guid: str, mode: FeedMode, instrument_keys: tuple[str, ...]
) -> str:
    if not instrument_keys:
        raise UpstoxFeedError(
            UpstoxFeedErrorCode.EMPTY_SUBSCRIPTION,
            "mode change requires at least one instrument key",
        )
    return _control_frame(
        guid=guid, method="change_mode", mode=mode, instrument_keys=instrument_keys
    )


def _control_frame(
    *, guid: str, method: str, mode: FeedMode, instrument_keys: tuple[str, ...]
) -> str:
    if not instrument_keys:
        raise UpstoxFeedError(
            UpstoxFeedErrorCode.EMPTY_SUBSCRIPTION,
            f"{method} requires at least one instrument key",
        )
    for key in instrument_keys:
        validate_feed_key(key)
    payload = _envelope(guid, method)
    payload["data"] = {
        "mode": mode.value,
        "instrumentKeys": _ordered_unique(instrument_keys),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _envelope(guid: str, method: str) -> dict[str, Any]:
    if not guid:
        raise ValueError("client guid must be non-empty")
    return {"guid": guid, "method": method}


def _ordered_unique(keys: tuple[str, ...]) -> list[str]:
    seen: dict[str, None] = {}
    for key in keys:
        validate_feed_key(key)
        seen[key] = None
    return sorted(seen)


def parse_control_acknowledgement(payload: str | bytes) -> tuple[str, str]:
    """Parse the documented control acknowledgement; malformed shapes fail closed."""

    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpstoxFeedError(
            UpstoxFeedErrorCode.MALFORMED_FRAME, "control frame is not valid JSON"
        ) from exc
    if not isinstance(document, dict):
        raise UpstoxFeedError(
            UpstoxFeedErrorCode.MALFORMED_FRAME, "control frame must be an object"
        )
    method = document.get("method")
    status = document.get("status")
    if not isinstance(method, str) or not isinstance(status, str):
        raise UpstoxFeedError(
            UpstoxFeedErrorCode.MALFORMED_FRAME,
            "control frame requires string method and status",
        )
    data: object = document.get("data")
    if isinstance(data, dict):
        for value in data.values():
            _reject_non_finite(value)
    return method, status


def _reject_non_finite(value: Any) -> None:
    if isinstance(value, float) and not Decimal(str(value)).is_finite():
        raise UpstoxFeedError(UpstoxFeedErrorCode.MALFORMED_FRAME, "non-finite number in frame")


__all__ = [
    "change_mode_frame",
    "parse_control_acknowledgement",
    "subscribe_frame",
    "unsubscribe_frame",
]
