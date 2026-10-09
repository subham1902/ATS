"""Versioned operator configuration. Saving settings never grants authority."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrategyAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    strategy_id: str = Field(pattern=r"^XAU-[0-9]{3,}$")
    strategy_version: int = Field(ge=1)
    enabled: bool = False


class AccountControlConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    revision: int = Field(ge=1)
    canonical_symbol: Literal["XAUUSD"] = "XAUUSD"
    risk_per_trade: Decimal = Field(gt=0, le=Decimal("0.03"))
    daily_loss_fraction: Decimal = Field(gt=0, le=Decimal("0.03"))
    monthly_loss_fraction: Decimal = Field(gt=0, le=Decimal("0.08"))
    max_open_risk_fraction: Decimal = Field(gt=0, le=Decimal("0.08"))
    max_strategy_risk_fraction: Decimal = Field(gt=0, le=Decimal("0.08"))
    max_volume: Decimal = Field(gt=0)
    max_positions: int = Field(ge=1, le=100)
    margin_fraction: Decimal = Field(gt=0, le=Decimal("0.30"))
    sizing_mode: Literal["RISK_BASED"] = "RISK_BASED"
    equity_reference: Literal["START_OF_PERIOD"] = "START_OF_PERIOD"
    loss_basis: Literal["NET_REALIZED"] = "NET_REALIZED"
    assignments: tuple[StrategyAssignment, ...] = ()
    paused: bool = True

    @model_validator(mode="after")
    def coherent(self) -> "AccountControlConfig":
        ids = [a.strategy_id for a in self.assignments]
        if len(ids) != len(set(ids)):
            raise ValueError("DUPLICATE_STRATEGY_ASSIGNMENT")
        if self.risk_per_trade > min(
            self.daily_loss_fraction,
            self.monthly_loss_fraction,
            self.max_open_risk_fraction,
            self.max_strategy_risk_fraction,
        ):
            raise ValueError("TRADE_RISK_EXCEEDS_ENVELOPE")
        return self
