from __future__ import annotations

from decimal import Decimal

from ats.contracts.common import SystemClock
from ats.market.derivatives.option_universe import (
    build_dynamic_option_universe,
    fixture_contract_master,
)
from ats.market.feeds.upstox_v3 import (
    FeedMode,
    UpstoxFeedAuthorization,
    UpstoxFeedConfiguration,
    UpstoxFeedLimits,
    WireFormat,
)
from ats.market.feeds.upstox_v3.proto import FeedResponse
from ats.market.feeds.upstox_v3.runtime_feed import UpstoxV3RuntimeFeed
from ats.trading_runtime.live_option_evidence import build_live_option_evidence
from pydantic import SecretStr


def test_live_chain_uses_only_fresh_provider_option_evidence() -> None:
    now = SystemClock().now()
    contracts = fixture_contract_master(
        underlying="NIFTY",
        spot=Decimal("25000"),
        expiry="2026-09-24",
        strike_step=Decimal("50"),
        lot_size=25,
        tick_size=Decimal("0.05"),
        half_width_strikes=4,
        as_of=now,
    )
    universe = build_dynamic_option_universe(
        contracts=contracts,
        spots={"NIFTY": Decimal("25000")},
        as_of=now,
        mode=FeedMode.FULL,
    )
    feed = UpstoxV3RuntimeFeed(
        authorization=UpstoxFeedAuthorization(bearer_token=SecretStr("REPLAY_PLACEHOLDER")),
        configuration=UpstoxFeedConfiguration(
            wire_format=WireFormat.PROTOBUF_BINARY,
            client_guid="live-option-evidence-test",
            limits=UpstoxFeedLimits(
                maximum_silence_ms=2_000,
                stale_after_ms=2_000,
            ),
        ),
    )
    feed.register_universe(universe)
    feed.register_reference_contracts(contracts)
    feed.connect_replay()

    response = FeedResponse(type=1, currentTs=int(now.timestamp() * 1000))
    option_specs = tuple(item for item in universe if item.instrument_kind == "OPTION")
    omitted_key = option_specs[-1].instrument_key
    for spec in option_specs[:-1]:
        market = response.feeds[spec.instrument_key].fullFeed.marketFF
        market.ltpc.ltp = 101.0
        market.ltpc.cp = 99.0
        market.ltpc.ltt = int(now.timestamp() * 1000)
        depth = market.marketLevel.bidAskQuote.add()
        depth.bidP = 100.0
        depth.bidQ = 100
        depth.askP = 101.0
        depth.askQ = 125
        market.vtt = 50_000
        market.oi = 100_000
        market.iv = 0.15
        market.optionGreeks.delta = 0.5 if spec.option_type == "CE" else -0.5
        market.optionGreeks.gamma = 0.001
        market.optionGreeks.theta = -4.0
        market.optionGreeks.vega = 8.0
        market.optionGreeks.rho = 1.0
    feed.ingest_frame(response.SerializeToString(), received_at=now)

    evidence = build_live_option_evidence(
        feed=feed,
        underlying="NIFTY",
        underlying_price=Decimal("25000"),
        evaluation_time=now,
        maximum_quote_age_ms=2_000,
    )
    assert evidence is not None
    assert len(evidence.option_chain.quotes) == len(option_specs) - 1
    omitted_id = next(
        instrument_id
        for instrument_id, provider_key in evidence.provider_key_by_instrument_id.items()
        if provider_key == omitted_key
    )
    assert omitted_id not in {quote.instrument_id for quote in evidence.option_chain.quotes}
    quote = evidence.option_chain.quotes[0]
    instrument = next(
        item
        for item in evidence.contract_master.instruments
        if item.instrument_id == quote.instrument_id
    )
    assert instrument.lot_size == 25
    assert instrument.tick_size == Decimal("0.05")
    assert quote.bid == Decimal("100.0")
    assert quote.ask == Decimal("101.0")
    assert quote.open_interest == 100_000
    assert quote.implied_volatility == 0.15
    assert quote.delta is not None
    assert quote.theta == -4.0
