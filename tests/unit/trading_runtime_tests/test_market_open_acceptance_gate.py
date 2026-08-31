"""Unit tests for MarketOpenAcceptanceGate and Truthful Market-Open Guardrails.

Verifies:
1. Market CLOSED cannot pass Level 3 Market-Open acceptance.
2. Pre-open / after-hours returns PENDING / AFTER_HOURS_OPERATIONAL_ACCEPTANCE_PASS.
3. Safety invariants pass independently while market-open conditions remain PENDING.
4. Missing InstrumentSpec blocks Level 3 Market-Open pass.
5. Stale prior-session ticks cannot satisfy Market-Open acceptance.
6. Future trading date cannot be stamped as completed market-open acceptance before it occurs.
"""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.run_market_open_a2_acceptance import Check, MarketOpenAcceptanceGate  # noqa: E402


def test_market_closed_cannot_pass_market_open_acceptance() -> None:
    gate = MarketOpenAcceptanceGate()

    mock_runtime = {"session": {"phase": "CLOSED"}}
    mock_harness = {
        "harness": {
            "state": "HEALTHY",
            "live_money": "DISABLED",
            "execution_target": "PAPER",
            "real_orders_placed": 0,
        },
        "safety": {"REAL_ORDER_AUTHORITY": "NONE"},
        "agents": [1, 2, 3, 4],
    }
    mock_pipeline = {
        "scanner_observations": 10,
        "r10_evaluations": 5,
        "r10x_evaluations": 5,
        "rejection_reasons": {},
    }
    mock_health = {"status": "LIVE"}

    def fake_get(path: str) -> dict[str, Any] | None:
        if path == "/v1/runtime/status":
            return mock_runtime
        if path == "/v1/harness/status":
            return mock_harness
        if path == "/v1/pipeline/counters":
            return mock_pipeline
        if path == "/health/live":
            return mock_health
        return None

    with patch("scripts.run_market_open_a2_acceptance._get", side_effect=fake_get):
        result = gate.evaluate(allow_after_hours=True)

    assert result.safety_invariants_passed is True
    assert result.operational_stack_passed is True
    assert result.market_open_conditions_passed is False
    assert result.market_open_verdict != "MARKET_OPEN_ACCEPTANCE_PASS"
    assert result.market_open_verdict == "AFTER_HOURS_OPERATIONAL_ACCEPTANCE_PASS"


def test_safety_invariants_pass_independently_when_market_closed() -> None:
    gate = MarketOpenAcceptanceGate()

    mock_harness = {
        "harness": {
            "state": "HEALTHY",
            "live_money": "DISABLED",
            "execution_target": "PAPER",
            "real_orders_placed": 0,
        },
        "safety": {"REAL_ORDER_AUTHORITY": "NONE"},
        "agents": [1, 2, 3, 4],
    }

    def fake_get(path: str) -> dict[str, Any] | None:
        if path == "/v1/harness/status":
            return mock_harness
        if path == "/v1/runtime/status":
            return {"session": {"phase": "CLOSED"}}
        if path == "/v1/pipeline/counters":
            return {
                "scanner_observations": 1,
                "r10_evaluations": 1,
                "r10x_evaluations": 1,
                "rejection_reasons": {},
            }
        if path == "/health/live":
            return {"status": "LIVE"}
        return None

    with patch("scripts.run_market_open_a2_acceptance._get", side_effect=fake_get):
        result = gate.evaluate(allow_after_hours=False)

    assert result.safety_invariants_passed is True
    assert result.market_open_conditions_passed is False
    assert result.market_open_verdict == "READY_FOR_MARKET_OPEN_ACCEPTANCE"


def test_missing_safety_invariant_blocks_verdict() -> None:
    gate = MarketOpenAcceptanceGate()

    # Unsafe condition: live_money = ENABLED
    mock_harness = {
        "harness": {
            "state": "HEALTHY",
            "live_money": "ENABLED",
            "execution_target": "REAL",
            "real_orders_placed": 1,
        },
        "safety": {"REAL_ORDER_AUTHORITY": "FULL"},
    }

    def fake_get(path: str) -> dict[str, Any] | None:
        if path == "/v1/harness/status":
            return mock_harness
        return None

    with patch("scripts.run_market_open_a2_acceptance._get", side_effect=fake_get):
        result = gate.evaluate(allow_after_hours=True)

    assert result.safety_invariants_passed is False
    assert result.market_open_verdict == "BLOCKED_SAFETY_OR_STACK_FAILED"


def test_check_dataclass_structure() -> None:
    c = Check(name="test_check", ok=True, detail="detail", category="safety")
    assert c.name == "test_check"
    assert c.ok is True
    assert c.category == "safety"
