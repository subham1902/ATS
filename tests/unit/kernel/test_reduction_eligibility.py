from __future__ import annotations

from decimal import Decimal

from ats.contracts.governance.types import ActionKind, RiskDirection
from ats.kernel.reduction import validate_reduction_eligibility
from ats.kernel.types import KernelOutcome
from tests.unit.contracts.domain.fixtures import make_contracts
from tests.unit.kernel.fixtures import T0, _validated, make_kernel_fixture, uid


def _context(*, position_id, policy_id, policy_version):
    x = make_kernel_fixture()
    return _validated(
        x["context"],
        action_subject_id=position_id,
        action_kind=ActionKind.CLOSE_POSITION,
        risk_direction=RiskDirection.REDUCE,
        candidate_id=None,
        candidate_version=None,
        position_thesis_id=uid(990),
        position_thesis_version=1,
        policy_id=policy_id,
        policy_version=policy_version,
    )


def test_position_bound_reduction_allows_safe_close_without_candidate() -> None:
    x = make_kernel_fixture()
    position = make_contracts()["Position"]
    policy = _validated(
        x["policy"], policy_id=position.policy_id, policy_version=position.policy_version
    )
    context = _context(
        position_id=position.position_id,
        policy_id=position.policy_id,
        policy_version=position.policy_version,
    )
    result = validate_reduction_eligibility(
        position=position,
        context=context,
        policy=policy,
        entry_constraints=x["constraints"],
        current_constraints=x["constraints"],
        capital_basis=x["basis"],
        requested_quantity=Decimal("10"),
        execution_safety=x["safety"],
        current_system_state_version=1,
        unresolved_reduction_exists=False,
        evaluation_time=T0,
    )
    assert result.outcome is KernelOutcome.ALLOW


def test_position_binding_quantity_and_pending_reduction_fail_closed() -> None:
    x = make_kernel_fixture()
    position = make_contracts()["Position"]
    policy = _validated(
        x["policy"], policy_id=position.policy_id, policy_version=position.policy_version
    )
    context = _context(
        position_id=uid(991), policy_id=position.policy_id, policy_version=position.policy_version
    )
    result = validate_reduction_eligibility(
        position=position,
        context=context,
        policy=policy,
        entry_constraints=x["constraints"],
        current_constraints=x["constraints"],
        capital_basis=x["basis"],
        requested_quantity=Decimal("11"),
        execution_safety=x["safety"],
        current_system_state_version=1,
        unresolved_reduction_exists=True,
        evaluation_time=T0,
    )
    assert result.outcome is KernelOutcome.DENY
