from __future__ import annotations

import json
from pathlib import Path

from ats.contracts.governance.types import CampaignStatus, CandidateStatus, PositionThesisState
from ats.contracts.intelligence.types import ExperimentStatus, MarketThesisStatus, StrategyStatus


def test_six_frozen_state_machine_tables_are_complete() -> None:
    tables = json.loads(Path(__file__).with_name("iba_state_transitions.json").read_text())
    enums = {
        "MarketThesis": MarketThesisStatus,
        "TradingCampaign": CampaignStatus,
        "OpportunityCandidate": CandidateStatus,
        "PositionThesis": PositionThesisState,
        "StrategyDefinition": StrategyStatus,
        "StrategyExperiment": ExperimentStatus,
    }
    assert set(tables) == set(enums)
    for name, enum in enums.items():
        assert set(tables[name]) == {item.value for item in enum}
        assert all(set(targets) <= set(tables[name]) for targets in tables[name].values())


def test_frozen_terminal_states_have_no_outgoing_transitions() -> None:
    tables = json.loads(Path(__file__).with_name("iba_state_transitions.json").read_text())
    terminal = {
        "MarketThesis": ("SUPERSEDED", "INVALIDATED", "EXPIRED"),
        "TradingCampaign": ("REJECTED", "COMPLETED", "HALTED", "EXPIRED"),
        "OpportunityCandidate": ("REJECTED", "EXPIRED", "CONSUMED"),
        "PositionThesis": ("CLOSED",),
        "StrategyDefinition": ("REJECTED", "RETIRED"),
        "StrategyExperiment": ("COMPLETED", "FAILED", "INVALIDATED", "CANCELLED"),
    }
    for name, states in terminal.items():
        assert all(tables[name][state] == [] for state in states)
