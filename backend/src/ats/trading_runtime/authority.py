"""TEST_ONLY-free authority wiring: portfolio reservation + A04 token/order binding.

This module contains no market-data fabrication. It binds the existing frozen
A04 kernel (autonomy + order_guard) and the existing SerializedPortfolioAuthority
(R17 durable) into the P0 runtime engine's candidate -> order path.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.models import AutonomyToken, OrderIntent
from ats.contracts.domain.types import PaperOrderType
from ats.contracts.governance.models import OpportunityCandidate
from ats.kernel.autonomy import construct_autonomy_token, validate_token_for_use
from ats.kernel.order_guard import validate_order_intent
from ats.kernel.types import KernelOutcome
from ats.portfolio.persistence import CapitalReservationRequest
from ats.portfolio.runtime import PortfolioReservationCommand, SerializedPortfolioAuthority

_AUTHORITY_NS = UUID("9f1a7c3e-4b2a-5c1d-9e3f-1a2b3c4d5e6f")


@dataclass(frozen=True)
class AuthorityBundle:
    token: AutonomyToken
    order_intent: OrderIntent
    reservation_id: UUID


def wire_candidate_to_order(
    *,
    candidate: OpportunityCandidate,
    token_inputs: dict[str, object],
    order_inputs: dict[str, object],
    portfolio_authority: SerializedPortfolioAuthority,
    reservation_request: CapitalReservationRequest,
    reservation_partition: object,
    evaluation_time: UTCDateTime,
    current_system_state_version: int,
) -> AuthorityBundle:
    from ats.portfolio.runtime import ReservationPartition

    assert isinstance(reservation_partition, ReservationPartition)
    eligibility = token_inputs["eligibility"]  # KernelResult
    assert hasattr(eligibility, "outcome")
    if eligibility.outcome is not KernelOutcome.ALLOW:
        raise ValueError("token eligibility did not ALLOW")

    token = construct_autonomy_token(
        eligibility=eligibility,  # type: ignore[arg-type]
        token_id=token_inputs["token_id"],  # type: ignore[arg-type]
        candidate=candidate,
        policy=token_inputs["policy"],  # type: ignore[arg-type]
        risk_decision=token_inputs["risk_decision"],  # type: ignore[arg-type]
        advisory=token_inputs["advisory"],  # type: ignore[arg-type]
        context=token_inputs["context"],  # type: ignore[arg-type]
        issued_at=token_inputs["issued_at"],  # type: ignore[arg-type]
        expires_at=token_inputs["expires_at"],  # type: ignore[arg-type]
        nonce=token_inputs["nonce"],  # type: ignore[arg-type]
        token_policy=token_inputs["token_policy"],  # type: ignore[arg-type]
    )

    command = PortfolioReservationCommand(
        request=reservation_request, partition=reservation_partition
    )
    reserved = portfolio_authority.reserve(command)

    order_intent = OrderIntent(
        schema_version="1.0",
        intent_id=order_inputs["intent_id"],  # type: ignore[arg-type]
        instrument_id=candidate.instrument_id,
        side=candidate.side,
        quantity=order_inputs["quantity"],  # type: ignore[arg-type]
        order_type=order_inputs.get("order_type", PaperOrderType.MARKET),  # type: ignore[arg-type]
        entry_conditions=candidate.entry_conditions,
        limit_price=order_inputs.get("limit_price"),  # type: ignore[arg-type]
        stop_price=order_inputs.get("stop_price"),  # type: ignore[arg-type]
        target_price=candidate.proposed_target_price,
        maximum_permitted_loss=order_inputs["maximum_permitted_loss"],  # type: ignore[arg-type]
        expected_reward=order_inputs["expected_reward"],  # type: ignore[arg-type]
        policy_id=token.policy_id,
        policy_version=token.policy_version,
        forecast_id=candidate.distribution_id,
        risk_decision_id=token.risk_decision_id,
        supervisor_advisory_id=token.advisory_id,
        autonomy_token_id=token.token_id,
        idempotency_key=order_inputs["idempotency_key"],  # type: ignore[arg-type]
        created_at=evaluation_time,
        payload_hash="0" * 64,
    )
    from ats.contracts.domain.hashing import compute_payload_hash

    order_intent = order_intent.model_copy(
        update={"payload_hash": compute_payload_hash(order_intent)}
    )

    guard_result = validate_order_intent(
        order_intent,
        token=token,
        candidate=candidate,
        context=token_inputs["context"],  # type: ignore[arg-type]
        campaign_state=order_inputs["campaign_state"],  # type: ignore[arg-type]
        issued_constraints=order_inputs["issued_constraints"],  # type: ignore[arg-type]
        current_constraints=order_inputs["current_constraints"],  # type: ignore[arg-type]
        capital_basis=order_inputs.get("capital_basis"),  # type: ignore[arg-type]
        order_facts=order_inputs["order_facts"],  # type: ignore[arg-type]
        order_policy=order_inputs["order_policy"],  # type: ignore[arg-type]
        execution_safety=order_inputs["execution_safety"],  # type: ignore[arg-type]
        evaluation_time=evaluation_time,
        current_system_state_version=current_system_state_version,
    )
    if guard_result.outcome is not KernelOutcome.ALLOW:
        portfolio_authority.release(reserved.reservation.reservation_id, updated_at=evaluation_time)
        raise ValueError(f"order guard denied: {guard_result.reason_codes}")

    token_check = validate_token_for_use(
        token,
        evaluation_time=evaluation_time,
        candidate_id=candidate.candidate_id,
        policy_id=token.policy_id,
        policy_version=token.policy_version,
        risk_decision_id=token.risk_decision_id,
        advisory_id=token.advisory_id,
        current_system_state_version=current_system_state_version,
    )
    if token_check.outcome is not KernelOutcome.ALLOW:
        portfolio_authority.release(reserved.reservation.reservation_id, updated_at=evaluation_time)
        raise ValueError(f"token validation failed: {token_check.reason_codes}")

    return AuthorityBundle(
        token=token, order_intent=order_intent, reservation_id=reserved.reservation.reservation_id
    )


__all__ = ["AuthorityBundle", "wire_candidate_to_order"]
