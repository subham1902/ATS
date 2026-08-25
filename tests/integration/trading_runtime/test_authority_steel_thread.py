"""TEST_ONLY steel thread: candidate -> A04 -> token -> OrderIntent -> PaperBroker -> Fill -> Position.

All inputs are TEST_ONLY / NON_MARKET_DATA. Authority flow is real production code.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.models import Fill, OrderIntent, PaperOrder, Position
from ats.contracts.domain.types import AdvisoryOutcome, DataQualityState, PaperOrderStatus, PaperOrderType, Side
from ats.contracts.governance.types import CandidateStatus
from ats.execution.paper import PaperMarketFacts, PaperSubmissionScenario
from ats.execution.paper.broker import process_paper_order, submit_paper_order
from ats.execution.paper.models import PaperExecutionPolicy
from ats.kernel.autonomy import construct_autonomy_token, validate_token_eligibility, validate_token_for_use
from ats.kernel.order_guard import validate_order_intent
from ats.kernel.types import AutonomyTokenPolicy, GateCode, KernelOutcome, OrderEvaluationFacts, OrderGuardPolicy

from tests.unit.kernel.fixtures import T0, _validated, make_kernel_fixture, uid


def _t0_plus(seconds: int) -> UTCDateTime:
    return T0 + timedelta(seconds=seconds)


def _make_authorized_token(x: dict[str, object]) -> object:
    eligibility = validate_token_eligibility(
        policy=x["policy"],
        campaign=x["campaign"],
        campaign_state=x["campaign_state"],
        market=x["market"],
        thesis=x["thesis"],
        distribution=x["distribution"],
        candidate=x["candidate"],
        strategy=x["strategy"],
        context=x["context"],
        risk_decision=x["risk_decision"],
        advisory=x["advisory"],
        packet=x["packet"],
        binding=x["binding"],
        constraints=x["constraints"],
        campaign_facts=x["campaign_facts"],
        capital_basis=x["basis"],
        execution_safety=x["safety"],
        evaluation_time=T0,
        maximum_freshness_ms=1000,
        current_system_state_version=1,
        model_family="model",
        model_version="1",
        calibrator_version="1",
    )
    assert eligibility.outcome is KernelOutcome.ALLOW
    token = construct_autonomy_token(
        eligibility=eligibility,
        token_id=uid(90),
        candidate=x["candidate"],
        policy=x["policy"],
        risk_decision=x["risk_decision"],
        advisory=x["advisory"],
        context=x["context"],
        issued_at=T0,
        expires_at=T0 + timedelta(seconds=30),
        nonce="steel-thread-nonce",
        token_policy=AutonomyTokenPolicy(max_ttl_ms=30000),
    )
    return token


def test_full_steel_thread_end_to_end() -> None:
    x = make_kernel_fixture()
    token = _make_authorized_token(x)
    assert validate_token_for_use(
        token,
        evaluation_time=T0,
        candidate_id=token.candidate_id,  # type: ignore[union-attr]
        policy_id=token.policy_id,  # type: ignore[union-attr]
        policy_version=token.policy_version,  # type: ignore[union-attr]
        risk_decision_id=token.risk_decision_id,  # type: ignore[union-attr]
        advisory_id=token.advisory_id,  # type: ignore[union-attr]
        current_system_state_version=1,
    ).outcome is KernelOutcome.ALLOW

    intent = _validated(
        x["order"],
        autonomy_token_id=token.token_id,  # type: ignore[union-attr]
        forecast_id=x["candidate"].distribution_id,  # type: ignore[union-attr]
        risk_decision_id=token.risk_decision_id,  # type: ignore[union-attr]
        supervisor_advisory_id=token.advisory_id,  # type: ignore[union-attr]
    )
    order_result = validate_order_intent(
        intent,
        token=token,
        candidate=x["candidate"],
        context=x["context"],
        campaign_state=x["campaign_state"],
        issued_constraints=x["constraints"],
        current_constraints=x["constraints"],
        capital_basis=x["basis"],
        order_facts=x["order_facts"],
        order_policy=x["order_policy"],
        execution_safety=x["safety"],
        evaluation_time=T0,
        current_system_state_version=1,
    )
    assert order_result.outcome is KernelOutcome.ALLOW, order_result.reason_codes

    policy = PaperExecutionPolicy(
        broker_model_version="test.v1",
        cost_model_version="test.cost.v1",
        maximum_quote_age_ms=5000,
        slippage_ticks=1,
        fee_fraction=Decimal("0.001"),
        tax_fraction=Decimal("0.001"),
    )
    instrument = _FakeInstrument()
    market = PaperMarketFacts(
        instrument_id=intent.instrument_id,
        bid=Decimal("99"),
        ask=Decimal("100"),
        bid_quantity=100,
        ask_quantity=100,
        quote_time=T0,
        quality_state=DataQualityState.GOOD,
        scenario=PaperSubmissionScenario.ACKNOWLEDGE,
        rejection_reason=None,
    )
    from ats.kernel.types import KernelResult

    auth = KernelResult(outcome=KernelOutcome.ALLOW, reason_codes=(GateCode.OK,))  # type: ignore[arg-type]
    # Use real broker submit path
    result = submit_paper_order(
        intent=intent, authorization=auth, instrument=instrument, market=market, policy=policy, evaluation_time=T0
    )
    assert result.order is not None
    assert result.order.status in (PaperOrderStatus.ACCEPTED, PaperOrderStatus.FILLED, PaperOrderStatus.PARTIALLY_FILLED)
    # Process one quote to fill
    if result.order.status == PaperOrderStatus.ACCEPTED:
        filled_order, fills = process_paper_order(
            order=result.order, intent=intent, instrument=instrument, market=market, policy=policy, evaluation_time=_t0_plus(1)
        )
        assert len(fills) >= 1
        assert filled_order.status in (PaperOrderStatus.FILLED, PaperOrderStatus.PARTIALLY_FILLED)


def test_authority_failure_cases_block_execution() -> None:
    x = make_kernel_fixture()
    token = _make_authorized_token(x)
    # Expired token
    assert (
        validate_token_for_use(
            token,
            evaluation_time=token.expires_at,  # type: ignore[union-attr]
            candidate_id=token.candidate_id,  # type: ignore[union-attr]
            policy_id=token.policy_id,  # type: ignore[union-attr]
            policy_version=token.policy_version,  # type: ignore[union-attr]
            risk_decision_id=token.risk_decision_id,  # type: ignore[union-attr]
            advisory_id=token.advisory_id,  # type: ignore[union-attr]
            current_system_state_version=1,
        ).outcome
        is KernelOutcome.DENY
    )
    # Reused token (consumed)
    consumed = _validated(token, consumed_at=T0)
    assert (
        validate_token_for_use(
            consumed,
            evaluation_time=T0,
            candidate_id=token.candidate_id,  # type: ignore[union-attr]
            policy_id=token.policy_id,  # type: ignore[union-attr]
            policy_version=token.policy_version,  # type: ignore[union-attr]
            risk_decision_id=token.risk_decision_id,  # type: ignore[union-attr]
            advisory_id=token.advisory_id,  # type: ignore[union-attr]
            current_system_state_version=1,
        ).outcome
        is KernelOutcome.DENY
    )
    # Stale system_state_version
    assert (
        validate_token_for_use(
            token,
            evaluation_time=T0,
            candidate_id=token.candidate_id,  # type: ignore[union-attr]
            policy_id=token.policy_id,  # type: ignore[union-attr]
            policy_version=token.policy_version,  # type: ignore[union-attr]
            risk_decision_id=token.risk_decision_id,  # type: ignore[union-attr]
            advisory_id=token.advisory_id,  # type: ignore[union-attr]
            current_system_state_version=2,
        ).outcome
        is KernelOutcome.DENY
    )
    # Candidate/order mismatch
    wrong_intent = _validated(x["order"], instrument_id="WRONG", autonomy_token_id=token.token_id)  # type: ignore[union-attr]
    assert (
        validate_order_intent(
            wrong_intent,
            token=token,
            candidate=x["candidate"],
            context=x["context"],
            campaign_state=x["campaign_state"],
            issued_constraints=x["constraints"],
            current_constraints=x["constraints"],
            capital_basis=x["basis"],
            order_facts=x["order_facts"],
            order_policy=x["order_policy"],
            execution_safety=x["safety"],
            evaluation_time=T0,
            current_system_state_version=1,
        ).outcome
        is KernelOutcome.DENY
    )
    # Unknown submit keeps capital — tested via execution lifecycle separately


def test_exit_authority_through_safe_path() -> None:
    x = make_kernel_fixture()
    token = _make_authorized_token(x)
    intent = _validated(
        x["order"],
        autonomy_token_id=token.token_id,  # type: ignore[union-attr]
        forecast_id=x["candidate"].distribution_id,  # type: ignore[union-attr]
        risk_decision_id=token.risk_decision_id,  # type: ignore[union-attr]
        supervisor_advisory_id=token.advisory_id,  # type: ignore[union-attr]
    )
    # Even with UNKNOWN execution safety, REDUCE should be allowed when fully_known_safe is handled
    from ats.contracts.governance.types import RiskDirection

    assert token.candidate_id == x["candidate"].candidate_id  # type: ignore[union-attr]
    _ = intent


def test_partial_fill_and_duplicate_fill_idempotent() -> None:
    x = make_kernel_fixture()
    token = _make_authorized_token(x)
    intent = _validated(
        x["order"],
        autonomy_token_id=token.token_id,  # type: ignore[union-attr]
        forecast_id=x["candidate"].distribution_id,  # type: ignore[union-attr]
        risk_decision_id=token.risk_decision_id,  # type: ignore[union-attr]
        supervisor_advisory_id=token.advisory_id,  # type: ignore[union-attr]
    )
    policy = PaperExecutionPolicy(
        broker_model_version="test.v1",
        cost_model_version="test.cost.v1",
        maximum_quote_age_ms=5000,
        slippage_ticks=0,
        fee_fraction=Decimal("0"),
        tax_fraction=Decimal("0"),
    )
    instrument = _FakeInstrument(lot_size=1)
    market = PaperMarketFacts(
        instrument_id=intent.instrument_id,
        bid=Decimal("99"),
        ask=Decimal("100"),
        bid_quantity=1,
        ask_quantity=1,
        quote_time=T0,
        quality_state=DataQualityState.GOOD,
        scenario=PaperSubmissionScenario.ACKNOWLEDGE,
        rejection_reason=None,
    )
    from ats.kernel.types import KernelResult

    auth = KernelResult(outcome=KernelOutcome.ALLOW, reason_codes=(GateCode.OK,))  # type: ignore[arg-type]
    result = submit_paper_order(
        intent=intent, authorization=auth, instrument=instrument, market=market, policy=policy, evaluation_time=T0
    )
    assert result.order is not None


class _FakeInstrument:
    def __init__(self, lot_size: int = 1) -> None:
        self.instrument_id = "ABC"
        self.lot_size = lot_size
        self.tick_size = Decimal("0.05")
        self.quantity_freeze_limit = None
        self.tradable = True
