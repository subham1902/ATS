from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.intelligence.types import ThesisStance
from ats.intelligence.instrument_selector import (
    InstrumentSelectionConfiguration,
    ThetaSemantics,
)
from ats.market.derivatives.option_chain import build_option_chain

from tests.unit.intelligence.thesis.helpers import distribution as base_distribution
from tests.unit.intelligence.thesis.test_synthesis import synthesize
from tests.unit.market.derivatives.option_chain.helpers import (
    AS_OF,
    master,
    quote,
)
from tests.unit.market.derivatives.option_chain.helpers import (
    context as chain_context,
)


def chain(**quote_updates: object):
    inputs = (
        quote("C1", **quote_updates),
        quote("C2", delta=0.6),
        quote("P2"),
        quote("P3", delta=-0.6),
    )
    return build_option_chain(contract_master=master(), context=chain_context(), inputs=inputs)


def distribution(*, expected_return: float = 0.01):
    value = base_distribution().model_copy(
        update={"expected_return_fraction": expected_return}
    )
    return value.model_copy(update={"payload_hash": compute_payload_hash(value)})


def thesis(*, stance: ThesisStance = ThesisStance.BULLISH):
    value = synthesize().thesis
    assert value is not None
    value = value.model_copy(
        update={"stance": stance, "distribution_id": distribution().distribution_id}
    )
    return value.model_copy(update={"payload_hash": compute_payload_hash(value)})


def configuration() -> InstrumentSelectionConfiguration:
    return InstrumentSelectionConfiguration(
        selector_id="LONG_OPTION_SELECTOR_V1",
        selector_version="1.0.0",
        maximum_master_age_ms=60_000,
        maximum_chain_age_ms=60_000,
        maximum_quote_age_ms=60_000,
        maximum_spread_fraction=Decimal("0.05"),
        minimum_top_quantity=65,
        minimum_volume=100,
        minimum_open_interest=100,
        maximum_premium_per_candidate=Decimal("10000"),
        slippage_fraction=Decimal("0.002"),
        transaction_cost_fraction=Decimal("0.001"),
        iv_penalty_factor=Decimal("0.01"),
        degraded_liquidity_penalty_fraction=Decimal("0.01"),
        near_expiry_threshold_hours=Decimal("24"),
        near_expiry_penalty_fraction=Decimal("0.02"),
        bar_duration_minutes=5,
        theta_semantics=ThetaSemantics.PER_CALENDAR_DAY,
    )


def evaluation_time():
    return AS_OF + timedelta(seconds=30)
