"""Official Upstox V3 Protobuf decoding into D08 feed updates."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from google.protobuf.message import DecodeError, Message

from .errors import UpstoxFeedError, UpstoxFeedErrorCode
from .instrument_keys import segment_of, validate_feed_key
from .messages import (
    MarketDepth,
    MarketDepthLevel,
    NormalizedFeedUpdate,
    UpdateKind,
    provider_greeks_version,
)
from .proto import FeedResponse


class UpstoxV3ProtobufDecoder:
    """Decode only the fields declared by the pinned official V3 schema."""

    def __init__(self) -> None:
        self._last_market_status: dict[str, str] = {}
        self._last_message_type: str | None = None
        self._last_current_timestamp: datetime | None = None

    @property
    def last_market_status(self) -> dict[str, str]:
        return dict(self._last_market_status)

    @property
    def last_message_type(self) -> str | None:
        return self._last_message_type

    @property
    def last_current_timestamp(self) -> datetime | None:
        return self._last_current_timestamp

    def decode(self, payload: bytes, *, received_at: datetime) -> tuple[NormalizedFeedUpdate, ...]:
        if not payload:
            raise UpstoxFeedError(UpstoxFeedErrorCode.MALFORMED_FRAME, "protobuf frame is empty")
        response = FeedResponse()
        try:
            response.ParseFromString(payload)
        except DecodeError as error:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.MALFORMED_FRAME,
                "protobuf frame does not match the pinned Upstox V3 schema",
            ) from error
        self._last_message_type = _enum_name(response, "type", response.type)
        self._last_current_timestamp = _milliseconds(response.currentTs, "currentTs")
        self._last_market_status = {
            segment: _map_enum_name(response.marketInfo, "segmentStatus", status)
            for segment, status in response.marketInfo.segmentStatus.items()
        }
        updates = [
            self._decode_feed(key, feed, received_at, self._last_current_timestamp)
            for key, feed in response.feeds.items()
        ]
        return tuple(sorted(updates, key=lambda item: item.instrument_key))

    def _decode_feed(
        self,
        key: str,
        feed: Message,
        received_at: datetime,
        default_timestamp: datetime | None,
    ) -> NormalizedFeedUpdate:
        validate_feed_key(key)
        union = feed.WhichOneof("FeedUnion")
        if union == "ltpc":
            values = _ltpc_values(feed.ltpc, default_timestamp)
        elif union == "fullFeed":
            branch = feed.fullFeed.WhichOneof("FullFeedUnion")
            if branch == "indexFF":
                values = _ltpc_values(feed.fullFeed.indexFF.ltpc, default_timestamp)
            elif branch == "marketFF":
                values = _market_values(feed.fullFeed.marketFF, default_timestamp)
            else:
                raise _malformed(key, "full feed has no selected union member")
        elif union == "firstLevelWithGreeks":
            values = _first_level_values(feed.firstLevelWithGreeks, default_timestamp)
        else:
            raise _malformed(key, "feed has no selected union member")
        return NormalizedFeedUpdate.model_validate(
            {
                "instrument_key": key,
                "kind": _kind(key),
                "received_at": received_at,
                "provider_timestamp": default_timestamp,
                **values,
            }
        )


def _kind(key: str) -> UpdateKind:
    return UpdateKind.INDEX if segment_of(key).endswith("INDEX") else UpdateKind.OPTION


def _ltpc_values(message: Message, fallback: datetime | None) -> dict[str, object]:
    timestamp = _milliseconds(message.ltt, "ltt") if message.ltt else fallback
    return {
        "exchange_timestamp": timestamp,
        "price_source_timestamp": timestamp,
        "last_traded_price": _positive_decimal(message.ltp, "ltp"),
        "close_price": _positive_decimal(message.cp, "cp"),
    }


def _market_values(message: Message, fallback: datetime | None) -> dict[str, object]:
    values = _ltpc_values(message.ltpc, fallback)
    quotes = list(message.marketLevel.bidAskQuote)
    values.update(_depth_values(quotes))
    values.update(_greek_values(message.optionGreeks) if message.HasField("optionGreeks") else {})
    values.update(
        volume=_non_negative_int(message.vtt, "vtt"),
        open_interest=_integral_float(message.oi, "oi"),
        implied_volatility=_non_negative_float(message.iv, "iv"),
    )
    values.update(
        depth_source_timestamp=fallback,
        volume_source_timestamp=fallback,
        oi_source_timestamp=fallback,
        iv_source_timestamp=fallback,
        greeks_source_timestamp=fallback,
    )
    return values


def _first_level_values(message: Message, fallback: datetime | None) -> dict[str, object]:
    values = _ltpc_values(message.ltpc, fallback)
    values.update(_depth_values([message.firstDepth]))
    values.update(_greek_values(message.optionGreeks))
    values.update(
        volume=_non_negative_int(message.vtt, "vtt"),
        open_interest=_integral_float(message.oi, "oi"),
        implied_volatility=_non_negative_float(message.iv, "iv"),
    )
    values.update(
        depth_source_timestamp=fallback,
        volume_source_timestamp=fallback,
        oi_source_timestamp=fallback,
        iv_source_timestamp=fallback,
        greeks_source_timestamp=fallback,
    )
    return values


def _depth_values(quotes: list[Message]) -> dict[str, object]:
    buys = tuple(
        MarketDepthLevel(
            price=_required_positive_decimal(item.bidP, "bidP"),
            quantity=_non_negative_int(item.bidQ, "bidQ"),
            orders=None,
        )
        for item in quotes
        if item.bidP > 0
    )
    sells = tuple(
        MarketDepthLevel(
            price=_required_positive_decimal(item.askP, "askP"),
            quantity=_non_negative_int(item.askQ, "askQ"),
            orders=None,
        )
        for item in quotes
        if item.askP > 0
    )
    depth = MarketDepth(buy_levels=buys, sell_levels=sells) if buys or sells else None
    first = quotes[0] if quotes else None
    return {
        "bid_price": _positive_decimal(first.bidP, "bidP") if first else None,
        "ask_price": _positive_decimal(first.askP, "askP") if first else None,
        "bid_quantity": _non_negative_int(first.bidQ, "bidQ") if first else None,
        "ask_quantity": _non_negative_int(first.askQ, "askQ") if first else None,
        "market_depth": depth,
    }


def _greek_values(message: Message) -> dict[str, object]:
    values = {
        "delta": _finite_float(message.delta, "delta"),
        "gamma": _non_negative_float(message.gamma, "gamma"),
        "theta": _finite_float(message.theta, "theta"),
        "vega": _non_negative_float(message.vega, "vega"),
        "rho": _finite_float(message.rho, "rho"),
        "greeks_method": "SOURCE_PROVIDED",
        "greeks_method_version": provider_greeks_version(),
    }
    return values


def _milliseconds(value: int, field: str) -> datetime | None:
    if value == 0:
        return None
    if value < 0:
        raise UpstoxFeedError(UpstoxFeedErrorCode.MALFORMED_FRAME, f"{field} is negative")
    try:
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    except (OverflowError, OSError, ValueError) as error:
        raise UpstoxFeedError(
            UpstoxFeedErrorCode.MALFORMED_FRAME, f"{field} is outside timestamp range"
        ) from error


def _positive_decimal(value: float, field: str) -> Decimal | None:
    number = _finite_float(value, field)
    return Decimal(str(number)) if number > 0 else None


def _required_positive_decimal(value: float, field: str) -> Decimal:
    number = _finite_float(value, field)
    if number <= 0:
        raise UpstoxFeedError(UpstoxFeedErrorCode.MALFORMED_FRAME, f"{field} is not positive")
    return Decimal(str(number))


def _finite_float(value: float, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise UpstoxFeedError(UpstoxFeedErrorCode.MALFORMED_FRAME, f"{field} is non-finite")
    return number


def _non_negative_float(value: float, field: str) -> float:
    number = _finite_float(value, field)
    if number < 0:
        raise UpstoxFeedError(UpstoxFeedErrorCode.MALFORMED_FRAME, f"{field} is negative")
    return number


def _non_negative_int(value: int, field: str) -> int:
    number = int(value)
    if number < 0:
        raise UpstoxFeedError(UpstoxFeedErrorCode.MALFORMED_FRAME, f"{field} is negative")
    return number


def _integral_float(value: float, field: str) -> int:
    number = _non_negative_float(value, field)
    if not number.is_integer():
        raise UpstoxFeedError(UpstoxFeedErrorCode.MALFORMED_FRAME, f"{field} is not integral")
    return int(number)


def _malformed(key: str, message: str) -> UpstoxFeedError:
    return UpstoxFeedError(UpstoxFeedErrorCode.MALFORMED_FRAME, f"{key}: {message}")


def _enum_name(message: Message, field: str, value: int) -> str:
    enum = message.DESCRIPTOR.fields_by_name[field].enum_type
    assert enum is not None
    return cast("str", enum.values_by_number[value].name)


def _map_enum_name(message: Message, field: str, value: int) -> str:
    entry = message.DESCRIPTOR.fields_by_name[field].message_type
    assert entry is not None
    enum = entry.fields_by_name["value"].enum_type
    assert enum is not None
    return cast("str", enum.values_by_number[value].name)


__all__ = ["UpstoxV3ProtobufDecoder"]
