from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from ats.market.derivatives.active_window import (
    ActiveWindowPolicy,
    build_active_option_window,
)
from ats.market.derivatives.contract_master import (
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
)
from ats.market.derivatives.normalization import NormalizedDerivativeContract

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)


def contracts() -> tuple[NormalizedDerivativeContract, ...]:
    result = []
    ordinal = 1
    for strike in range(50, 160, 10):
        for side in (OptionType.CE, OptionType.PE):
            result.append(
                NormalizedDerivativeContract(
                    schema_version="1.0",
                    instrument_id=UUID(int=ordinal),
                    exchange="NSE",
                    segment="FO",
                    underlying=DerivativeUnderlying.NIFTY,
                    instrument_type=DerivativeInstrumentType.OPTIDX,
                    expiry="2026-08-25",
                    strike=Decimal(strike),
                    option_type=side,
                    lot_size=1,
                    tick_size=Decimal("0.05"),
                    freeze_quantity=100,
                    weekly=None,
                    tradable=True,
                    provider="TEST_PROVIDER",
                    provider_underlying="TEST_ONLY",
                    provider_instrument_key=f"TEST|{ordinal}",
                    provider_exchange_token=None,
                    provider_trading_symbol=f"TEST {ordinal}",
                    source_as_of=NOW,
                    provider_source_hash="a" * 64,
                    reference_source_hash="b" * 64,
                    contract_hash=f"{ordinal:064x}",
                )
            )
            ordinal += 1
    return tuple(result)


@pytest.mark.parametrize("window_size", range(1, 6))
def test_configured_window_always_uses_actual_symmetric_pairs(window_size: int) -> None:
    available = contracts()
    result = build_active_option_window(
        contracts=available,
        underlying=DerivativeUnderlying.NIFTY,
        underlying_price=Decimal("100"),
        as_of_time=NOW,
        policy=ActiveWindowPolicy(
            window_size=window_size,
            expiry="2026-08-25",
            maximum_master_age_ms=1000,
            maximum_quote_age_ms=1000,
        ),
    )
    actual_ids = {item.instrument_id for item in available}
    assert len(result.pairs) == window_size * 2 + 1
    assert set(result.contract_ids()) <= actual_ids
    assert result.pairs[window_size].strike == result.atm_strike


@pytest.mark.parametrize("price", ("99", "100", "101"))
def test_repetition_is_deterministic_across_near_atm_prices(price: str) -> None:
    inputs = {
        "contracts": contracts(),
        "underlying": DerivativeUnderlying.NIFTY,
        "underlying_price": Decimal(price),
        "as_of_time": NOW,
        "policy": ActiveWindowPolicy(
            window_size=2,
            expiry="2026-08-25",
            maximum_master_age_ms=1000,
            maximum_quote_age_ms=1000,
        ),
    }
    assert build_active_option_window(**inputs) == build_active_option_window(**inputs)
