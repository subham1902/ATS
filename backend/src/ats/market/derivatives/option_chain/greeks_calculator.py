"""Explicitly-labelled deterministic Black-Scholes Greeks calculator.

This module exists so that ATS can distinguish provider-supplied Greeks from
ATS-computed Greeks. It is never invoked automatically by feed normalization:
a caller must deliberately pass genuine market inputs here, and every result
is stamped with ``GreeksMethod.DETERMINISTIC_CALCULATOR`` plus an explicit
calculator version so the two provenance classes can never be conflated.

All mathematics are closed-form Black-Scholes with ``math.erf``; results are
deterministic binary64 computations with NaN/Inf rejected at both input and
output boundaries.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, FiniteFloat
from ats.contracts.domain.types import NonEmptyStr
from ats.market.derivatives.contract_master import OptionType

from .models import GreeksMethod

CALCULATOR_VERSION = "ATS-BLACK-SCHOLES-1.0"
_DAYS_PER_YEAR = 365.0


class DeterministicGreeksRequest(ATSBaseModel):
    """Genuine market inputs supplied by the caller; nothing here is invented."""

    underlying_price: FiniteFloat
    strike: FiniteFloat
    time_to_expiry_days: FiniteFloat
    implied_volatility: FiniteFloat
    risk_free_rate: FiniteFloat
    option_type: OptionType

    @model_validator(mode="after")
    def validate_ranges(self) -> DeterministicGreeksRequest:
        if self.underlying_price <= 0:
            raise ValueError("underlying_price must be positive")
        if self.strike <= 0:
            raise ValueError("strike must be positive")
        if self.time_to_expiry_days <= 0:
            raise ValueError("time_to_expiry_days must be positive")
        if self.implied_volatility <= 0:
            raise ValueError("implied_volatility must be positive")
        return self


class ComputedOptionGreeks(ATSBaseModel):
    """Calculator-stamped Greeks; structurally distinct from source-provided values."""

    greeks_method: Literal[GreeksMethod.DETERMINISTIC_CALCULATOR]
    greeks_method_version: NonEmptyStr
    delta: FiniteFloat
    gamma: FiniteFloat
    theta_per_year: FiniteFloat
    theta_per_calendar_day: FiniteFloat
    vega_per_iv_point: FiniteFloat
    request: DeterministicGreeksRequest

    @model_validator(mode="after")
    def reject_non_finite_outputs(self) -> ComputedOptionGreeks:
        values = (
            self.delta,
            self.gamma,
            self.theta_per_year,
            self.theta_per_calendar_day,
            self.vega_per_iv_point,
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError("computed Greeks must be finite")
        return self


def compute_deterministic_greeks(
    request: DeterministicGreeksRequest,
) -> ComputedOptionGreeks:
    """Compute closed-form European-option Greeks from explicitly supplied inputs."""

    spot = request.underlying_price
    strike = request.strike
    years = request.time_to_expiry_days / _DAYS_PER_YEAR
    sigma = request.implied_volatility
    rate = request.risk_free_rate
    sqrt_years = math.sqrt(years)
    sigma_sqrt_t = sigma * sqrt_years
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * years) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t
    density = _normal_density(d1)
    discount = math.exp(-rate * years)
    if request.option_type is OptionType.CE:
        delta = _normal_cdf(d1)
        theta_core = -(spot * density * sigma) / (
            2 * sqrt_years
        ) - rate * strike * discount * _normal_cdf(d2)
    else:
        delta = _normal_cdf(d1) - 1.0
        theta_core = -(spot * density * sigma) / (
            2 * sqrt_years
        ) + rate * strike * discount * _normal_cdf(-d2)
    gamma = density / (spot * sigma_sqrt_t)
    vega_per_iv_point = spot * density * sqrt_years / 100.0
    outputs = {
        "delta": delta,
        "gamma": gamma,
        "theta_per_year": theta_core,
        "theta_per_calendar_day": theta_core / _DAYS_PER_YEAR,
        "vega_per_iv_point": vega_per_iv_point,
    }
    if any(not math.isfinite(value) for value in outputs.values()):
        raise ValueError("Black-Scholes evaluation produced a non-finite value")
    return ComputedOptionGreeks(
        greeks_method=GreeksMethod.DETERMINISTIC_CALCULATOR,
        greeks_method_version=CALCULATOR_VERSION,
        delta=outputs["delta"],
        gamma=outputs["gamma"],
        theta_per_year=outputs["theta_per_year"],
        theta_per_calendar_day=outputs["theta_per_calendar_day"],
        vega_per_iv_point=outputs["vega_per_iv_point"],
        request=request,
    )


def _normal_density(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2.0 * math.pi)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


__all__ = [
    "CALCULATOR_VERSION",
    "ComputedOptionGreeks",
    "DeterministicGreeksRequest",
    "compute_deterministic_greeks",
]
