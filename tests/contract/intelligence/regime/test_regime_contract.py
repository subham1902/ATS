from __future__ import annotations

from ats.contracts.intelligence.models import RegimeEvidence
from ats.intelligence.regime import detect_regime

from tests.unit.intelligence.regime.helpers import bundle, configuration, context


def test_frozen_regime_schema_exports() -> None:
    schema = RegimeEvidence.model_json_schema()
    assert schema["type"] == "object"
    assert len(RegimeEvidence.model_fields) == 19


def test_detector_returns_exact_frozen_contract_round_trip() -> None:
    current = bundle(1)
    evidence = detect_regime(
        market_context=context(current),
        feature_history=(current,),
        configuration=configuration(),
    )
    assert type(evidence) is RegimeEvidence
    assert RegimeEvidence.model_validate_json(evidence.model_dump_json()) == evidence


def test_no_probability_or_authority_fields() -> None:
    fields = set(RegimeEvidence.model_fields)
    assert fields.isdisjoint({"probability", "order_intent", "risk_decision", "autonomy_token"})
