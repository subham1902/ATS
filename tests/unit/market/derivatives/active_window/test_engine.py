from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from ats.market.derivatives.active_window import (
    ActiveWindowError,
    ActiveWindowErrorCode,
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


def contract(
    strike: str,
    side: OptionType,
    *,
    ordinal: int,
    expiry: str = "2026-08-25",
    underlying: DerivativeUnderlying = DerivativeUnderlying.NIFTY,
    source_as_of: datetime = NOW,
    tradable: bool = True,
) -> NormalizedDerivativeContract:
    return NormalizedDerivativeContract(
        schema_version="1.0",
        instrument_id=UUID(int=ordinal),
        exchange="NSE",
        segment="FO",
        underlying=underlying,
        instrument_type=DerivativeInstrumentType.OPTIDX,
        expiry=expiry,
        strike=Decimal(strike),
        option_type=side,
        lot_size=1,
        tick_size=Decimal("0.05"),
        freeze_quantity=100,
        weekly=None,
        tradable=tradable,
        provider="TEST_PROVIDER",
        provider_underlying="TEST_ONLY_NIFTY",
        provider_instrument_key=f"TEST|{ordinal}",
        provider_exchange_token=f"EDGE-{ordinal}",
        provider_trading_symbol=f"TEST ONLY {strike} {side.value}",
        source_as_of=source_as_of,
        provider_source_hash="a" * 64,
        reference_source_hash="b" * 64,
        contract_hash=f"{ordinal:064x}",
    )


def universe(
    strikes: tuple[str, ...] = ("90", "100", "115", "130", "160"),
) -> tuple[NormalizedDerivativeContract, ...]:
    result = []
    ordinal = 1
    for strike in strikes:
        for side in (OptionType.CE, OptionType.PE):
            result.append(contract(strike, side, ordinal=ordinal))
            ordinal += 1
    return tuple(result)


def policy(**changes: object) -> ActiveWindowPolicy:
    values = {
        "window_size": 2,
        "expiry": "2026-08-25",
        "maximum_master_age_ms": 60_000,
        "maximum_quote_age_ms": 1_000,
    }
    values.update(changes)
    return ActiveWindowPolicy.model_validate(values)


def test_selects_actual_irregular_paired_strikes_without_synthesis() -> None:
    result = build_active_option_window(
        contracts=universe(),
        underlying=DerivativeUnderlying.NIFTY,
        underlying_price=Decimal("116"),
        as_of_time=NOW,
        policy=policy(),
    )
    assert result.atm_strike == Decimal("115")
    assert tuple(item.strike for item in result.pairs) == (
        Decimal("90"),
        Decimal("100"),
        Decimal("115"),
        Decimal("130"),
        Decimal("160"),
    )
    assert len(result.contract_ids()) == 10


def test_nearest_atm_tie_breaks_to_lower_actual_strike() -> None:
    result = build_active_option_window(
        contracts=universe(("80", "90", "100", "120", "140", "160", "180")),
        underlying=DerivativeUnderlying.NIFTY,
        underlying_price=Decimal("110"),
        as_of_time=NOW,
        policy=policy(),
    )
    assert result.atm_strike == Decimal("100")


def test_missing_pair_and_boundary_shortage_fail_closed() -> None:
    missing_pe = tuple(
        item
        for item in universe()
        if not (item.strike == Decimal("115") and item.option_type is OptionType.PE)
    )
    with pytest.raises(ActiveWindowError) as raised:
        build_active_option_window(
            contracts=missing_pe,
            underlying=DerivativeUnderlying.NIFTY,
            underlying_price=Decimal("115"),
            as_of_time=NOW,
            policy=policy(),
        )
    assert raised.value.code is ActiveWindowErrorCode.INSUFFICIENT_PAIRED_STRIKES


def test_multiple_expiries_are_filtered_by_explicit_policy() -> None:
    other = tuple(
        contract(
            str(200 + ordinal * 10),
            side,
            ordinal=100 + ordinal * 2 + (1 if side is OptionType.PE else 0),
            expiry="2026-09-29",
        )
        for ordinal in range(5)
        for side in (OptionType.CE, OptionType.PE)
    )
    result = build_active_option_window(
        contracts=universe() + other,
        underlying=DerivativeUnderlying.NIFTY,
        underlying_price=Decimal("115"),
        as_of_time=NOW,
        policy=policy(),
    )
    assert result.expiry == "2026-08-25"


def test_expired_or_stale_master_is_rejected() -> None:
    with pytest.raises(ActiveWindowError) as expired:
        build_active_option_window(
            contracts=universe(),
            underlying=DerivativeUnderlying.NIFTY,
            underlying_price=Decimal("115"),
            as_of_time=datetime(2026, 8, 26, tzinfo=UTC),
            policy=policy(),
        )
    assert expired.value.code is ActiveWindowErrorCode.EXPIRY_NOT_ELIGIBLE

    stale = tuple(
        item.model_copy(update={"source_as_of": NOW - timedelta(minutes=2)}) for item in universe()
    )
    with pytest.raises(ActiveWindowError) as stale_error:
        build_active_option_window(
            contracts=stale,
            underlying=DerivativeUnderlying.NIFTY,
            underlying_price=Decimal("115"),
            as_of_time=NOW,
            policy=policy(),
        )
    assert stale_error.value.code is ActiveWindowErrorCode.CONTRACT_MASTER_STALE


def test_duplicate_contract_side_is_rejected() -> None:
    duplicate = contract("115", OptionType.CE, ordinal=999)
    with pytest.raises(ActiveWindowError) as raised:
        build_active_option_window(
            contracts=universe() + (duplicate,),
            underlying=DerivativeUnderlying.NIFTY,
            underlying_price=Decimal("115"),
            as_of_time=NOW,
            policy=policy(),
        )
    assert raised.value.code is ActiveWindowErrorCode.DUPLICATE_CONTRACT_SIDE


def test_same_inputs_produce_identical_window_hash() -> None:
    values = {
        "contracts": universe(),
        "underlying": DerivativeUnderlying.NIFTY,
        "underlying_price": Decimal("115"),
        "as_of_time": NOW,
        "policy": policy(),
    }
    first = build_active_option_window(**values)
    second = build_active_option_window(**values)
    assert first == second


def test_naive_time_and_nonfinite_underlying_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_active_option_window(
            contracts=universe(),
            underlying=DerivativeUnderlying.NIFTY,
            underlying_price=Decimal("115"),
            as_of_time=datetime(2026, 8, 24, 4, 0),
            policy=policy(),
        )
    with pytest.raises(ValueError, match="positive finite"):
        build_active_option_window(
            contracts=universe(),
            underlying=DerivativeUnderlying.NIFTY,
            underlying_price=Decimal("NaN"),
            as_of_time=NOW,
            policy=policy(),
        )
