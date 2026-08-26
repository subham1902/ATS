"""Adverse-price fill models for research backtests.

Fills at the raw next-bar open are systematically optimistic: real orders
walk the spread and move liquidity. A :class:`SlippageModel` degrades every
fill price against the strategy before costs are applied, so reported net PnL
can only be equal or worse than live reality — never better.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from ats.contracts.common import ATSBaseModel


class SlippageModel(Protocol):
    """Authoritative adverse-fill model; version is mandatory."""

    slippage_model_version: str

    def applied_price(
        self,
        *,
        price: Decimal,
        quantity: Decimal,
        side: str,
    ) -> Decimal:
        """Return the degraded execution price for a single fill."""
        ...


class ZeroSlippageModel(ATSBaseModel):
    """Explicit no-slippage baseline; only for controlled comparisons."""

    slippage_model_version: str = "zero-v1"

    def applied_price(
        self,
        *,
        price: Decimal,
        quantity: Decimal,
        side: str,
    ) -> Decimal:
        _ = quantity, side
        return price


class FixedBpsSlippageModel(ATSBaseModel):
    """Deterministic fixed basis-point degradation against the strategy.

    Buys pay up to ``slippage_bps`` above the reference price; sells receive
    ``slippage_bps`` below it. Quantities do not scale v1 slippage; the model
    exists to remove systematic same-open optimism, not to microstructure.
    """

    slippage_model_version: str
    slippage_bps: Decimal

    def applied_price(
        self,
        *,
        price: Decimal,
        quantity: Decimal,
        side: str,
    ) -> Decimal:
        _ = quantity
        normalized_side = side.upper()
        if normalized_side not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")
        if price <= 0:
            raise ValueError("price must be positive")
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps must be non-negative")
        factor = Decimal(1) + (
            self.slippage_bps / Decimal("10000")
            if normalized_side == "BUY"
            else -(self.slippage_bps / Decimal("10000"))
        )
        degraded = price * factor
        if degraded <= 0 or not degraded.is_finite():
            raise ValueError("degraded price must remain finite and positive")
        return degraded


__all__ = ["FixedBpsSlippageModel", "SlippageModel", "ZeroSlippageModel"]
