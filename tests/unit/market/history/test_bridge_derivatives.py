"""Gated sidecar observations (quotes/metadata/events) and attribution ledger."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from ats.market import (
    ApprovedFixture,
    ReplayConfiguration,
    nse_cash_alpha_v1_calendar,
)
from ats.market.fixtures.loader import _load_approved_fixture
from ats.market.history import (
    AttributionRecord,
    HistoryTimeSemantics,
    ObservationKind,
    RawRecordReference,
    create_history_gated_replay,
    historical_contract_metadata_observation,
    historical_event_observation,
    historical_option_quote_observation,
)

TEST_SOURCE = "ATS_TEST_ONLY_SYNTHETIC"
REALISTIC = HistoryTimeSemantics(
    source_publication_delay_ms=500,
    ingestion_delay_ms=1000,
    strategy_visibility_delay_ms=500,
)


def _dataset():
    calendar = nse_cash_alpha_v1_calendar()
    return _load_approved_fixture(ApprovedFixture.NSE_CASH_RELIANCE_5M_V1, calendar)


def _configuration(dataset):
    manifest = dataset.manifest
    return ReplayConfiguration(start_at=manifest.first_bar, received_delay_ms=250)


def _provenance(identity: str) -> RawRecordReference:
    return RawRecordReference(
        source_id=TEST_SOURCE,
        raw_record_sha256="a" * 64,
        raw_location=f"test_only/{identity}",
    )


def test_converters_emit_canonical_kinds() -> None:
    event_time = _dataset().bars[0].bar_timestamp
    quote = historical_option_quote_observation(
        instrument="RELIANCE",
        event_time=event_time,
        underlying="NIFTY",
        trading_symbol="NIFTY_TEST_CE",
        expiry_date="2030-01-01",
        strike=Decimal("24000"),
        option_type="CE",
        bid=Decimal("100"),
        ask=Decimal("101"),
        provenance=_provenance("quote"),
        semantics=REALISTIC,
    )
    metadata = historical_contract_metadata_observation(
        instrument="NIFTY",
        event_time=event_time,
        contract_master_id="TEST_MASTER_V1",
        trading_symbol="NIFTY_TEST_CE",
        underlying="NIFTY",
        instrument_type="OPTIDX",
        expiry_date="2030-01-01",
        strike=Decimal("24000"),
        option_type="CE",
        lot_size=25,
        provenance=_provenance("meta"),
        semantics=REALISTIC,
    )
    news = historical_event_observation(
        instrument="RELIANCE",
        event_time=event_time,
        event_class="NEWS",
        headline="TEST_ONLY_HEADLINE",
        provenance=_provenance("news"),
        semantics=REALISTIC,
    )
    assert quote.kind is ObservationKind.OPTION_CHAIN_QUOTE
    assert metadata.kind is ObservationKind.CONTRACT_METADATA
    assert news.kind is ObservationKind.MARKET_EVENT


def test_sidecar_observations_obey_availability_gate() -> None:
    dataset = _dataset()
    bars = dataset.bars
    first_event = bars[0].bar_timestamp
    metadata_visible_after_first = historical_contract_metadata_observation(
        instrument="NIFTY",
        event_time=first_event,
        contract_master_id="TEST_MASTER_V1",
        trading_symbol="NIFTY_TEST_CE",
        underlying="NIFTY",
        instrument_type="OPTIDX",
        expiry_date="2030-01-01",
        provenance=_provenance("meta-visible-late"),
        semantics=HistoryTimeSemantics(
            source_publication_delay_ms=0,
            ingestion_delay_ms=0,
            strategy_visibility_delay_ms=2_000,
        ),
    )
    quote_always_future = historical_option_quote_observation(
        instrument="RELIANCE",
        event_time=bars[-1].bar_timestamp + timedelta(days=365),
        underlying="NIFTY",
        trading_symbol="NIFTY_FUTURE_CE",
        expiry_date="2040-01-01",
        strike=Decimal("25000"),
        option_type="PE",
        bid=Decimal("50"),
        ask=Decimal("51"),
        provenance=_provenance("quote-future"),
        semantics=REALISTIC,
    )
    session = create_history_gated_replay(
        dataset,
        _configuration(dataset),
        semantics=REALISTIC,
        extra_observations=(metadata_visible_after_first, quote_always_future),
    )

    session.advance()
    visible_now = {item.observation_id for item in session.visible_observations()}
    assert metadata_visible_after_first.observation_id not in visible_now

    session.advance()
    visible_now = {item.observation_id for item in session.visible_observations()}
    assert metadata_visible_after_first.observation_id in visible_now

    while session.state.phase.value != "TERMINAL":
        session.advance()
    final_visible = {item.observation_id for item in session.visible_observations()}
    assert quote_always_future.observation_id not in final_visible


def test_attribution_ledger_is_deterministic_and_monotonic() -> None:
    dataset = _dataset()
    configuration = _configuration(dataset)
    first = create_history_gated_replay(dataset, configuration, semantics=REALISTIC)
    second = create_history_gated_replay(dataset, configuration, semantics=REALISTIC)
    for _ in range(len(dataset.bars)):
        first.advance()
        second.advance()
    ledger: tuple[AttributionRecord, ...] = first.attribution_ledger()
    assert len(ledger) == len(dataset.bars)
    assert ledger == second.attribution_ledger()
    counts = [record.visible_count for record in ledger]
    assert all(later >= earlier for earlier, later in zip(counts, counts[1:], strict=False))
    digests = {record.window_sha256 for record in ledger}
    assert len(digests) >= 2
