from __future__ import annotations

from ats.contracts.domain.hashing import compute_payload_hash
from ats.intelligence.calibration import calibrate_outcome_distribution

from tests.unit.intelligence.calibration.helpers import (
    calibration_config,
    ensemble,
    observations,
)
from tests.unit.intelligence.ensemble.helpers import context


def test_raw_ensemble_to_authoritative_calibrated_distribution() -> None:
    raw = ensemble()
    result = calibrate_outcome_distribution(
        ensemble=raw,
        market_context=context(),
        target_outcome_code="ABOVE",
        observations=observations(),
        configuration=calibration_config(),
        regime_evidence=None,
    )
    assert result.distribution is not None
    assert result.distribution.ensemble_forecast_id == raw.ensemble_forecast_id
    assert result.distribution.event_definition_id == raw.event_definition_id
    assert result.distribution.payload_hash == compute_payload_hash(result.distribution)
    assert raw.raw_outcomes[0].probability != result.distribution.outcomes[0].probability
