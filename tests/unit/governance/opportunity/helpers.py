"""Fully bound evidence fixtures for the R10 construction boundary."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.governance.models import TradingCampaign
from ats.contracts.governance.types import CampaignStatus
from ats.governance.campaign import initialize_campaign_state
from ats.governance.opportunity import (
    OpportunityConstructionConfiguration,
    OpportunityEconomicsFacts,
)
from ats.intelligence.instrument_selector import select_derivative_instruments

from tests.unit.intelligence.instrument_selector.helpers import (
    chain,
    distribution,
    evaluation_time,
    thesis,
)
from tests.unit.intelligence.instrument_selector.helpers import (
    configuration as selector_configuration,
)
from tests.unit.kernel.fixtures import make_kernel_fixture
from tests.unit.market.derivatives.option_chain.helpers import master


def _rehash(value: object, **updates: object):  # type: ignore[no-untyped-def]
    raw = {**value.model_dump(mode="python"), **updates}  # type: ignore[attr-defined]
    raw["payload_hash"] = "0" * 64
    result = type(value).model_validate(raw)
    return result.model_copy(update={"payload_hash": compute_payload_hash(result)})


def bound_inputs() -> dict[str, object]:
    now = evaluation_time()
    selected_thesis = thesis()
    selected_distribution = distribution()
    selection = select_derivative_instruments(
        contract_master=master(),
        option_chain=chain(),
        thesis=selected_thesis,
        distribution=selected_distribution,
        configuration=selector_configuration(),
        evaluation_time=now,
    )
    assert selection.candidates
    instrument = selection.candidates[0]

    kernel = make_kernel_fixture()
    raw_campaign = kernel["campaign"]
    assert isinstance(raw_campaign, TradingCampaign)
    strategy = _rehash(
        kernel["strategy"],
        compatible_instruments=(instrument.instrument_id,),
        compatible_timeframes=(selected_thesis.timeframe,),
    )
    campaign = _rehash(
        raw_campaign,
        instrument_universe=(instrument.instrument_id,),
        allowed_strategies=(
            {
                "strategy_definition_id": strategy.strategy_definition_id,
                "strategy_definition_version": strategy.strategy_definition_version,
            },
        ),
        allowed_timeframes=(selected_thesis.timeframe,),
        status=CampaignStatus.ACTIVE,
        created_at=now - timedelta(hours=2),
        start_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=1),
        activated_at=now - timedelta(minutes=30),
    )
    state = initialize_campaign_state(campaign, as_of_time=now)
    return {
        "instrument_candidate": instrument,
        "thesis": selected_thesis,
        "distribution": selected_distribution,
        "campaign": campaign,
        "campaign_state": state,
        "strategy": strategy,
        "economics": OpportunityEconomicsFacts(
            maximum_loss=Decimal("6500"),
            expected_reward=Decimal("13000"),
            proposed_stop_price=Decimal("80"),
            proposed_target_price=Decimal("130"),
        ),
        "configuration": OpportunityConstructionConfiguration(
            governor_id="OPPORTUNITY_GOVERNOR_V1",
            governor_version="1.0.0",
            target_outcome_code="ABOVE",
            maximum_ttl_ms=60_000,
        ),
        "evaluation_time": now,
    }


__all__ = ["_rehash", "bound_inputs"]
