from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid5

from ats.contracts.domain import MarketSnapshot, compute_payload_hash
from ats.contracts.domain.types import DataQualityState, SessionState
from ats.contracts.ids import ATS_FIXTURE_NAMESPACE

START = datetime(2026, 1, 5, 4, 0, tzinfo=UTC)


def snapshot(
    sequence: int,
    *,
    instrument: str = "RELIANCE",
    timeframe: str = "5m",
    open_: str = "100",
    high: str = "102",
    low: str = "99",
    close: str = "101",
    volume: str = "1000",
    quality_state: DataQualityState = DataQualityState.GOOD,
    quality_flags: tuple[str, ...] = (),
) -> MarketSnapshot:
    timestamp = START + timedelta(minutes=5 * (sequence - 1))
    value = MarketSnapshot(
        snapshot_id=uuid5(ATS_FIXTURE_NAMESPACE, f"r01/snapshot/{sequence}/{instrument}"),
        instrument_id=instrument,
        exchange="NSE",
        segment="CASH",
        timeframe=timeframe,
        bar_timestamp=timestamp,
        received_at=timestamp + timedelta(milliseconds=250),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
        sequence=sequence,
        quality_state=quality_state,
        quality_flags=quality_flags,
        source="r01-test",
        source_version="1.0.0",
        session_state=SessionState.OPEN,
        payload_hash="0" * 64,
    )
    return value.model_copy(update={"payload_hash": compute_payload_hash(value)})


def four_bars() -> tuple[MarketSnapshot, ...]:
    return (
        snapshot(1, open_="100", high="102", low="99", close="101", volume="1000"),
        snapshot(2, open_="101", high="104", low="100", close="103", volume="1200"),
        snapshot(3, open_="103", high="105", low="101", close="102", volume="800"),
        snapshot(4, open_="102", high="107", low="101", close="106", volume="1600"),
    )
