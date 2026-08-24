from __future__ import annotations

from ats.execution.paper import submit_paper_order
from ats.kernel.types import ALLOW

from tests.unit.execution.paper.helpers import evaluation_time, instrument, intent, market, policy


def run():
    return submit_paper_order(
        intent=intent(),
        authorization=ALLOW,
        instrument=instrument(),
        market=market(),
        policy=policy(),
        evaluation_time=evaluation_time(),
    )


def test_identical_execution_input_is_json_deterministic() -> None:
    assert run().model_dump_json() == run().model_dump_json()


def test_fill_never_exceeds_intent_quantity() -> None:
    result = run()
    assert result.order is not None
    assert result.order.filled_quantity <= result.order.quantity


def test_execution_has_no_live_submission_surface() -> None:
    result = run()
    assert not hasattr(result, "broker_session")
    assert not hasattr(result, "live_order_id")
