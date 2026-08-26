"""Versioned explicit cost model: brokerage, exchange fees, STT, GST."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Protocol

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel


class CostModel(Protocol):
    cost_model_version: str
    cost_model_authoritative: bool

    def cost_per_trade(
        self,
        *,
        price: Decimal,
        quantity: Decimal,
        side: str,
    ) -> Decimal: ...

    def breakdown_per_fill(
        self,
        *,
        price: Decimal,
        quantity: Decimal,
        side: str,
    ) -> dict[str, Decimal]: ...


INDIA_COST_MODEL_VERSION = "india-cash-v1"
CONSERVATIVE_COST_MODEL_VERSION = "india-cash-conservative-v1"


class ZeroCostModel:
    """Only for tests where costs are explicitly zeroed; not authoritative."""

    cost_model_version = "zero-v1"
    cost_model_authoritative = False

    def cost_per_trade(self, *, price: Decimal, quantity: Decimal, side: str) -> Decimal:
        return Decimal("0")

    def breakdown_per_fill(
        self, *, price: Decimal, quantity: Decimal, side: str
    ) -> dict[str, Decimal]:
        return {"total": Decimal("0")}


class FixedBpsCostModel(ATSBaseModel):
    """Deterministic fixed bps + per-trade fee; version mandatory."""

    cost_model_version: str
    fee_bps: Decimal
    per_trade_fee: Decimal
    cost_model_authoritative: bool = True

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

    def breakdown_per_fill(
        self, *, price: Decimal, quantity: Decimal, side: str
    ) -> dict[str, Decimal]:
        total = self.cost_per_trade(price=price, quantity=quantity, side=side)
        return {
            "bps_fee": total - Decimal("0"),
            "per_trade_fee": self.per_trade_fee,
            "total": total,
        }


class IndiaCashCostModel(ATSBaseModel):
    """India NSE CASH explicit cost stack; version mandatory; conservative flag for uncertainty.

    Components (per fill, on notional = price * quantity):
      brokerage:        bps on notional
      exchange_fee:     bps on notional (NSE transaction charges)
      stt:              bps on notional (sell-side STT for cash delivery vs intraday)
      stamp_duty:       bps on notional (buy side)
      gst:              rate on (brokerage + exchange_fee)
      sebi_fee:         bps on notional
      spread_bps:       half-spread captured as cost
      slippage_bps:     conservative execution uncertainty

    GST is applied to brokerage + exchange_fee only, matching Indian regulation.
    All bps are basis points (1 bps = 0.01%).
    """

    cost_model_version: str
    brokerage_bps: Decimal = Decimal("0")
    exchange_fee_bps: Decimal = Decimal("0")
    stt_bps: Decimal = Decimal("0")
    stamp_duty_bps: Decimal = Decimal("0")
    sebi_bps: Decimal = Decimal("0")
    gst_rate: Decimal = Decimal("0.18")
    spread_bps: Decimal = Decimal("0")
    slippage_bps: Decimal = Decimal("0")
    per_trade_fee: Decimal = Decimal("0")
    cost_model_authoritative: bool = True
    conservative: bool = False
    fill_assumption: Literal["next_open", "conservative_next_open"] = "conservative_next_open"
    uncertainty_label: str = "explicit_stack"

    @model_validator(mode="after")
    def validate_model(self) -> IndiaCashCostModel:
        for name in (
            "brokerage_bps",
            "exchange_fee_bps",
            "stt_bps",
            "stamp_duty_bps",
            "sebi_bps",
            "spread_bps",
            "slippage_bps",
            "per_trade_fee",
        ):
            val = getattr(self, name)
            if val < 0 or not val.is_finite():
                raise ValueError(f"{name} must be finite and >=0")
        if self.gst_rate < 0 or not self.gst_rate.is_finite():
            raise ValueError("gst_rate must be finite and >=0")
        if not self.cost_model_version or not self.cost_model_version.strip():
            raise ValueError("cost_model_version required")
        if self.fill_assumption == "next_open" and self.conservative:
            raise ValueError("next_open fill cannot be marked conservative")
        return self

    def breakdown_per_fill(
        self, *, price: Decimal, quantity: Decimal, side: str
    ) -> dict[str, Decimal]:
        if price <= 0 or quantity <= 0:
            raise ValueError("price/quantity must be positive")
        _ = side
        notional = price * quantity
        bps = Decimal("10000")
        brokerage = notional * self.brokerage_bps / bps
        exchange_fee = notional * self.exchange_fee_bps / bps
        stt = notional * self.stt_bps / bps
        stamp = notional * self.stamp_duty_bps / bps
        sebi = notional * self.sebi_bps / bps
        spread = notional * self.spread_bps / bps
        slippage = notional * self.slippage_bps / bps
        gst = (brokerage + exchange_fee) * self.gst_rate
        total = brokerage + exchange_fee + stt + stamp + sebi
        total += spread + slippage + gst + self.per_trade_fee
        if total < 0 or not total.is_finite():
            raise ValueError("non-finite cost")
        return {
            "brokerage": brokerage,
            "exchange_fee": exchange_fee,
            "stt": stt,
            "stamp_duty": stamp,
            "sebi_fee": sebi,
            "spread": spread,
            "slippage": slippage,
            "gst": gst,
            "per_trade_fee": self.per_trade_fee,
            "total": total,
        }

    def cost_per_trade(self, *, price: Decimal, quantity: Decimal, side: str) -> Decimal:
        return self.breakdown_per_fill(price=price, quantity=quantity, side=side)["total"]


class ConservativeCostModel(ATSBaseModel):
    """Conservative wrapper: always labels OHLC-fill uncertainty as conservative.

    If OHLC-only evidence is supplied, execution is assumed at adverse next-open
    (already handled by backtester) plus an explicit slippage buffer. This model
    documents that no magical candle-close fill is assumed.
    """

    cost_model_version: str = CONSERVATIVE_COST_MODEL_VERSION
    inner: IndiaCashCostModel
    extra_slippage_bps: Decimal = Decimal("5")
    cost_model_authoritative: bool = True
    uncertainty_label: str = "conservative_ohlc_next_open_plus_slippage"

    @model_validator(mode="after")
    def validate_wrapper(self) -> ConservativeCostModel:
        if self.extra_slippage_bps < 0 or not self.extra_slippage_bps.is_finite():
            raise ValueError("extra_slippage_bps must be finite and >=0")
        return self

    def breakdown_per_fill(
        self, *, price: Decimal, quantity: Decimal, side: str
    ) -> dict[str, Decimal]:
        inner_bd = self.inner.breakdown_per_fill(price=price, quantity=quantity, side=side)
        extra = price * quantity * self.extra_slippage_bps / Decimal("10000")
        out = dict(inner_bd)
        out["extra_conservative_slippage"] = extra
        out["total"] = inner_bd["total"] + extra
        return out

    def cost_per_trade(self, *, price: Decimal, quantity: Decimal, side: str) -> Decimal:
        return self.breakdown_per_fill(price=price, quantity=quantity, side=side)["total"]


def default_india_conservative_cost_model() -> ConservativeCostModel:
    inner = IndiaCashCostModel(
        cost_model_version=INDIA_COST_MODEL_VERSION,
        brokerage_bps=Decimal("1"),
        exchange_fee_bps=Decimal("0.3"),
        stt_bps=Decimal("2.5"),
        stamp_duty_bps=Decimal("1.5"),
        sebi_bps=Decimal("0.05"),
        gst_rate=Decimal("0.18"),
        spread_bps=Decimal("2"),
        slippage_bps=Decimal("3"),
        per_trade_fee=Decimal("0"),
        cost_model_authoritative=True,
        conservative=True,
        fill_assumption="conservative_next_open",
        uncertainty_label="india_cash_conservative_stack",
    )
    return ConservativeCostModel(
        cost_model_version=CONSERVATIVE_COST_MODEL_VERSION,
        inner=inner,
        extra_slippage_bps=Decimal("2"),
        cost_model_authoritative=True,
        uncertainty_label="india_cash_conservative_stack_plus_buffer",
    )


COST_MODEL_REGISTRY: dict[str, str] = {
    "zero-v1": "ZeroCostModel",
    "india-cash-v1": "IndiaCashCostModel",
    "india-cash-conservative-v1": "ConservativeCostModel",
}

__all__ = [
    "CONSERVATIVE_COST_MODEL_VERSION",
    "COST_MODEL_REGISTRY",
    "ConservativeCostModel",
    "CostModel",
    "FixedBpsCostModel",
    "INDIA_COST_MODEL_VERSION",
    "IndiaCashCostModel",
    "ZeroCostModel",
    "default_india_conservative_cost_model",
]
