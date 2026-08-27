from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from ats.market.derivatives.acquisition import (
    UpstoxInstrumentShapePolicy,
    parse_upstox_bod_records,
)
from ats.market.derivatives.contract_master import (
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
)
from ats.market.derivatives.normalization import NormalizedDerivativeContract
from ats.market.derivatives.reference_authority import (
    InstrumentReferenceAuthority,
    InstrumentReferenceError,
    provider_records_to_reference_contracts,
)
from ats.trading_runtime.lot_size import LotSizeRegistry

NOW = datetime(2026, 8, 27, tzinfo=UTC)


def contract(*, source_as_of: datetime = NOW) -> NormalizedDerivativeContract:
    return NormalizedDerivativeContract(
        schema_version="1.0",
        instrument_id=uuid4(),
        exchange="NSE",
        segment="NSE_FO",
        underlying=DerivativeUnderlying.NIFTY,
        instrument_type=DerivativeInstrumentType.OPTIDX,
        expiry="2026-09-03",
        strike=Decimal("25000"),
        option_type=OptionType.CE,
        lot_size=37,
        tick_size=Decimal("0.05"),
        freeze_quantity=1800,
        weekly=True,
        tradable=True,
        provider="UPSTOX",
        provider_underlying="NIFTY",
        provider_instrument_key="NSE_FO|dynamic-key",
        provider_exchange_token="123",
        provider_trading_symbol="NIFTY26SEP25000CE",
        source_as_of=source_as_of,
        provider_source_hash="a" * 64,
        reference_source_hash="b" * 64,
        contract_hash="c" * 64,
    )


def test_reference_spec_preserves_provider_values_and_hash() -> None:
    authority = InstrumentReferenceAuthority(
        contracts=(contract(),), retrieved_at=NOW, maximum_age=timedelta(hours=1)
    )
    spec = authority.resolve("NSE_FO|dynamic-key", as_of=NOW)
    assert spec.lot_size == 37
    assert spec.tick_size == Decimal("0.05")
    assert spec.expiry == "2026-09-03"
    assert spec.instrument_key == "NSE_FO|dynamic-key"
    registry = LotSizeRegistry.from_instrument_specs((spec,))
    assert registry.lot_size_for(spec.instrument_key) == 37


def test_missing_or_stale_reference_fails_closed() -> None:
    authority = InstrumentReferenceAuthority(
        contracts=(contract(source_as_of=NOW - timedelta(hours=2)),),
        retrieved_at=NOW,
        maximum_age=timedelta(minutes=30),
    )
    with pytest.raises(InstrumentReferenceError, match="REFERENCE_STALE"):
        authority.resolve("NSE_FO|dynamic-key", as_of=NOW)
    with pytest.raises(InstrumentReferenceError, match="INSTRUMENT_NOT_LISTED"):
        authority.resolve("NSE_FO|missing", as_of=NOW)


def test_production_lot_registry_has_no_nifty_banknifty_constants() -> None:
    source = open("backend/src/ats/trading_runtime/lot_size.py", encoding="utf-8").read()
    assert '"NIFTY": 25' not in source
    assert '"BANKNIFTY": 15' not in source


def test_current_provider_bod_values_become_authoritative_specs() -> None:
    records = parse_upstox_bod_records(
        b"""[{"segment":"NSE_FO","exchange":"NSE","instrument_type":"CE",
        "instrument_key":"NSE_FO|live-key","exchange_token":"987",
        "underlying_symbol":"NIFTY","trading_symbol":"NIFTY ACTUAL CE",
        "expiry":"2026-09-03","strike_price":25000,"lot_size":73,
        "tick_size":5,"freeze_quantity":1460}]""",
        source_as_of=NOW,
        policy=UpstoxInstrumentShapePolicy(
            schema_version="1.0",
            strike_price_scale=Decimal("1"),
            tick_size_scale=Decimal("0.01"),
            tradable_default=True,
        ),
    )
    contracts = provider_records_to_reference_contracts(
        records, underlying_aliases={"NIFTY": DerivativeUnderlying.NIFTY}
    )
    spec = InstrumentReferenceAuthority(
        contracts=contracts, retrieved_at=NOW, maximum_age=timedelta(hours=1)
    ).resolve("NSE_FO|live-key", as_of=NOW)
    assert (spec.lot_size, spec.tick_size, spec.strike) == (
        73,
        Decimal("0.05"),
        Decimal("25000"),
    )
