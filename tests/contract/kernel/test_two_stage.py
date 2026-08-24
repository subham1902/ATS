from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from ats.contracts.domain.types import Side
from ats.contracts.governance.types import StrategyExecutionMode, SystemState
from ats.contracts.intelligence.types import StrategyStatus
from ats.kernel.autonomy import (
    construct_autonomy_token,
    validate_decision_packet_binding,
    validate_token_eligibility,
    validate_token_for_use,
)
from ats.kernel.governance import validate_strategy_status
from ats.kernel.order_guard import validate_order_intent
from ats.kernel.types import AutonomyTokenPolicy, KernelOutcome

from tests.unit.kernel.fixtures import T0, _validated, make_kernel_fixture, uid


def authorize(x: dict[str, object]):  # type: ignore[no-untyped-def]
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
    token = construct_autonomy_token(
        eligibility=eligibility,
        token_id=uid(84),
        candidate=x["candidate"],
        policy=x["policy"],
        risk_decision=x["risk_decision"],
        advisory=x["advisory"],
        context=x["context"],
        issued_at=T0,
        expires_at=T0 + timedelta(seconds=30),
        nonce="caller-nonce",
        token_policy=AutonomyTokenPolicy(max_ttl_ms=30000),
    )
    return eligibility, token


def guard(x: dict[str, object], token: object, **changes: object):  # type: ignore[no-untyped-def]
    args = {
        "intent": x["order"],
        "token": token,
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
    args.update(changes)
    return validate_order_intent(**args)


def test_valid_candidate_gate_token_and_exact_order() -> None:
    x = make_kernel_fixture()
    eligibility, token = authorize(x)
    assert eligibility.outcome is KernelOutcome.ALLOW
    assert guard(x, token).outcome is KernelOutcome.ALLOW


def test_valid_token_is_not_unrestricted_order_authority() -> None:
    x = make_kernel_fixture()
    _, token = authorize(x)
    oversized = x["order_facts"].model_copy(update={"estimated_maximum_loss": Decimal("101")})
    wrong_instrument = _validated(x["order"], instrument_id="XYZ")
    wrong_side = _validated(x["order"], side=Side.SELL)
    assert guard(x, token, order_facts=oversized).outcome is KernelOutcome.DENY
    assert guard(x, token, intent=wrong_instrument).outcome is KernelOutcome.DENY
    assert guard(x, token, intent=wrong_side).outcome is KernelOutcome.DENY


def test_post_issuance_state_budget_and_constraint_changes_deny() -> None:
    x = make_kernel_fixture()
    _, token = authorize(x)
    assert guard(x, token, current_system_state_version=2).outcome is KernelOutcome.DENY
    exhausted = _validated(x["campaign_state"], capital_committed=Decimal("10000"))
    assert guard(x, token, campaign_state=exhausted).outcome is KernelOutcome.DENY
    loosened = x["constraints"].model_copy(update={"max_trades": 20})
    assert guard(x, token, current_constraints=loosened).outcome is KernelOutcome.DENY


def test_consumed_expired_and_reference_mismatched_tokens_deny() -> None:
    x = make_kernel_fixture()
    _, token = authorize(x)
    consumed = _validated(token, consumed_at=T0)
    common = {
        "candidate_id": token.candidate_id,
        "policy_id": token.policy_id,
        "policy_version": token.policy_version,
        "risk_decision_id": token.risk_decision_id,
        "advisory_id": token.advisory_id,
        "current_system_state_version": 1,
    }
    assert (
        validate_token_for_use(consumed, evaluation_time=T0, **common).outcome is KernelOutcome.DENY
    )
    assert (
        validate_token_for_use(token, evaluation_time=token.expires_at, **common).outcome
        is KernelOutcome.DENY
    )
    assert (
        validate_token_for_use(
            token, evaluation_time=T0, **{**common, "candidate_id": uid(999)}
        ).outcome
        is KernelOutcome.DENY
    )


def test_decision_packet_binding_is_typed_and_hash_bound() -> None:
    x = make_kernel_fixture()
    assert (
        validate_decision_packet_binding(
            x["packet"],
            x["binding"],
            candidate=x["candidate"],
            context=x["context"],
            campaign=x["campaign"],
            thesis=x["thesis"],
            distribution=x["distribution"],
            strategy=x["strategy"],
            risk_decision=x["risk_decision"],
        ).outcome
        is KernelOutcome.ALLOW
    )
    wrong = x["binding"].model_copy(update={"candidate_version": 2})
    assert (
        validate_decision_packet_binding(
            x["packet"],
            wrong,
            candidate=x["candidate"],
            context=x["context"],
            campaign=x["campaign"],
            thesis=x["thesis"],
            distribution=x["distribution"],
            strategy=x["strategy"],
            risk_decision=x["risk_decision"],
        ).outcome
        is KernelOutcome.DENY
    )


def test_isolated_challenger_exception_is_exact() -> None:
    x = make_kernel_fixture()
    strategy = _validated(x["strategy"], status=StrategyStatus.CHALLENGER)
    campaign = _validated(
        x["campaign"], strategy_execution_mode=StrategyExecutionMode.ISOLATED_CHALLENGER_PAPER
    )
    assert validate_strategy_status(strategy, campaign).outcome is KernelOutcome.ALLOW


def test_stage1_stale_system_state_denies_token_eligibility() -> None:
    x = make_kernel_fixture()
    x["context"] = x["context"].model_copy(update={"system_state": SystemState.DEGRADED})
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
    assert eligibility.outcome is KernelOutcome.DENY
