"""Bounded descriptive option-chain evidence; no forecast or probability."""

from __future__ import annotations

import math
from collections.abc import Iterable
from decimal import Decimal
from uuid import uuid5

from ats.contracts.domain.hashing import compute_payload_hash

from ..contract_master import OptionType
from .models import Moneyness, OptionChainEvidence, OptionChainState, OptionQuote

SECONDS_PER_YEAR = 365.0 * 24.0 * 60.0 * 60.0


def compute_option_chain_evidence(
    chain: OptionChainState, *, method_version: str = "OPTION_CHAIN_V1"
) -> OptionChainEvidence:
    """Compute finite descriptive metrics from one normalized expiry chain."""

    calls = tuple(q for q in chain.quotes if q.option_type is OptionType.CE)
    puts = tuple(q for q in chain.quotes if q.option_type is OptionType.PE)
    atm_calls = tuple(q for q in calls if q.moneyness is Moneyness.ATM)
    atm_puts = tuple(q for q in puts if q.moneyness is Moneyness.ATM)
    call_iv = _mean_float(q.implied_volatility for q in atm_calls)
    put_iv = _mean_float(q.implied_volatility for q in atm_puts)
    atm_iv = _mean_float(value for value in (call_iv, put_iv))
    iv_difference = None if call_iv is None or put_iv is None else put_iv - call_iv
    call_oi = sum((q.open_interest or 0) for q in calls)
    put_oi = sum((q.open_interest or 0) for q in puts)
    call_volume = sum((q.volume or 0) for q in calls)
    put_volume = sum((q.volume or 0) for q in puts)
    oi_ratio = _ratio(put_oi, call_oi)
    volume_ratio = _ratio(put_volume, call_volume)
    volume_total = call_volume + put_volume
    imbalance = None if volume_total == 0 else (call_volume - put_volume) / volume_total
    straddle = _atm_straddle(atm_calls, atm_puts)
    years = (chain.expiry_time - chain.as_of_time).total_seconds() / SECONDS_PER_YEAR
    expected_move = None
    if atm_iv is not None and years >= 0:
        expected_move = chain.underlying_price * Decimal(str(atm_iv * math.sqrt(years)))
    spread_mean = _mean_decimal(q.spread_fraction for q in chain.quotes)
    gamma_concentration = _gamma_concentration(chain.quotes, atm_calls + atm_puts)
    theta_intensity = _theta_intensity(chain.quotes)
    reasons: list[str] = []
    for value, code in (
        (atm_iv, "ATM_IV_UNAVAILABLE"),
        (straddle, "ATM_STRADDLE_UNAVAILABLE"),
        (gamma_concentration, "GAMMA_CONCENTRATION_UNAVAILABLE"),
        (theta_intensity, "THETA_INTENSITY_UNAVAILABLE"),
    ):
        if value is None:
            reasons.append(code)
    evidence = OptionChainEvidence(
        schema_version="1.0",
        evidence_id=uuid5(chain.chain_id, method_version),
        chain_id=chain.chain_id,
        method_version=method_version,
        as_of_time=chain.as_of_time,
        data_cutoff=chain.data_cutoff,
        atm_iv=atm_iv,
        put_call_iv_difference=iv_difference,
        put_call_open_interest_ratio=oi_ratio,
        put_call_volume_ratio=volume_ratio,
        atm_straddle_premium=straddle,
        implied_expected_move=expected_move,
        call_put_volume_imbalance=None if imbalance is None else float(imbalance),
        mean_spread_fraction=None if spread_mean is None else float(spread_mean),
        gamma_concentration=gamma_concentration,
        theta_decay_intensity=theta_intensity,
        quality_state=chain.quality_state,
        reason_codes=tuple(reasons),
        payload_hash="0" * 64,
    )
    return evidence.model_copy(update={"payload_hash": compute_payload_hash(evidence)})


def _mean_float(values: Iterable[float | None]) -> float | None:
    finite = [float(value) for value in values if value is not None]
    if not finite:
        return None
    result = sum(finite) / len(finite)
    return result if math.isfinite(result) else None


def _mean_decimal(values: Iterable[Decimal | None]) -> Decimal | None:
    finite = [value for value in values if value is not None]
    return None if not finite else sum(finite, Decimal("0")) / Decimal(len(finite))


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    result = numerator / denominator
    return float(result) if math.isfinite(result) and result >= 0 else None


def _mark(quote: OptionQuote) -> Decimal | None:
    if quote.bid is not None and quote.ask is not None:
        return (quote.bid + quote.ask) / Decimal("2")
    return quote.last_price


def _atm_straddle(calls: tuple[OptionQuote, ...], puts: tuple[OptionQuote, ...]) -> Decimal | None:
    call_marks = tuple(value for quote in calls if (value := _mark(quote)) is not None)
    put_marks = tuple(value for quote in puts if (value := _mark(quote)) is not None)
    if not call_marks or not put_marks:
        return None
    return min(call_marks) + min(put_marks)


def _gamma_concentration(
    quotes: tuple[OptionQuote, ...], atm_quotes: tuple[OptionQuote, ...]
) -> float | None:
    def exposure(quote: OptionQuote) -> float | None:
        if quote.gamma is None or quote.open_interest is None:
            return None
        return quote.gamma * quote.open_interest

    total = sum(value for quote in quotes if (value := exposure(quote)) is not None)
    atm = sum(value for quote in atm_quotes if (value := exposure(quote)) is not None)
    if total <= 0:
        return None
    result = atm / total
    return float(result) if math.isfinite(result) and 0 <= result <= 1 else None


def _theta_intensity(quotes: tuple[OptionQuote, ...]) -> float | None:
    values: list[float] = []
    for quote in quotes:
        mark = _mark(quote)
        if quote.theta is not None and mark is not None and mark > 0:
            values.append(abs(quote.theta) / float(mark))
    return _mean_float(values)


__all__ = ["compute_option_chain_evidence"]
