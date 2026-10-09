from datetime import UTC, datetime, timedelta

import pytest
from ats.market.domain import XauUsdDomain
from ats.market.metatrader.clock import BrokerClockEvidence
from ats.market.metatrader.connector import MetaTraderConnector

from backend.tests.test_xauusd_foundation import FakeTransport


def evidence():
    now = datetime(2026, 10, 8, 11, tzinfo=UTC)
    stamp = int(now.timestamp())
    return BrokerClockEvidence(
        server="TEST",
        terminal_gmt_epoch=stamp,
        terminal_server_epoch=stamp + 10800,
        tick_epoch_ms=(stamp + 10800) * 1000,
        independent_utc_epoch=stamp,
        captured_at=now,
        probe_hash="a" * 64,
        independent_source="INDEPENDENT_TEST_CLOCK",
    )


def test_verified_offset_live_raw_epoch_preserved():
    proof = evidence()
    connector = MetaTraderConnector(
        XauUsdDomain(), FakeTransport(), clock=lambda: proof.captured_at, clock_evidence=proof
    )
    quote = connector.normalize(
        {"time_msc": proof.tick_epoch_ms, "server": "TEST", "bid": 2000, "ask": 2001}
    )
    assert quote.timestamp == proof.captured_at
    assert quote.raw_source_epoch_ms == proof.tick_epoch_ms
    assert quote.clock_evidence_hash == proof.evidence_hash
    assert quote.timestamp_provenance == "VERIFIED_SERVER_WALL_LIVE_ONLY"
    assert quote.volume is None and quote.real_volume is None


def test_default_still_rejects_future():
    proof = evidence()
    connector = MetaTraderConnector(
        XauUsdDomain(), FakeTransport(), clock=lambda: proof.captured_at
    )
    with pytest.raises(ValueError, match="FUTURE_SOURCE_TIMESTAMP"):
        connector.normalize({"time_msc": proof.tick_epoch_ms, "bid": 2000})


def test_no_extrapolation_expired_wrong_server_or_historical():
    proof = evidence()
    with pytest.raises(ValueError, match="SERVER_MISMATCH"):
        proof.normalize(proof.tick_epoch_ms, "OTHER", proof.captured_at)
    with pytest.raises(ValueError, match="EXPIRED"):
        proof.normalize(proof.tick_epoch_ms, "TEST", proof.captured_at + timedelta(seconds=901))
    connector = MetaTraderConnector(
        XauUsdDomain(), FakeTransport(), clock=lambda: proof.captured_at, clock_evidence=proof
    )
    with pytest.raises(ValueError, match="HISTORICAL_CLOCK_PROFILE_REQUIRED"):
        connector.normalize(
            {"_historical": True, "time_msc": proof.tick_epoch_ms, "server": "TEST", "bid": 2000}
        )


def test_independent_anchor_disagreement_rejected():
    proof = evidence()
    with pytest.raises(ValueError):
        BrokerClockEvidence.model_validate(proof.model_dump() | {"independent_utc_epoch": 1})
