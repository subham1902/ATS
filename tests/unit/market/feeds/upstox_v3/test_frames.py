from __future__ import annotations

import json

import pytest
from ats.market.feeds.upstox_v3 import (
    FeedMode,
    UpstoxFeedError,
    UpstoxFeedErrorCode,
    change_mode_frame,
    parse_control_acknowledgement,
    subscribe_frame,
    unsubscribe_frame,
)

from .helpers import INDEX_KEY, OPTION_KEY, SECOND_OPTION_KEY


class TestSubscribeFrames:
    def test_subscribe_frame_is_canonical_and_sorted(self) -> None:
        frame = subscribe_frame(
            guid="guid-1",
            mode=FeedMode.OPTION_GREEKS,
            instrument_keys=(OPTION_KEY, INDEX_KEY),
        )
        document = json.loads(frame)
        assert document["guid"] == "guid-1"
        assert document["method"] == "sub"
        assert document["data"]["mode"] == FeedMode.OPTION_GREEKS.value
        assert document["data"]["instrumentKeys"] == sorted([INDEX_KEY, OPTION_KEY])

    def test_identical_inputs_produce_byte_identical_frames(self) -> None:
        first = subscribe_frame(guid="g", mode=FeedMode.FULL, instrument_keys=(INDEX_KEY,))
        second = subscribe_frame(guid="g", mode=FeedMode.FULL, instrument_keys=(INDEX_KEY,))
        assert first == second

    def test_empty_key_set_is_refused(self) -> None:
        with pytest.raises(UpstoxFeedError) as error:
            subscribe_frame(guid="g", mode=FeedMode.FULL, instrument_keys=())
        assert error.value.code is UpstoxFeedErrorCode.EMPTY_SUBSCRIPTION

    def test_malformed_instrument_key_is_refused(self) -> None:
        with pytest.raises(UpstoxFeedError) as error:
            subscribe_frame(guid="g", mode=FeedMode.FULL, instrument_keys=("NOSEPARATOR",))
        assert error.value.code is UpstoxFeedErrorCode.MALFORMED_FRAME

    def test_duplicates_are_collapsed_deterministically(self) -> None:
        frame = subscribe_frame(
            guid="g",
            mode=FeedMode.LTPC,
            instrument_keys=(SECOND_OPTION_KEY, SECOND_OPTION_KEY),
        )
        assert json.loads(frame)["data"]["instrumentKeys"] == [SECOND_OPTION_KEY]


class TestUnsubscribeAndModeFrames:
    def test_unsubscribe_frame_shape(self) -> None:
        frame = unsubscribe_frame(guid="g", instrument_keys=(INDEX_KEY,))
        document = json.loads(frame)
        assert document["method"] == "unsub"
        assert "mode" not in document["data"]

    def test_mode_change_frame_carries_mode(self) -> None:
        frame = change_mode_frame(
            guid="g", mode=FeedMode.OPTION_GREEKS, instrument_keys=(OPTION_KEY,)
        )
        document = json.loads(frame)
        assert document["method"] == "change_mode"
        assert document["data"]["mode"] == FeedMode.OPTION_GREEKS.value


class TestControlAcknowledgements:
    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            ('{"method":"sub","status":"ok"}', ("sub", "ok")),
            (b'{"method":"mode","status":"error"}', ("mode", "error")),
        ],
    )
    def test_valid_acknowledgement(self, payload: object, expected: tuple[str, str]) -> None:
        assert parse_control_acknowledgement(payload) == expected  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "payload",
        ["not-json", "[1,2]", '{"method":1,"status":"ok"}', '{"status":"ok"}'],
    )
    def test_malformed_acknowledgement_fails_closed(self, payload: str) -> None:
        with pytest.raises(UpstoxFeedError) as error:
            parse_control_acknowledgement(payload)
        assert error.value.code is UpstoxFeedErrorCode.MALFORMED_FRAME
