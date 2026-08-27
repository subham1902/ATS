"""Message-decoding boundary for Market Data Feed V3 payloads.

Two wire formats exist at this seam:

* ``JSON_TEXT`` — decoded here deterministically from the documented response
  grammar using only the standard library.
* ``PROTOBUF_BINARY`` — a hard boundary that requires an externally supplied
  compiled decoder. Without one, decoding fails closed with
  ``PROTOBUF_DECODER_REQUIRED``; ATS never guesses undocumented wire bytes.

All numeric parsing rejects NaN/Inf at the JSON layer itself. Provider prices
arrive as exact integers and are divided by an operator-configured
``price_scale``; no scale is ever assumed.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, model_validator

from ats.contracts.domain.types import PositiveDecimal

from .errors import UpstoxFeedError, UpstoxFeedErrorCode
from .instrument_keys import validate_feed_key
from .messages import (
    MarketDepth,
    MarketDepthLevel,
    NormalizedFeedUpdate,
    UpdateKind,
    provider_greeks_version,
)


@runtime_checkable
class BinaryFeedDecoder(Protocol):
    """Externally supplied compiled Protobuf decoder for binary frames."""

    def decode(
        self, payload: bytes, *, received_at: datetime
    ) -> tuple[NormalizedFeedUpdate, ...]: ...


class FeedPayloadDecoder(Protocol):
    def decode(
        self, payload: bytes | str, *, received_at: datetime
    ) -> tuple[NormalizedFeedUpdate, ...]: ...


class JsonFeedPayloadDecoder(BaseModel):
    """Deterministic decoder for the documented JSON text-frame grammar."""

    price_scale: PositiveDecimal

    @model_validator(mode="after")
    def require_conservative_scale(self) -> JsonFeedPayloadDecoder:
        if self.price_scale > 1:
            raise ValueError("price_scale cannot increase provider price units")
        return self

    def decode(
        self, payload: bytes | str, *, received_at: datetime
    ) -> tuple[NormalizedFeedUpdate, ...]:
        document = _strict_json(payload)
        feeds = document.get("feeds")
        if not isinstance(feeds, dict):
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.MALFORMED_FRAME, "feed frame requires feeds map"
            )
        default_ts = _millis(document.get("ts"), "top-level ts")
        updates: list[NormalizedFeedUpdate] = []
        for key, entry in feeds.items():
            validate_feed_key(str(key))
            updates.append(self._decode_entry(str(key), entry, received_at, default_ts))
        return tuple(updates)

    def _decode_entry(
        self,
        key: str,
        entry: object,
        received_at: datetime,
        default_ts: datetime | None,
    ) -> NormalizedFeedUpdate:
        if not isinstance(entry, dict):
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.MALFORMED_FRAME, f"feed entry for {key!r} must be an object"
            )
        exchange_ts = default_ts
        ltp: Decimal | None = None
        close: Decimal | None = None
        bid: Decimal | None = None
        ask: Decimal | None = None
        bid_quantity: int | None = None
        ask_quantity: int | None = None
        volume: int | None = None
        open_interest: int | None = None
        open_interest_change: int | None = None
        market_depth: MarketDepth | None = None
        greeks: dict[str, float | None] = {}

        ltpc = entry.get("ltpc")
        if ltpc is not None:
            if not isinstance(ltpc, dict):
                raise UpstoxFeedError(
                    UpstoxFeedErrorCode.MALFORMED_FRAME,
                    f"ltpc for {key!r} must be an object",
                )
            ltp = self._price(ltpc.get("ltp"), "ltp", key)
            close = self._price(ltpc.get("cp"), "cp", key)
            if ltpc.get("ltt") is not None:
                exchange_ts = _millis(ltpc.get("ltt"), f"ltt for {key!r}")

        market_data = entry.get("market_data")
        if market_data is not None:
            if not isinstance(market_data, dict):
                raise UpstoxFeedError(
                    UpstoxFeedErrorCode.MALFORMED_FRAME,
                    f"market_data for {key!r} must be an object",
                )
            bid = self._price(market_data.get("bid"), "bid", key)
            ask = self._price(market_data.get("ask"), "ask", key)
            volume = self._count(market_data.get("vol"), "vol", key)
            open_interest = self._count(market_data.get("oi"), "oi", key)
            open_interest_change = self._signed(
                market_data.get("change_oi"), "change_oi", key
            )
            bid_quantity = self._count(market_data.get("bid_qty"), "bid_qty", key)
            ask_quantity = self._count(market_data.get("ask_qty"), "ask_qty", key)
            depth = market_data.get("depth")
            if depth is not None:
                market_depth = self._depth(depth, key)

        option_greeks = entry.get("option_greeks")
        if option_greeks is not None:
            if not isinstance(option_greeks, dict):
                raise UpstoxFeedError(
                    UpstoxFeedErrorCode.MALFORMED_FRAME,
                    f"option_greeks for {key!r} must be an object",
                )
            greeks = {
                "implied_volatility": _finite_float(option_greeks.get("iv"), "iv", key),
                "delta": _finite_float(option_greeks.get("delta"), "delta", key),
                "gamma": _finite_float(option_greeks.get("gamma"), "gamma", key),
                "theta": _finite_float(option_greeks.get("theta"), "theta", key),
                "vega": _finite_float(option_greeks.get("vega"), "vega", key),
            }

        carried_greeks = any(value is not None for value in greeks.values())
        evidence = greeks if carried_greeks else {}
        return NormalizedFeedUpdate(
            instrument_key=key,
            kind=UpdateKind.INDEX if key.startswith("NSE_INDEX|") else UpdateKind.OPTION,
            received_at=received_at,
            exchange_timestamp=exchange_ts,
            provider_timestamp=default_ts,
            price_source_timestamp=exchange_ts if ltp is not None else None,
            depth_source_timestamp=default_ts if bid is not None or ask is not None else None,
            volume_source_timestamp=default_ts if volume is not None else None,
            oi_source_timestamp=default_ts if open_interest is not None else None,
            iv_source_timestamp=(
                default_ts if evidence.get("implied_volatility") is not None else None
            ),
            greeks_source_timestamp=default_ts if carried_greeks else None,
            last_traded_price=ltp,
            close_price=close,
            bid_price=bid,
            ask_price=ask,
            bid_quantity=bid_quantity,
            ask_quantity=ask_quantity,
            volume=volume,
            open_interest=open_interest,
            open_interest_change=open_interest_change,
            implied_volatility=evidence.get("implied_volatility"),
            delta=evidence.get("delta"),
            gamma=evidence.get("gamma"),
            theta=evidence.get("theta"),
            vega=evidence.get("vega"),
            market_depth=market_depth,
            greeks_method="SOURCE_PROVIDED" if carried_greeks else "UNAVAILABLE",
            greeks_method_version=provider_greeks_version() if carried_greeks else None,
        )

    def _price(self, value: object, field: str, key: str) -> Decimal | None:
        if value is None:
            return None
        number = _exact_number(value, field, key)
        try:
            scaled = number * self.price_scale
        except InvalidOperation as exc:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.MALFORMED_FRAME, f"{field} for {key!r} cannot be scaled"
            ) from exc
        if not scaled.is_finite():
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.MALFORMED_FRAME, f"{field} for {key!r} is non-finite"
            )
        if scaled <= 0:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.MALFORMED_FRAME,
                f"{field} for {key!r} must be positive",
            )
        return scaled

    def _count(self, value: object, field: str, key: str) -> int | None:
        if value is None:
            return None
        number = _exact_number(value, field, key)
        if number != number.to_integral_value():
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.MALFORMED_FRAME,
                f"{field} for {key!r} must be an integer",
            )
        return int(number)

    def _signed(self, value: object, field: str, key: str) -> int | None:
        if value is None:
            return None
        number = _exact_number(value, field, key)
        if number != number.to_integral_value():
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.MALFORMED_FRAME,
                f"{field} for {key!r} must be an integer",
            )
        return int(number)

    def _depth(self, depth: object, key: str) -> MarketDepth:
        if not isinstance(depth, dict) or set(depth.keys()) != {"buy", "sell"}:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.MALFORMED_FRAME,
                f"depth for {key!r} requires buy/sell",
            )
        return MarketDepth(
            buy_levels=self._levels(depth["buy"], "buy", key),
            sell_levels=self._levels(depth["sell"], "sell", key),
        )

    def _levels(self, side: object, field: str, key: str) -> tuple[MarketDepthLevel, ...]:
        if not isinstance(side, list):
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.MALFORMED_FRAME,
                f"depth {field} for {key!r} must be a list",
            )
        levels: list[MarketDepthLevel] = []
        for item in side:
            if not isinstance(item, dict):
                raise UpstoxFeedError(
                UpstoxFeedErrorCode.MALFORMED_FRAME,
                f"depth level for {key!r} must be an object",
            )
            price = self._price(item.get("price"), f"depth.{field}.price", key)
            quantity = self._count(item.get("quantity"), f"depth.{field}.quantity", key)
            orders = self._count(item.get("orders"), f"depth.{field}.orders", key)
            if price is None or quantity is None:
                raise UpstoxFeedError(
                    UpstoxFeedErrorCode.MALFORMED_FRAME,
                    f"depth level for {key!r} requires price and quantity",
                )
            levels.append(MarketDepthLevel(price=price, quantity=quantity, orders=orders))
        return tuple(levels)


class ProtobufDecodingSeam:
    """Fail-closed boundary awaiting an operator-supplied compiled decoder."""

    def __init__(self, decoder: BinaryFeedDecoder | None) -> None:
        self._decoder = decoder

    def decode(
        self, payload: bytes | str, *, received_at: datetime
    ) -> tuple[NormalizedFeedUpdate, ...]:
        if self._decoder is None:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.PROTOBUF_DECODER_REQUIRED,
                "binary frames require an injected compiled Protobuf decoder",
            )
        if not isinstance(payload, bytes):
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.MALFORMED_FRAME,
                "binary decoder requires bytes payload",
            )
        return self._decoder.decode(payload, received_at=received_at)


def _strict_json(payload: bytes | str) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        document = json.loads(
            text,
            parse_float=Decimal,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, InvalidOperation) as exc:
        raise UpstoxFeedError(
                UpstoxFeedErrorCode.MALFORMED_FRAME, "feed frame is not valid JSON"
            ) from exc
    if not isinstance(document, dict):
        raise UpstoxFeedError(
                UpstoxFeedErrorCode.MALFORMED_FRAME, "feed frame must be a JSON object"
            )
    return document


def _reject_constant(name: str) -> Decimal:
    raise UpstoxFeedError(
        UpstoxFeedErrorCode.MALFORMED_FRAME, f"non-finite JSON constant {name} is rejected"
    )


def _exact_number(value: object, field: str, key: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | Decimal):
        raise UpstoxFeedError(
            UpstoxFeedErrorCode.MALFORMED_FRAME, f"{field} for {key!r} must be an exact JSON number"
        )
    number = Decimal(value)
    if not number.is_finite():
        raise UpstoxFeedError(
            UpstoxFeedErrorCode.MALFORMED_FRAME, f"{field} for {key!r} is non-finite"
        )
    return number


def _finite_float(value: object, field: str, key: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float | Decimal):
        raise UpstoxFeedError(
            UpstoxFeedErrorCode.MALFORMED_FRAME,
            f"{field} for {key!r} must be numeric",
        )
    converted = float(value)
    if not math.isfinite(converted):
        raise UpstoxFeedError(
            UpstoxFeedErrorCode.MALFORMED_FRAME, f"{field} for {key!r} is non-finite"
        )
    return converted


def _millis(value: object, field: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise UpstoxFeedError(
            UpstoxFeedErrorCode.MALFORMED_FRAME,
            f"{field} must be integer milliseconds",
        )
    if value < 0:
        raise UpstoxFeedError(UpstoxFeedErrorCode.MALFORMED_FRAME, f"{field} must be non-negative")
    return datetime.fromtimestamp(value / 1000.0, tz=UTC)


__all__ = [
    "BinaryFeedDecoder",
    "FeedPayloadDecoder",
    "JsonFeedPayloadDecoder",
    "ProtobufDecodingSeam",
]
