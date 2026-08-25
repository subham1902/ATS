from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ats.market.derivatives.active_window import (
    ActiveWindowPolicy,
    build_active_option_window,
)
from ats.market.derivatives.contract_master import (
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
)
from ats.market.derivatives.normalization import (
    ProviderInstrumentRecord,
    ReferenceInstrumentRecord,
    UnderlyingAlias,
    normalize_contracts,
)

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)


def test_d02_normalized_contracts_feed_d04_without_provider_identity_becoming_canonical() -> None:
    providers = []
    references = []
    ordinal = 1
    for strike in (90, 100, 110, 120, 130):
        for side in (OptionType.CE, OptionType.PE):
            providers.append(
                ProviderInstrumentRecord(
                    provider="FAKE_UPSTOX",
                    provider_instrument_key=f"TEST_FO|{ordinal}",
                    provider_exchange_token=f"EDGE-{ordinal}",
                    provider_underlying="TEST_ONLY_NIFTY",
                    exchange="NSE",
                    segment="FO",
                    trading_symbol=f"TEST ONLY {strike} {side.value}",
                    instrument_type=DerivativeInstrumentType.OPTIDX,
                    expiry="2026-08-25",
                    strike=Decimal(strike),
                    option_type=side,
                    lot_size=1,
                    tick_size=Decimal("0.05"),
                    freeze_quantity=100,
                    weekly=None,
                    tradable=True,
                    source_as_of=NOW,
                    source_hash="a" * 64,
                )
            )
            references.append(
                ReferenceInstrumentRecord(
                    reference_id=f"TEST_NSE_REFERENCE_{ordinal}",
                    exchange="NSE",
                    segment="FO",
                    underlying=DerivativeUnderlying.NIFTY,
                    instrument_type=DerivativeInstrumentType.OPTIDX,
                    expiry="2026-08-25",
                    strike=Decimal(strike),
                    option_type=side,
                    lot_size=1,
                    freeze_quantity=100,
                    effective_at=NOW,
                    source_hash="b" * 64,
                )
            )
            ordinal += 1
    normalized = normalize_contracts(
        provider_records=tuple(providers),
        reference_records=tuple(references),
        aliases=(
            UnderlyingAlias(
                provider_underlying="TEST_ONLY_NIFTY",
                canonical_underlying=DerivativeUnderlying.NIFTY,
            ),
        ),
    )
    window = build_active_option_window(
        contracts=normalized.contracts,
        underlying=DerivativeUnderlying.NIFTY,
        underlying_price=Decimal("110"),
        as_of_time=NOW,
        policy=ActiveWindowPolicy(
            window_size=2,
            expiry="2026-08-25",
            maximum_master_age_ms=1000,
            maximum_quote_age_ms=1000,
        ),
    )
    assert not normalized.issues
    assert len(window.pairs) == 5
    assert all("TEST_FO" not in str(contract_id) for contract_id in window.contract_ids())
