"""Monotonic loss-state helpers; no adaptive trading behavior."""

from __future__ import annotations

from ats.contracts.domain.types import LossState, LossStatePolicy

from .types import ALLOW, GateCode, KernelOutcome, KernelResult

LOSS_STATE_ORDER = {
    LossState.NORMAL: 0,
    LossState.CAUTION: 1,
    LossState.COOLDOWN: 2,
    LossState.HALTED: 3,
}


def validate_loss_state_policy(policy: LossStatePolicy) -> KernelResult:
    expected = tuple(sorted(policy.states, key=LOSS_STATE_ORDER.__getitem__))
    if policy.states != expected or len(set(policy.states)) != len(LOSS_STATE_ORDER):
        return KernelResult(
            outcome=KernelOutcome.DENY,
            reason_codes=(GateCode.LOSS_STATE_NON_MONOTONIC,),
        )
    return ALLOW


def validate_loss_state_transition(current: LossState, proposed: LossState) -> KernelResult:
    if LOSS_STATE_ORDER[proposed] < LOSS_STATE_ORDER[current]:
        return KernelResult(
            outcome=KernelOutcome.DENY,
            reason_codes=(GateCode.LOSS_STATE_NON_MONOTONIC,),
        )
    return ALLOW


__all__ = ["LOSS_STATE_ORDER", "validate_loss_state_policy", "validate_loss_state_transition"]
