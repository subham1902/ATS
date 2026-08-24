from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from ats.contracts.domain.types import LossState
from ats.portfolio.persistence import PortfolioCapitalAccount
from pydantic import ValidationError

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
PORTFOLIO_ID = UUID("60000000-0000-0000-0000-000000000001")


def account(**updates: object) -> PortfolioCapitalAccount:
    values: dict[str, object] = {
        "portfolio_id": PORTFOLIO_ID,
        "version": 1,
        "total_capital": Decimal("500000"),
        "deployable_capital": Decimal("500000"),
        "reserved_capital": Decimal("0"),
        "used_capital": Decimal("0"),
        "available_capital": Decimal("500000"),
        "realized_pnl": Decimal("0"),
        "unrealized_pnl": Decimal("0"),
        "daily_loss": Decimal("0"),
        "maximum_drawdown": Decimal("0"),
        "loss_state": LossState.NORMAL,
        "updated_at": NOW,
    }
    values.update(updates)
    return PortfolioCapitalAccount(**values)


def test_capital_identity_is_explicit() -> None:
    value = account(
        reserved_capital=Decimal("200000"),
        used_capital=Decimal("100000"),
        available_capital=Decimal("200000"),
    )
    assert value.available_capital == Decimal("200000")


def test_inconsistent_available_capital_is_rejected() -> None:
    with pytest.raises(ValidationError, match="available capital"):
        account(reserved_capital=Decimal("1"))


def test_deployable_cannot_exceed_total() -> None:
    with pytest.raises(ValidationError, match="deployable"):
        account(
            deployable_capital=Decimal("500001"),
            available_capital=Decimal("500001"),
        )


def test_negative_capital_is_rejected() -> None:
    with pytest.raises(ValidationError):
        account(reserved_capital=Decimal("-1"), available_capital=Decimal("500001"))


def test_loss_state_is_explicit_and_fail_closed_capable() -> None:
    assert account(loss_state=LossState.HALTED).loss_state is LossState.HALTED
