"""Refusal semantics: a reduction that cannot be authorized must never look closed.

Each case is the same claim from a different direction -- DENY, UNKNOWN, a
provider that throws, a stale snapshot, ALLOW without artifacts, and no provider
at all must all leave positions open and the session un-closed. If any of them
reported CLOSED, a blocked risk event would be indistinguishable from a
completed one.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from ats.contracts.domain.models import Position
from ats.kernel.types import ALLOW
from ats.trading_runtime.broker import InMemoryMarketFeed
from ats.trading_runtime.exit_authorization import ExitAuthorizationRequest, ExitAuthorizationResult

from tests.unit.trading_runtime.exit_authorization_doubles import (
    DenyingExitAuthorization,
    ExplodingExitAuthorization,
    PermissiveExitAuthorization,
    PermissiveExitAuthorizationWithoutArtifacts,
    UnknownExitAuthorization,
    allow_all_with_binding,
    build_test_exit_intent,
    build_test_position,
)

from .helpers import (
    NOW,
    SYMBOL,
    allow_all,
    build_orchestrator,
    market_facts,
)

INDEX = "XAUUSD"
PREV = Decimal("25000")
BULL_MARK = Decimal("25600")
SHUTDOWN_AT = NOW + timedelta(minutes=1)


def _facts_provider(iid: str, at):
    if iid == SYMBOL:
        return market_facts(
            instrument_id=SYMBOL,
            bid=Decimal("99"),
            ask=Decimal("101"),
            bid_quantity=130,
            ask_quantity=130,
            at=at,
        )
    return None


def _entry_orchestrator(exit_authorization_provider=None):
    """One open position, with exit authority supplied only if the test asks.

    ``exit_authorization_provider=None`` means "do not wire one", which is what
    production does until an operator configures a durable authority.
    """
    feed = InMemoryMarketFeed()
    feed.set_mark(INDEX, PREV, NOW)
    feed.set_mark(SYMBOL, Decimal("101"), NOW)
    orch = build_orchestrator(
        market_facts_provider=_facts_provider,
        feed=feed,
        authorization_provider=allow_all,
        intent_binding_provider=allow_all_with_binding,
        exit_authorization_provider=exit_authorization_provider,
    )
    orch.runtime.market_feed.set_mark(INDEX, BULL_MARK, NOW)
    orch.bar(INDEX, close=BULL_MARK, previous_close=PREV, at=NOW)
    assert len(orch.get_open_positions()) == 1, "fixture must open exactly one position"
    return orch


def _assert_blocked(orch) -> None:
    """The universal invariant shared by every refusal case."""
    result = orch.request_shutdown(SHUTDOWN_AT)
    assert result["status"] == "NOT_CLOSED", "a refused reduction must not report closed"
    assert len(orch.get_open_positions()) == 1, "position must remain open"
    assert orch.counters.exit_authorization_refused >= 1, "refusal must be recorded"
    assert orch.counters.emergency_exits == 0, "a refused exit is not an emergency exit"
    report = orch.session_report
    assert report is not None
    assert report.status != "CLOSED"
    assert report.closed_successfully is False


class _StaleSnapshotAuthority:
    """Returns ALLOW with artifacts whose identity no longer matches."""

    def authorize_exit(self, request: ExitAuthorizationRequest) -> ExitAuthorizationResult:
        at = request.at
        assert at is not None, "test requests always carry an evaluation timestamp"
        position = build_test_position(request, at=at)
        stale = position.model_copy(
            update={"net_quantity": position.net_quantity / 2, "instrument_id": "XAUUSD:PE"}
        )
        assert isinstance(stale, Position)
        return ExitAuthorizationResult(
            decision=ALLOW,
            exit_intent=build_test_exit_intent(request, at=at),
            position=stale,
        )


def test_deny_blocks_shutdown() -> None:
    _assert_blocked(_entry_orchestrator(DenyingExitAuthorization()))


def test_unknown_blocks_shutdown() -> None:
    _assert_blocked(_entry_orchestrator(UnknownExitAuthorization()))


def test_provider_exception_fails_closed() -> None:
    """A throwing authority must degrade to refusal, not propagate upward."""
    orch = _entry_orchestrator(ExplodingExitAuthorization())
    _assert_blocked(orch)  # no RuntimeError escapes


def test_allow_without_artifacts_blocks_shutdown() -> None:
    _assert_blocked(_entry_orchestrator(PermissiveExitAuthorizationWithoutArtifacts()))


def test_unconfigured_authority_blocks_shutdown() -> None:
    """The default provider, i.e. nobody having wired an authority at all."""
    _assert_blocked(_entry_orchestrator(None))


def test_stale_position_snapshot_is_refused() -> None:
    """A snapshot that no longer describes this position cannot reduce it."""
    _assert_blocked(_entry_orchestrator(_StaleSnapshotAuthority()))


def test_matched_snapshot_authorizes_and_closes() -> None:
    """Control: the same path with a coherent snapshot does flatten."""
    orch = _entry_orchestrator(PermissiveExitAuthorization())
    result = orch.request_shutdown(SHUTDOWN_AT)
    assert result["status"] == "CLOSED"
    assert orch.is_position_empty()
    assert orch.counters.exit_authorization_refused == 0
    assert orch.counters.emergency_exits == 1
