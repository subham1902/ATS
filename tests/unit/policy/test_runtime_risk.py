from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from ats.policy import (
    RiskPolicyQuery,
    RiskPolicyScope,
    RuntimeRiskConstraints,
    RuntimeRiskOverride,
    bind_runtime_risk_policy,
    resolve_runtime_constraints,
)
from ats.trading_runtime.modes import TradingMode

NOW = datetime(2026, 8, 27, tzinfo=UTC)


def policy():
    return bind_runtime_risk_policy(
        {
            "schema_version": "1.0",
            "policy_id": uuid4(),
            "policy_version": 1,
            "created_at": NOW,
            "effective_from": NOW,
            "source": "PROVISIONAL_SAFE_DEFAULTS_NOT_EMPIRICALLY_OPTIMAL",
            "base": RuntimeRiskConstraints(
                maximum_spread_fraction=Decimal("0.05"),
                maximum_positions=4,
                maximum_utilization=Decimal("0.8"),
                minimum_expected_net_value=Decimal("5"),
                minimum_liquidity=Decimal("0.5"),
            ),
            "overrides": (
                RuntimeRiskOverride(
                    scope=RiskPolicyScope(mode=TradingMode.SAFE),
                    constraints=RuntimeRiskConstraints(
                        maximum_spread_fraction=Decimal("0.02"),
                        maximum_positions=1,
                        maximum_utilization=Decimal("0.3"),
                        minimum_expected_net_value=Decimal("20"),
                        minimum_liquidity=Decimal("0.8"),
                    ),
                ),
            ),
        }
    )


def query() -> RiskPolicyQuery:
    return RiskPolicyQuery(
        mode=TradingMode.SAFE,
        underlying="NIFTY",
        strategy_id=uuid4(),
        expiry_bucket="NEAR",
        regime="TREND",
        session_phase="ENTRY_ALLOWED",
    )


def test_strictest_constraints_win_across_matching_scopes() -> None:
    result = resolve_runtime_constraints(policy(), query=query(), evaluation_time=NOW)
    assert result.maximum_spread_fraction == Decimal("0.02")
    assert result.maximum_positions == 1
    assert result.maximum_utilization == Decimal("0.3")
    assert result.minimum_expected_net_value == Decimal("20")
    assert result.minimum_liquidity == Decimal("0.8")


def test_tamper_or_not_yet_effective_fails_closed() -> None:
    value = policy()
    tampered = value.model_copy(update={"source": "changed"})
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        resolve_runtime_constraints(tampered, query=query(), evaluation_time=NOW)
    with pytest.raises(ValueError, match="NOT_EFFECTIVE"):
        resolve_runtime_constraints(value, query=query(), evaluation_time=NOW.replace(year=2025))
