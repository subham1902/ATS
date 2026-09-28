import json
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

from ats.contracts.common import UTCDateTime
from ats.observability.jev_telemetry import (
    _invoke_jev_sync,
    invoke_jev_shadow_async,
    record_shadow_assessment,
)


def test_jev_success():
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({
        "status": "success",
        "mode": "shadow",
        "model": "typesafe-ai/jev",
        "latencyMs": 42,
        "assessment": {
            "marketRegime": "TRENDING",
            "signalQuality": "STRONG",
            "riskState": "LOW",
            "engineAgreement": "AGREEMENT",
            "anomalySuspected": False,
            "requiresReview": False
        }
    }).encode("utf-8")
    
    with patch("urllib.request.urlopen") as mock_urlopen, \
         patch("ats.observability.jev_telemetry.record_shadow_assessment") as mock_record:
        
        mock_urlopen.return_value.__enter__.return_value = mock_response
        _invoke_jev_sync({"test": "data"})
        
        mock_record.assert_called_once()
        result = mock_record.call_args[0][0]
        assert result["status"] == "success"
        assert result["assessment"]["marketRegime"] == "TRENDING"

def test_jev_disabled():
    with patch("ats.observability.jev_telemetry.logger.info") as mock_logger:
        record_shadow_assessment({"status": "disabled"})
        mock_logger.assert_not_called()

def test_jev_api_failure():
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("Connection refused"),
    ) as _mock_urlopen, patch(
        "ats.observability.jev_telemetry.logger.warning"
    ) as mock_logger:

        # Should not raise exception
        _invoke_jev_sync({"test": "data"})

        mock_logger.assert_called_with(
            "Jev API unreachable or timed out: <urlopen error Connection refused>"
        )

def test_jev_timeout():
    with patch("urllib.request.urlopen", side_effect=Exception("Timeout")) as _mock_urlopen, \
         patch("ats.observability.jev_telemetry.logger.warning") as mock_logger:
        
        # Should not raise exception
        _invoke_jev_sync({"test": "data"})
        
        mock_logger.assert_called_with("Jev API invocation failed: Timeout")

def test_jev_invalid_response():
    mock_response = MagicMock()
    mock_response.status = 500
    mock_response.read.return_value = b"Internal Server Error"
    
    with patch("urllib.request.urlopen") as mock_urlopen, \
         patch("ats.observability.jev_telemetry.record_shadow_assessment") as mock_record, \
         patch("ats.observability.jev_telemetry.logger.warning") as _mock_logger:
        
        mock_urlopen.return_value.__enter__.return_value = mock_response
        _invoke_jev_sync({"test": "data"})
        
        mock_record.assert_not_called()

def test_invoke_jev_shadow_async_does_not_block():
    with patch("threading.Thread.start") as mock_start:
        invoke_jev_shadow_async({"candidate_id": "123"}, UTCDateTime(2026, 9, 19, 10, 0, 0))
        mock_start.assert_called_once()

def test_invoke_jev_shadow_async_fails_safe():
    with patch(
        "threading.Thread.start", side_effect=Exception("Thread limit reached")
    ) as _mock_start, patch(
        "ats.observability.jev_telemetry.logger.error"
    ) as mock_logger:
        
        invoke_jev_shadow_async({"candidate_id": "123"}, UTCDateTime(2026, 9, 19, 10, 0, 0))
        mock_logger.assert_called_with("Failed to spawn Jev shadow thread: Thread limit reached")
