from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from ats.market.feeds.upstox_v3 import (
    JsonFeedPayloadDecoder,
    ProtobufDecodingSeam,
    UpdateKind,
    UpstoxFeedError,
    UpstoxFeedErrorCode,
)

from . import helpers as fix

RECEIVED_AT = datetime(2026, 8, 24, 4, 0, 1, tzinfo=UTC)


class TestJsonDecoding:
    def test_ltpc_entry_is_normalized_with_scaling(self) -> None:
        frame = fix.ltpc_frame(
            instrument_key=fix.INDEX_KEY, ltp=2500150, cp=2495000, ltt_ms=1771000000000, ts_ms=0
        )
        (update,) = fix.decoder().decode(frame, received_at=RECEIVED_AT)
        assert update.instrument_key == fix.INDEX_KEY
        assert update.kind is UpdateKind.INDEX
        assert update.last_traded_price == Decimal("25001.50")
        assert update.close_price == Decimal("24950.00")
        assert update.exchange_timestamp is not None

    def test_full_option_entry_carries_provider_greeks_label(self) -> None:
        frame = fix.full_option_frame(
            instrument_key=fix.OPTION_KEY,
            ltp=12550,
            bid=12400,
            ask=12700,
            volume=1500,
            oi=90000,
            delta=-0.42,
            iv=13.5,
            ts_ms=1771000001000,
        )
        (update,) = fix.decoder().decode(frame, received_at=RECEIVED_AT)
        assert update.kind is UpdateKind.OPTION
        assert update.bid_price == Decimal("124.00")
        assert update.ask_price == Decimal("127.00")
        assert update.volume == 1500
        assert update.open_interest == 90000
        assert update.open_interest_change == 25
        assert update.delta == pytest.approx(-0.42)
        assert update.implied_volatility == pytest.approx(13.5)
        assert update.greeks_method == "SOURCE_PROVIDED"
        assert update.greeks_method_version == "UPSTOX-V3-FEED"

    def test_entry_without_greeks_is_unavailable(self) -> None:
        frame = fix.ltpc_frame(
            instrument_key=fix.OPTION_KEY, ltp=100, cp=90, ltt_ms=1, ts_ms=1
        )
        (update,) = fix.decoder().decode(frame, received_at=RECEIVED_AT)
        assert update.greeks_method == "UNAVAILABLE"
        assert update.greeks_method_version is None

    def test_depth_levels_are_scaled_and_ordered(self) -> None:
        frame = (
            f'{{"feeds": {{"{fix.OPTION_KEY}": {{"market_data": {{"depth": {{"buy": ['
            '{"price": 12400, "quantity": 300, "orders": 5},'
            '{"price": 12350, "quantity": 200, "orders": 2}'
            '], "sell": [{"price": 12600, "quantity": 400, "orders": 7}]}}}}, "ts": 5}'
        )
        (update,) = fix.decoder().decode(frame, received_at=RECEIVED_AT)
        assert update.market_depth is not None
        assert update.market_depth.buy_levels[0].price == Decimal("124.00")
        assert update.market_depth.buy_levels[1].quantity == 200
        assert update.market_depth.sell_levels[0].orders == 7

    def test_decoding_is_deterministic(self) -> None:
        frame = fix.full_option_frame(
            instrument_key=fix.OPTION_KEY,
            ltp=12550,
            bid=12400,
            ask=12700,
            volume=1500,
            oi=90000,
            delta=-0.42,
            iv=13.5,
            ts_ms=1771000001000,
        )
        first = fix.decoder().decode(frame, received_at=RECEIVED_AT)
        second = fix.decoder().decode(frame, received_at=RECEIVED_AT)
        assert first == second


class TestMalformedFrames:
    def test_non_json_payload_fails_closed(self) -> None:
        with pytest.raises(UpstoxFeedError) as error:
            fix.decoder().decode(b"\x00\x01\x02", received_at=RECEIVED_AT)
        assert error.value.code is UpstoxFeedErrorCode.MALFORMED_FRAME

    def test_missing_feeds_map_fails_closed(self) -> None:
        with pytest.raises(UpstoxFeedError):
            fix.decoder().decode('{"ts": 1}', received_at=RECEIVED_AT)

    @pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
    def test_nan_and_infinity_constants_are_rejected(self, constant: str) -> None:
        frame = f'{{"feeds": {{"{fix.INDEX_KEY}": {{"ltpc": {{"ltp": {constant}, "cp": 1}}}}}}}}'
        with pytest.raises(UpstoxFeedError) as error:
            fix.decoder().decode(frame, received_at=RECEIVED_AT)
        assert error.value.code is UpstoxFeedErrorCode.MALFORMED_FRAME

    def test_non_positive_price_is_rejected(self) -> None:
        frame = f'{{"feeds": {{"{fix.INDEX_KEY}": {{"ltpc": {{"ltp": 0, "cp": 1}}}}}}}}'
        with pytest.raises(UpstoxFeedError):
            fix.decoder().decode(frame, received_at=RECEIVED_AT)

    def test_fractional_quantity_rejected(self) -> None:
        frame = (
            f'{{"feeds": {{"{fix.INDEX_KEY}": {{"market_data": {{"vol": 12.34}}}}}}, "ts": 1}}'
        )
        with pytest.raises(UpstoxFeedError):
            fix.decoder().decode(frame, received_at=RECEIVED_AT)

    def test_bad_instrument_grammar_rejected(self) -> None:
        frame = '{"feeds": {"BADKEY": {"ltpc": {"ltp": 1, "cp": 1}}}, "ts": 1}'
        with pytest.raises(UpstoxFeedError):
            fix.decoder().decode(frame, received_at=RECEIVED_AT)

    def test_scale_above_one_is_refused(self) -> None:
        with pytest.raises(ValueError):
            JsonFeedPayloadDecoder(price_scale=Decimal("2"))


class TestProtobufSeam:
    def test_missing_compiled_decoder_fails_closed(self) -> None:
        seam = ProtobufDecodingSeam(decoder=None)
        with pytest.raises(UpstoxFeedError) as error:
            seam.decode(b"\x0a\x05hello", received_at=RECEIVED_AT)
        assert error.value.code is UpstoxFeedErrorCode.PROTOBUF_DECODER_REQUIRED

    def test_injected_decoder_is_used_verbatim(self) -> None:
        class StubDecoder:
            def decode(self, payload: bytes, *, received_at: datetime):  # type: ignore[no-untyped-def]
                return ()

        seam = ProtobufDecodingSeam(decoder=StubDecoder())
        assert seam.decode(b"whatever", received_at=RECEIVED_AT) == ()
