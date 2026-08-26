from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState
from ats.intelligence.calibration import (
    CalibrationEvaluationStatus,
    CalibrationInputError,
    calibrate_outcome_distribution,
)
from pydantic import ValidationError

from tests.unit.intelligence.ensemble.helpers import context

from .helpers import calibration_config, ensemble, observation, observations, regime


def calibrate(**overrides: object):
    arguments = {
        "ensemble": ensemble(),
        "market_context": context(),
        "target_outcome_code": "ABOVE",
        "observations": observations(),
        "configuration": calibration_config(),
        "regime_evidence": None,
    }
    arguments.update(overrides)
    return calibrate_outcome_distribution(**arguments)  # type: ignore[arg-type]


def test_empirical_probability_and_complement_are_exact() -> None:
    result = calibrate()
    assert result.status is CalibrationEvaluationStatus.CALIBRATED_DISTRIBUTION
    assert result.distribution is not None
    assert result.distribution.outcomes[0].probability == Decimal(2) / Decimal(3)
    assert sum(item.probability for item in result.distribution.outcomes) == Decimal(1)
    assert result.distribution.payload_hash == compute_payload_hash(result.distribution)


def test_probability_interval_contains_each_probability() -> None:
    distribution = calibrate().distribution
    assert distribution is not None
    assert all(
        outcome.interval.low <= outcome.probability <= outcome.interval.high
        for outcome in distribution.outcomes
    )


def test_insufficient_support_produces_no_probability_contract() -> None:
    result = calibrate(configuration=calibration_config(minimum_support=4))
    assert result.status is CalibrationEvaluationStatus.INSUFFICIENT_EVIDENCE
    assert result.distribution is None
    assert result.support_count == 3


def test_future_observation_is_rejected() -> None:
    future = observation(9, True, minutes_before=-1)
    with pytest.raises(CalibrationInputError, match="future"):
        calibrate(observations=observations() + (future,))


def test_duplicate_observation_is_rejected() -> None:
    items = observations()
    with pytest.raises(CalibrationInputError, match="duplicate"):
        calibrate(observations=items + (items[0],))


def test_target_must_exist() -> None:
    with pytest.raises(CalibrationInputError, match="target outcome"):
        calibrate(target_outcome_code="MISSING")


def test_invalid_context_quality_fails_closed() -> None:
    current = context()
    invalid = current.model_copy(update={"data_quality_state": DataQualityState.UNKNOWN})
    invalid = invalid.model_copy(update={"payload_hash": compute_payload_hash(invalid)})
    with pytest.raises(CalibrationInputError, match="quality"):
        calibrate(market_context=invalid)


def test_tampered_ensemble_is_rejected() -> None:
    changed = ensemble().model_copy(update={"horizon_bars": 3})
    with pytest.raises(CalibrationInputError, match="payload hash"):
        calibrate(ensemble=changed)


def test_regime_conditioning_requires_exact_lineage() -> None:
    current_regime = regime()
    result = calibrate(
        configuration=calibration_config(regime_conditioned=True),
        regime_evidence=current_regime,
        observations=observations(regime_id=current_regime.regime_evidence_id),
    )
    assert result.distribution is not None
    assert result.distribution.regime_evidence_id == current_regime.regime_evidence_id


def test_regime_conditioning_without_evidence_is_rejected() -> None:
    with pytest.raises(CalibrationInputError, match="requires regime"):
        calibrate(configuration=calibration_config(regime_conditioned=True))


def test_unconditioned_calibration_rejects_regime_argument() -> None:
    with pytest.raises(CalibrationInputError, match="must not receive"):
        calibrate(regime_evidence=regime())


def test_invalid_configuration_is_contract_invalid() -> None:
    with pytest.raises(ValidationError):
        calibration_config().model_copy(update={"tail_loss_return_threshold": 0.0}).model_validate(
            calibration_config().model_dump() | {"tail_loss_return_threshold": 0.0}
        )


def test_valid_until_is_explicit_configuration_offset() -> None:
    distribution = calibrate().distribution
    assert distribution is not None
    assert distribution.valid_until == distribution.as_of_time + timedelta(minutes=5)


def test_metrics_are_finite_and_cost_free_of_authority() -> None:
    distribution = calibrate().distribution
    assert distribution is not None
    assert 0.0 <= distribution.brier_score <= 1.0
    assert 0.0 <= distribution.expected_calibration_error <= 1.0
    assert not hasattr(distribution, "authorize")
    assert not hasattr(distribution, "place_order")
