from __future__ import annotations

from ats.contracts.domain.hashing import compute_payload_hash
from ats.intelligence.thesis import ThesisSynthesisError, synthesize_market_thesis

from tests.unit.intelligence.calibration.helpers import ensemble, regime
from tests.unit.intelligence.ensemble.helpers import context
from tests.unit.intelligence.thesis.helpers import configuration, distribution, facts


def run():
    return synthesize_market_thesis(
        market_context=context(),
        regime_evidence=regime(),
        ensemble=ensemble(),
        distribution=distribution(),
        facts=facts(),
        configuration=configuration(),
    )


def test_identical_inputs_are_json_deterministic() -> None:
    assert run().model_dump_json() == run().model_dump_json()


def test_evidence_refs_have_deterministic_order() -> None:
    thesis = run().thesis
    assert thesis is not None
    assert thesis.evidence_refs == (
        context().market_context_id,
        regime().regime_evidence_id,
        ensemble().ensemble_forecast_id,
        distribution().distribution_id,
    )


def test_future_cutoff_cannot_be_normalized_into_thesis() -> None:
    current = context().model_copy(update={"data_cutoff": context().as_of_time})
    current = current.model_copy(update={"payload_hash": compute_payload_hash(current)})
    try:
        synthesize_market_thesis(
            market_context=current,
            regime_evidence=regime(),
            ensemble=ensemble(),
            distribution=distribution(),
            facts=facts(),
            configuration=configuration(),
        )
    except ThesisSynthesisError as error:
        assert "lineage" in str(error)
    else:
        raise AssertionError("mismatched future cutoff unexpectedly synthesized")
