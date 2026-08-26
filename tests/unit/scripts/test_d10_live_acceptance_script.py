import subprocess
import sys
from pathlib import Path

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
