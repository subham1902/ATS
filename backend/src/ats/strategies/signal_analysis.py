"""Proposal schema; heuristic confidence is never a calibrated probability."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SignalAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    strategy_id: str = Field(pattern=r"^XAU-[0-9]{3,}$")
    strategy_version: int = Field(ge=1)
    timestamp: datetime
    direction: Literal["LONG", "SHORT", "BOTH"] | None = None
    trade_horizon: Literal["SCALP", "INTRADAY", "SWING", "POSITION"] | None = None
    market_regime: str = "UNKNOWN"
    entry_status: Literal["UNKNOWN", "NO_SIGNAL", "WAITING_FOR_ENTRY", "PROPOSED"] = "UNKNOWN"
    entry_zone: tuple[Decimal, Decimal] | None = None
    entry_invalidation: str | None = None
    stop_loss: Decimal | None = None
    take_profit_1: Decimal | None = None
    take_profit_2: Decimal | None = None
    trailing_logic: str | None = None
    risk_reward: Decimal | None = None
    expected_holding_period_seconds: int | None = Field(default=None, gt=0)
    model_confidence: float | None = Field(default=None, ge=0, le=1)
    # No repository calibration verifier exists yet: fail closed by construction.
    empirical_success_probability: None = None
    probability_source: Literal["UNKNOWN"] = "UNKNOWN"
    supporting_factors: tuple[str, ...] = ()
    contradicting_factors: tuple[str, ...] = ()
    data_freshness: Literal["LIVE", "STALE", "UNKNOWN"] = "UNKNOWN"

    @model_validator(mode="after")
    def validate_geometry(self) -> SignalAnalysis:
        if self.timestamp.tzinfo is None:
            raise ValueError("TIMEZONE_REQUIRED")
        values = (*self.entry_zone,) if self.entry_zone else ()
        for price in (*values, self.stop_loss, self.take_profit_1, self.take_profit_2):
            if price is not None and (not price.is_finite() or price <= 0):
                raise ValueError("INVALID_SIGNAL_PRICE")
        if self.risk_reward is not None and (
            not self.risk_reward.is_finite() or self.risk_reward <= 0
        ):
            raise ValueError("INVALID_RISK_REWARD")
        if self.entry_zone is not None:
            low, high = self.entry_zone
            if low > high:
                raise ValueError("INVALID_ENTRY_ZONE")
            if self.direction == "LONG" and (
                self.stop_loss is not None
                and self.stop_loss >= low
                or self.take_profit_1 is not None
                and self.take_profit_1 <= high
            ):
                raise ValueError("INVALID_LONG_GEOMETRY")
            if self.direction == "SHORT" and (
                self.stop_loss is not None
                and self.stop_loss <= high
                or self.take_profit_1 is not None
                and self.take_profit_1 >= low
            ):
                raise ValueError("INVALID_SHORT_GEOMETRY")
        if self.entry_status == "PROPOSED" and (
            self.direction not in {"LONG", "SHORT"}
            or self.entry_zone is None
            or self.stop_loss is None
            or self.data_freshness != "LIVE"
        ):
            raise ValueError("INCOMPLETE_OR_STALE_PROPOSAL")
        return self
