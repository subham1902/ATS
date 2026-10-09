"""One supervised spawn worker, with enforced timeout and durable cancellation.

An OS file lock excludes other supervisors, including across API processes.
The child receives only dataset/strategy/configuration: no credentials or broker.
"""

from __future__ import annotations

import importlib
import multiprocessing
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ats.agents.managed import ManagedAgentStore
from ats.datasets.ingestion import XauUsdDatasetStore
from ats.strategies.operating_system import StrategyRecord, document_hash
from ats.strategies.quote_research import run_quote_research, verify_job
from ats.strategies.research_jobs import ResearchJob, ResearchQueue


@contextmanager
def supervisor_lock(path: Path) -> Any:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            windows_locking: Any = importlib.import_module("msvcrt")
            windows_locking.locking(stream.fileno(), windows_locking.LK_NBLCK, 1)
        else:
            locking: Any = importlib.import_module("fcntl")
            locking.flock(stream.fileno(), locking.LOCK_EX | locking.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                windows_locking.locking(stream.fileno(), windows_locking.LK_UNLCK, 1)
            else:
                locking.flock(stream.fileno(), locking.LOCK_UN)


def _child(pipe: Any, request: str, strategy: str, dataset_root: str) -> None:
    try:
        result = run_quote_research(
            ResearchJob.model_validate_json(request),
            StrategyRecord.model_validate_json(strategy),
            XauUsdDatasetStore(Path(dataset_root)),
        )
        pipe.send((True, result))
    except Exception:
        pipe.send((False, None))
    finally:
        pipe.close()


class ResearchWorker:
    def __init__(
        self, queue: ResearchQueue, datasets: XauUsdDatasetStore, agents: ManagedAgentStore
    ) -> None:
        self.queue, self.datasets, self.agents = queue, datasets, agents

    def validate(self, job: ResearchJob) -> StrategyRecord:
        agent = self.agents.require_active(job.agent_id)
        if (
            not agent.enabled
            or agent.current_config_version != job.agent_config_version
            or "RUN_BACKTEST" not in agent.capabilities
            or not {"XAUUSD_DATASETS", "XAUUSD_STRATEGIES"}.issubset(agent.data_scopes)
            or job.timeout_seconds > agent.timeout_s
            or job.cadence != "MANUAL"
        ):
            raise ValueError("RESEARCH_CAPABILITY_OR_VERSION_DENIED")
        record = self.queue.strategies.get(job.strategy_id, job.strategy_version)
        verify_job(job, record, self.datasets)
        return record

    def run_once(self) -> str | None:
        try:
            with supervisor_lock(self.queue.path.with_suffix(".worker.lock")):
                self.queue.recover_interrupted()
                return self._run_claim()
        except OSError:
            return None

    def _run_claim(self) -> str | None:
        claim = self.queue.claim()
        if claim is None:
            return None
        run_id, nonce, job = claim
        try:
            record = self.validate(job)
            persisted = next(row for row in self.queue.list() if row["run_id"] == run_id)
            if persisted["strategy_hash"] != document_hash(record):
                raise ValueError("PROVENANCE_MISMATCH")
            agent_run = self.agents.record_run_start(job.agent_id)
        except Exception:
            self.queue.finish(run_id, nonce, result=None, error="PROVENANCE_MISMATCH")
            return run_id
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=False)
        process = context.Process(
            target=_child,
            args=(child, job.model_dump_json(), record.model_dump_json(), str(self.datasets.root)),
            daemon=True,
        )
        success = False
        try:
            process.start()
            child.close()
            deadline = time.monotonic() + job.timeout_seconds
            while self.queue.is_running(run_id, nonce):
                if parent.poll(0.1):
                    ok, result = parent.recv()
                    self.queue.finish(
                        run_id,
                        nonce,
                        result=result if ok else None,
                        error=None if ok else "JOB_FAILED",
                    )
                    success = bool(ok)
                    break
                if time.monotonic() >= deadline:
                    self.queue.finish(run_id, nonce, result=None, error="TIMEOUT")
                    break
                if not process.is_alive():
                    self.queue.finish(run_id, nonce, result=None, error="JOB_FAILED")
                    break
        except Exception:
            if self.queue.is_running(run_id, nonce):
                self.queue.finish(run_id, nonce, result=None, error="JOB_FAILED")
        finally:
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=2)
                process.close()
            parent.close()
            child.close()
            self.agents.record_run_finish(
                agent_run.run_id, ok=success, error=None if success else "BOUNDED_JOB_FAILED"
            )
        return run_id
