from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState
from ats.contracts.intelligence.types import (
    PriceLevel,
    PriceLevelKind,
    RegimeDirection,
    ThesisStance,
)
from ats.intelligence.thesis import (
    ThesisSynthesisError,
    ThesisSynthesisStatus,
    synthesize_market_thesis,
)
from pydantic import ValidationError

from tests.unit.intelligence.calibration.helpers import ensemble, regime
from tests.unit.intelligence.ensemble.helpers import context

from .helpers import configuration, distribution, facts


def synthesize(**overrides: object):
    arguments = {
        "market_context": context(),
        "regime_evidence": regime(),
        "ensemble": ensemble(),
        "distribution": distribution(),
        "facts": facts(),
        "configuration": configuration(),
    }
    arguments.update(overrides)
    return synthesize_market_thesis(**arguments)  # type: ignore[arg-type]


def test_active_thesis_has_exact_lineage_and_hash() -> None:
    result = synthesize()
    assert result.status is ThesisSynthesisStatus.ACTIVE_THESIS
    assert result.thesis is not None
    assert result.thesis.distribution_id == distribution().distribution_id
    assert result.thesis.payload_hash == compute_payload_hash(result.thesis)


def test_bullish_calibration_produces_bullish_stance() -> None:
    thesis = synthesize().thesis
    assert thesis is not None
    assert thesis.stance is ThesisStance.BULLISH
    assert thesis.thesis_strength == pytest.approx(1.0 / 3.0)


def test_regime_contradiction_is_explicitly_mixed() -> None:
    evidence = regime().model_copy(update={"direction": RegimeDirection.DOWN})
    evidence = evidence.model_copy(update={"payload_hash": compute_payload_hash(evidence)})
    thesis = synthesize(regime_evidence=evidence).thesis
    assert thesis is not None
    assert thesis.stance is ThesisStance.MIXED


def test_conditions_are_required_for_active_thesis() -> None:
    incomplete = facts().model_copy(update={"invalidation_conditions": ()})
    result = synthesize(facts=incomplete)
    assert result.status is ThesisSynthesisStatus.INSUFFICIENT_EVIDENCE
    assert result.thesis is None


def test_unknown_regime_produces_no_thesis() -> None:
    evidence = regime().model_copy(update={"direction": RegimeDirection.UNKNOWN})
    evidence = evidence.model_copy(update={"payload_hash": compute_payload_hash(evidence)})
    assert synthesize(regime_evidence=evidence).thesis is None


def test_unknown_quality_produces_no_thesis() -> None:
    current = context().model_copy(update={"data_quality_state": DataQualityState.UNKNOWN})
    current = current.model_copy(update={"payload_hash": compute_payload_hash(current)})
    assert synthesize(market_context=current).thesis is None


def test_wrong_price_level_kind_is_rejected() -> None:
    invalid = facts().model_copy(
        update={
            "support_levels": (
                PriceLevel(
                    kind=PriceLevelKind.RESISTANCE,
                    price=Decimal("24500"),
                    source_ref=context().market_context_id,
                ),
            )
        }
    )
    with pytest.raises(ThesisSynthesisError, match="non-support"):
        synthesize(facts=invalid)


def test_unbound_price_level_source_is_rejected() -> None:
    changed = (
        facts()
        .support_levels[0]
        .model_copy(update={"source_ref": UUID("50000000-0000-0000-0000-000000000001")})
    )
    invalid = facts().model_copy(update={"support_levels": (changed,)})
    with pytest.raises(ThesisSynthesisError, match="outside supplied evidence"):
        synthesize(facts=invalid)


def test_tampered_distribution_is_rejected() -> None:
    changed = distribution().model_copy(update={"support_count": 999})
    with pytest.raises(ThesisSynthesisError, match="payload hash"):
        synthesize(distribution=changed)


def test_distribution_ensemble_mismatch_is_rejected() -> None:
    changed = distribution().model_copy(
        update={"ensemble_forecast_id": regime().regime_evidence_id}
    )
    changed = changed.model_copy(update={"payload_hash": compute_payload_hash(changed)})
    with pytest.raises(ThesisSynthesisError, match="forecast/distribution"):
        synthesize(distribution=changed)


def test_expiry_is_bounded_by_distribution_and_configuration() -> None:
    thesis = synthesize().thesis
    assert thesis is not None
    assert thesis.expires_at == context().as_of_time + timedelta(minutes=2)


def test_activation_threshold_must_exceed_one_half() -> None:
    payload = configuration().model_dump()
    payload["activation_probability"] = Decimal("0.5")
    with pytest.raises(ValidationError):
        configuration().__class__.model_validate(payload)


def test_thesis_exposes_no_candidate_or_order_authority() -> None:
    thesis = synthesize().thesis
    assert thesis is not None
    fields = set(type(thesis).model_fields)
    assert "candidate_id" not in fields
    assert "order_intent" not in fields
    assert not hasattr(thesis, "authorize")
