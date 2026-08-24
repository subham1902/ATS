from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState
from ats.market.derivatives.option_chain import (
    GreeksMethod,
    Moneyness,
    OptionChainError,
    OptionChainErrorCode,
    OptionQuoteInput,
    build_option_chain,
)

from .helpers import AS_OF, context, master, quote


def test_builds_normalized_chain_and_hash() -> None:
    chain = build_option_chain(
        contract_master=master(),
        context=context(),
        inputs=(quote("P2"), quote("C2")),
    )
    assert tuple(item.instrument_id for item in chain.quotes) == ("C2", "P2")
    assert all(item.moneyness is Moneyness.ATM for item in chain.quotes)
    assert chain.payload_hash == compute_payload_hash(chain)
    assert chain.quality_state is DataQualityState.GOOD


def test_call_and_put_moneyness_are_directional() -> None:
    chain = build_option_chain(
        contract_master=master(),
        context=context(),
        inputs=(quote("C1"), quote("P3")),
    )
    assert all(item.moneyness is Moneyness.ITM for item in chain.quotes)
    assert {item.distance_from_atm for item in chain.quotes} == {Decimal("-100"), Decimal("100")}


@pytest.mark.parametrize(
    ("inputs", "code"),
    [
        ((), OptionChainErrorCode.EMPTY_CHAIN),
        ((quote("UNKNOWN"),), OptionChainErrorCode.UNKNOWN_CONTRACT),
        ((quote("C2"), quote("C2")), OptionChainErrorCode.DUPLICATE_QUOTE),
    ],
)
def test_invalid_inventory_fails_closed(
    inputs: tuple[OptionQuoteInput, ...], code: OptionChainErrorCode
) -> None:
    with pytest.raises(OptionChainError) as caught:
        build_option_chain(contract_master=master(), context=context(), inputs=inputs)
    assert caught.value.code is code


def test_future_and_stale_quote_rejected() -> None:
    with pytest.raises(OptionChainError) as future:
        build_option_chain(
            contract_master=master(),
            context=context(),
            inputs=(quote("C2", quote_time=AS_OF + timedelta(microseconds=1)),),
        )
    assert future.value.code is OptionChainErrorCode.FUTURE_QUOTE
    with pytest.raises(OptionChainError) as stale:
        build_option_chain(
            contract_master=master(),
            context=context(),
            inputs=(quote("C2", quote_time=AS_OF - timedelta(milliseconds=1001)),),
        )
    assert stale.value.code is OptionChainErrorCode.STALE_QUOTE


def test_crossed_market_rejected() -> None:
    with pytest.raises(OptionChainError) as caught:
        build_option_chain(
            contract_master=master(),
            context=context(),
            inputs=(quote("C2", bid=Decimal("102"), ask=Decimal("101")),),
        )
    assert caught.value.code is OptionChainErrorCode.CROSSED_MARKET


@pytest.mark.parametrize(
    ("updates", "flag", "state"),
    [
        ({"bid": None}, "MISSING_QUOTE", DataQualityState.INVALID),
        ({"bid": Decimal("0")}, "ZERO_BID", DataQualityState.DEGRADED),
        (
            {"bid": Decimal("50"), "ask": Decimal("150")},
            "WIDE_SPREAD",
            DataQualityState.DEGRADED,
        ),
        ({"bid_qty": 1}, "LOW_TOP_QUANTITY", DataQualityState.DEGRADED),
        ({"volume": 1}, "LOW_VOLUME", DataQualityState.DEGRADED),
        ({"open_interest": 1}, "LOW_OPEN_INTEREST", DataQualityState.DEGRADED),
    ],
)
def test_liquidity_quality_is_explicit(
    updates: dict[str, object], flag: str, state: DataQualityState
) -> None:
    chain = build_option_chain(
        contract_master=master(),
        context=context(),
        inputs=(quote("C2", **updates),),
    )
    assert flag in chain.quotes[0].quality_flags
    assert chain.quotes[0].quality_state is state
    assert chain.quality_state is state


def test_unavailable_greeks_are_preserved_not_fabricated() -> None:
    chain = build_option_chain(
        contract_master=master(),
        context=context(),
        inputs=(
            quote(
                "C2",
                delta=None,
                gamma=None,
                theta=None,
                vega=None,
                greeks_method=GreeksMethod.UNAVAILABLE,
                greeks_method_version=None,
            ),
        ),
    )
    normalized = chain.quotes[0]
    assert (normalized.delta, normalized.gamma, normalized.theta, normalized.vega) == (
        None,
        None,
        None,
        None,
    )
    assert "GREEKS_UNAVAILABLE" in normalized.quality_flags


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("implied_volatility", -0.1),
        ("implied_volatility", float("nan")),
        ("delta", 1.1),
        ("gamma", float("inf")),
        ("theta", float("nan")),
        ("vega", -1.0),
    ],
)
def test_bad_iv_and_greeks_rejected(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        quote("C2", **{field: value})


def test_greeks_method_cannot_lie() -> None:
    with pytest.raises(ValueError):
        quote("C2", greeks_method=GreeksMethod.UNAVAILABLE)
    with pytest.raises(ValueError):
        quote("C2", greeks_method_version=None)


def test_explicit_expiry_time_and_cutoff_required() -> None:
    with pytest.raises(ValueError):
        context().model_copy(update={"expiry": "2026-09-02"}).model_validate(
            context().model_copy(update={"expiry": "2026-09-02"})
        )


def test_time_to_expiry_comes_from_explicit_timestamp() -> None:
    chain = build_option_chain(contract_master=master(), context=context(), inputs=(quote("C2"),))
    expected = (context().expiry_time - context().as_of_time).total_seconds()
    assert chain.quotes[0].time_to_expiry == expected
