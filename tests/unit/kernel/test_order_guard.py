from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from ats.contracts.domain.models import ExitIntent
from ats.contracts.domain.types import ExitReason, PaperOrderType, Side
from ats.contracts.governance.types import ActionKind, RiskDirection, SystemState
from ats.kernel.autonomy import construct_autonomy_token, validate_token_eligibility
from ats.kernel.order_guard import validate_exit_intent, validate_order_intent
from ats.kernel.types import (
    AutonomyTokenPolicy,
    ExecutionSafetyFacts,
    ExitEvaluationFacts,
    KernelOutcome,
)

from tests.unit.kernel.fixtures import T0, _validated, make_kernel_fixture, uid


def _token(x: dict[str, object]):  # type: ignore[no-untyped-def]
    eligibility = validate_token_eligibility(
        policy=x["policy"],
        campaign=x["campaign"],
        campaign_state=x["campaign_state"],
        market=x["market"],
        thesis=x["thesis"],
        distribution=x["distribution"],
        candidate=x["candidate"],
        strategy=x["strategy"],
        context=x["context"],
        risk_decision=x["risk_decision"],
        advisory=x["advisory"],
        packet=x["packet"],
        binding=x["binding"],
        constraints=x["constraints"],
        campaign_facts=x["campaign_facts"],
        capital_basis=x["basis"],
        execution_safety=x["safety"],
        evaluation_time=T0,
        maximum_freshness_ms=1000,
        current_system_state_version=1,
        model_family="model",
        model_version="1",
        calibrator_version="1",
    )
    return construct_autonomy_token(
        eligibility=eligibility,
        token_id=uid(84),
        candidate=x["candidate"],
        policy=x["policy"],
        risk_decision=x["risk_decision"],
        advisory=x["advisory"],
        context=x["context"],
        issued_at=T0,
        expires_at=T0 + timedelta(seconds=30),
        nonce="nonce",
        token_policy=AutonomyTokenPolicy(max_ttl_ms=30000),
    )


def _guard(x: dict[str, object], **changes: object):  # type: ignore[no-untyped-def]
    values = {
        "intent": x["order"],
        "token": _token(x),
        "candidate": x["candidate"],
        "context": x["context"],
        "campaign_state": x["campaign_state"],
        "issued_constraints": x["constraints"],
        "current_constraints": x["constraints"],
        "capital_basis": x["basis"],
        "order_facts": x["order_facts"],
        "order_policy": x["order_policy"],
        "execution_safety": x["safety"],
        "evaluation_time": T0,
        "current_system_state_version": 1,
    }
    values.update(changes)
    return validate_order_intent(**values)


def test_valid_token_and_exact_order_allows_stage2() -> None:
    x = make_kernel_fixture()
    assert _guard(x).outcome is KernelOutcome.ALLOW


def test_token_alone_cannot_authorize_wrong_instrument_or_side() -> None:
    x = make_kernel_fixture()
    for change in ({"instrument_id": "XYZ"}, {"side": Side.SELL}):
        intent = _validated(x["order"], **change)
        assert _guard(x, intent=intent).outcome is KernelOutcome.DENY
    rebound_candidate = _validated(x["candidate"], risk_decision_id=uid(99))
    assert _guard(x, candidate=rebound_candidate).outcome is KernelOutcome.DENY


def test_valid_token_cannot_authorize_oversize_loss_or_budget() -> None:
    x = make_kernel_fixture()
    high_loss = x["order_facts"].model_copy(update={"estimated_maximum_loss": Decimal("101")})
    assert _guard(x, order_facts=high_loss).outcome is KernelOutcome.DENY
    high_budget = x["order_facts"].model_copy(update={"estimated_notional": Decimal("101")})
    assert _guard(x, order_facts=high_budget).outcome is KernelOutcome.DENY


def test_notional_and_cost_degraded_economics_deny() -> None:
    x = make_kernel_fixture()
    wrong_notional = x["order_facts"].model_copy(update={"estimated_notional": Decimal("99")})
    assert _guard(x, order_facts=wrong_notional).outcome is KernelOutcome.DENY
    costs = x["order_facts"].model_copy(
        update={"estimated_fees": Decimal("60"), "estimated_slippage": Decimal("50")}
    )
    assert _guard(x, order_facts=costs).outcome is KernelOutcome.DENY


def test_stale_state_exhausted_campaign_and_loosened_constraint_deny() -> None:
    x = make_kernel_fixture()
    assert _guard(x, current_system_state_version=2).outcome is KernelOutcome.DENY
    exhausted = _validated(x["campaign_state"], capital_committed=Decimal("10000"))
    assert _guard(x, campaign_state=exhausted).outcome is KernelOutcome.DENY
    loosened = x["constraints"].model_copy(update={"capital_budget": Decimal("20000")})
    assert _guard(x, current_constraints=loosened).outcome is KernelOutcome.DENY


def test_consumed_token_and_ambiguous_execution_deny() -> None:
    x = make_kernel_fixture()
    consumed = _validated(_token(x), consumed_at=T0)
    assert _guard(x, token=consumed).outcome is KernelOutcome.DENY
    unsafe = ExecutionSafetyFacts(
        position_state_known=True,
        execution_state_known=False,
        position_ownership_known=True,
        ambiguous_exit_pending=True,
        reconciliation_mismatch=True,
    )
    context = x["context"].model_copy(update={"system_state": SystemState.RECONCILING})
    assert _guard(x, context=context, execution_safety=unsafe).outcome is KernelOutcome.DENY


def test_exit_guard_requires_binding_quantity_and_safe_reduction() -> None:
    x = make_kernel_fixture()
    token = _token(x)
    from tests.unit.contracts.domain.fixtures import make_contracts as make_a02

    real_position = make_a02()["Position"]
    context = _validated(
        x["context"],
        action_kind=ActionKind.CLOSE_POSITION,
        risk_direction=RiskDirection.REDUCE,
        position_thesis_id=uid(90),
        position_thesis_version=1,
    )
    exit_intent = ExitIntent(
        schema_version="1.0",
        exit_intent_id=uid(91),
        position_id=real_position.position_id,
        position_version=real_position.version,
        reason=ExitReason.TARGET,
        quantity=Decimal("10"),
        order_type=PaperOrderType.MARKET,
        limit_price=None,
        stop_price=None,
        risk_decision_id=token.risk_decision_id,
        autonomy_token_id=token.token_id,
        idempotency_key="exit",
        created_at=T0,
        payload_hash="0" * 64,
    )
    result = validate_exit_intent(
        exit_intent,
        token=token,
        candidate=x["candidate"],
        position=real_position,
        context=context,
        exit_facts=ExitEvaluationFacts(reducible_quantity=Decimal("10")),
        execution_safety=x["safety"],
        evaluation_time=T0,
        current_system_state_version=1,
    )
    assert result.outcome is KernelOutcome.ALLOW
    too_large = exit_intent.model_copy(update={"quantity": Decimal("11")})
    assert (
        validate_exit_intent(
            too_large,
            token=token,
            candidate=x["candidate"],
            position=real_position,
            context=context,
            exit_facts=ExitEvaluationFacts(reducible_quantity=Decimal("10")),
            execution_safety=x["safety"],
            evaluation_time=T0,
            current_system_state_version=1,
        ).outcome
        is KernelOutcome.DENY
    )
