"""Exit authorization seam for the trading runtime.

Why this exists
---------------
Closing a position is not the mirror image of opening one: it is a *reduction*
of live risk and therefore requires its own authority. Historically the
orchestrator satisfied the canonical exit gate by handing the Stage-2 check a
module-level ``ALLOW`` constant and a set of freshly minted ``uuid4()`` values
standing in for ``risk_decision_id`` and ``autonomy_token_id``. That satisfied
every downstream binding check while carrying no evidence whatsoever: the exit
looked authorized because the runtime said so.

This module replaces that with an explicit capability. The orchestrator asks a
provider whether a reduction is authorized and receives either authoritative
artifacts or a refusal carrying kernel reason codes. **The orchestrator can no
longer manufacture those artifacts itself.**

Design rules enforced here:

- Absence of a provider means DENY/UNKNOWN, never ALLOW.
- Refusal is expressed as :class:`~ats.kernel.types.KernelResult`, preserving
  the repo's existing tri-state vocabulary (ALLOW / DENY / UNKNOWN) and reason
  codes rather than introducing a boolean.
- An ALLOW that arrives without the artifacts needed to act on it is treated as
  unusable (see :meth:`ExitAuthorizationResult.allows_exit`) rather than being
  backfilled with synthesised values.
- Exceptions from a provider are failures, not permissions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.models import ExitIntent, Position
from ats.contracts.domain.types import ExitReason
from ats.kernel.types import GateCode, KernelOutcome, KernelResult

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


def _refuse(outcome: KernelOutcome, reason_codes: tuple[GateCode, ...]) -> KernelResult:
    """Build a non-ALLOW kernel result. Non-ALLOW requires at least one reason."""
    return KernelResult(outcome=outcome, reason_codes=reason_codes)


@dataclass(frozen=True)
class ExitAuthorizationRequest:
    """A request to reduce a single monitored position.

    ``position_key`` is the runtime's **real** position identity. It is never
    synthesised: it comes from the entry fill (``instrument:fill_id``) that
    created the position, so the request binds to an actual open risk.
    """

    position_key: str
    exit_intent_id: UUID
    instrument_id: str
    quantity: Decimal
    reason: ExitReason
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    idempotency_key: str = ""
    at: UTCDateTime | None = None
    source: str = "ORCHESTRATOR"


@dataclass(frozen=True)
class ExitAuthorizationResult:
    """Outcome of an exit authorization attempt plus the artifacts to act on it.

    ``exit_intent`` and ``position`` are populated only from authoritative
    sources. When they are absent there is nothing safe to submit, regardless
    of what ``decision`` says.
    """

    decision: KernelResult
    exit_intent: ExitIntent | None = None
    position: Position | None = None

    def allows_exit(self) -> bool:
        """True only when the reduction is authorized *and* executable.

        An ALLOW without artifacts is not executable: fabricating the missing
        identity here would reintroduce exactly the defect this module removes.
        """
        return (
            self.decision.outcome is KernelOutcome.ALLOW
            and self.exit_intent is not None
            and self.position is not None
        )

    def refusal_reason(self) -> tuple[GateCode, ...]:
        """Why an exit could not proceed, including the artifact-less case."""
        reasons = list(self.decision.reason_codes)
        if self.decision.outcome is KernelOutcome.ALLOW and not self.allows_exit():
            reasons.append(GateCode.POSITION_BINDING)
        return tuple(reasons)


@runtime_checkable
class ExitAuthorizationProvider(Protocol):
    """Capability the runtime needs: is this reduction authorized?"""

    def authorize_exit(self, request: ExitAuthorizationRequest) -> ExitAuthorizationResult: ...


class UnavailableExitAuthorization:
    """Fail-closed default installed when no provider has been wired.

    This is the production default position. It answers UNKNOWN rather than DENY
    to keep ''we do not know'' distinguishable from ''we were told no'', and it
    never yields artifacts, so no exit can be executed through it.
    """

    def authorize_exit(self, request: ExitAuthorizationRequest) -> ExitAuthorizationResult:
        _ = request
        return ExitAuthorizationResult(
            decision=_refuse(KernelOutcome.UNKNOWN, (GateCode.TOKEN_INVALID,))
        )


class ReductionAuthorityExitAuthorization:
    """Adapter onto the legitimate durable reduction authority.

    Delegates the actual decision to :class:`ReductionAuthorityService`, which
    commits the whole authority chain atomically and mints the real autonomy
    token. The adapter contributes no authorization logic of its own -- it only
    translates the runtime's request into a ``BeginReductionRequest`` and maps
    the result back, failing closed on every error path.
    """

    def __init__(
        self,
        reduction_authority: Any,
        reduction_request_builder: Any,
        position_source: Any,
    ) -> None:
        self._reduction_authority = reduction_authority
        self._reduction_request_builder = reduction_request_builder
        self._position_source = position_source

    def authorize_exit(self, request: ExitAuthorizationRequest) -> ExitAuthorizationResult:
        try:
            begin_request = self._reduction_request_builder(
                request.position_key,
                request.at,
                request.reason_codes,
                request.source,
            )
        except Exception:
            return ExitAuthorizationResult(
                decision=_refuse(KernelOutcome.UNKNOWN, (GateCode.ORDER_BINDING,))
            )

        try:
            reduction = self._reduction_authority.begin_reduction(begin_request)
        except Exception:
            # A refusal, an integrity violation and a lost connection are all
            # 'not authorized'. None of them is permission.
            return ExitAuthorizationResult(
                decision=_refuse(KernelOutcome.DENY, (GateCode.TOKEN_INVALID,))
            )

        exit_intent = getattr(reduction, "exit_intent", None)
        if not isinstance(exit_intent, ExitIntent):
            return ExitAuthorizationResult(
                decision=_refuse(KernelOutcome.DENY, (GateCode.ORDER_BINDING,))
            )

        try:
            position = self._position_source(request.position_key)
        except Exception:
            return ExitAuthorizationResult(
                decision=_refuse(KernelOutcome.UNKNOWN, (GateCode.POSITION_BINDING,))
            )

        if not isinstance(position, Position):
            # Refuse rather than snapshot around a position we cannot load.
            return ExitAuthorizationResult(
                decision=_refuse(KernelOutcome.UNKNOWN, (GateCode.POSITION_BINDING,))
            )

        return ExitAuthorizationResult(
            decision=KernelResult(outcome=KernelOutcome.ALLOW, reason_codes=(GateCode.OK,)),
            exit_intent=exit_intent,
            position=position,
        )


__all__ = [
    "ExitAuthorizationProvider",
    "ExitAuthorizationRequest",
    "ExitAuthorizationResult",
    "ReductionAuthorityExitAuthorization",
    "UnavailableExitAuthorization",
]
