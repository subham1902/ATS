"""Fully bound evidence fixtures for the R10 construction boundary."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.governance.models import TradingCampaign
from ats.contracts.governance.types import CampaignStatus
from ats.governance.campaign import initialize_campaign_state
from ats.governance.opportunity import (
    OpportunityConstructionConfiguration,
    OpportunityEconomicsFacts,
)
from ats.governance.opportunity.instrument import InstrumentCandidate

from tests.unit.intelligence.thesis.helpers import distribution
from tests.unit.intelligence.thesis.test_synthesis import synthesize
from tests.unit.kernel.fixtures import make_kernel_fixture
from tests.unit.market.xauusd import AS_OF


def _rehash(value: object, **updates: object):  # type: ignore[no-untyped-def]
    raw = {**value.model_dump(mode="python"), **updates}  # type: ignore[attr-defined]
    raw["payload_hash"] = "0" * 64
    result = type(value).model_validate(raw)
    return result.model_copy(update={"payload_hash": compute_payload_hash(result)})


def bound_inputs() -> dict[str, object]:
    now = AS_OF + timedelta(seconds=30)
    selected_distribution = _rehash(distribution(), instrument_id="XAUUSD")
    selected_thesis = _rehash(
        synthesize().thesis,
        instrument_id="XAUUSD",
        distribution_id=selected_distribution.distribution_id,
    )
    instrument = InstrumentCandidate(
        schema_version="1.0",
        instrument_candidate_id=UUID("00000000-0000-0000-0000-000000000703"),
        thesis_id=selected_thesis.thesis_id,
        thesis_version=selected_thesis.thesis_version,
        distribution_id=selected_distribution.distribution_id,
        quantity=Decimal("1"),
        entry_ask=Decimal("101"),
        expected_gross_pnl=Decimal("20"),
        estimated_spread_cost=Decimal("2"),
        estimated_slippage=Decimal("1"),
        estimated_transaction_cost=Decimal("1"),
        expected_net_pnl=Decimal("16"),
        as_of_time=AS_OF,
        data_cutoff=AS_OF,
        method_version="SYNTHETIC-V1",
        payload_hash="0" * 64,
    )
    instrument = instrument.model_copy(update={"payload_hash": compute_payload_hash(instrument)})

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
