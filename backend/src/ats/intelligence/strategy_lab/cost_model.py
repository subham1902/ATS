"""Cost model protocol and deterministic v1 implementations."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from ats.contracts.common import ATSBaseModel


class CostModel(Protocol):
    """Authoritative cost model; net result must include costs."""

    cost_model_version: str

    def cost_per_trade(
        self,
        *,
        price: Decimal,
        quantity: Decimal,
        side: str,
    ) -> Decimal:
        """Return explicit non-negative cost for a single fill."""
        ...


class ZeroCostModel:
    """Only for tests where costs are explicitly zeroed; not authoritative."""

    cost_model_version = "zero-v1"

    def cost_per_trade(self, *, price: Decimal, quantity: Decimal, side: str) -> Decimal:
        return Decimal("0")


class FixedBpsCostModel(ATSBaseModel):
    """Deterministic fixed bps + per-trade fee; version mandatory."""

    cost_model_version: str
    fee_bps: Decimal
    per_trade_fee: Decimal

    def cost_per_trade(self, *, price: Decimal, quantity: Decimal, side: str) -> Decimal:
        _ = side
        if price <= 0 or quantity <= 0:
            raise ValueError("price/quantity must be positive")
        if self.fee_bps < 0 or self.per_trade_fee < 0:
            raise ValueError("cost parameters must be non-negative")
        notional = price * quantity
        bps_cost = notional * self.fee_bps / Decimal("10000")
        total = bps_cost + self.per_trade_fee
        if total < 0 or not total.is_finite():
            raise ValueError("non-finite cost")
        return total


__all__ = ["CostModel", "FixedBpsCostModel", "ZeroCostModel"]
