"""Versioned provisional runtime-risk policy with deterministic strictest-wins scopes."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import NonEmptyStr, PositiveInt, Sha256
from ats.trading_runtime.modes import TradingMode


class RiskPolicyScope(ATSBaseModel):
    mode: TradingMode | None = None
    underlying: NonEmptyStr | None = None
    strategy_id: UUID | None = None
    expiry_bucket: NonEmptyStr | None = None
    regime: NonEmptyStr | None = None
    session_phase: NonEmptyStr | None = None


class RuntimeRiskConstraints(ATSBaseModel):
    maximum_spread_fraction: Decimal | None = None
    maximum_iv_collapse_fraction: Decimal | None = None
    maximum_theta_budget_fraction: Decimal | None = None
    minimum_directional_cooldown_minutes: PositiveInt | None = None
    maximum_positions: PositiveInt | None = None
    maximum_utilization: Decimal | None = None
    minimum_expected_net_value: Decimal | None = None
    minimum_liquidity: Decimal | None = None
    correlation_penalty: Decimal | None = None
    concentration_penalty: Decimal | None = None
    drawdown_penalty_multiplier: Decimal | None = None

    @model_validator(mode="after")
    def validate_values(self) -> RuntimeRiskConstraints:
        for name, value in self.model_dump().items():
            if value is not None and isinstance(value, Decimal) and value < 0:
                raise ValueError(f"{name} must be non-negative")
        return self


class RuntimeRiskOverride(ATSBaseModel):
    scope: RiskPolicyScope
    constraints: RuntimeRiskConstraints


class RuntimeRiskPolicy(ATSBaseModel):
    schema_version: Literal["1.0"]
    policy_id: UUID
    policy_version: PositiveInt
    created_at: UTCDateTime
    effective_from: UTCDateTime
    source: NonEmptyStr
    base: RuntimeRiskConstraints
    overrides: tuple[RuntimeRiskOverride, ...]
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_dates(self) -> RuntimeRiskPolicy:
        if self.effective_from < self.created_at:
            raise ValueError("effective_from must not precede created_at")
        return self


class RiskPolicyQuery(ATSBaseModel):
    mode: TradingMode
    underlying: NonEmptyStr
    strategy_id: UUID
    expiry_bucket: NonEmptyStr
    regime: NonEmptyStr
    session_phase: NonEmptyStr


_MAXIMUM_FIELDS = frozenset(
    {
        "maximum_spread_fraction",
        "maximum_iv_collapse_fraction",
        "maximum_theta_budget_fraction",
        "maximum_positions",
        "maximum_utilization",
    }
)


def bind_runtime_risk_policy(values: dict[str, object]) -> RuntimeRiskPolicy:
    draft = RuntimeRiskPolicy.model_validate({**values, "payload_hash": "0" * 64})
    return draft.model_copy(update={"payload_hash": compute_payload_hash(draft)})


def resolve_runtime_constraints(
    policy: RuntimeRiskPolicy, *, query: RiskPolicyQuery, evaluation_time: UTCDateTime
) -> RuntimeRiskConstraints:
    if policy.payload_hash != compute_payload_hash(policy):
        raise ValueError("RUNTIME_RISK_POLICY_HASH_MISMATCH")
    if evaluation_time < policy.effective_from:
        raise ValueError("RUNTIME_RISK_POLICY_NOT_EFFECTIVE")
    applicable = [policy.base]
    applicable.extend(item.constraints for item in policy.overrides if _matches(item.scope, query))
    resolved: dict[str, object] = {}
    for field in RuntimeRiskConstraints.model_fields:
        candidates = [
            getattr(item, field) for item in applicable if getattr(item, field) is not None
        ]
        if not candidates:
            resolved[field] = None
        elif field in _MAXIMUM_FIELDS:
            resolved[field] = min(candidates)
        else:
            resolved[field] = max(candidates)
    return RuntimeRiskConstraints.model_validate(resolved)


def _matches(scope: RiskPolicyScope, query: RiskPolicyQuery) -> bool:
    return all(
        expected is None or expected == actual
        for expected, actual in (
            (scope.mode, query.mode),
            (scope.underlying, query.underlying),
            (scope.strategy_id, query.strategy_id),
            (scope.expiry_bucket, query.expiry_bucket),
            (scope.regime, query.regime),
            (scope.session_phase, query.session_phase),
        )
    )


__all__ = [
    "RiskPolicyQuery",
    "RiskPolicyScope",
    "RuntimeRiskConstraints",
    "RuntimeRiskOverride",
    "RuntimeRiskPolicy",
    "bind_runtime_risk_policy",
    "resolve_runtime_constraints",
]
