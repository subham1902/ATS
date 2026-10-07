"""Exit-authorization boundary: the runtime cannot manufacture dismissal of its own risk.

Reducing a position is not the inverse of opening one. It needs its own
authority, so the runtime must not be able to (a) assert ALLOW for itself,
(b) invent the identities that authority evidence is supposed to supply, or
(c) write its own settlement state. Entry authority gets the same treatment:
omitting a provider must deny, and the default capital authority must grant
nothing. These are source-level guards; companion behavioural tests live in
tests/unit/trading_runtime.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from ats.contracts.domain.types import ExitReason
from ats.kernel.types import ALLOW, KernelOutcome
from ats.trading_runtime.exit_authorization import (
    ExitAuthorizationRequest,
    ExitAuthorizationResult,
    UnavailableExitAuthorization,
)

REPO_ROOT = Path(__file__).parents[3]
ORCHESTRATOR = REPO_ROOT / "backend" / "src" / "ats" / "trading_runtime" / "orchestrator.py"
BROKER = REPO_ROOT / "backend" / "src" / "ats" / "trading_runtime" / "broker.py"
SEAM = REPO_ROOT / "backend" / "src" / "ats" / "trading_runtime" / "exit_authorization.py"
ENGINE = REPO_ROOT / "backend" / "src" / "ats" / "trading_runtime" / "engine.py"
AUTHORITY_SERVICE = (
    REPO_ROOT / "backend" / "src" / "ats" / "trading_runtime" / "authority_service.py"
)
TEST_HELPERS = REPO_ROOT / "tests" / "unit" / "trading_runtime" / "helpers.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def _source(name: str) -> str:
    return _read({"orchestrator": ORCHESTRATOR, "broker": BROKER, "seam": SEAM}[name])


# Loose, lowercased substrings: a rename should still trip the guard rather than
# silently disabling it.
FORBIDDEN_IN_ORCHESTRATOR = (
    "authorization=allow",  # asserting the exit outcome itself
    "authorization = allow",
    "risk_decision_id=uuid4()",  # fabricating authority identity
    "autonomy_token_id=uuid4()",
    "_snapshot_position_id",  # the hardcoded synthetic position identity
    "uuid(int=1)",  # sequentially minted policy identity
)

# Code patterns rather than prose: the module docstring is allowed to describe
# what was removed, but no implementation of it may exist.
BROKER_FORBIDDEN_PATTERNS = (
    ("sequentially minted authority identity", re.compile(r"uuid\(int=\d+\)")),
    ("manual fill injection", re.compile(r"def\s+seed_fill\b|\.seed_fill\s*\(")),
    ("fabricated risk economics", re.compile(r"lot_size\s*\*\s*tick_size\s*\*\s*\d+")),
)


def test_orchestrator_cannot_assert_its_own_authorization() -> None:
    source = _source("orchestrator")
    present = {token for token in FORBIDDEN_IN_ORCHESTRATOR if token in source}
    assert not present, f"orchestrator still contains unauthorized construction: {sorted(present)}"


def test_orchestrator_has_no_local_exit_authority_helper() -> None:
    """The helpers that used to synthesize an ExitIntent/Position must not return."""

    from ats.trading_runtime import orchestrator as module

    for name in ("_snapshot_position_id", "_position_snapshot"):
        assert not hasattr(module, name), f"{name} reappeared; exits must use provided artifacts"


def test_orchestrator_has_no_default_intent_binding() -> None:
    """A binding provider must be threaded in, never defaulted to permissive."""
    source = _source("orchestrator")
    assert "intent_binding_provider" in source, "binding seam removed"
    assert not re.search(r"intent_binding_provider\s*=\s*(none|\w*allow\w*)\s*[,)]", source), (
        "intent binding must not default to a permissive provider"
    )


def test_broker_cannot_synthesize_authority_identities() -> None:
    source = _source("broker")
    present = [label for label, pattern in BROKER_FORBIDDEN_PATTERNS if pattern.search(source)]
    assert not present, f"broker still fabricates order binding: {present}"


def test_broker_requires_real_upstream_binding() -> None:
    """Refusing an unbound order is the fail-closed path, not an exception swallow."""
    from ats.trading_runtime.broker import OrderIntentBinding, OrderRequest, UnboundOrderError

    assert issubclass(UnboundOrderError, RuntimeError)
    request = OrderRequest(
        instrument_id="XAUUSD",
        side="BUY",
        quantity=Decimal("50"),
        order_type="MARKET",
        limit_price=None,
        idempotency_key="K-UNBOUND-1",
        intent_id=str(uuid4()),
        binding=None,
    )
    assert request.binding is None

    # The binding type carries every identity Stage-2 binds against, so it
    # cannot be constructed as "default ids" either.
    assert OrderIntentBinding.__dataclass_fields__.keys() >= {
        "policy_id",
        "forecast_id",
        "risk_decision_id",
        "supervisor_advisory_id",
        "autonomy_token_id",
    }


def test_broker_has_no_manual_fill_primitive() -> None:
    from ats.trading_runtime.broker import PaperBrokerAdapter

    assert not hasattr(PaperBrokerAdapter, "seed_fill"), (
        "manual fill injection returned to the production adapter"
    )


def test_autonomous_runtime_cannot_reach_the_test_fill_seeder() -> None:
    """Production code must never import the test-only fill seeding helper."""
    import_line = re.compile(r"^\s*(?:from|import)\s+\S*paper_fill_seed", re.MULTILINE)
    production_root = REPO_ROOT / "backend" / "src"
    offending = [
        str(path.relative_to(REPO_ROOT))
        for path in production_root.rglob("*.py")
        if import_line.search(path.read_text(encoding="utf-8"))
    ]
    assert not offending, f"production imports the test-only seeder: {offending}"


def test_fail_closed_default_is_not_a_permit() -> None:
    """Absence of a configured provider must resolve to UNKNOWN, never ALLOW."""
    request = ExitAuthorizationRequest(
        position_key="XAUUSD:1",
        exit_intent_id=uuid4(),
        instrument_id="XAUUSD",
        quantity=Decimal("50"),
        reason=ExitReason.RISK,
        reason_codes=("STOP_LOSS",),
        idempotency_key="EXIT:1",
    )
    result = UnavailableExitAuthorization().authorize_exit(request)
    assert result.decision.outcome is not KernelOutcome.ALLOW
    assert not result.allows_exit()


def test_allow_without_artifacts_is_not_actionable() -> None:
    """A claim of permission alone must not be enough to execute anything."""
    hollow = ExitAuthorizationResult(decision=ALLOW)
    assert not hollow.allows_exit()
    assert hollow.refusal_reason()  # an explanation exists for refusing


def test_no_implicit_allow_fallback_in_test_helpers() -> None:
    """`allow_all` is for explicit injection, never a default or fallback."""
    source = _read(TEST_HELPERS)
    assert "or allow_all" not in source, "permissive fallback reappeared in test helpers"
    assert "or allow-all" not in source
    signature = re.search(r"def build_orchestrator\((.*?)\)\s*(?:->|:)", source, re.DOTALL)
    assert signature is not None, "build_orchestrator signature not found"
    assert "allow_all" not in signature.group(1), (
        "allow_all must not appear in build_orchestrator defaults; "
        "tests that want ALLOW pass it explicitly"
    )


def test_noop_authority_service_cannot_grant_allow() -> None:
    """The default capital authority answers UNKNOWN, never ALLOW."""
    import inspect
    from datetime import UTC, datetime

    from ats.kernel.types import KernelOutcome
    from ats.trading_runtime.authority_service import NoopAuthorityService

    class_source = inspect.getsource(NoopAuthorityService)
    assert "KernelOutcome.ALLOW" not in class_source, "Noop grants ALLOW again"
    assert "NOOP_ALLOW" not in class_source, "the old permissive reason code returned"
    assert "AUTHORITY_UNAVAILABLE" in class_source, "fail-closed marker missing"

    # The method ignores its inputs by design, so the call below proves the
    # outcome cannot depend on a crafted request: it is UNKNOWN regardless.
    decision = NoopAuthorityService().try_reserve_for_candidate(
        None,  # type: ignore[arg-type]
        evaluation_time=datetime(2026, 8, 24, 4, 0, tzinfo=UTC),
    )
    assert decision.outcome is KernelOutcome.UNKNOWN
    assert decision.outcome is not KernelOutcome.ALLOW
    assert decision.reservation_id is None
    assert decision.token is None
    assert decision.order_intent is None


def test_engine_never_reports_exit_authorized_without_durable_authority() -> None:
    """A listing is bookkeeping, not permission: no durable authority means
    the exit is listed as unauthorized, with the reason stated."""
    from datetime import UTC, date, datetime, time
    from decimal import Decimal

    from ats.market.calendar.models import SessionCalendar
    from ats.trading_runtime.broker import InMemoryMarketFeed, PaperBrokerAdapter
    from ats.trading_runtime.engine import RuntimeConfig, TradingRuntime

    source = _read(ENGINE)
    assert not re.search(r"authorized\s*=\s*isinstance", source), (
        "exit authorization derived from an isinstance check again"
    )

    at = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
    runtime = TradingRuntime(
        config=RuntimeConfig(
            calendar=SessionCalendar(
                calendar_id="T",
                calendar_version="1.0.0",
                timezone="Asia/Kolkata",
                trading_dates=(date(2026, 8, 24),),
                preopen_start=time(9),
                market_open=time(9, 15),
                market_close=time(15, 30),
                overrides=(),
            )
        ),
        market_feed=InMemoryMarketFeed(),
        broker=PaperBrokerAdapter(),
        # No authority wired: the default Noop must grant nothing.
    )
    runtime.handle_fill("SYMBOL:1", Decimal("100"), Decimal("75"), at, lot_size=Decimal("1"))
    result = runtime.request_exit("SYMBOL:1", at, source="DASHBOARD")
    assert result["accepted"] is True
    assert result["authorized"] is False
    assert "EXIT_EVIDENCE_REQUIRED" in result["reasons"]
    assert "SYMBOL:1" in runtime.state.open_positions
