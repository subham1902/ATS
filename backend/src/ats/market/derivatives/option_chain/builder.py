"""Pure option-chain normalization against an authoritative contract master."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState

from ..contract_master import (
    ContractMaster,
    DerivativeInstrument,
    DerivativeInstrumentType,
    OptionType,
    validate_master_for_use,
)
from .errors import OptionChainError, OptionChainErrorCode
from .models import (
    GreeksMethod,
    Moneyness,
    OptionChainBuildContext,
    OptionChainState,
    OptionQuote,
    OptionQuoteInput,
)


def build_option_chain(
    *,
    contract_master: ContractMaster,
    context: OptionChainBuildContext,
    inputs: tuple[OptionQuoteInput, ...],
) -> OptionChainState:
    if not inputs:
        raise OptionChainError(OptionChainErrorCode.EMPTY_CHAIN, "at least one quote is required")
    validate_master_for_use(
        contract_master,
        evaluation_time=context.as_of_time,
        maximum_age_ms=context.policy.maximum_master_age_ms,
    )
    contracts = {item.instrument_id: item for item in contract_master.instruments}
    seen: set[str] = set()
    quotes: list[OptionQuote] = []
    for raw in inputs:
        if raw.instrument_id in seen:
            raise OptionChainError(OptionChainErrorCode.DUPLICATE_QUOTE, raw.instrument_id)
        seen.add(raw.instrument_id)
        contract = contracts.get(raw.instrument_id)
        if contract is None:
            raise OptionChainError(OptionChainErrorCode.UNKNOWN_CONTRACT, raw.instrument_id)
        _validate_contract(contract, context)
        _validate_quote_time(raw, context)
        quotes.append(_normalize_quote(contract, raw, context))

    ordered = tuple(sorted(quotes, key=lambda q: (q.strike, q.option_type.value, q.instrument_id)))
    state = OptionChainState(
        schema_version="1.0",
        chain_id=context.chain_id,
        underlying=context.underlying,
        expiry=context.expiry,
        underlying_price=context.underlying_price,
        atm_strike=context.atm_strike,
        as_of_time=context.as_of_time,
        data_cutoff=context.data_cutoff,
        expiry_time=context.expiry_time,
        source_id=context.source_id,
        source_version=context.source_version,
        quotes=ordered,
        quality_state=_chain_quality(ordered),
        payload_hash="0" * 64,
    )
    return state.model_copy(update={"payload_hash": compute_payload_hash(state)})


def _validate_contract(contract: DerivativeInstrument, context: OptionChainBuildContext) -> None:
    if (
        contract.instrument_type is not DerivativeInstrumentType.OPTIDX
        or contract.underlying is not context.underlying
        or contract.expiry != context.expiry
        or contract.strike is None
        or contract.option_type is None
        or not contract.tradable
    ):
        raise OptionChainError(
            OptionChainErrorCode.CONTRACT_MISMATCH,
            f"{contract.instrument_id} is not eligible for requested chain",
        )
    if date.fromisoformat(contract.expiry) != context.expiry_time.date():
        raise OptionChainError(
            OptionChainErrorCode.EXPIRY_TIME_MISMATCH,
            contract.instrument_id,
        )


def _validate_quote_time(raw: OptionQuoteInput, context: OptionChainBuildContext) -> None:
    if raw.quote_time > context.data_cutoff:
        raise OptionChainError(OptionChainErrorCode.FUTURE_QUOTE, raw.instrument_id)
    maximum_age = timedelta(milliseconds=context.policy.maximum_quote_age_ms)
    if context.data_cutoff - raw.quote_time > maximum_age:
        raise OptionChainError(OptionChainErrorCode.STALE_QUOTE, raw.instrument_id)
    if context.expiry_time <= context.as_of_time:
        raise OptionChainError(OptionChainErrorCode.EXPIRED_CHAIN, context.expiry)


def _normalize_quote(
    contract: DerivativeInstrument,
    raw: OptionQuoteInput,
    context: OptionChainBuildContext,
) -> OptionQuote:
    assert contract.strike is not None and contract.option_type is not None
    if raw.bid is not None and raw.ask is not None and raw.ask < raw.bid:
        raise OptionChainError(OptionChainErrorCode.CROSSED_MARKET, raw.instrument_id)
    spread = None
    spread_fraction = None
    if raw.bid is not None and raw.ask is not None:
        spread = raw.ask - raw.bid
        midpoint = (raw.ask + raw.bid) / Decimal("2")
        if midpoint > 0:
            spread_fraction = spread / midpoint
    flags = _quality_flags(raw, spread_fraction, context)
    quality = _quote_quality(raw.source_quality_state, flags)
    time_to_expiry = (context.expiry_time - context.as_of_time).total_seconds()
    return OptionQuote(
        instrument_id=contract.instrument_id,
        underlying=contract.underlying,
        expiry=contract.expiry,
        strike=contract.strike,
        option_type=contract.option_type,
        bid=raw.bid,
        ask=raw.ask,
        bid_qty=raw.bid_qty,
        ask_qty=raw.ask_qty,
        last_price=raw.last_price,
        volume=raw.volume,
        open_interest=raw.open_interest,
        change_in_oi=raw.change_in_oi,
        implied_volatility=raw.implied_volatility,
        delta=raw.delta,
        gamma=raw.gamma,
        theta=raw.theta,
        vega=raw.vega,
        greeks_method=raw.greeks_method,
        greeks_method_version=raw.greeks_method_version,
        spread=spread,
        spread_fraction=spread_fraction,
        moneyness=_moneyness(contract.strike, contract.option_type, context),
        distance_from_atm=contract.strike - context.atm_strike,
        time_to_expiry=float(time_to_expiry),
        quote_time=raw.quote_time,
        data_cutoff=context.data_cutoff,
        quality_state=quality,
        quality_flags=flags,
    )


def _moneyness(
    strike: Decimal, option_type: OptionType, context: OptionChainBuildContext
) -> Moneyness:
    distance_fraction = abs(strike - context.underlying_price) / context.underlying_price
    if distance_fraction <= context.policy.atm_tolerance_fraction:
        return Moneyness.ATM
    if option_type is OptionType.CE:
        return Moneyness.ITM if strike < context.underlying_price else Moneyness.OTM
    return Moneyness.ITM if strike > context.underlying_price else Moneyness.OTM


def _quality_flags(
    raw: OptionQuoteInput,
    spread_fraction: Decimal | None,
    context: OptionChainBuildContext,
) -> tuple[str, ...]:
    flags: list[str] = []
    if raw.bid is None or raw.ask is None or raw.last_price is None:
        flags.append("MISSING_QUOTE")
    if raw.bid == 0:
        flags.append("ZERO_BID")
    if spread_fraction is not None and spread_fraction > context.policy.maximum_spread_fraction:
        flags.append("WIDE_SPREAD")
    if (
        raw.bid_qty is None
        or raw.ask_qty is None
        or min(raw.bid_qty, raw.ask_qty) < context.policy.minimum_top_quantity
    ):
        flags.append("LOW_TOP_QUANTITY")
    if raw.volume is None or raw.volume < context.policy.minimum_volume:
        flags.append("LOW_VOLUME")
    if raw.open_interest is None or raw.open_interest < context.policy.minimum_open_interest:
        flags.append("LOW_OPEN_INTEREST")
    if raw.implied_volatility is None:
        flags.append("IV_UNAVAILABLE")
    if raw.greeks_method is GreeksMethod.UNAVAILABLE:
        flags.append("GREEKS_UNAVAILABLE")
    elif any(value is None for value in (raw.delta, raw.gamma, raw.theta, raw.vega)):
        flags.append("INCOMPLETE_GREEKS")
    return tuple(flags)


def _quote_quality(source: DataQualityState, flags: tuple[str, ...]) -> DataQualityState:
    if source in (DataQualityState.INVALID, DataQualityState.UNKNOWN):
        return source
    if "MISSING_QUOTE" in flags:
        return DataQualityState.INVALID
    if flags or source is DataQualityState.DEGRADED:
        return DataQualityState.DEGRADED
    return DataQualityState.GOOD


def _chain_quality(quotes: tuple[OptionQuote, ...]) -> DataQualityState:
    states = {quote.quality_state for quote in quotes}
    if DataQualityState.INVALID in states:
        return DataQualityState.INVALID
    if DataQualityState.UNKNOWN in states:
        return DataQualityState.UNKNOWN
    if DataQualityState.DEGRADED in states:
        return DataQualityState.DEGRADED
    return DataQualityState.GOOD


__all__ = ["build_option_chain"]
