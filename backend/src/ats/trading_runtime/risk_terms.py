"""Explicit capital and loss semantics used at the position-monitor boundary."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PositionRiskTerms:
    capital_committed: Decimal
    risk_budget: Decimal
    quantity: Decimal
    maximum_loss_per_unit: Decimal

    def __post_init__(self) -> None:
        if self.capital_committed <= 0 or self.risk_budget <= 0 or self.quantity <= 0:
            raise ValueError("capital, risk budget, and quantity must be positive")
        if self.risk_budget > self.capital_committed:
            raise ValueError("risk budget cannot exceed committed capital")
        expected = self.risk_budget / self.quantity
        if self.maximum_loss_per_unit != expected:
            raise ValueError("maximum_loss_per_unit must equal risk_budget / quantity")


def derive_position_risk_terms(
    *,
    entry_price: Decimal,
    quantity: Decimal,
    risk_fraction: Decimal,
) -> PositionRiskTerms:
    if risk_fraction <= 0 or risk_fraction > 1:
        raise ValueError("risk_fraction must be in (0, 1]")
    committed = entry_price * quantity
    budget = committed * risk_fraction
    return PositionRiskTerms(
        capital_committed=committed,
        risk_budget=budget,
        quantity=quantity,
        maximum_loss_per_unit=budget / quantity,
    )


__all__ = ["PositionRiskTerms", "derive_position_risk_terms"]
