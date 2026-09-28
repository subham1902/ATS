import json
import logging
import threading
import urllib.error
import urllib.request
from typing import Any

from ats.contracts.common import UTCDateTime

logger = logging.getLogger("ats.jev_telemetry")

# In a real environment, this might be configured via environment variables
JEV_API_URL = "http://localhost:3000/api/jev"

def record_shadow_assessment(result: dict[str, Any]) -> None:
    """Safely log the Jev assessment without secrets."""
    try:
        # Extract fields to log
        status = result.get("status")
        if status == "disabled":
            return
            
        model = result.get("model", "unknown")
        latency = result.get("latencyMs", -1)
        assessment = result.get("assessment", {})
        
        logger.info(
            "Jev Shadow Assessment",
            extra={
                "jev_status": status,
                "jev_model": model,
                "jev_latency_ms": latency,
                "jev_marketRegime": assessment.get("marketRegime"),
                "jev_signalQuality": assessment.get("signalQuality"),
                "jev_riskState": assessment.get("riskState"),
                "jev_engineAgreement": assessment.get("engineAgreement"),
                "jev_anomalySuspected": assessment.get("anomalySuspected"),
                "jev_requiresReview": assessment.get("requiresReview")
            }
        )
    except Exception as e:
        logger.error(f"Failed to record Jev shadow assessment: {e}")

def _invoke_jev_sync(candidate_snapshot: dict[str, Any]) -> None:
    """Synchronous HTTP call to the Node adapter, safe to run in thread."""
    try:
        req = urllib.request.Request(
            JEV_API_URL, 
            data=json.dumps(candidate_snapshot).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5.0) as response:
            if response.status == 200:
                body = response.read().decode("utf-8")
                result = json.loads(body)
                record_shadow_assessment(result)
    except urllib.error.URLError as e:
        logger.warning(f"Jev API unreachable or timed out: {e}")
    except Exception as e:
        logger.warning(f"Jev API invocation failed: {e}")

def invoke_jev_shadow_async(candidate: dict[str, Any], at: UTCDateTime) -> None:
    """Fire-and-forget invocation of Jev shadow evaluation.
    
    This must NEVER block the ATS execution path or raise exceptions.
    """
    try:
        # Create a safe snapshot of the candidate state, removing any internal
        # engine instances or un-serializable types. In this case, we serialize
        # to a plain dict string/float representations.
        # Assuming candidate is already a dict, we just copy it.
        snapshot = {
            "timestamp": at.isoformat(),
            "candidate": candidate
        }
        
        # Fire and forget
        thread = threading.Thread(
            target=_invoke_jev_sync,
            args=(snapshot,),
            daemon=True,
            name="JevShadowThread"
        )
        thread.start()
    except Exception as e:
        logger.error(f"Failed to spawn Jev shadow thread: {e}")
