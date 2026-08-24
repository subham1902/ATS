from __future__ import annotations

import inspect
import json
from pathlib import Path

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.governance import GOVERNANCE_CONTRACTS
from ats.contracts.governance import types as governance_types
from ats.contracts.intelligence import INTELLIGENCE_CONTRACTS
from ats.contracts.intelligence import types as intelligence_types
from tests.unit.contracts.intelligence.fixtures import make_contracts

HERE = Path(__file__).parent
ALL_CONTRACTS = INTELLIGENCE_CONTRACTS + GOVERNANCE_CONTRACTS
EXPECTED_COUNTS = {
    "InstrumentSpec": 29, "MarketContext": 19, "RegimeEvidence": 19,
    "AnalogueEvidence": 22, "EnsembleForecast": 18,
    "CalibratedOutcomeDistribution": 27, "MarketThesis": 26,
    "AnalystAssessment": 15, "TradingCampaign": 34, "CampaignState": 19,
    "OpportunityCandidate": 30, "PositionThesis": 24, "GovernanceContext": 30,
    "StrategyDefinition": 23, "FormulaDefinition": 19, "StrategyExperiment": 28,
    "StrategyScorecard": 28, "PromotionDecision": 17,
    "PerformanceAttribution": 18, "ExplanationEvidence": 16,
}


def test_exact_twenty_contracts_and_461_fields() -> None:
    actual = {contract.__name__: len(contract.model_fields) for contract in ALL_CONTRACTS}
    assert actual == EXPECTED_COUNTS
    assert len(actual) == 20
    assert sum(actual.values()) == 461


def test_field_coverage_manifest_matches_annotations_and_requiredness() -> None:
    manifest = json.loads((HERE / "iba_field_coverage.json").read_text(encoding="utf-8"))
    assert manifest["expected_contract_count"] == 20
    assert manifest["expected_field_total"] == 461
    assert set(manifest["contracts"]) == set(EXPECTED_COUNTS)
    for contract in ALL_CONTRACTS:
        entry = manifest["contracts"][contract.__name__]
        assert entry["frozen_field_count"] == entry["implemented_concrete_field_count"]
        assert entry["implemented_concrete_field_count"] == EXPECTED_COUNTS[contract.__name__]
        fields = entry["fields"]
        assert [field["frozen_field"] for field in fields] == list(contract.model_fields)
        assert [field["implemented_field"] for field in fields] == list(contract.model_fields)
        for evidence, (name, field) in zip(fields, contract.model_fields.items(), strict=True):
            assert evidence["exact_type_representation"] == contract.__annotations__[name]
            assert evidence["required"] is field.is_required()


def test_registry_is_complete_and_matches_frozen_classes() -> None:
    registry = json.loads((HERE / "iba_contract_registry.json").read_text(encoding="utf-8"))["contracts"]
    assert set(registry) == set(EXPECTED_COUNTS)
    assert registry["FormulaDefinition"]["producer"] == "Strategy Lab"
    assert registry["GovernanceContext"]["authority"] == "KERNEL_INPUT"
    assert registry["TradingCampaign"]["authority"] == "CONTROL_CONSTRAINT"
    assert registry["ExplanationEvidence"]["authority"] == "READ_ONLY"


def test_all_top_level_and_support_schemas_export() -> None:
    for contract in ALL_CONTRACTS:
        assert contract.model_json_schema()["properties"]["schema_version"]["const"] == "1.0"
    support = []
    for module in (intelligence_types, governance_types):
        support.extend(
            cls for _, cls in inspect.getmembers(module, inspect.isclass)
            if issubclass(cls, ATSBaseModel) and cls is not ATSBaseModel and cls.__module__ == module.__name__
        )
    assert len(support) == 18
    for model in support:
        assert model.model_json_schema()


def test_representative_hash_goldens() -> None:
    expected = {
        "InstrumentSpec": "4e184915a4dff573a09eccf5a96d68bf113093ae3f84fb9449c1f7fc86a13072",
        "MarketContext": "141ecf843615780adde7580fb8963a7bac3068047f897f7192cb99af312a35b3",
        "AnalogueEvidence": "8dab41df8816c4b58b64a0a5c2dc481e59e7ab11634f4e97639cf8a3120c7145",
        "CalibratedOutcomeDistribution": "b77645e8c26b35c7ff8019f48cf70f94ae895d79645fa653442d40914ea3c707",
        "MarketThesis": "25615142705be754ecabecc353804a31f67bdbd4e176472be87af160d6463a28",
        "TradingCampaign": "af543c84946c82aa94cd5ce8a1c309a68d8ea6d67e8f4faaf6a25941e9e2166d",
        "OpportunityCandidate": "d7669c8532c901652cf723cc2946b9ac5b47c4829b505e28cf97576efd413f7e",
        "GovernanceContext": "d0da070b155d648f765b776e285c7b3ffbb460e24c6dd12c1d6c7c26ba959199",
        "FormulaDefinition": "c5032b500d25ec22c55033244396a1d7c34171b812bd4e0264a40f70433fc8aa",
        "StrategyExperiment": "6bdf37803cfb4859c5855347edc87abf4b49b8506d264e691d762dbf0ac4a4f5",
        "ExplanationEvidence": "3ebd3a1b25599884cffde44d811ae31be194c5c5b84ec56b4497ac67f84d6f31",
    }
    fixtures = make_contracts()
    assert {name: compute_payload_hash(fixtures[name]) for name in expected} == expected


def test_no_contract_exposes_service_or_authority_methods() -> None:
    forbidden = {"place_order", "issue_token", "activate", "evaluate", "backtest"}
    for contract in ALL_CONTRACTS:
        assert not (forbidden & set(contract.__dict__))
