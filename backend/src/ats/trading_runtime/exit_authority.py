# ruff: noqa: E501
"""Deterministic exit authority — dashboard/manual/automatic exits converge here."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.models import ExitIntent, Position
from ats.contracts.domain.types import PaperOrderType
from ats.kernel.order_guard import validate_exit_intent
from ats.kernel.types import ExecutionSafetyFacts, ExitEvaluationFacts, KernelOutcome


@dataclass(frozen=True)
class ExitRequest:
    position_id: UUID
    quantity: Decimal
    order_type: PaperOrderType = PaperOrderType.MARKET


@dataclass(frozen=True)
class ExitDecision:
    allowed: bool
    reason_codes: tuple[str, ...]
    exit_intent: ExitIntent | None


def authorize_exit(
    *,
    request: ExitRequest,
    position: Position,
    exit_intent_id: UUID,
    risk_decision_id: UUID,
    autonomy_token_id: UUID,
    idempotency_key: str,
    created_at: UTCDateTime,
    execution_safety: ExecutionSafetyFacts,
    current_system_state_version: int,
    token: object,
    candidate: object,
    context: object,
    campaign_state: object,
    issued_constraints: object,
    current_constraints: object,
) -> ExitDecision:
    _ = (token, candidate, context, campaign_state, issued_constraints, current_constraints)
    from ats.contracts.domain.hashing import compute_payload_hash

    intent = ExitIntent(
        schema_version="1.0",
        exit_intent_id=exit_intent_id,
        position_id=request.position_id,
        position_version=position.version,
        reason=__import__("ats.contracts.domain.types", fromlist=["ExitReason"]).ExitReason.RISK,
        quantity=request.quantity,
        order_type=request.order_type,
        limit_price=None,
        stop_price=None,
        risk_decision_id=risk_decision_id,
        autonomy_token_id=autonomy_token_id,
        idempotency_key=idempotency_key,
        created_at=created_at,
        payload_hash="0" * 64,
    )
    intent = intent.model_copy(update={"payload_hash": compute_payload_hash(intent)})

    facts = ExitEvaluationFacts(reducible_quantity=position.net_quantity)
    from ats.contracts.governance.types import RiskDirection as _RD

    risk_dir = getattr(context, "risk_direction", None)
    if risk_dir is not _RD.REDUCE:  # noqa: E501
        return ExitDecision(
            allowed=False, reason_codes=("EXIT_REQUIRES_REDUCE_CONTEXT",), exit_intent=None
        )

    result = validate_exit_intent(
        intent,
        token=token,  # type: ignore[arg-type]
        candidate=candidate,  # type: ignore[arg-type]
        position=position,
        context=context,  # type: ignore[arg-type]
        exit_facts=facts,
        execution_safety=execution_safety,
        evaluation_time=created_at,
        current_system_state_version=current_system_state_version,
    )
    if result.outcome is not KernelOutcome.ALLOW:
        codes = tuple(str(c) for c in result.reason_codes)
        return ExitDecision(allowed=False, reason_codes=codes, exit_intent=None)
    return ExitDecision(allowed=True, reason_codes=("EXIT_AUTHORIZED",), exit_intent=intent)


__all__ = ["ExitDecision", "ExitRequest", "authorize_exit"]
