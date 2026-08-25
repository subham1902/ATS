"""P0 fast safety loop — deterministic checks, no LLM, no synchronous analytics DB query."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.models import Position
from ats.contracts.domain.types import LossState
from ats.trading_runtime.session import SessionStatus


class SafetyVerdict(StrEnum):
    ALLOW_NEW_RISK = "ALLOW_NEW_RISK"
    BLOCK_NEW_RISK = "BLOCK_NEW_RISK"
    REQUIRE_REDUCE_ONLY = "REQUIRE_REDUCE_ONLY"
    REQUIRE_FLATTEN = "REQUIRE_FLATTEN"
    HALT = "HALT"


@dataclass(frozen=True)
class SafetyFacts:
    session: SessionStatus
    kill_switch_active: bool
    data_fresh: bool
    broker_healthy: bool
    capital_ok: bool
    clock_healthy: bool
    position_max_loss_breached: bool
    daily_loss_limit_breached: bool
    loss_state: LossState
    open_positions: tuple[Position, ...]
    current_equity: Decimal
    peak_equity: Decimal


@dataclass(frozen=True)
class SafetyResult:
    verdict: SafetyVerdict
    reason_codes: tuple[str, ...]
    block_new_risk: bool
    require_reduce_only: bool
    require_flatten: bool
    is_halted: bool


def evaluate_p0_safety(*, facts: SafetyFacts, evaluation_time: UTCDateTime) -> SafetyResult:
    _ = evaluation_time
    reasons: list[str] = []
    if facts.kill_switch_active:
        reasons.append("KILL_SWITCH_ACTIVE")
    if facts.session.is_halted:
        reasons.append("SESSION_HALTED")
    if facts.loss_state is LossState.HALTED:
        reasons.append("LOSS_STATE_HALTED")
    if facts.daily_loss_limit_breached:
        reasons.append("DAILY_LOSS_LIMIT_BREACHED")
    if facts.position_max_loss_breached:
        reasons.append("POSITION_MAX_LOSS_BREACHED")
    if not facts.broker_healthy:
        reasons.append("BROKER_UNHEALTHY")
    if not facts.clock_healthy:
        reasons.append("CLOCK_UNHEALTHY")
    if not facts.capital_ok:
        reasons.append("CAPITAL_INVARIANT_BREACHED")

    if reasons:
        halt_reasons = ("KILL_SWITCH_ACTIVE", "LOSS_STATE_HALTED", "SESSION_HALTED")
        if any(r in reasons for r in halt_reasons):
            return SafetyResult(
                verdict=SafetyVerdict.HALT,
                reason_codes=tuple(reasons),
                block_new_risk=True,
                require_reduce_only=True,
                require_flatten=True,
                is_halted=True,
            )
        if "POSITION_MAX_LOSS_BREACHED" in reasons:
            return SafetyResult(
                verdict=SafetyVerdict.REQUIRE_FLATTEN,
                reason_codes=tuple(reasons),
                block_new_risk=True,
                require_reduce_only=True,
                require_flatten=True,
                is_halted=False,
            )
        return SafetyResult(
            verdict=SafetyVerdict.REQUIRE_REDUCE_ONLY,
            reason_codes=tuple(reasons),
            block_new_risk=True,
            require_reduce_only=True,
            require_flatten=False,
            is_halted=False,
        )

    if not facts.data_fresh:
        reasons.append("DATA_STALE_OR_UNKNOWN")
        return SafetyResult(
            verdict=SafetyVerdict.BLOCK_NEW_RISK,
            reason_codes=tuple(reasons),
            block_new_risk=True,
            require_reduce_only=False,
            require_flatten=False,
            is_halted=False,
        )

    if facts.session.must_flatten:
        return SafetyResult(
            verdict=SafetyVerdict.REQUIRE_FLATTEN,
            reason_codes=("SESSION_FLATTENING",),
            block_new_risk=True,
            require_reduce_only=True,
            require_flatten=True,
            is_halted=False,
        )
    if not facts.session.can_enter:
        if facts.session.can_reduce:
            return SafetyResult(
                verdict=SafetyVerdict.REQUIRE_REDUCE_ONLY,
                reason_codes=("SESSION_EXIT_ONLY",),
                block_new_risk=True,
                require_reduce_only=True,
                require_flatten=False,
                is_halted=False,
            )
        return SafetyResult(
            verdict=SafetyVerdict.BLOCK_NEW_RISK,
            reason_codes=("SESSION_ENTRY_BLOCKED",),
            block_new_risk=True,
            require_reduce_only=False,
            require_flatten=False,
            is_halted=False,
        )

    return SafetyResult(
        verdict=SafetyVerdict.ALLOW_NEW_RISK,
        reason_codes=("SAFETY_ALLOW",),
        block_new_risk=False,
        require_reduce_only=False,
        require_flatten=False,
        is_halted=False,
    )


__all__ = ["SafetyFacts", "SafetyResult", "SafetyVerdict", "evaluate_p0_safety"]
