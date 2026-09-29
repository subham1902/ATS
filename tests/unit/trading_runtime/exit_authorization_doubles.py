"""Explicit exit-authorization test doubles.

Every provider here is **opt-in**. No test gets one by default: when a test omits
``exit_authorization_provider`` the orchestrator installs its fail-closed default
and positions stay open. That asymmetry is intentional -- it is what makes "the
runtime flattened a position" a statement a test has to earn rather than inherit.

The identities below are named constants rather than ``uuid4()`` values so that a
failure report identifies exactly which synthetic artifact was involved. They are
test doubles standing in for artifacts the durable reduction authority would
produce; they are never importable from production code paths.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.models import ExitIntent, Position
from ats.contracts.domain.types import PaperOrderType, PositionStatus
from ats.kernel.types import ALLOW, GateCode, KernelOutcome, KernelResult
from ats.trading_runtime.broker import OrderIntentBinding
from ats.trading_runtime.exit_authorization import (
    ExitAuthorizationRequest,
    ExitAuthorizationResult,
)

TEST_POLICY_ID = UUID("0000aaaa-0000-0000-0000-000000000001")
TEST_PORTFOLIO_ID = UUID("0000aaaa-0000-0000-0000-000000000002")
TEST_LAST_FILL_ID = UUID("0000aaaa-0000-0000-0000-000000000003")
TEST_RISK_DECISION_ID = UUID("0000aaaa-0000-0000-0000-000000000004")
TEST_AUTONOMY_TOKEN_ID = UUID("0000aaaa-0000-0000-0000-000000000005")
TEST_FORECAST_ID = UUID("0000aaaa-0000-0000-0000-000000000006")
TEST_ADVISORY_ID = UUID("0000aaaa-0000-0000-0000-000000000007")


def test_intent_binding() -> OrderIntentBinding:
    """An explicit, fully-populated order binding for tests.

    Named constants rather than ``uuid4()`` so a failure identifies the exact
    artifact involved. Tests must ask for this: with no binding provider wired,
    the orchestrator submits nothing.
    """
    return OrderIntentBinding(
        policy_id=TEST_POLICY_ID,
        policy_version=1,
        forecast_id=TEST_FORECAST_ID,
        risk_decision_id=TEST_RISK_DECISION_ID,
        supervisor_advisory_id=TEST_ADVISORY_ID,
        autonomy_token_id=TEST_AUTONOMY_TOKEN_ID,
        maximum_permitted_loss=Decimal("1500"),
        expected_reward=Decimal("3000"),
    )


def allow_all_with_binding(candidate: dict) -> OrderIntentBinding:
    """Binding provider counterpart to ``allow_all``, bound to real-shaped evidence."""
    _ = candidate
    return test_intent_binding()


def _payload_hash(model: Any) -> str:
    from ats.contracts.domain.hashing import compute_payload_hash

    return str(compute_payload_hash(model))


def build_test_exit_intent(
    request: ExitAuthorizationRequest,
    *,
    at: UTCDateTime,
) -> ExitIntent:
    """Authoritative-shaped ExitIntent for the given request.

    Reuses the request's own ``exit_intent_id`` and ``idempotency_key`` so the
    artifact binds to the caller's actual intent rather than a fresh random one.
    """
    intent = ExitIntent(
        schema_version="1.0",
        exit_intent_id=request.exit_intent_id,
        position_id=TEST_POLICY_ID,
        position_version=1,
        reason=request.reason,
        quantity=request.quantity,
        order_type=PaperOrderType.MARKET,
        limit_price=None,
        stop_price=None,
        risk_decision_id=TEST_RISK_DECISION_ID,
        autonomy_token_id=TEST_AUTONOMY_TOKEN_ID,
        idempotency_key=request.idempotency_key,
        created_at=at,
        payload_hash="0" * 64,
    )
    return intent.model_copy(update={"payload_hash": _payload_hash(intent)})


def build_test_position(request: ExitAuthorizationRequest, *, at: UTCDateTime) -> Position:
    """Snapshot-shaped Position matching the instrument/quantity being reduced."""
    value = Position(
        schema_version="1.0",
        position_id=TEST_POLICY_ID,
        portfolio_id=TEST_PORTFOLIO_ID,
        instrument_id=request.instrument_id,
        net_quantity=request.quantity,
        average_entry_price=Decimal("100"),
        mark_price=Decimal("101"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        cash_effect=Decimal("0"),
        policy_id=TEST_POLICY_ID,
        policy_version=1,
        opened_at=at,
        updated_at=at,
        closed_at=None,
        status=PositionStatus.OPEN,
        version=1,
        last_fill_id=TEST_LAST_FILL_ID,
        payload_hash="0" * 64,
    )
    return value.model_copy(update={"payload_hash": _payload_hash(value)})


class PermissiveExitAuthorization:
    """Authorizes every reduction, supplying artifacts so the exit is executable.

    Use this only where the test's subject is *something other than* exit
    authority (shutdown bookkeeping, reconciliation, restart recovery). Tests
    about refusal semantics use :class:`DenyingExitAuthorization` or omit the
    provider entirely.
    """

    def authorize_exit(self, request: ExitAuthorizationRequest) -> ExitAuthorizationResult:
        at = request.at
        assert at is not None, "test requests always carry an evaluation timestamp"
        return ExitAuthorizationResult(
            decision=ALLOW,
            exit_intent=build_test_exit_intent(request, at=at),
            position=build_test_position(request, at=at),
        )


class DenyingExitAuthorization:
    """Refuses every reduction with an explicit reason."""

    def __init__(self, reason_codes: tuple[GateCode, ...] = (GateCode.TOKEN_INVALID,)) -> None:
        self._reason_codes = reason_codes

    def authorize_exit(self, request: ExitAuthorizationRequest) -> ExitAuthorizationResult:
        return ExitAuthorizationResult(
            decision=KernelResult(
                outcome=KernelOutcome.DENY, reason_codes=self._reason_codes
            )
        )


class UnknownExitAuthorization:
    """Cannot determine authorization (models A04 being unavailable)."""

    def authorize_exit(self, request: ExitAuthorizationRequest) -> ExitAuthorizationResult:
        return ExitAuthorizationResult(
            decision=KernelResult(
                outcome=KernelOutcome.UNKNOWN, reason_codes=(GateCode.TOKEN_INVALID,)
            )
        )


class ExplodingExitAuthorization:
    """Raises, to prove that a provider failure is never treated as permission."""

    def authorize_exit(self, request: ExitAuthorizationRequest) -> ExitAuthorizationResult:
        raise RuntimeError("authority backend unavailable")


class PermissiveExitAuthorizationWithoutArtifacts:
    """Answers ALLOW but supplies no artifacts.

    Proves that a claim of permission is not enough on its own: with nothing
    authoritative to submit, the orchestrator must refuse rather than improvise.
    """

    def authorize_exit(self, request: ExitAuthorizationRequest) -> ExitAuthorizationResult:
        _ = request
        return ExitAuthorizationResult(decision=ALLOW)


__all__ = [
    "allow_all_with_binding",
    "test_intent_binding",
    "DenyingExitAuthorization",
    "ExplodingExitAuthorization",
    "PermissiveExitAuthorization",
    "PermissiveExitAuthorizationWithoutArtifacts",
    "UnknownExitAuthorization",
    "build_test_exit_intent",
    "build_test_position",
]
