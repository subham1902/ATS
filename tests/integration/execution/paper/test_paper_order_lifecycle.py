from __future__ import annotations

from ats.contracts.domain.types import PaperOrderStatus
from ats.execution.paper import process_paper_order, submit_paper_order
from ats.kernel.types import ALLOW

from tests.unit.execution.paper.helpers import evaluation_time, instrument, intent, market, policy


def test_authorized_order_partial_then_full_fill_lifecycle() -> None:
    order_intent = intent(quantity="130")
    first = submit_paper_order(
        intent=order_intent,
        authorization=ALLOW,
        instrument=instrument(),
        market=market(ask_quantity=65),
        policy=policy(),
        evaluation_time=evaluation_time(),
    )
    assert first.order is not None
    final, second_fills = process_paper_order(
        order=first.order,
        intent=order_intent,
        instrument=instrument(),
        market=market(ask_quantity=65),
        policy=policy(),
        evaluation_time=evaluation_time(),
    )
    assert final.status is PaperOrderStatus.FILLED
    assert len(first.fills + second_fills) == 2
