import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from ats.agents.managed import ManagedAgentStore
from ats.datasets.ingestion import XauUsdDatasetStore
from ats.strategies.lineages import bootstrap_store
from ats.strategies.quote_research import run_quote_research
from ats.strategies.research_jobs import ResearchJob, ResearchQueue
from ats.strategies.research_worker import ResearchWorker, supervisor_lock


def setup_job(tmp_path: Path):
    source = tmp_path / "quotes.csv"
    start = datetime(2026, 1, 5, 12, tzinfo=UTC)
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "bid", "ask"])
        for i in range(200):
            # Deterministic synthetic test fixture, never operator research evidence.
            bid = 2000 + i * 0.2
            writer.writerow([(start + timedelta(seconds=30 * i)).isoformat(), bid, bid + 0.3])
    datasets = XauUsdDatasetStore(tmp_path / "datasets")
    manifest = datasets.import_file(
        source, source="TEST_FIXTURE", broker_symbol="XAUUSDm", source_timezone="UTC"
    )
    store = bootstrap_store(tmp_path / "strategies.db")
    agents = ManagedAgentStore(path=tmp_path / "agents.json")
    agent = agents.create(
        name="Backtest",
        capabilities=["RUN_BACKTEST"],
        data_scopes=["XAUUSD_DATASETS", "XAUUSD_STRATEGIES"],
        timeout_s=30,
    )
    agent = agents.set_enabled(agent.agent_id, True)
    job = ResearchJob(
        agent_id=agent.agent_id,
        agent_config_version=agent.current_config_version,
        strategy_id="XAU-003",
        strategy_version=1,
        dataset_id=manifest["dataset_id"],
        dataset_hash=manifest["normalized_hash"],
        method_version="CAUSAL-QUOTE-V1",
        cost_model_version="QUOTE-COST-V1",
        parameters={
            "tick_size": 0.01,
            "quantity": 1,
            "commission": 0.2,
            "slippage": 0.01,
            "latency_ms": 0,
            "bar_seconds": 60,
        },
        budget_rows=200,
        timeout_seconds=30,
    )
    return ResearchWorker(ResearchQueue(tmp_path / "jobs.db", store), datasets, agents), job


def test_bounded_spawn_worker_end_to_end(tmp_path):
    worker, job = setup_job(tmp_path)
    run = worker.queue.submit(job, "unique")
    assert worker.run_once() == run
    row = worker.queue.list()[0]
    assert row["status"] == "SUCCEEDED"
    result = row["result"]
    assert result["dataset_hash"] == job.dataset_hash
    assert result["strategy_id"] == "XAU-003"
    assert result["authority"] == "RESEARCH_ONLY"
    assert result["latest_signal"]["empirical_probability"] is None
    assert result["holdout_status"] == "NOT_RUN"
    assert result["trade_count"] > 0
    for trade in result["trades"]:
        assert trade["entry_time"] < trade["exit_time"]
    assert worker.run_once() is None


@pytest.mark.parametrize(
    "change",
    [
        {"dataset_hash": "0" * 64},
        {"budget_rows": 1},
        {"strategy_id": "XAU-008"},
        {"method_version": "made-up"},
        {"cadence": "NIGHTLY"},
        {"timeout_seconds": 31},
        {"agent_config_version": 99},
        {"parameters": {}},
    ],
)
def test_fail_closed_admission(tmp_path, change):
    worker, job = setup_job(tmp_path)
    with pytest.raises(ValueError):
        worker.validate(job.model_copy(update=change))


def test_disabled_agent_cannot_run(tmp_path):
    worker, job = setup_job(tmp_path)
    worker.agents.set_enabled(job.agent_id, False)
    run = worker.queue.submit(job, "run")
    worker.run_once()
    assert worker.queue.list()[0]["status"] == "FAILED"
    assert worker.queue.list()[0]["run_id"] == run


def test_cancellation_and_late_result(tmp_path):
    worker, job = setup_job(tmp_path)
    run = worker.queue.submit(job, "run")
    _, nonce, _ = worker.queue.claim()
    worker.queue.cancel(run)
    assert not worker.queue.is_running(run, nonce)
    with pytest.raises(ValueError):
        worker.queue.finish(run, nonce, result={"late": True})
    assert worker.queue.list()[0]["status"] == "CANCELLED"


def test_supervisors_exclude_each_other(tmp_path):
    worker, job = setup_job(tmp_path)
    worker.queue.submit(job, "run")
    with supervisor_lock(worker.queue.path.with_suffix(".worker.lock")):
        assert worker.run_once() is None
    assert worker.queue.list()[0]["status"] == "QUEUED"


def test_changed_dataset_is_rejected(tmp_path):
    worker, job = setup_job(tmp_path)
    path = worker.datasets.root / job.dataset_id / "observations.jsonl"
    path.write_text("corrupt", encoding="utf-8")
    with pytest.raises(ValueError, match="DATASET_CONTENT_CHANGED"):
        run_quote_research(job, worker.queue.strategies.get(job.strategy_id), worker.datasets)


def test_deterministic_replay(tmp_path):
    worker, job = setup_job(tmp_path)
    record = worker.queue.strategies.get(job.strategy_id)
    assert run_quote_research(job, record, worker.datasets) == run_quote_research(
        job, record, worker.datasets
    )
