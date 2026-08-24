from __future__ import annotations

from ats.intelligence.instrument_selector import select_derivative_instruments

from tests.unit.intelligence.instrument_selector.helpers import (
    chain,
    configuration,
    distribution,
    evaluation_time,
    thesis,
)
from tests.unit.market.derivatives.option_chain.helpers import master


def run(option_chain=None):
    return select_derivative_instruments(
        contract_master=master(),
        option_chain=option_chain or chain(),
        thesis=thesis(),
        distribution=distribution(),
        evaluation_time=evaluation_time(),
        configuration=configuration(),
    )


def test_repetition_is_json_deterministic() -> None:
    assert run().model_dump_json() == run().model_dump_json()


def test_quote_input_order_does_not_change_selection() -> None:
    value = chain()
    reversed_chain = value.model_copy(update={"quotes": tuple(reversed(value.quotes))})
    from ats.contracts.domain.hashing import compute_payload_hash

    reversed_chain = reversed_chain.model_copy(
        update={"payload_hash": compute_payload_hash(reversed_chain)}
    )
    assert run(value).candidates == run(reversed_chain).candidates


def test_no_duplicate_economic_expression_escapes() -> None:
    result = run()
    keys = tuple(
        (item.underlying, item.expiry, item.option_type, item.thesis_id)
        for item in result.candidates
    )
    assert len(keys) == len(set(keys))
