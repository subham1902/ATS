from __future__ import annotations

from ats.intelligence.instrument_selector import (
    InstrumentSelectionStatus,
    select_derivative_instruments,
)

from tests.unit.intelligence.instrument_selector.helpers import (
    chain,
    configuration,
    distribution,
    evaluation_time,
    thesis,
)
from tests.unit.market.derivatives.option_chain.helpers import master


def test_contract_chain_thesis_distribution_to_long_option_evidence() -> None:
    result = select_derivative_instruments(
        contract_master=master(),
        option_chain=chain(),
        thesis=thesis(),
        distribution=distribution(),
        evaluation_time=evaluation_time(),
        configuration=configuration(),
    )
    assert result.status is InstrumentSelectionStatus.CANDIDATES_AVAILABLE
    assert len(result.candidates) == 1
    assert result.candidates[0].expected_net_pnl > 0
