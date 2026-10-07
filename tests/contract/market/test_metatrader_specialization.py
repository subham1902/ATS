"""Specialization and account foundation cannot erode the trusted boundaries."""

import ast
from pathlib import Path

from ats.agents.managed import DATA_SCOPE_ALLOWLIST

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "backend/src/ats"


def test_no_deleted_provider_production_references():
    for path in SOURCE.rglob("*.py"):
        assert "upstox" not in path.read_text(encoding="utf-8").lower(), path
    assert not (SOURCE / "market/providers/upstox").exists()


def test_only_metatrader_external_adapters_and_no_order_surface():
    assert {p.stem for p in (SOURCE / "market/providers").glob("*.py")} <= {"__init__", "base"}
    assert (SOURCE / "market/metatrader/mt5.py").is_file()
    assert (SOURCE / "market/metatrader/mt4.py").is_file()
    for path in (SOURCE / "market").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"order_send", "order_check", "position_close"}, path


def test_agents_cannot_import_account_sessions_credentials_or_brokers():
    forbidden = (
        "ats.execution",
        "ats.trading_runtime.broker",
        "ats.market.metatrader",
        "MetaTrader5",
    )
    for path in (SOURCE / "agents").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(forbidden), path
            elif isinstance(node, ast.Import):
                assert not any(alias.name.startswith(forbidden) for alias in node.names), path


def test_managed_scopes_remain_inside_xauusd_and_system_health():
    assert all(
        scope.startswith("XAUUSD_") or scope == "SYSTEM_HEALTH" for scope in DATA_SCOPE_ALLOWLIST
    )


def test_account_administration_never_mints_execution_authority():
    source = (SOURCE / "console/accounts_router.py").read_text(encoding="utf-8")
    for forbidden in (
        "AutonomyToken(",
        "AuthorizedExecutionIntent(",
        "OrderIntent(",
        "order_send",
        "submit_order",
        "consume_token",
    ):
        assert forbidden not in source
