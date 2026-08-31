"""Unit tests for canonical historical observation models and time semantics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState
from ats.market.history import (
    AS_OF_INFORMATION_MODEL,
    HistoricalOptionType,
    MarketBarPayload,
    ObservationKind,
    ObservationTimes,
    OptionChainQuotePayload,
)
from pydantic import ValidationError

from tests.unit.market.history.fixtures import (
    SESSION_START,
    make_bar_observation,
    make_option_quote_observation,
)


def test_four_clock_ordering_is_enforced() -> None:
    event = datetime(2024, 6, 3, 3, 45, tzinfo=UTC)
    times = ObservationTimes(
        event_time=event,
        source_time=event + timedelta(milliseconds=500),
        ingest_time=event + timedelta(seconds=1),
        available_to_strategy_time=event + timedelta(seconds=2),
    )
    assert times.available_to_strategy_time > times.ingest_time


@pytest.mark.parametrize(
    ("field", "offset_ms"),
    [
        ("source_time", -1_000),
        ("ingest_time", -750),
        ("available_to_strategy_time", -1_500),
    ],
)
def test_out_of_order_clocks_are_rejected(field: str, offset_ms: int) -> None:
    event = datetime(2024, 6, 3, 3, 45, tzinfo=UTC)
    raw = {
        "event_time": event,
        "source_time": event + timedelta(milliseconds=500),
        "ingest_time": event + timedelta(seconds=1),
        "available_to_strategy_time": event + timedelta(seconds=2),
    }
    raw[field] = event + timedelta(milliseconds=offset_ms)
    with pytest.raises(ValueError, match="must be >="):
        ObservationTimes(**raw)  # type: ignore[arg-type]


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ObservationTimes(
            event_time=datetime(2024, 6, 3, 3, 45),
            source_time=datetime(2024, 6, 3, 3, 45),
            ingest_time=datetime(2024, 6, 3, 3, 45),
            available_to_strategy_time=datetime(2024, 6, 3, 3, 45),
        )


@pytest.mark.parametrize(
    ("low", "open_price", "high", "close"),
    [
        ("2910.00", "2915.00", "2920.00", "2909.00"),
        ("2921.00", "2915.00", "2920.00", "2918.00"),
        ("2912.00", "2911.00", "2920.00", "2918.00"),
        ("2912.00", "2918.00", "2917.00", "2916.00"),
    ],
)
def test_invalid_ohlc_payloads_are_rejected(
    low: str, open_price: str, high: str, close: str
) -> None:
    with pytest.raises(ValueError):
        MarketBarPayload(
            payload_kind=ObservationKind.MARKET_BAR,
            timeframe="5m",
            open=Decimal(open_price),
            high=Decimal(high),
            low=Decimal(low),
            close=Decimal(close),
            volume=Decimal("10"),
        )


def test_bid_without_ask_is_rejected() -> None:
    with pytest.raises(ValueError, match="provided together"):
        OptionChainQuotePayload(
            payload_kind=ObservationKind.OPTION_CHAIN_QUOTE,
            underlying="NIFTY",
            trading_symbol="NIFTY24JUN24000CE",
            expiry_date="2024-06-27",
            strike=Decimal("24000"),
            option_type=HistoricalOptionType.CALL,
            bid=Decimal("100"),
            ask=None,
        )


def test_observation_is_frozen() -> None:
    observation = make_bar_observation(sequence=1)
    with pytest.raises(ValidationError, match="frozen"):
        observation.instrument = "TCS"  # type: ignore[misc]


def test_kind_reflects_discriminated_payload() -> None:
    bar = make_bar_observation(sequence=1)
    quote = make_option_quote_observation(event_time=SESSION_START)
    assert bar.kind is ObservationKind.MARKET_BAR
    assert quote.kind is ObservationKind.OPTION_CHAIN_QUOTE


def test_payload_hash_covers_every_authoritative_field() -> None:
    observation = make_bar_observation(sequence=1)
    assert observation.payload_hash == compute_payload_hash(observation)
    tampered = observation.model_copy(update={"quality_state": DataQualityState.DEGRADED})
    assert tampered.payload_hash != compute_payload_hash(tampered)


def test_identity_is_deterministic_and_content_sensitive() -> None:
    left = make_bar_observation(sequence=1)
    right = make_bar_observation(sequence=1)
    different_close = make_bar_observation(sequence=1, close_price=Decimal("2919.00"))
    assert left.observation_id == right.observation_id
    assert left.observation_id != different_close.observation_id


def test_as_of_information_model_is_pinned() -> None:
    assert AS_OF_INFORMATION_MODEL.model_id == "AS_OF_INFORMATION_MODEL_V1"
    assert (
        AS_OF_INFORMATION_MODEL.admission_rule
        == "observation.times.available_to_strategy_time <= decision_time"
    )
    assert AS_OF_INFORMATION_MODEL.availability_field == "times.available_to_strategy_time"
    assert (
        AS_OF_INFORMATION_MODEL.time_order_rule
        == "event_time <= source_time <= ingest_time <= available_to_strategy_time"
    )
