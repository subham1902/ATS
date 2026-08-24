"""Versioned deterministic R02 detector configuration."""

from __future__ import annotations

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain.types import NonEmptyStr, PositiveInt, UnitIntervalFloat
from ats.contracts.intelligence.types import PositiveFiniteFloat


class RegimeDetectorConfiguration(ATSBaseModel):
    detector_id: NonEmptyStr
    detector_version: NonEmptyStr
    direction_threshold: PositiveFiniteFloat
    trend_threshold: PositiveFiniteFloat
    breakout_high: UnitIntervalFloat
    breakout_low: UnitIntervalFloat
    low_volatility_threshold: PositiveFiniteFloat
    high_volatility_threshold: PositiveFiniteFloat
    expansion_ratio: PositiveFiniteFloat
    contraction_ratio: PositiveFiniteFloat
    change_return_scale: PositiveFiniteFloat
    change_volatility_scale: PositiveFiniteFloat
    full_familiarity_bars: PositiveInt

    @model_validator(mode="after")
    def validate_thresholds(self) -> RegimeDetectorConfiguration:
        if self.breakout_low >= self.breakout_high:
            raise ValueError("breakout_low must be below breakout_high")
        if self.low_volatility_threshold >= self.high_volatility_threshold:
            raise ValueError("low volatility threshold must be below high threshold")
        if self.expansion_ratio <= 1.0:
            raise ValueError("expansion_ratio must be > 1")
        if self.contraction_ratio >= 1.0:
            raise ValueError("contraction_ratio must be < 1")
        return self


__all__ = ["RegimeDetectorConfiguration"]
