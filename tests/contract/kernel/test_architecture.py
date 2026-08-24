from __future__ import annotations

import inspect
from pathlib import Path

from ats.contracts.governance import GOVERNANCE_CONTRACTS
from ats.contracts.intelligence import INTELLIGENCE_CONTRACTS
from ats.kernel import autonomy, governance, order_guard, policy
from ats.kernel.types import SystemConstraintSet


def test_iba_registry_remains_exactly_twenty_contracts() -> None:
    assert len(INTELLIGENCE_CONTRACTS + GOVERNANCE_CONTRACTS) == 20
    assert SystemConstraintSet not in INTELLIGENCE_CONTRACTS + GOVERNANCE_CONTRACTS


def test_time_sensitive_functions_require_explicit_time() -> None:
    functions = (
        policy.validate_strategy_policy,
        governance.validate_campaign_gate,
        governance.validate_intelligence_freshness,
        autonomy.validate_token_eligibility,
        autonomy.validate_token_for_use,
        order_guard.validate_order_intent,
        order_guard.validate_exit_intent,
    )
    for function in functions:
        assert "evaluation_time" in inspect.signature(function).parameters


def test_kernel_source_has_no_external_runtime_or_ambient_authority() -> None:
    root = Path(__file__).parents[3] / "backend" / "src" / "ats" / "kernel"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    forbidden = (
        "requests",
        "httpx",
        "socket",
        "sqlalchemy",
        "psycopg",
        "fastapi",
        "redis",
        "nats",
        "kafka",
        "torch",
        "transformers",
        "playwright",
        "selenium",
        "subprocess",
        "eval(",
        "exec(",
        "compile(",
        "datetime.now(",
        "datetime.utcnow(",
        "time.time(",
        "random.random",
        "place_order",
        "submit_order",
        "send_order",
    )
    assert all(item not in source for item in forbidden)


def test_no_atomic_token_consume_or_submission_api_exists() -> None:
    assert not hasattr(autonomy, "consume_token")
    assert not hasattr(order_guard, "submit_order")
