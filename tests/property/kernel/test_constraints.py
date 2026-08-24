from __future__ import annotations

from decimal import Decimal

import pytest
from ats.contracts.domain.types import MoneyOrPortfolioFraction, ValueKind
from ats.contracts.governance.types import ConstraintCode, StrategyExecutionMode
from ats.kernel.constraints import compose_constraints
from ats.kernel.order_guard import constraints_no_broader

from tests.unit.kernel.fixtures import make_kernel_fixture


def money(value: str) -> MoneyOrPortfolioFraction:
    return MoneyOrPortfolioFraction(kind=ValueKind.MONEY, value=Decimal(value))


def test_all_fifteen_constraints_use_strictest_wins() -> None:
    x = make_kernel_fixture()
    effective = x["constraints"]
    assert effective.maximum_loss_per_trade.value == Decimal("100")
    assert effective.maximum_campaign_loss.value == Decimal("100")
    assert effective.drawdown_limit == Decimal("0.1")
    assert effective.max_trades == 10
    assert effective.max_concurrent_positions == 2
    assert effective.capital_budget == Decimal("10000")
    assert effective.maximum_budget_per_trade.value == Decimal("100")
    assert effective.minimum_calibrated_probability == Decimal("0.6")
    assert effective.minimum_calibration_support == 20
    assert effective.minimum_expected_edge_r == 0.2
    assert effective.minimum_reward_risk == Decimal("2")
    assert effective.allowed_instruments == ("ABC",)
    assert effective.allowed_timeframes == ("5m",)
    assert len(effective.allowed_strategies) == 1
    assert effective.strategy_execution_mode is StrategyExecutionMode.CHAMPION_ONLY
    assert {item.constraint_code for item in x["provenance"]} == set(ConstraintCode)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("maximum_loss_per_trade", money("90"), Decimal("90")),
        ("maximum_campaign_loss", money("90"), Decimal("90")),
        ("drawdown_limit", Decimal("0.05"), Decimal("0.05")),
        ("max_trades", 5, 5),
        ("max_concurrent_positions", 1, 1),
        ("capital_budget", Decimal("9000"), Decimal("9000")),
        ("maximum_budget_per_trade", money("90"), Decimal("90")),
    ],
)
def test_tightening_maximum_never_broadens(field: str, value: object, expected: object) -> None:
    x = make_kernel_fixture()
    system = x["system"].model_copy(update={field: value})
    result = compose_constraints(system, x["policy"], x["campaign"], capital_basis=x["basis"])
    actual = getattr(result.effective, field)
    assert getattr(actual, "value", actual) == expected
    assert constraints_no_broader(result.effective, x["constraints"], capital_basis=x["basis"])


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("minimum_calibrated_probability", Decimal("0.7"), Decimal("0.7")),
        ("minimum_calibration_support", 30, 30),
        ("minimum_expected_edge_r", 0.3, 0.3),
        ("minimum_reward_risk", Decimal("3"), Decimal("3")),
    ],
)
def test_raising_minimum_never_broadens(field: str, value: object, expected: object) -> None:
    x = make_kernel_fixture()
    system = x["system"].model_copy(update={field: value})
    result = compose_constraints(system, x["policy"], x["campaign"], capital_basis=x["basis"])
    assert getattr(result.effective, field) == expected
    assert constraints_no_broader(result.effective, x["constraints"], capital_basis=x["basis"])


def test_allowlist_intersection_cannot_gain_and_empty_fails_closed() -> None:
    x = make_kernel_fixture()
    restricted = x["system"].model_copy(update={"allowed_instruments": ("ABC",)})
    result = compose_constraints(restricted, x["policy"], x["campaign"], capital_basis=x["basis"])
    assert set(result.effective.allowed_instruments) <= set(x["constraints"].allowed_instruments)
    empty = x["system"].model_copy(update={"allowed_instruments": ("XYZ",)})
    with pytest.raises(ValueError):
        compose_constraints(empty, x["policy"], x["campaign"], capital_basis=x["basis"])


def test_set_like_input_order_does_not_change_semantics() -> None:
    x = make_kernel_fixture()
    system = x["system"].model_copy(
        update={
            "allowed_instruments": tuple(reversed(x["system"].allowed_instruments)),
            "allowed_timeframes": tuple(reversed(x["system"].allowed_timeframes)),
        }
    )
    first = compose_constraints(x["system"], x["policy"], x["campaign"], capital_basis=x["basis"])
    second = compose_constraints(system, x["policy"], x["campaign"], capital_basis=x["basis"])
    assert first.effective == second.effective


def test_repeated_composition_is_deterministic() -> None:
    x = make_kernel_fixture()
    first = compose_constraints(x["system"], x["policy"], x["campaign"], capital_basis=x["basis"])
    second = compose_constraints(x["system"], x["policy"], x["campaign"], capital_basis=x["basis"])
    assert first == second


def test_explanatory_selected_value_cannot_change_typed_authority() -> None:
    x = make_kernel_fixture()
    changed = tuple(
        item.model_copy(update={"selected_value": "999999999"}) for item in x["provenance"]
    )
    assert changed != x["provenance"]
    assert x["constraints"].maximum_loss_per_trade.value == Decimal("100")


def test_missing_fraction_basis_fails_closed() -> None:
    x = make_kernel_fixture()
    fractional = x["system"].model_copy(
        update={
            "maximum_loss_per_trade": MoneyOrPortfolioFraction(
                kind=ValueKind.PORTFOLIO_FRACTION, value=Decimal("0.01")
            )
        }
    )
    with pytest.raises(ValueError):
        compose_constraints(fractional, x["policy"], x["campaign"], capital_basis=None)
