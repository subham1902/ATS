from __future__ import annotations

from decimal import Decimal

import pytest
from ats.contracts.domain.types import AutonomyLevel, LossState, PolicyStatus, Side
from ats.contracts.governance.types import ActionKind, RiskDirection, SystemState
from ats.kernel.action_risk import classify_action, validate_declared_action_risk
from ats.kernel.governance import validate_system_state
from ats.kernel.loss_state import validate_loss_state_policy, validate_loss_state_transition
from ats.kernel.policy import validate_strategy_policy
from ats.kernel.types import (
    CancelOrderFacts,
    ExecutionSafetyFacts,
    KernelOutcome,
    OrderSemanticRole,
    ProtectionChange,
    ProtectiveExitChangeFacts,
)

from tests.unit.kernel.fixtures import T0, _validated, make_kernel_fixture


def test_active_a2_policy_semantics_allow() -> None:
    x = make_kernel_fixture()
    result = validate_strategy_policy(
        x["policy"],
        evaluation_time=T0,
        timeframe="5m",
        event_definition_id=str(x["candidate"].event_definition_id),  # type: ignore[attr-defined]
        model_version="1",
        calibrator_version="1",
    )
    assert result.outcome is KernelOutcome.ALLOW


@pytest.mark.parametrize("level", [AutonomyLevel.A0, AutonomyLevel.A1])
def test_non_a2_policy_denied(level: AutonomyLevel) -> None:
    x = make_kernel_fixture()
    policy = _validated(x["policy"], autonomy_level=level)
    result = validate_strategy_policy(
        policy,
        evaluation_time=T0,
        timeframe="5m",
        event_definition_id=str(x["candidate"].event_definition_id),  # type: ignore[attr-defined]
        model_version="1",
        calibrator_version="1",
    )
    assert result.outcome is KernelOutcome.DENY


def test_inactive_and_invalid_time_policy_denied() -> None:
    x = make_kernel_fixture()
    inactive = _validated(x["policy"], lifecycle_status=PolicyStatus.VALIDATED, activated_at=None)
    for policy, at in ((inactive, T0), (x["policy"], x["policy"].valid_until)):  # type: ignore[attr-defined]
        result = validate_strategy_policy(
            policy,
            evaluation_time=at,
            timeframe="5m",
            event_definition_id=str(x["candidate"].event_definition_id),  # type: ignore[attr-defined]
            model_version="1",
            calibrator_version="1",
        )
        assert result.outcome is KernelOutcome.DENY


def test_loss_state_progression_is_monotonic() -> None:
    x = make_kernel_fixture()
    assert (
        validate_loss_state_policy(x["policy"].after_loss_state_machine).outcome
        is KernelOutcome.ALLOW
    )  # type: ignore[attr-defined]
    assert (
        validate_loss_state_transition(LossState.CAUTION, LossState.COOLDOWN).outcome
        is KernelOutcome.ALLOW
    )
    assert (
        validate_loss_state_transition(LossState.HALTED, LossState.NORMAL).outcome
        is KernelOutcome.DENY
    )


@pytest.mark.parametrize(
    ("kind", "direction"),
    [
        (ActionKind.OPEN_POSITION, RiskDirection.INCREASE),
        (ActionKind.INCREASE_POSITION, RiskDirection.INCREASE),
        (ActionKind.REDUCE_POSITION, RiskDirection.REDUCE),
        (ActionKind.CLOSE_POSITION, RiskDirection.REDUCE),
        (ActionKind.EMERGENCY_FLATTEN, RiskDirection.REDUCE),
    ],
)
def test_fixed_action_classification(kind: ActionKind, direction: RiskDirection) -> None:
    assert classify_action(kind).direction is direction


@pytest.mark.parametrize(
    ("side", "current", "proposed", "direction", "change"),
    [
        (Side.BUY, "90", "95", RiskDirection.REDUCE, ProtectionChange.TIGHTENED),
        (Side.BUY, "95", "90", RiskDirection.INCREASE, ProtectionChange.LOOSENED),
        (Side.SELL, "110", "105", RiskDirection.REDUCE, ProtectionChange.TIGHTENED),
        (Side.SELL, "105", "110", RiskDirection.INCREASE, ProtectionChange.LOOSENED),
    ],
)
def test_protective_exit_classification(
    side: Side,
    current: str,
    proposed: str,
    direction: RiskDirection,
    change: ProtectionChange,
) -> None:
    result = classify_action(
        ActionKind.MODIFY_PROTECTIVE_EXIT,
        protective_exit_facts=ProtectiveExitChangeFacts(
            position_side=side,
            current_protective_price=Decimal(current),
            proposed_protective_price=Decimal(proposed),
            current_protected_quantity=Decimal("1"),
            proposed_protected_quantity=Decimal("1"),
        ),
    )
    assert (result.direction, result.protection_change) == (direction, change)


def test_removed_and_unknown_protection_fail_closed_direction() -> None:
    removed = ProtectiveExitChangeFacts(
        position_side=Side.BUY,
        current_protective_price=Decimal("90"),
        proposed_protective_price=None,
        current_protected_quantity=Decimal("1"),
        proposed_protected_quantity=Decimal("0"),
    )
    unknown = removed.model_copy(update={"current_protective_price": None})
    assert (
        classify_action(ActionKind.MODIFY_PROTECTIVE_EXIT, protective_exit_facts=removed).direction
        is RiskDirection.INCREASE
    )
    assert (
        classify_action(ActionKind.MODIFY_PROTECTIVE_EXIT, protective_exit_facts=unknown).direction
        is None
    )


@pytest.mark.parametrize(
    ("role", "direction"),
    [
        (OrderSemanticRole.ENTRY, RiskDirection.REDUCE),
        (OrderSemanticRole.POSITION_INCREASE, RiskDirection.REDUCE),
        (OrderSemanticRole.PROTECTIVE_EXIT, RiskDirection.INCREASE),
        (OrderSemanticRole.POSITION_REDUCTION, RiskDirection.INCREASE),
    ],
)
def test_cancel_role_classification(role: OrderSemanticRole, direction: RiskDirection) -> None:
    result = classify_action(
        ActionKind.CANCEL_ORDER, cancel_order_facts=CancelOrderFacts(role=role)
    )
    assert result.direction is direction


def test_declared_direction_mismatch_denied() -> None:
    x = make_kernel_fixture()
    context = _validated(
        x["context"],
        action_kind=ActionKind.CANCEL_ORDER,
        risk_direction=RiskDirection.INCREASE,
    )
    result = validate_declared_action_risk(
        context, cancel_order_facts=CancelOrderFacts(role=OrderSemanticRole.ENTRY)
    )
    assert result.outcome is KernelOutcome.DENY


@pytest.mark.parametrize(
    "state",
    [SystemState.DEGRADED, SystemState.RECONCILING, SystemState.HALTED, SystemState.UNKNOWN],
)
def test_nonready_increase_denied(state: SystemState) -> None:
    x = make_kernel_fixture()
    context = _validated(x["context"], system_state=state)
    assert validate_system_state(context, x["safety"]).outcome is KernelOutcome.DENY


def test_safe_reduction_matrix() -> None:
    x = make_kernel_fixture()
    for state in (SystemState.DEGRADED, SystemState.RECONCILING, SystemState.HALTED):
        context = _validated(
            x["context"],
            action_kind=ActionKind.CLOSE_POSITION,
            risk_direction=RiskDirection.REDUCE,
            position_thesis_id=x["candidate"].candidate_id,  # type: ignore[attr-defined]
            position_thesis_version=1,
        )
        context = context.model_copy(update={"system_state": state})
        assert validate_system_state(context, x["safety"]).outcome is KernelOutcome.ALLOW
    unsafe = ExecutionSafetyFacts(
        position_state_known=True,
        execution_state_known=False,
        position_ownership_known=True,
        ambiguous_exit_pending=True,
        reconciliation_mismatch=False,
    )
    assert validate_system_state(context, unsafe).outcome is KernelOutcome.DENY


def test_unknown_allows_only_known_safe_emergency_flatten() -> None:
    x = make_kernel_fixture()
    emergency = _validated(
        x["context"],
        action_kind=ActionKind.EMERGENCY_FLATTEN,
        risk_direction=RiskDirection.REDUCE,
    ).model_copy(update={"system_state": SystemState.UNKNOWN})
    assert validate_system_state(emergency, x["safety"]).outcome is KernelOutcome.ALLOW
    close = _validated(
        x["context"],
        action_kind=ActionKind.CLOSE_POSITION,
        risk_direction=RiskDirection.REDUCE,
        position_thesis_id=x["candidate"].candidate_id,  # type: ignore[attr-defined]
        position_thesis_version=1,
    ).model_copy(update={"system_state": SystemState.UNKNOWN})
    assert validate_system_state(close, x["safety"]).outcome is KernelOutcome.DENY
