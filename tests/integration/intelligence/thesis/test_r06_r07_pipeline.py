from __future__ import annotations

from ats.intelligence.thesis import ThesisSynthesisStatus, synthesize_market_thesis

from tests.unit.intelligence.calibration.helpers import ensemble, regime
from tests.unit.intelligence.ensemble.helpers import context
from tests.unit.intelligence.thesis.helpers import configuration, distribution, facts


def test_calibrated_distribution_to_market_thesis() -> None:
    calibrated = distribution()
    result = synthesize_market_thesis(
        market_context=context(),
        regime_evidence=regime(),
        ensemble=ensemble(),
        distribution=calibrated,
        facts=facts(),
        configuration=configuration(),
    )
    assert result.status is ThesisSynthesisStatus.ACTIVE_THESIS
    assert result.thesis is not None
    assert result.thesis.distribution_id == calibrated.distribution_id
    assert result.thesis.analogue_evidence_id is None
