"""Cross-contract A02 registry, schema, numeric, safety, and hash evidence."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ats.contracts import canonical_sha256
from ats.contracts.domain import DOMAIN_CONTRACTS, compute_payload_hash
from ats.contracts.domain.models import (
    AutonomyToken,
    ConfidenceEvidence,
    StrategyPolicy,
    StrategyPolicyDraft,
    SupervisorAdvisory,
)
from ats.contracts.domain.types import (
    AdvisoryOutcome,
    Predicate,
    PredicateOperator,
    RiskOutcome,
)
from tests.unit.contracts.domain.fixtures import make_contracts

EXPECTED_CONTRACT_NAMES = (
    "MarketSnapshot",
    "FeatureBundle",
    "ForecastBundle",
    "ConfidenceEvidence",
    "StrategyPolicyDraft",
    "StrategyPolicy",
    "RiskFacts",
    "RiskDecision",
    "DecisionPacket",
    "SupervisorAdvisory",
    "AutonomyToken",
    "OrderIntent",
    "PaperOrder",
    "Fill",
    "Position",
    "ExitIntent",
    "TradeReview",
    "AuditEvent",
)


def test_registry_is_exactly_the_18_frozen_contracts() -> None:
    assert tuple(contract.__name__ for contract in DOMAIN_CONTRACTS) == EXPECTED_CONTRACT_NAMES


def test_all_18_json_schemas_export_with_v1_literal() -> None:
    for contract in DOMAIN_CONTRACTS:
        schema = contract.model_json_schema()
        version_schema = schema["properties"]["schema_version"]
        assert version_schema["const"] == "1.0"


def test_uuid_references_survive_immutable_round_trip() -> None:
    for value in make_contracts().values():
        restored = type(value).model_validate_json(value.model_dump_json())
        for name, field_value in value.model_dump().items():
            if name.endswith("_id") and not isinstance(field_value, str):
                assert restored.model_dump()[name] == field_value


@pytest.mark.parametrize("value", [Decimal("-0.01"), Decimal("1.01"), Decimal("NaN")])
def test_true_probability_fields_reject_out_of_range(value: Decimal) -> None:
    confidence = make_contracts()["ConfidenceEvidence"]
    with pytest.raises(ValidationError):
        ConfidenceEvidence.model_validate(
            {**confidence.model_dump(), "raw_probability": value}
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_analytical_float_fields_reject_non_finite(value: float) -> None:
    feature = make_contracts()["FeatureBundle"]
    with pytest.raises(ValidationError):
        type(feature).model_validate({**feature.model_dump(), "features": {"bad": value}})


def test_financial_fields_reject_python_float() -> None:
    fill = make_contracts()["Fill"]
    with pytest.raises(ValidationError):
        type(fill).model_validate({**fill.model_dump(), "price": 100.0})


def test_alpha_authority_literals_are_closed() -> None:
    fixtures = make_contracts()
    draft = fixtures["StrategyPolicyDraft"]
    policy = fixtures["StrategyPolicy"]
    token = fixtures["AutonomyToken"]
    with pytest.raises(ValidationError):
        StrategyPolicyDraft.model_validate({**draft.model_dump(), "requested_autonomy": "A3"})
    with pytest.raises(ValidationError):
        StrategyPolicy.model_validate({**policy.model_dump(), "autonomy_level": "A4"})
    with pytest.raises(ValidationError):
        AutonomyToken.model_validate({**token.model_dump(), "scope": "A3_LIVE"})


def test_draft_and_advisory_cannot_express_executable_authority() -> None:
    draft = make_contracts()["StrategyPolicyDraft"]
    advisory = make_contracts()["SupervisorAdvisory"]
    with pytest.raises(ValidationError):
        StrategyPolicyDraft.model_validate({**draft.model_dump(), "executable": True})
    assert "executable" not in SupervisorAdvisory.model_fields


@pytest.mark.parametrize("decision", list(RiskOutcome))
def test_risk_outcomes_are_closed_and_unknown_is_representable(decision: RiskOutcome) -> None:
    value = make_contracts()["RiskDecision"]
    reasons = () if decision is RiskOutcome.ALLOW else ("REASON",)
    restored = type(value).model_validate(
        {**value.model_dump(), "decision": decision, "reason_codes": reasons}
    )
    assert restored.decision is decision  # type: ignore[attr-defined]


@pytest.mark.parametrize("recommendation", list(AdvisoryOutcome))
def test_advisory_outcomes_are_closed(recommendation: AdvisoryOutcome) -> None:
    value = make_contracts()["SupervisorAdvisory"]
    restored = type(value).model_validate(
        {**value.model_dump(), "recommendation": recommendation}
    )
    assert restored.recommendation is recommendation  # type: ignore[attr-defined]


def test_predicate_has_bounded_declarative_shape_only() -> None:
    assert set(Predicate.model_fields) == {"field", "operator", "value"}
    with pytest.raises(ValidationError):
        Predicate(
            field="signal",
            operator=PredicateOperator.GT,
            value={"python_source": "eval('x')"},
        )


def test_payload_hash_excludes_only_itself_and_is_order_independent() -> None:
    market = make_contracts()["MarketSnapshot"]
    first = compute_payload_hash(market)
    reordered = dict(reversed(list(market.model_dump().items())))
    assert compute_payload_hash(reordered) == first
    changed = {**market.model_dump(), "sequence": 2}
    assert compute_payload_hash(changed) != first


def test_representative_committed_hash_goldens() -> None:
    values = make_contracts()
    expected = {
        "MarketSnapshot": "df122f177ef9fa4e4e73e5fa81f07a7ad13a06b2fb465cbbd716c70f6f64637e",
        "FeatureBundle": "5f90a1262cb27721629df7847a6cc84652e17ce4d6205b1e1f939dfa8659a88a",
        "StrategyPolicy": "d4d724e19141a03672c6f8968b5c0057b730ce564100729683519ed26c6e8359",
        "RiskDecision": "c7d4aff8eb8675dec0376c885f6e5638d74d7972cc1992095b6a89230ea52226",
        "AutonomyToken": "e4dfdf5612164f93ff30e1a00649362f189615f11626725c5e3b05587dd82166",
        "OrderIntent": "138cc5cf10934d2544bafd294d2482f7798110a34a75224b376e5a3254e9361d",
        "Fill": "892da13b65196458f1e6441ab701c4afeb851a822714d8b00bebc825af34a63f",
        "TradeReview": "f7a2667e8cb524e12797a0cbafc5f92b66d4b0aebe7ba698a589d9a1edf57e75",
    }
    for name, golden in expected.items():
        value = values[name]
        actual = (
            compute_payload_hash(value)
            if "payload_hash" in type(value).model_fields
            else canonical_sha256(value)
        )
        assert actual == golden
