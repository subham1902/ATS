from __future__ import annotations

from datetime import timedelta

import pytest
from ats.market.derivatives.option_chain import OptionChainError, build_option_chain

from tests.unit.market.derivatives.option_chain.helpers import AS_OF, context, master, quote


def test_input_order_does_not_change_chain() -> None:
    inputs = (quote("P2"), quote("C1"), quote("C2"), quote("P3"))
    first = build_option_chain(contract_master=master(), context=context(), inputs=inputs)
    second = build_option_chain(
        contract_master=master(), context=context(), inputs=tuple(reversed(inputs))
    )
    assert first == second


def test_future_suffix_cannot_enter_cutoff_state() -> None:
    valid = (quote("C2"), quote("P2"))
    baseline = build_option_chain(contract_master=master(), context=context(), inputs=valid)
    assert baseline.quotes
    with pytest.raises(OptionChainError):
        build_option_chain(
            contract_master=master(),
            context=context(),
            inputs=valid + (quote("C1", quote_time=AS_OF + timedelta(seconds=1)),),
        )


def test_repeated_inputs_repeat_exact_json_and_hash() -> None:
    first = build_option_chain(
        contract_master=master(), context=context(), inputs=(quote("C2"), quote("P2"))
    )
    second = build_option_chain(
        contract_master=master(), context=context(), inputs=(quote("C2"), quote("P2"))
    )
    assert first.model_dump_json() == second.model_dump_json()
    assert first.payload_hash == second.payload_hash
