"""Clean-room features never inherit old calibrated strategy authority."""

from ats.trading_runtime.intelligence_pipeline import MarketIntelligencePipeline

from tests.unit.market.features.helpers import snapshot


def test_unvalidated_xauusd_pipeline_is_research_only():
    rows = tuple(snapshot(n, instrument="XAUUSD") for n in (1, 2, 3))
    result = MarketIntelligencePipeline().evaluate(snapshots=rows, cutoff_sequence=3)
    assert not result.is_actionable
    assert result.expected_edge_r is None
    assert result.candidate is result.thesis is result.distribution is None
    assert "XAUUSD_EVIDENCE_REQUIRED" in result.reason_codes


def test_missing_features_fail_closed():
    result = MarketIntelligencePipeline().evaluate(snapshots=(), cutoff_sequence=1)
    assert not result.is_actionable
    assert result.reason_codes == ("FEATURE_EVIDENCE_UNAVAILABLE",)
