from decimal import Decimal

import pytest
from ats.trading_runtime.risk_terms import PositionRiskTerms, derive_position_risk_terms


def test_risk_budget_quantity_identity_is_explicit() -> None:
    terms = derive_position_risk_terms(
        entry_price=Decimal("200"), quantity=Decimal("25"), risk_fraction=Decimal("0.015")
    )
    assert terms.capital_committed == Decimal("5000")
    assert terms.risk_budget == Decimal("75.000")
    assert terms.maximum_loss_per_unit == Decimal("3.000")


def test_risk_budget_is_not_committed_capital_or_loss_recovery_sizing() -> None:
    with pytest.raises(ValueError, match="cannot exceed committed"):
        PositionRiskTerms(
            capital_committed=Decimal("100"),
            risk_budget=Decimal("150"),
            quantity=Decimal("10"),
            maximum_loss_per_unit=Decimal("15"),
        )
    with pytest.raises(ValueError, match="risk_budget / quantity"):
        PositionRiskTerms(
            capital_committed=Decimal("1000"),
            risk_budget=Decimal("100"),
            quantity=Decimal("10"),
            maximum_loss_per_unit=Decimal("11"),
        )
