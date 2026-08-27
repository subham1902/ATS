import subprocess
import sys
from pathlib import Path

from ats.market.derivatives.providers.models import SourceFreshness

from scripts.run_d10_live_acceptance import (
    _classify_session_evidence,
    _failure_evidence,
    _percentiles,
)

SCRIPT = Path("scripts/run_d10_live_acceptance.py")


def test_dry_run_is_machine_readable_and_order_free() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert '"status": "DRY_RUN_PASS"' in result.stdout
    assert '"real_orders_placed": 0' in result.stdout


def test_live_runner_has_no_order_or_account_api_surface() -> None:
    source = SCRIPT.read_text(encoding="utf-8").lower()
    for forbidden in (
        "place_order",
        "modify_order",
        "cancel_order",
        "/user/profile",
        "/portfolio",
        "/orders",
        "/trades",
    ):
        assert forbidden not in source


def test_closed_or_inactive_session_is_deferred_without_fake_freshness() -> None:
    result = _classify_session_evidence(
        {"NSE_INDEX|Nifty 50": SourceFreshness.STALE},
        {"NSE_EQ": "CLOSED"},
    )
    assert result is not None
    evidence, code = result
    assert code == 3
    assert evidence["status"] == "ACTIVE_MARKET_SESSION_REQUIRED_FOR_D10_ACCEPTANCE"
    assert evidence["freshness"] == {"NSE_INDEX|Nifty 50": "STALE"}
    assert evidence["real_orders_placed"] == 0


def test_malformed_provider_failure_is_not_relabelled_as_session_deferral() -> None:
    evidence, code = _failure_evidence(ValueError("MALFORMED_PROVIDER_RESPONSE"))
    assert code == 2
    assert evidence == {
        "status": "D10_LIVE_ACCEPTANCE_FAILED",
        "error_type": "ValueError",
        "real_orders_placed": 0,
    }


def test_active_valid_session_fixture_proceeds_to_fresh_acceptance_checks() -> None:
    result = _classify_session_evidence(
        {
            "NSE_INDEX|Nifty 50": SourceFreshness.FRESH,
            "NSE_INDEX|Nifty Bank": SourceFreshness.FRESH,
        },
        {"NSE_EQ": "NORMAL_OPEN", "NSE_FO": "NORMAL_OPEN"},
    )
    assert result is None


def test_latency_percentiles_use_nearest_rank_for_small_samples() -> None:
    result = _percentiles([644.0, 1644.0])
    assert result == {
        "count": 2,
        "p50": 1144.0,
        "p95": 1644.0,
        "p99": 1644.0,
        "max": 1644.0,
    }
