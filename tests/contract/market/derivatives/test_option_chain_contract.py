from __future__ import annotations

import pytest
from ats.market.derivatives.option_chain import (
    OptionChainEvidence,
    OptionChainState,
    OptionQuote,
    build_option_chain,
    compute_option_chain_evidence,
)

from tests.unit.market.derivatives.option_chain.helpers import context, master, quote


@pytest.mark.parametrize("model", [OptionQuote, OptionChainState, OptionChainEvidence])
def test_option_chain_models_export_strict_schema(model: type[object]) -> None:
    schema = model.model_json_schema()  # type: ignore[attr-defined]
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False


def test_chain_and_evidence_json_round_trip() -> None:
    chain = build_option_chain(
        contract_master=master(), context=context(), inputs=(quote("C2"), quote("P2"))
    )
    evidence = compute_option_chain_evidence(chain)
    assert OptionChainState.model_validate_json(chain.model_dump_json()) == chain
    assert OptionChainEvidence.model_validate_json(evidence.model_dump_json()) == evidence


def test_no_probability_or_authority_fields() -> None:
    fields = set(OptionChainEvidence.model_fields)
    assert not any("probability" in field for field in fields)
    assert fields.isdisjoint({"order_intent", "risk_decision", "autonomy_token", "campaign"})
