"""Pure semantic validation for the frozen A02 StrategyPolicy."""

from __future__ import annotations

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.models import StrategyPolicy
from ats.contracts.domain.types import AutonomyLevel, PolicyStatus, contains_executable_marker

from .loss_state import validate_loss_state_policy
from .types import ALLOW, GateCode, KernelOutcome, KernelResult


def validate_strategy_policy(
    policy: StrategyPolicy,
    *,
    evaluation_time: UTCDateTime,
    timeframe: str,
    event_definition_id: str,
    model_version: str,
    calibrator_version: str,
) -> KernelResult:
    reasons: list[GateCode] = []
    if policy.lifecycle_status is not PolicyStatus.ACTIVE:
        reasons.append(GateCode.POLICY_INACTIVE)
    if policy.autonomy_level is not AutonomyLevel.A2:
        reasons.append(GateCode.AUTONOMY_NOT_A2)
    if not policy.valid_from <= evaluation_time < policy.valid_until:
        reasons.append(GateCode.POLICY_TIME_INVALID)
    if (
        policy.timeframe != timeframe
        or policy.event_definition_id != event_definition_id
        or model_version not in policy.compatible_model_versions
        or calibrator_version not in policy.compatible_calibrator_versions
    ):
        reasons.append(GateCode.POLICY_INCOMPATIBLE)
    if any(contains_executable_marker(item.value) for item in policy.entry_predicates):
        reasons.append(GateCode.POLICY_INCOMPATIBLE)
    if (
        validate_loss_state_policy(policy.after_loss_state_machine).outcome
        is not KernelOutcome.ALLOW
    ):
        reasons.append(GateCode.LOSS_STATE_NON_MONOTONIC)
    if not any(rule.hard_stop for rule in policy.stop_rules):
        reasons.append(GateCode.POLICY_INCOMPATIBLE)
    if not policy.target_rules and policy.time_exit is None:
        reasons.append(GateCode.POLICY_INCOMPATIBLE)
    if reasons:
        return KernelResult(outcome=KernelOutcome.DENY, reason_codes=tuple(dict.fromkeys(reasons)))
    return ALLOW


__all__ = ["validate_strategy_policy"]
