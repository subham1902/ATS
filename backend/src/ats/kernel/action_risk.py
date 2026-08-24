"""Deterministic action-risk classification and declared-direction checks."""

from __future__ import annotations

from ats.contracts.domain.types import Side
from ats.contracts.governance.models import GovernanceContext
from ats.contracts.governance.types import ActionKind, RiskDirection

from .types import (
    CancelOrderFacts,
    GateCode,
    KernelOutcome,
    KernelResult,
    OrderSemanticRole,
    ProtectionChange,
    ProtectiveExitChangeFacts,
    RiskClassification,
    RiskClassificationStatus,
)

FIXED_DIRECTIONS = {
    ActionKind.OPEN_POSITION: RiskDirection.INCREASE,
    ActionKind.INCREASE_POSITION: RiskDirection.INCREASE,
    ActionKind.REDUCE_POSITION: RiskDirection.REDUCE,
    ActionKind.CLOSE_POSITION: RiskDirection.REDUCE,
    ActionKind.EMERGENCY_FLATTEN: RiskDirection.REDUCE,
}


def classify_protective_exit(facts: ProtectiveExitChangeFacts) -> RiskClassification:
    if facts.current_protective_price is None:
        return RiskClassification(
            status=RiskClassificationStatus.UNKNOWN,
            direction=None,
            protection_change=ProtectionChange.UNKNOWN,
            reason_codes=(GateCode.ACTION_RISK_UNKNOWN,),
        )
    if facts.proposed_protective_price is None:
        return RiskClassification(
            status=RiskClassificationStatus.CLASSIFIED,
            direction=RiskDirection.INCREASE,
            protection_change=ProtectionChange.REMOVED,
            reason_codes=(),
        )
    price_delta = facts.proposed_protective_price - facts.current_protective_price
    price_safer = price_delta > 0 if facts.position_side is Side.BUY else price_delta < 0
    price_riskier = price_delta < 0 if facts.position_side is Side.BUY else price_delta > 0
    quantity_safer = facts.proposed_protected_quantity > facts.current_protected_quantity
    quantity_riskier = facts.proposed_protected_quantity < facts.current_protected_quantity
    if price_riskier or quantity_riskier:
        change = ProtectionChange.LOOSENED
        direction = RiskDirection.INCREASE
    elif price_safer or quantity_safer:
        change = ProtectionChange.TIGHTENED
        direction = RiskDirection.REDUCE
    else:
        change = ProtectionChange.UNCHANGED
        direction = RiskDirection.NEUTRAL
    return RiskClassification(
        status=RiskClassificationStatus.CLASSIFIED,
        direction=direction,
        protection_change=change,
        reason_codes=(),
    )


def classify_cancel_order(facts: CancelOrderFacts) -> RiskClassification:
    if facts.role in (OrderSemanticRole.ENTRY, OrderSemanticRole.POSITION_INCREASE):
        direction = RiskDirection.REDUCE
    elif facts.role in (
        OrderSemanticRole.PROTECTIVE_EXIT,
        OrderSemanticRole.POSITION_REDUCTION,
    ):
        direction = RiskDirection.INCREASE
    else:
        return RiskClassification(
            status=RiskClassificationStatus.UNKNOWN,
            direction=None,
            protection_change=None,
            reason_codes=(GateCode.ACTION_RISK_UNKNOWN,),
        )
    return RiskClassification(
        status=RiskClassificationStatus.CLASSIFIED,
        direction=direction,
        protection_change=None,
        reason_codes=(),
    )


def classify_action(
    action_kind: ActionKind,
    *,
    protective_exit_facts: ProtectiveExitChangeFacts | None = None,
    cancel_order_facts: CancelOrderFacts | None = None,
) -> RiskClassification:
    if action_kind in FIXED_DIRECTIONS:
        return RiskClassification(
            status=RiskClassificationStatus.CLASSIFIED,
            direction=FIXED_DIRECTIONS[action_kind],
            protection_change=None,
            reason_codes=(),
        )
    if action_kind is ActionKind.MODIFY_PROTECTIVE_EXIT and protective_exit_facts is not None:
        return classify_protective_exit(protective_exit_facts)
    if action_kind is ActionKind.CANCEL_ORDER and cancel_order_facts is not None:
        return classify_cancel_order(cancel_order_facts)
    return RiskClassification(
        status=RiskClassificationStatus.UNKNOWN,
        direction=None,
        protection_change=None,
        reason_codes=(GateCode.ACTION_RISK_UNKNOWN,),
    )


def validate_declared_action_risk(
    context: GovernanceContext,
    *,
    protective_exit_facts: ProtectiveExitChangeFacts | None = None,
    cancel_order_facts: CancelOrderFacts | None = None,
) -> KernelResult:
    classification = classify_action(
        context.action_kind,
        protective_exit_facts=protective_exit_facts,
        cancel_order_facts=cancel_order_facts,
    )
    if classification.status is RiskClassificationStatus.UNKNOWN:
        return KernelResult(
            outcome=KernelOutcome.UNKNOWN,
            reason_codes=(GateCode.ACTION_RISK_UNKNOWN,),
        )
    if classification.direction is not context.risk_direction:
        return KernelResult(
            outcome=KernelOutcome.DENY,
            reason_codes=(GateCode.ACTION_RISK_MISMATCH,),
        )
    from .types import ALLOW

    return ALLOW


__all__ = [
    "FIXED_DIRECTIONS",
    "classify_action",
    "classify_cancel_order",
    "classify_protective_exit",
    "validate_declared_action_risk",
]
