from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from ats.agents.managed import CAPABILITY_ALLOWLIST, DATA_SCOPE_ALLOWLIST
from ats.agents.research_templates import research_templates
from ats.strategies.lineages import DEFINITIONS, bootstrap_store
from ats.strategies.operating_system import StrategyStore
from ats.strategies.research_jobs import ResearchJob, ResearchQueue
from ats.strategies.signal_analysis import SignalAnalysis
from pydantic import ValidationError


def test_bootstrap_and_restart_keep_exact_ids(tmp_path):
    store = bootstrap_store(tmp_path / "strategies.db")
    assert len(store.list()) == 20
    assert [r.definition_id for r in store.list()] == list(DEFINITIONS)
    assert store.get("XAU-017").definition_id == "S5_ORB_XAUUSD"
    assert store.get("XAU-018").definition_id == "gold_triple_s1_intraday_retest"
    assert store.get("XAU-019").definition_id == "gold_triple_s2_intraday_retest"
    assert store.get("XAU-020").definition_id == "gold_triple_s3_h4_close_retest"
    assert bootstrap_store(store.path).list() == store.list()
    for invalid in ("XAU", "XAU-01", "S5_ORB_XAUUSD", "XAU-001_extra"):
        with pytest.raises(KeyError):
            store.get(invalid)
    assert all(r.status == "RESEARCH" and not r.datasets_tested for r in store.list())


def test_concurrent_registration_and_retirement_never_reuse_ids(tmp_path):
    store = StrategyStore(tmp_path / "s.db")
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: store.register("same", "Same").strategy_id, range(8)))
    assert ids == ["XAU-001"] * 8
    previous = store.get("XAU-001")
    retired = previous.model_copy(update={"version": 2, "status": "RETIRED"})
    store.revise(retired, expected_version=1, reason="Operator retirement")
    assert store.register("new", "New").strategy_id == "XAU-002"
    assert store.register("same", "Same").status == "RETIRED"
    with pytest.raises(ValueError, match="IMMUTABLE"):
        store.revise(retired.model_copy(update={"version": 3}), expected_version=2, reason="x")


def test_versions_conflicts_and_unverified_evidence_fail_closed(tmp_path):
    store = StrategyStore(tmp_path / "s.db")
    old = store.register("trend", "Trend")
    new = old.model_copy(update={"version": 2, "hypothesis": "Test trend persistence"})
    store.revise(new, expected_version=1, reason="Research revision")
    assert store.get(old.strategy_id, 1) == old
    with pytest.raises(ValueError, match="VERSION_CONFLICT"):
        store.revise(new, expected_version=1, reason="Stale")
    with pytest.raises(ValueError, match="INDEPENDENT_VALIDATION"):
        store.revise(
            new.model_copy(update={"version": 3, "status": "ACTIVE"}),
            expected_version=2,
            reason="Promote",
        )
    with pytest.raises(ValueError, match="EVIDENCE_VERIFIER"):
        store.revise(
            new.model_copy(update={"version": 3, "backtest_results": ("fake",)}),
            expected_version=2,
            reason="Fake",
        )


def test_corrupt_versions_rejected(tmp_path):
    store = StrategyStore(tmp_path / "s.db")
    store.register("a", "A")
    with store._connect() as db:
        db.execute("UPDATE versions SET hash='bad'")
    with pytest.raises(ValueError, match="CORRUPT"):
        store.get("XAU-001")


def request():
    return ResearchJob(
        agent_id="agent-1",
        agent_config_version=1,
        strategy_id="XAU-001",
        strategy_version=1,
        dataset_id="xauusd-" + "a" * 64,
        dataset_hash="b" * 64,
        method_version="synthetic-test-v1",
        cost_model_version="explicit-test-cost-v1",
        budget_rows=100,
        timeout_seconds=10,
    )


def test_queue_idempotency_single_claim_and_immutable_results(tmp_path):
    store = bootstrap_store(tmp_path / "s.db")
    queue = ResearchQueue(tmp_path / "q.db", store)
    run = queue.submit(request(), "key")
    assert queue.submit(request(), "key") == run
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        queue.submit(request().model_copy(update={"budget_rows": 10}), "key")
    claim = queue.claim()
    assert claim is not None and claim[0] == run
    assert queue.claim() is None
    with pytest.raises(ValueError, match="CLAIM_CONFLICT"):
        queue.finish(run, "wrong", result={"trades": []})
    queue.finish(run, claim[1], result={"trades": [], "provenance": "SYNTHETIC_TEST"})
    assert queue.list()[0]["status"] == "SUCCEEDED"
    assert queue.list()[0]["result_hash"]
    with pytest.raises(ValueError, match="CLAIM_CONFLICT"):
        queue.finish(run, claim[1], result={"trades": ["replacement"]})
    with queue._connect() as db:
        db.execute("UPDATE jobs SET result='{}'")
    with pytest.raises(ValueError, match="CORRUPT"):
        queue.list()


def test_queue_interruption_and_budget_validation(tmp_path):
    queue = ResearchQueue(tmp_path / "q.db", bootstrap_store(tmp_path / "s.db"))
    queue.submit(request(), "key")
    claim = queue.claim()
    assert claim is not None
    assert queue.recover_interrupted() == 1
    assert queue.list()[0]["error"] == "INTERRUPTED"
    with pytest.raises(ValueError, match="CLAIM_CONFLICT"):
        queue.finish(claim[0], claim[1], result={})
    with pytest.raises(ValidationError):
        ResearchJob(**{**request().model_dump(), "budget_rows": 0})


def test_signal_probability_and_geometry_honesty():
    fields = {"strategy_id": "XAU-001", "strategy_version": 1, "timestamp": datetime.now(UTC)}
    signal = SignalAnalysis(**fields, model_confidence=0.9)
    assert signal.empirical_success_probability is None
    with pytest.raises(ValidationError):
        SignalAnalysis(**fields, empirical_success_probability=0.9)
    with pytest.raises(ValidationError):
        SignalAnalysis(
            **fields,
            entry_status="PROPOSED",
            direction="LONG",
            entry_zone=(Decimal(100), Decimal(101)),
            stop_loss=Decimal(102),
            data_freshness="LIVE",
        )
    with pytest.raises(ValidationError):
        SignalAnalysis(**fields, model_confidence=float("nan"))
    with pytest.raises(ValidationError):
        SignalAnalysis(**{**fields, "timestamp": datetime(2026, 1, 1)})


def test_templates_have_only_research_capabilities():
    templates = research_templates()
    assert len(templates) == 10
    for item in templates:
        assert set(item["capabilities"]) <= CAPABILITY_ALLOWLIST
        assert set(item["data_scopes"]) <= DATA_SCOPE_ALLOWLIST
        assert item["financial_authority"] == "NONE"


def test_export_is_projection_not_new_authority(tmp_path):
    store = bootstrap_store(tmp_path / "s.db")
    store.export_workspace(tmp_path / "workspace")
    assert (tmp_path / "workspace/STRATEGY_INDEX.yaml").exists()
    assert (tmp_path / "workspace/XAU-017/VALIDATION.md").read_text().endswith("authority.\n")
    assert all(not record.backtest_results for record in store.list())


def test_database_handles_close_after_read_and_write(tmp_path):
    store = StrategyStore(tmp_path / "s.db")
    store.register("a", "A")
    store.list()
    store.path.unlink()  # Windows rejects this if any connection remains open.


def test_api_exact_ids_and_templates_use_isolated_root(tmp_path):
    from ats.console.app import create_console_app
    from fastapi.testclient import TestClient

    client = TestClient(create_console_app())
    response = client.get("/v1/strategy-os")
    assert response.status_code == 200
    assert response.json()["research_worker"] == "BOUNDED_MANUAL_QUOTE_REPLAY"
    assert response.json()["strategies"][0]["strategy_id"] == "XAU-001"
    assert client.get("/v1/strategy-os/XAU-001?version=1").status_code == 200
    assert client.get("/v1/strategy-os/XAU-01").status_code == 404
    assert len(client.get("/v1/strategy-os/templates").json()) == 10
    assert client.get("/v1/strategy-os/jobs").json()["jobs"] == []
    compatibility = client.get("/v1/strategies/registry").json()
    assert compatibility["strategies"][0]["strategy_id"] == "XAU-001"
    assert (tmp_path / "data/system/strategies/registry.sqlite3").exists()
