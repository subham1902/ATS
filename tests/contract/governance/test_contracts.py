from __future__ import annotations

from ats.contracts.governance import GOVERNANCE_CONTRACTS
from ats.contracts.governance.types import ConstraintCode


def test_governance_contract_inventory() -> None:
    assert tuple(contract.__name__ for contract in GOVERNANCE_CONTRACTS) == (
        "TradingCampaign",
        "CampaignState",
        "OpportunityCandidate",
        "PositionThesis",
        "GovernanceContext",
    )


def test_constraint_code_set_is_exactly_fifteen() -> None:
    assert len(ConstraintCode) == 15
