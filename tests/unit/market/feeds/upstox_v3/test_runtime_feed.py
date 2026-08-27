"""C1 offline acceptance: transport frame -> decode -> normalized -> freshness -> runtime.

Uses deterministic protobuf fixture frames over the pinned Upstox V3 schema so
the chain is provable without a live exchange session. No active-session FRESH
claim is made here.
"""

from __future__ import annotations

import time
from decimal import Decimal

from ats.contracts.common import SystemClock
from ats.market.derivatives.option_universe import (
    build_dynamic_option_universe,
    fixture_contract_master,
)
from ats.market.feeds.upstox_v3.config import (
    UpstoxFeedAuthorization,
    UpstoxFeedConfiguration,
    UpstoxFeedLimits,
    WireFormat,
)
from ats.market.feeds.upstox_v3.proto import FeedResponse
from ats.market.feeds.upstox_v3.runtime_feed import UpstoxV3RuntimeFeed


def _make_config() -> UpstoxFeedConfiguration:
    return UpstoxFeedConfiguration(
        wire_format=WireFormat.PROTOBUF_BINARY,
        client_guid="ats-c1-acceptance",
        limits=UpstoxFeedLimits(maximum_silence_ms=3_000, stale_after_ms=5_000),
    )


def _make_auth() -> UpstoxFeedAuthorization:
    from pydantic import SecretStr

    return UpstoxFeedAuthorization(bearer_token=SecretStr("REPLAY_PLACEHOLDER"))


def _encode_ltpc_frame(quotes: dict[str, float], ts_ms: int) -> bytes:
    response = FeedResponse()
    response.type = 1  # live_feed
    response.currentTs = ts_ms
    for key, ltp in quotes.items():
        feed = response.feeds[key]
        feed.ltpc.ltp = float(ltp)
        feed.ltpc.cp = float(ltp)
        feed.ltpc.ltt = ts_ms
    return response.SerializeToString()


def _build_universe():
    clock = SystemClock()
    as_of = clock.now()
    nifty = fixture_contract_master(
        underlying="NIFTY",
        spot=Decimal("25000"),
        expiry="2026-09-24",
        strike_step=Decimal("50"),
        lot_size=25,
        tick_size=Decimal("0.05"),
        half_width_strikes=10,
        as_of=as_of,
    )
    banknifty = fixture_contract_master(
        underlying="BANKNIFTY",
        spot=Decimal("57000"),
        expiry="2026-09-24",
        strike_step=Decimal("100"),
        lot_size=15,
        tick_size=Decimal("0.05"),
        half_width_strikes=10,
        as_of=as_of,
    )
    contracts = nifty + banknifty
    spots = {"NIFTY": Decimal("25000"), "BANKNIFTY": Decimal("57000")}
    return build_dynamic_option_universe(contracts=contracts, spots=spots, as_of=as_of)


def test_c1_dynamic_universe_has_22_subscriptions():
    universe = _build_universe()
    assert len(universe) == 22
    indices = [u for u in universe if u.instrument_kind == "INDEX"]
    options = [u for u in universe if u.instrument_kind == "OPTION"]
    assert len(indices) == 2
    assert len(options) == 20
    # 10 NIFTY options + 10 BANKNIFTY options
    nifty_opts = [u for u in options if u.underlying == "NIFTY"]
    bank_opts = [u for u in options if u.underlying == "BANKNIFTY"]
    assert len(nifty_opts) == 10
    assert len(bank_opts) == 10
    # no hard-coded lot sizes leaking: each option carries reference lot size
    assert all(u.lot_size in (25, 15) for u in options)


def test_c1_recorded_frame_chain_reaches_runtime():
    universe = _build_universe()
    feed = UpstoxV3RuntimeFeed(
        authorization=_make_auth(),
        configuration=_make_config(),
    )
    feed.register_universe(universe)
    assert feed.registry.instrument_keys().__len__() == 22
    feed.connect_replay()

    received: list[tuple[str, str]] = []

    def _handler(update, freshness):
        received.append((update.instrument_key, freshness.value))

    feed._on_normalized = _handler

    now_ms = int(time.time() * 1000)
    quotes = {
        "NSE_INDEX|Nifty 50": 25012.5,
        "NSE_INDEX|Nifty Bank": 57103.25,
        universe[2].instrument_key: 120.5,  # first NIFTY option
        universe[12].instrument_key: 95.25,  # first BANKNIFTY option
    }
    frame = _encode_ltpc_frame(quotes, now_ms)

    applied = feed.ingest_frame(frame)
    telemetry = feed.telemetry()

    assert telemetry["upstox_raw_messages"] == 1
    assert telemetry["protobuf_frames_decoded"] == 1
    assert telemetry["normalized_updates"] == 4
    assert applied == 4
    assert telemetry["fresh_updates"] == 4
    assert telemetry["unknown_updates"] == 0
    assert len(received) == 4
    # scanner received the normalized updates
    keys = {r[0] for r in received}
    assert "NSE_INDEX|Nifty 50" in keys

    # Freshness board reports FRESH for the keys we fed.
    freshness = feed.freshness_summary()
    assert freshness["NSE_INDEX|Nifty 50"] == "FRESH"
    assert freshness[universe[2].instrument_key] == "FRESH"
