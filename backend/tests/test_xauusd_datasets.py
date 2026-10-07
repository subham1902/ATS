"""Dataset quality and immutable replay without real market inputs."""

from datetime import UTC, datetime
from decimal import Decimal

import pyarrow as pa
import pyarrow.parquet as parquet
import pytest
from ats.datasets.ingestion import XauUsdDatasetStore
from ats.market.observations import VolumeProvenance

OPTIONS = dict(source="SYNTHETIC_TEST", broker_symbol="GOLD", source_timezone="UTC")


def test_import_identity_missing_fields_and_tamper_detection(tmp_path):
    source = tmp_path / "quotes.csv"
    source.write_text(
        "timestamp,bid,ask,tick_volume,symbol\n"
        "2026-10-01T00:00:00Z,2300,2300.2,4,GOLD\n"
        "2026-10-01T00:10:00Z,2301,2301.3,,GOLD\n"
    )
    store = XauUsdDatasetStore(tmp_path / "datasets")
    result = store.import_file(source, **OPTIONS)
    assert result["status"] == "RESEARCH_ONLY"
    assert result["quality"]["missing_periods"] == 1
    assert result["quality"]["missing_fields"]["real_volume"] == 2
    assert result["quality"]["spread_max"] == "0.3"
    assert store.import_file(source, **OPTIONS) == result
    ticks = list(store.replay(result["dataset_id"]))
    assert ticks[0].volume_provenance == VolumeProvenance.TICK_VOLUME
    assert ticks[0].real_volume is None
    assert ticks[1].tick_volume is None
    alternate = store.import_file(source, **{**OPTIONS, "source": "OTHER_SYNTHETIC_TEST"})
    assert alternate["dataset_id"] != result["dataset_id"]
    normalized = store.root / result["dataset_id"] / "observations.jsonl"
    normalized.write_text(normalized.read_text() + "\n")
    with pytest.raises(ValueError, match="CONTENT_CHANGED"):
        list(store.replay(result["dataset_id"]))


@pytest.mark.parametrize(
    "row",
    [
        "2026-10-01T00:00:00Z,corrupt,2300.2,1,XAUUSD",
        "2026-10-01T00:00:00Z,2301,2300.2,1,XAUUSD",
        "2026-10-01T00:00:00Z,-2300,2300.2,1,XAUUSD",
        "2026-10-01T00:00:00Z,2300,2300.2,-1,XAUUSD",
        "2026-10-01T00:00:00Z,2300,2300.2,1,EURUSD",
        "invalid-time,2300,2300.2,1,XAUUSD",
    ],
)
def test_corrupt_rows_reported_and_ineligible(tmp_path, row):
    source = tmp_path / "quotes.csv"
    source.write_text("timestamp,bid,ask,tick_volume,symbol\n" + row + "\n")
    store = XauUsdDatasetStore(tmp_path / "datasets")
    result = store.import_file(source, **OPTIONS)
    assert result["status"] == "NOT_ELIGIBLE"
    assert result["quality"]["invalid_rows"] == 1
    with pytest.raises(ValueError, match="QUALITY_NOT_ELIGIBLE"):
        list(store.replay(result["dataset_id"]))


def test_duplicates_and_ordering_are_fail_closed(tmp_path):
    source = tmp_path / "quotes.csv"
    source.write_text(
        "timestamp,bid\n2026-10-01T00:01:00Z,2300\n"
        "2026-10-01T00:01:00Z,2300\n2026-10-01T00:00:00Z,2301\n"
    )
    result = XauUsdDatasetStore(tmp_path / "datasets").import_file(source, **OPTIONS)
    assert result["quality"]["duplicates"] == 1
    assert result["quality"]["out_of_order"] == 1
    assert result["status"] == "NOT_ELIGIBLE"


def test_parquet_bars_preserve_volume_and_close_availability(tmp_path):
    source = tmp_path / "bars.parquet"
    parquet.write_table(
        pa.Table.from_pylist(
            [
                dict(
                    timestamp=datetime(2026, 10, 1, tzinfo=UTC),
                    open=2300,
                    high=2302,
                    low=2299,
                    close=2301,
                    tick_volume=12,
                    real_volume=3,
                )
            ]
        ),
        source,
    )
    store = XauUsdDatasetStore(tmp_path / "datasets")
    result = store.import_file(source, **OPTIONS, timeframe="1m", price_basis="BID")
    (bar,) = store.replay(result["dataset_id"])
    assert bar.tick_volume == Decimal(12)
    assert bar.real_volume == Decimal(3)
    assert bar.volume is None
    assert (bar.available_at - bar.timestamp).total_seconds() == 60
    assert not list((store.root / result["dataset_id"]).glob("*.sqlite3"))


def test_ambiguous_local_time_and_unknown_provenance_rejected(tmp_path):
    source = tmp_path / "quotes.csv"
    source.write_text("timestamp,bid\n2026-11-01T01:30:00,2300\n")
    store = XauUsdDatasetStore(tmp_path / "datasets")
    result = store.import_file(source, **{**OPTIONS, "source_timezone": "America/New_York"})
    assert result["status"] == "NOT_ELIGIBLE"
    with pytest.raises(ValueError, match="PROVENANCE_REQUIRED"):
        store.import_file(source, **{**OPTIONS, "source": "UNKNOWN"})
