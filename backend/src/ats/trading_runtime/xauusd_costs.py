"""Explicit versioned assumptions for future clean-room XAUUSD simulations."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from ats.contracts.common import ATSBaseModel


class XAUUSDExecutionModel(ATSBaseModel):
    version: str
    spread_source: Literal["OBSERVED_BID_ASK", "MODELED"]
    modeled_spread: Decimal | None = Field(default=None, ge=0)
    commission_per_unit: Decimal = Field(ge=0)
    slippage_price: Decimal = Field(ge=0)
    latency_ms: int = Field(ge=0)
    fill_model: Literal["NEXT_OBSERVED_QUOTE"] = "NEXT_OBSERVED_QUOTE"
    price_source: Literal["BID_ASK", "BID", "LAST"]
    position_sizing: str
    session_policy: str
    rollover_per_unit: Decimal | None
    overnight_holding: bool
    weekend_gap_policy: Literal["OBSERVED_ONLY", "NO_WEEKEND_HOLD"]
    liquidity_assumption: str

    @model_validator(mode="after")
    def validate_costs(self) -> XAUUSDExecutionModel:
        if (
            not self.version.strip()
            or not self.position_sizing.strip()
            or not self.session_policy.strip()
            or not self.liquidity_assumption.strip()
        ):
            raise ValueError("ALL_EXECUTION_ASSUMPTIONS_MUST_BE_DOCUMENTED")
        if self.spread_source == "MODELED" and self.modeled_spread is None:
            raise ValueError("MODELED_SPREAD_REQUIRED")
        if self.spread_source == "OBSERVED_BID_ASK" and self.modeled_spread is not None:
            raise ValueError("OBSERVED_SPREAD_MUST_NOT_HAVE_A_FALLBACK")
        if self.overnight_holding and self.rollover_per_unit is None:
            raise ValueError("OVERNIGHT_COST_UNKNOWN")
        return self

    def crossing_price(
        self,
        *,
        side: Literal["BUY", "SELL"],
        bid: Decimal | None,
        ask: Decimal | None,
        reference: Decimal | None = None,
    ) -> Decimal:
        if self.spread_source == "OBSERVED_BID_ASK":
            if bid is None or ask is None or bid <= 0 or ask < bid:
                raise ValueError("OBSERVED_SPREAD_UNAVAILABLE")
            price = ask if side == "BUY" else bid
        else:
            if reference is None or reference <= 0 or self.modeled_spread is None:
                raise ValueError("MODELED_PRICE_UNAVAILABLE")
            price = (
                reference + self.modeled_spread / 2
                if side == "BUY"
                else reference - self.modeled_spread / 2
            )
        return price + self.slippage_price if side == "BUY" else price - self.slippage_price
