"""Versioned Upstox response-shape parsing into strict ATS edge records."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import PositiveDecimal
from ats.market.derivatives.contract_master import DerivativeInstrumentType, OptionType
from ats.market.derivatives.normalization import ProviderInstrumentRecord
from ats.market.derivatives.replay_data.models import OneMinuteDerivativeBar


class UpstoxInstrumentShapePolicy(ATSBaseModel):
    schema_version: Literal["1.0"]
    price_scale: PositiveDecimal
    tradable_default: bool

    @model_validator(mode="after")
    def require_explicit_scale(self) -> UpstoxInstrumentShapePolicy:
        if self.price_scale > Decimal("1"):
            raise ValueError("price_scale cannot increase provider price units")
        return self


def parse_expiries(body: bytes) -> tuple[str, ...]:
    document = _json_document(body)
    data = document.get("data")
    if document.get("status") != "success" or not isinstance(data, list):
        raise ValueError("invalid expiry response shape")
    expiries: list[str] = []
    for value in data:
        if not isinstance(value, str):
            raise ValueError("expiry must be a string")
        datetime.strptime(value, "%Y-%m-%d")
        expiries.append(value)
    if len(set(expiries)) != len(expiries):
        raise ValueError("duplicate expiry")
    return tuple(sorted(expiries))


def parse_upstox_bod_records(
    body: bytes,
    *,
    source_as_of: UTCDateTime,
    policy: UpstoxInstrumentShapePolicy,
) -> tuple[ProviderInstrumentRecord, ...]:
    document = json.loads(body, parse_float=Decimal)
    if not isinstance(document, list):
        raise ValueError("BOD instrument payload must be a JSON array")
    source_hash = hashlib.sha256(body).hexdigest()
    records: list[ProviderInstrumentRecord] = []
    for item in document:
        if not isinstance(item, dict):
            raise ValueError("BOD instrument row must be an object")
        if item.get("segment") != "NSE_FO":
            continue
        raw_type = item.get("instrument_type")
        if raw_type not in {"CE", "PE", "FUT", "OPTIDX", "FUTIDX"}:
            continue
        instrument_type = (
            DerivativeInstrumentType.OPTIDX
            if raw_type in {"CE", "PE", "OPTIDX"}
            else DerivativeInstrumentType.FUTIDX
        )
        option_type = raw_type if raw_type in {"CE", "PE"} else item.get("option_type")
        strike_value = item.get("strike_price", item.get("strike"))
        records.append(
            ProviderInstrumentRecord(
                provider="UPSTOX",
                provider_instrument_key=_required_text(item, "instrument_key"),
                provider_exchange_token=_optional_text(item.get("exchange_token")),
                provider_underlying=_required_text_any(
                    item, ("underlying_symbol", "name", "underlying_key")
                ),
                exchange=_required_text(item, "exchange"),
                segment="FO",
                trading_symbol=_required_text_any(item, ("trading_symbol", "tradingsymbol")),
                instrument_type=instrument_type,
                expiry=_expiry(item.get("expiry")),
                strike=(
                    _decimal(strike_value) * policy.price_scale
                    if instrument_type is DerivativeInstrumentType.OPTIDX
                    else None
                ),
                option_type=OptionType(option_type) if option_type is not None else None,
                lot_size=_positive_integer(item.get("lot_size"), "lot_size"),
                tick_size=_decimal(item.get("tick_size")) * policy.price_scale,
                freeze_quantity=_optional_positive_integer(
                    item.get("freeze_quantity"), "freeze_quantity"
                ),
                weekly=item.get("weekly") if isinstance(item.get("weekly"), bool) else None,
                tradable=policy.tradable_default,
                source_as_of=source_as_of,
                source_hash=source_hash,
            )
        )
    records.sort(key=lambda item: item.provider_instrument_key)
    return tuple(records)


def parse_upstox_candles_1m(
    body: bytes, *, instrument_id: str
) -> tuple[OneMinuteDerivativeBar, ...]:
    document = _json_document(body)
    data = document.get("data")
    candles = data.get("candles") if isinstance(data, dict) else None
    if document.get("status") != "success" or not isinstance(candles, list):
        raise ValueError("invalid candle response shape")
    result: list[OneMinuteDerivativeBar] = []
    for raw in candles:
        if not isinstance(raw, list) or len(raw) < 7:
            raise ValueError("candle row must contain timestamp, OHLC, volume, and OI")
        timestamp = datetime.fromisoformat(_text(raw[0], "timestamp"))
        result.append(
            OneMinuteDerivativeBar(
                instrument_id=instrument_id,
                minute_start=timestamp,
                open=_decimal(raw[1]),
                high=_decimal(raw[2]),
                low=_decimal(raw[3]),
                close=_decimal(raw[4]),
                volume=_decimal(raw[5]),
                open_interest=_decimal(raw[6]),
            )
        )
    result.sort(key=lambda item: item.minute_start)
    if len({item.minute_start for item in result}) != len(result):
        raise ValueError("duplicate candle timestamp")
    return tuple(result)


def _json_document(body: bytes) -> dict[str, Any]:
    document = json.loads(body, parse_float=Decimal)
    if not isinstance(document, dict):
        raise ValueError("provider response must be a JSON object")
    return document


def _required_text(item: dict[str, Any], name: str) -> str:
    return _text(item.get(name), name)


def _expiry(value: object) -> str:
    if isinstance(value, str):
        datetime.strptime(value, "%Y-%m-%d")
        return value
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expiry must be an ISO date or epoch milliseconds")
    return datetime.fromtimestamp(value / 1000, tz=UTC).date().isoformat()


def _required_text_any(item: dict[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = item.get(name)
        if isinstance(value, str) and value:
            return value
    raise ValueError(f"one of {names!r} must be a non-empty string")


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _text(value, "optional text")


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal | int):
        raise ValueError("provider numeric value must be an exact JSON decimal/integer")
    return Decimal(value)


def _positive_integer(value: object, name: str) -> int:
    decimal = _decimal(value)
    if decimal <= 0 or decimal != decimal.to_integral_value():
        raise ValueError(f"{name} must be a positive integer")
    return int(decimal)


def _optional_positive_integer(value: object, name: str) -> int | None:
    return None if value is None else _positive_integer(value, name)


__all__ = [
    "UpstoxInstrumentShapePolicy",
    "parse_expiries",
    "parse_upstox_bod_records",
    "parse_upstox_candles_1m",
]
