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


def _adapter_references(tree: ast.AST, path: Path) -> list[str]:
    """Every way a module could reach the live order adapter."""
    package = path.relative_to(SOURCE).parent.parts
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.endswith("metatrader_adapter")]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                base = package[: len(package) - node.level + 1]
                module = ".".join(("ats", *base, *([module] if module else [])))
            names = {a.name for a in node.names}
            if module.endswith("metatrader_adapter") or (
                module == "ats.execution" and names & {"metatrader_adapter", "MT5ExecutionAdapter"}
            ):
                found.append(module)
        elif isinstance(node, ast.Name) and node.id == "MT5ExecutionAdapter":
            found.append(node.id)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "metatrader_adapter" in node.value
        ):
            found.append(f"string {node.value!r}")
    return found


def test_live_order_adapter_is_reachable_from_no_production_module():
    # The adapter holds a real sdk.order_send. Step 3 is not implemented, so no
    # production path may reach it: wiring it in must be a deliberate change to
    # this test, reviewed as the act of enabling external execution.
    adapter = SOURCE / "execution/metatrader_adapter.py"
    offenders = {}
    for path in SOURCE.rglob("*.py"):
        if path == adapter:
            continue
        refs = _adapter_references(ast.parse(path.read_text(encoding="utf-8")), path)
        if refs:
            offenders[str(path.relative_to(ROOT))] = refs
    assert not offenders, offenders


def test_adapter_reference_detector_catches_every_import_form():
    # Guard the guard: a detector that matches nothing passes vacuously.
    exec_pkg = SOURCE / "execution" / "external.py"
    other = SOURCE / "trading_runtime" / "broker.py"
    cases = {
        "import ats.execution.metatrader_adapter": other,
        "from ats.execution.metatrader_adapter import MT5ExecutionAdapter": other,
        "from ats.execution import metatrader_adapter": other,
        "from ats.execution import MT5ExecutionAdapter": other,
        "from .metatrader_adapter import MT5ExecutionAdapter": exec_pkg,
        "from . import metatrader_adapter": exec_pkg,
        "from ..execution.metatrader_adapter import MT5ExecutionAdapter": other,
        "importlib.import_module('ats.execution.metatrader_adapter')": other,
    }
    for code, path in cases.items():
        assert _adapter_references(ast.parse(code), path), code
    assert not _adapter_references(ast.parse("from ats.execution import paper"), other)


def test_research_worker_has_no_execution_or_credentials_dependencies():
    source = (SOURCE / "strategies/research_worker.py").read_text(encoding="utf-8")
    for forbidden in ("ats.execution", "ats.market.metatrader", "CredentialVault", "AutonomyToken"):
        assert forbidden not in source
