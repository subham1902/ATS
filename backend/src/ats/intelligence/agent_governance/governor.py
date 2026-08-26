"""Deterministic governor for advisory-agent runtime change proposals."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from ats.contracts.common import ClockProtocol
from ats.contracts.domain.hashing import compute_payload_hash
from ats.trading_runtime.modes import TradingMode

from .models import (
    GovernedAgentOutput,
    RuntimeChangeAudit,
    RuntimeChangeCategory,
    RuntimeChangeDecision,
    RuntimeChangeOutcome,
    RuntimeChangeProposal,
    RuntimeChangeType,
)

ChangeApplier = Callable[[RuntimeChangeProposal], dict[str, object]]

_AUTO_ALLOWED = frozenset(
    {
        RuntimeChangeType.UPDATE_RESEARCH_QUEUE,
        RuntimeChangeType.CREATE_HYPOTHESIS,
        RuntimeChangeType.SET_ANALYSIS_PRIORITY,
        RuntimeChangeType.REQUEST_THESIS_RECOMPUTATION,
        RuntimeChangeType.PROPOSE_EXPERIMENT,
        RuntimeChangeType.ADD_ANNOTATION,
        RuntimeChangeType.REQUEST_POSITION_REVIEW,
        RuntimeChangeType.REQUEST_CANDIDATE_REEVALUATION,
    }
)
_VALIDATED_DEESCALATIONS = frozenset(
    {
        RuntimeChangeType.SET_SAFE_MODE,
        RuntimeChangeType.PAUSE_STRATEGY,
        RuntimeChangeType.REDUCE_ALLOCATION,
        RuntimeChangeType.TIGHTEN_THRESHOLD,
    }
)
_ALWAYS_REJECT = frozenset(
    {
        RuntimeChangeType.SET_AGGRESSIVE_MODE,
        RuntimeChangeType.INCREASE_HARD_RISK,
        RuntimeChangeType.PLACE_ORDER,
        RuntimeChangeType.PROMOTE_STRATEGY,
    }
)


class RuntimeChangeGovernor:
    def __init__(self, *, clock: ClockProtocol, applier: ChangeApplier | None = None) -> None:
        self._clock = clock
        self._applier = applier
        self._decisions: dict[object, RuntimeChangeDecision] = {}
        self._audits: list[RuntimeChangeAudit] = []

    @property
    def audits(self) -> tuple[RuntimeChangeAudit, ...]:
        return tuple(self._audits)

    def evaluate(
        self,
        proposal: RuntimeChangeProposal,
        *,
        effective_mode: TradingMode,
    ) -> RuntimeChangeDecision:
        existing = self._decisions.get(proposal.proposal_id)
        if existing is not None:
            return existing
        now = self._clock.now()
        reasons: tuple[str, ...]
        permitted = False
        if proposal.payload_hash != compute_payload_hash(proposal):
            reasons = ("PROPOSAL_HASH_MISMATCH",)
        elif now > proposal.valid_until:
            reasons = ("PROPOSAL_STALE",)
        elif proposal.category is RuntimeChangeCategory.FINANCIAL_AUTHORITY:
            reasons = ("FINANCIAL_AUTHORITY_FORBIDDEN",)
        elif proposal.proposal_type in _ALWAYS_REJECT:
            reasons = ("RISK_BROADENING_FORBIDDEN",)
        elif proposal.proposal_type in _AUTO_ALLOWED:
            permitted = True
            reasons = ("NON_FINANCIAL_CHANGE_ALLOWED",)
        elif proposal.proposal_type in _VALIDATED_DEESCALATIONS:
            permitted, reasons = self._validate_deescalation(proposal, effective_mode)
        else:
            reasons = ("CHANGE_NOT_ALLOWLISTED",)
        applied = None
        if permitted:
            applied = (
                self._applier(proposal) if self._applier is not None else proposal.proposed_value
            )
        draft = RuntimeChangeDecision(
            decision_id=uuid4(),
            proposal_id=proposal.proposal_id,
            proposal_hash=proposal.payload_hash,
            outcome=RuntimeChangeOutcome.APPLY if permitted else RuntimeChangeOutcome.REJECT,
            reason_codes=reasons,
            evaluated_at=now,
            applied_change=applied,
            payload_hash="0" * 64,
        )
        decision = draft.model_copy(update={"payload_hash": compute_payload_hash(draft)})
        self._decisions[proposal.proposal_id] = decision
        self._audits.append(
            RuntimeChangeAudit(
                audit_id=uuid4(),
                proposal_id=proposal.proposal_id,
                decision_id=decision.decision_id,
                actor_id=proposal.agent_id,
                outcome=decision.outcome,
                reason_codes=decision.reason_codes,
                occurred_at=now,
                proposal_hash=proposal.payload_hash,
                decision_hash=decision.payload_hash,
            )
        )
        return decision

    def output_is_current(self, output: GovernedAgentOutput, *, context_hash: str) -> bool:
        now = self._clock.now()
        return output.valid_until >= now and output.context_hash == context_hash

    @staticmethod
    def _validate_deescalation(
        proposal: RuntimeChangeProposal, effective_mode: TradingMode
    ) -> tuple[bool, tuple[str, ...]]:
        if proposal.proposal_type is RuntimeChangeType.SET_SAFE_MODE:
            requested = proposal.proposed_value.get("mode")
            if requested != TradingMode.SAFE.value:
                return False, ("SAFE_MODE_VALUE_REQUIRED",)
            if effective_mode is TradingMode.HALTED:
                return False, ("HALT_CANNOT_BE_CLEARED_BY_AGENT",)
        if proposal.proposal_type is RuntimeChangeType.REDUCE_ALLOCATION:
            current = proposal.current_value.get("allocation")
            proposed = proposal.proposed_value.get("allocation")
            if not isinstance(current, int | float) or not isinstance(proposed, int | float):
                return False, ("ALLOCATION_VALUES_INVALID",)
            if proposed < 0 or proposed >= current:
                return False, ("ALLOCATION_MUST_STRICTLY_DECREASE",)
        if proposal.proposal_type is RuntimeChangeType.TIGHTEN_THRESHOLD:
            if proposal.proposed_value.get("direction") != "TIGHTER":
                return False, ("THRESHOLD_MUST_TIGHTEN",)
        return True, ("BOUNDED_DEESCALATION_ALLOWED",)


__all__ = ["ChangeApplier", "RuntimeChangeGovernor"]
