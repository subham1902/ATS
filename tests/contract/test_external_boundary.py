import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend/src/ats"


def test_sdk_order_calls_are_only_in_approved_adapter():
    allowed = SOURCE / "execution/metatrader_adapter.py"
    for path in SOURCE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"order_send", "order_check"}:
                assert path == allowed, path


def test_paper_contract_not_widened_and_console_not_routed():
    source = (SOURCE / "execution/external.py").read_text(encoding="utf-8")
    assert "AutonomyToken" not in source
    assert "A3_EXTERNAL_DEMO" in source and "A4_EXTERNAL_LIVE" in source
    app = (SOURCE / "console/app.py").read_text(encoding="utf-8")
    assert "MT5ExecutionAdapter" not in app


def test_research_worker_has_no_execution_or_credentials_dependencies():
    source = (SOURCE / "strategies/research_worker.py").read_text(encoding="utf-8")
    for forbidden in ("ats.execution", "ats.market.metatrader", "CredentialVault", "AutonomyToken"):
        assert forbidden not in source
