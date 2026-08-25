from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from ats.market.derivatives.acquisition import (
    UpstoxInstrumentShapePolicy,
    parse_expiries,
    parse_upstox_bod_records,
    parse_upstox_candles_1m,
)


def test_expiry_parser_orders_actual_provider_values_without_weekday_assumption() -> None:
    body = b'{"status":"success","data":["2026-08-25","2026-08-18"]}'
    assert parse_expiries(body) == ("2026-08-18", "2026-08-25")


def test_expiry_parser_rejects_duplicates_and_malformed_values() -> None:
    with pytest.raises(ValueError, match="duplicate expiry"):
        parse_expiries(b'{"status":"success","data":["2026-08-25","2026-08-25"]}')
    with pytest.raises(ValueError):
        parse_expiries(b'{"status":"success","data":["Tuesday"]}')


def test_bod_parser_uses_explicit_price_scale_and_provider_key_identity() -> None:
    body = b"""[
      {
        "segment":"NSE_FO", "exchange":"NSE", "instrument_type":"OPTIDX",
        "instrument_key":"TEST_FO|123", "exchange_token":"123",
        "underlying_symbol":"NIFTY", "trading_symbol":"TEST ONLY NIFTY CE",
        "expiry":"2026-08-25", "strike_price":2500000,
        "option_type":"CE", "lot_size":65, "tick_size":5.0,
        "freeze_quantity":1800.0, "weekly":true
      }
    ]"""
    records = parse_upstox_bod_records(
        body,
        source_as_of=datetime(2026, 8, 24, tzinfo=UTC),
        policy=UpstoxInstrumentShapePolicy(
            schema_version="1.0", price_scale=Decimal("0.01"), tradable_default=True
        ),
    )
    record = records[0]
    assert record.provider_instrument_key == "TEST_FO|123"
    assert record.provider_exchange_token == "123"
    assert record.strike == Decimal("25000")
    assert record.tick_size == Decimal("0.05")
    assert record.lot_size == 65


def test_bod_parser_does_not_hard_code_contract_values() -> None:
    template = b"""[
      {"segment":"NSE_FO","exchange":"NSE","instrument_type":"FUTIDX",
       "instrument_key":"TEST_FO|BANK-FUT","exchange_token":"999",
       "underlying_symbol":"BANKNIFTY","tradingsymbol":"TEST BANK FUT",
       "expiry":"2026-09-29","lot_size":37,"tick_size":2,
       "freeze_quantity":777}
    ]"""
    record = parse_upstox_bod_records(
        template,
        source_as_of=datetime(2026, 8, 24, tzinfo=UTC),
        policy=UpstoxInstrumentShapePolicy(
            schema_version="1.0", price_scale=Decimal("0.01"), tradable_default=False
        ),
    )[0]
    assert (record.lot_size, record.freeze_quantity, record.expiry) == (
        37,
        777,
        "2026-09-29",
    )
    assert record.strike is None


def test_candle_parser_preserves_real_shape_values_and_orders_provider_rows() -> None:
    body = b"""{
      "status":"success", "data":{"candles":[
        ["2026-08-24T09:16:00+05:30",101.0,103.0,100.0,102.0,20,1001],
        ["2026-08-24T09:15:00+05:30",100.0,102.0,99.0,101.0,10,1000]
      ]}
    }"""
    candles = parse_upstox_candles_1m(body, instrument_id="TEST_ONLY_OPTION")
    assert candles[0].open == Decimal("100.0")
    assert candles[1].open_interest == Decimal("1001")
    assert candles[0].minute_start < candles[1].minute_start


def test_candle_parser_rejects_duplicates() -> None:
    body = b"""{
      "status":"success", "data":{"candles":[
        ["2026-08-24T09:15:00+05:30",100,101,99,100,1,1],
        ["2026-08-24T09:15:00+05:30",100,101,99,100,1,1]
      ]}
    }"""
    with pytest.raises(ValueError, match="duplicate candle"):
        parse_upstox_candles_1m(body, instrument_id="TEST_ONLY_OPTION")
