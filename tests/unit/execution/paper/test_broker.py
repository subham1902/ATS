from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState, PaperOrderStatus, PaperOrderType, Side
from ats.execution.paper import (
    ObservedSubmissionState,
    PaperExecutionError,
    PaperSubmissionScenario,
    PaperSubmissionState,
    ReconciliationOutcome,
    SubmissionObservation,
    cancel_paper_order,
    process_paper_order,
    reconcile_unknown_submission,
    submit_paper_exit,
    submit_paper_order,
)
from ats.kernel.types import GateCode, KernelOutcome, KernelResult

from tests.unit.market.derivatives.option_chain.helpers import AS_OF

from .helpers import evaluation_time, exit_intent, instrument, intent, market, policy, position

ALLOW = KernelResult(outcome=KernelOutcome.ALLOW, reason_codes=(GateCode.OK,))


def submit(**overrides: object):
    arguments = {
        "intent": intent(),
        "authorization": ALLOW,
        "instrument": instrument(),
        "market": market(),
        "policy": policy(),
        "evaluation_time": evaluation_time(),
    }
    arguments.update(overrides)
    return submit_paper_order(**arguments)  # type: ignore[arg-type]


def test_market_buy_fills_at_ask_plus_tick_slippage() -> None:
    result = submit()
    assert result.submission_state is PaperSubmissionState.ACKNOWLEDGED
    assert result.order is not None and result.order.status is PaperOrderStatus.FILLED
    assert result.fills[0].price == Decimal("101.10")
    assert result.fills[0].quantity == Decimal("65")
    assert result.fills[0].payload_hash == compute_payload_hash(result.fills[0])


def test_fill_costs_are_explicit_and_not_ltp_based() -> None:
    fill = submit().fills[0]
    assert fill.fees == fill.price * fill.quantity * Decimal("0.001")
    assert fill.taxes == fill.price * fill.quantity * Decimal("0.002")
    assert fill.slippage == Decimal("0.10") * fill.quantity


def test_top_of_book_liquidity_produces_partial_fill() -> None:
    result = submit(intent=intent(quantity="130"), market=market(ask_quantity=65))
    assert result.order is not None
    assert result.order.status is PaperOrderStatus.PARTIALLY_FILLED
    assert result.order.filled_quantity == Decimal("65")


def test_less_than_one_lot_remains_accepted_unfilled() -> None:
    result = submit(market=market(ask_quantity=64))
    assert result.order is not None and result.order.status is PaperOrderStatus.ACCEPTED
    assert result.fills == ()


def test_second_quote_can_complete_partial_order() -> None:
    original_intent = intent(quantity="130")
    first = submit(intent=original_intent, market=market(ask_quantity=65))
    assert first.order is not None
    updated, fills = process_paper_order(
        order=first.order,
        intent=original_intent,
        instrument=instrument(),
        market=market(ask_quantity=65),
        policy=policy(),
        evaluation_time=evaluation_time() + timedelta(seconds=1),
    )
    assert updated.status is PaperOrderStatus.FILLED
    assert updated.filled_quantity == Decimal("130")
    assert len(fills) == 1


def test_non_marketable_limit_waits_without_fake_fill() -> None:
    order_intent = intent(order_type=PaperOrderType.LIMIT, limit_price=Decimal("100"))
    result = submit(intent=order_intent)
    assert result.order is not None and result.order.status is PaperOrderStatus.ACCEPTED
    assert result.fills == ()


def test_marketable_limit_fills_within_limit() -> None:
    order_intent = intent(order_type=PaperOrderType.LIMIT, limit_price=Decimal("102"))
    assert submit(intent=order_intent).fills[0].price == Decimal("101.10")


def test_stop_limit_does_not_fill_before_trigger() -> None:
    order_intent = intent(
        order_type=PaperOrderType.STOP_LIMIT,
        stop_price=Decimal("102"),
        limit_price=Decimal("103"),
    )
    assert submit(intent=order_intent).fills == ()


def test_rejection_is_bounded_paper_order() -> None:
    result = submit(
        market=market(
            scenario=PaperSubmissionScenario.REJECT,
            rejection_reason="SIMULATED_EXCHANGE_REJECT",
        )
    )
    assert result.submission_state is PaperSubmissionState.REJECTED
    assert result.order is not None and result.order.status is PaperOrderStatus.REJECTED
    assert result.fills == ()


def test_timeout_is_unknown_and_does_not_fabricate_order() -> None:
    result = submit(market=market(scenario=PaperSubmissionScenario.TIMEOUT_UNKNOWN))
    assert result.submission_state is PaperSubmissionState.UNKNOWN
    assert result.order is None
    assert result.fills == ()


@pytest.mark.parametrize("outcome", [KernelOutcome.DENY, KernelOutcome.UNKNOWN])
def test_a04_non_allow_never_executes(outcome: KernelOutcome) -> None:
    result = KernelResult(outcome=outcome, reason_codes=(GateCode.SYSTEM_STATE_DENY,))
    with pytest.raises(PaperExecutionError, match="A04"):
        submit(authorization=result)


def test_sell_entry_is_rejected_to_prevent_naked_short_option() -> None:
    with pytest.raises(PaperExecutionError, match="long options"):
        submit(intent=intent(side=Side.SELL))


def test_wrong_lot_size_is_rejected() -> None:
    with pytest.raises(PaperExecutionError, match="lot multiple"):
        submit(intent=intent(quantity="64"))


def test_quantity_freeze_limit_is_enforced() -> None:
    with pytest.raises(PaperExecutionError, match="freeze"):
        submit(intent=intent(quantity="1820"))


def test_non_tick_aligned_limit_is_rejected() -> None:
    with pytest.raises(PaperExecutionError, match="tick"):
        submit(intent=intent(order_type=PaperOrderType.LIMIT, limit_price=Decimal("101.03")))


def test_stale_quote_is_rejected() -> None:
    with pytest.raises(PaperExecutionError, match="stale"):
        submit(evaluation_time=AS_OF + timedelta(minutes=2))


def test_unknown_market_quality_is_rejected() -> None:
    with pytest.raises(PaperExecutionError, match="quality"):
        submit(market=market(quality_state=DataQualityState.UNKNOWN))


def test_missing_ask_is_rejected() -> None:
    with pytest.raises(PaperExecutionError, match="ask"):
        submit(market=market(ask=None))


def test_open_partial_order_can_be_cancelled() -> None:
    result = submit(intent=intent(quantity="130"), market=market(ask_quantity=65))
    assert result.order is not None
    cancelled = cancel_paper_order(
        result.order, cancelled_at=evaluation_time() + timedelta(seconds=2)
    )
    assert cancelled.status is PaperOrderStatus.CANCELLED
    assert cancelled.filled_quantity == Decimal("65")


def test_filled_order_cannot_be_cancelled() -> None:
    order = submit().order
    assert order is not None
    with pytest.raises(PaperExecutionError, match="open"):
        cancel_paper_order(order, cancelled_at=evaluation_time())


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (ObservedSubmissionState.ABSENT, ReconciliationOutcome.CONFIRMED_ABSENT),
        (ObservedSubmissionState.UNKNOWN, ReconciliationOutcome.STILL_UNKNOWN),
    ],
)
def test_unknown_reconciliation_never_permits_blind_retry(state, expected) -> None:
    result = reconcile_unknown_submission(
        intent=intent(),
        observation=SubmissionObservation(state=state, order=None, observed_at=evaluation_time()),
    )
    assert result.outcome is expected
    assert result.retry_permitted is False


def test_reconciliation_can_confirm_matching_order_present() -> None:
    order = submit().order
    assert order is not None
    result = reconcile_unknown_submission(
        intent=intent(),
        observation=SubmissionObservation(
            state=ObservedSubmissionState.PRESENT,
            order=order,
            observed_at=evaluation_time(),
        ),
    )
    assert result.outcome is ReconciliationOutcome.CONFIRMED_PRESENT
    assert result.retry_permitted is False


def test_exit_sells_known_long_position_against_bid() -> None:
    result = submit_paper_exit(
        intent=exit_intent(),
        position=position(),
        authorization=ALLOW,
        instrument=instrument(),
        market=market(),
        policy=policy(),
        evaluation_time=evaluation_time(),
    )
    assert result.order is not None and result.order.side is Side.SELL
    assert result.fills[0].price == Decimal("98.90")
    assert result.fills[0].quantity == Decimal("65")


def test_exit_cannot_exceed_known_position() -> None:
    with pytest.raises(PaperExecutionError, match="exceeds known"):
        submit_paper_exit(
            intent=exit_intent(quantity="195"),
            position=position(),
            authorization=ALLOW,
            instrument=instrument(),
            market=market(),
            policy=policy(),
            evaluation_time=evaluation_time(),
        )


def test_exit_position_version_mismatch_fails_closed() -> None:
    with pytest.raises(PaperExecutionError, match="binding"):
        submit_paper_exit(
            intent=exit_intent(position_version=2),
            position=position(version=1),
            authorization=ALLOW,
            instrument=instrument(),
            market=market(),
            policy=policy(),
            evaluation_time=evaluation_time(),
        )


def test_exit_timeout_remains_unknown_without_blind_fill() -> None:
    result = submit_paper_exit(
        intent=exit_intent(),
        position=position(),
        authorization=ALLOW,
        instrument=instrument(),
        market=market(scenario=PaperSubmissionScenario.TIMEOUT_UNKNOWN),
        policy=policy(),
        evaluation_time=evaluation_time(),
    )
    assert result.submission_state is PaperSubmissionState.UNKNOWN
    assert result.order is None and result.fills == ()
