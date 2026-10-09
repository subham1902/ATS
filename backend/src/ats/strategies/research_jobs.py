"""Persistent bounded research queue. No broker, secrets or authorization dependency."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ats.strategies.operating_system import StrategyStore, document_hash


class ResearchJob(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    agent_id: str = Field(min_length=1, max_length=100)
    agent_config_version: int = Field(ge=1)
    strategy_id: str = Field(pattern=r"^XAU-[0-9]{3,}$")
    strategy_version: int = Field(ge=1)
    dataset_id: str = Field(pattern=r"^xauusd-[a-f0-9]{64}$")
    dataset_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    method_version: str = Field(min_length=1, max_length=100)
    cost_model_version: str = Field(min_length=1, max_length=100)
    parameters: dict[str, float | int | str | bool] = Field(default_factory=dict)
    budget_rows: int = Field(ge=1, le=2_000_000)
    timeout_seconds: int = Field(ge=1, le=3600)
    cadence: Literal["MANUAL", "ON_DATASET", "ON_VERSION", "NIGHTLY", "WEEKLY"] = "MANUAL"


class ResearchQueue:
    """Atomic claim; explicit recovery makes interrupted runs fail, never resume silently.

    Cadence is recorded intent, not an installed scheduler. The caller must
    verify the dataset hash and managed agent capability before submission.
    Completion requires the claim nonce, preventing late/stale workers writing
    into another run. Failed runs retain their idempotency identity.
    """

    def __init__(self, path: Path, strategies: StrategyStore) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.strategies = path, strategies
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                run_id TEXT PRIMARY KEY, idempotency TEXT UNIQUE NOT NULL,
                request TEXT NOT NULL, strategy_hash TEXT NOT NULL,
                status TEXT NOT NULL, claim TEXT, started_at TEXT, finished_at TEXT,
                result TEXT, result_hash TEXT, error TEXT
            )""")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    def submit(self, request: ResearchJob, idempotency: str) -> str:
        request = ResearchJob.model_validate(request.model_dump())
        if not 1 <= len(idempotency) <= 128:
            raise ValueError("RESEARCH_IDEMPOTENCY_REQUIRED")
        strategy = self.strategies.get(request.strategy_id, request.strategy_version)
        if strategy.status == "RETIRED":
            raise ValueError("STRATEGY_RETIRED")
        document = request.model_dump_json()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT * FROM jobs WHERE idempotency=?", (idempotency,)).fetchone()
            if prior:
                if prior["request"] != document:
                    raise ValueError("RESEARCH_IDEMPOTENCY_CONFLICT")
                return str(prior["run_id"])
            run_id = "RUN-" + uuid4().hex
            db.execute(
                "INSERT INTO jobs(run_id,idempotency,request,strategy_hash,status) "
                "VALUES(?,?,?,?,?)",
                (run_id, idempotency, document, document_hash(strategy), "QUEUED"),
            )
            return run_id

    def claim(self) -> tuple[str, str, ResearchJob] | None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # One global worker for this queue; no unbounded optimization fanout.
            if db.execute("SELECT 1 FROM jobs WHERE status='RUNNING'").fetchone():
                return None
            row = db.execute(
                "SELECT * FROM jobs WHERE status='QUEUED' ORDER BY rowid LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            nonce = uuid4().hex
            db.execute(
                "UPDATE jobs SET status='RUNNING',claim=?,started_at=? WHERE run_id=?",
                (nonce, datetime.now(UTC).isoformat(), row["run_id"]),
            )
            return row["run_id"], nonce, ResearchJob.model_validate_json(row["request"])

    def finish(
        self,
        run_id: str,
        nonce: str,
        *,
        result: dict[str, Any] | None,
        error: Literal["JOB_FAILED", "TIMEOUT", "BUDGET_EXCEEDED", "PROVENANCE_MISMATCH"]
        | None = None,
    ) -> None:
        if (result is None) == (error is None):
            raise ValueError("EXACTLY_ONE_RESEARCH_OUTCOME_REQUIRED")
        document = (
            json.dumps(result, sort_keys=True, allow_nan=False) if result is not None else None
        )
        digest = hashlib.sha256(document.encode()).hexdigest() if document is not None else None
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE jobs SET status=?,finished_at=?,result=?,result_hash=?,error=? "
                "WHERE run_id=? AND claim=? AND status='RUNNING'",
                (
                    "SUCCEEDED" if result is not None else "FAILED",
                    datetime.now(UTC).isoformat(),
                    document,
                    digest,
                    error,
                    run_id,
                    nonce,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("RESEARCH_CLAIM_CONFLICT")

    def recover_interrupted(self) -> int:
        """Call only once with exclusive worker ownership at process startup."""
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE jobs SET status='FAILED',error='INTERRUPTED',finished_at=? "
                "WHERE status='RUNNING'",
                (datetime.now(UTC).isoformat(),),
            )
            return cursor.rowcount

    def cancel(self, run_id: str) -> None:
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE jobs SET status='CANCELLED',finished_at=?,error='OPERATOR_CANCELLED' "
                "WHERE run_id=? AND status IN ('QUEUED','RUNNING')",
                (datetime.now(UTC).isoformat(), run_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("RESEARCH_RUN_NOT_CANCELLABLE")

    def is_running(self, run_id: str, nonce: str) -> bool:
        with self._connect() as db:
            return db.execute(
                "SELECT 1 FROM jobs WHERE run_id=? AND claim=? AND status='RUNNING'",
                (run_id, nonce),
            ).fetchone() is not None

    def list(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM jobs ORDER BY rowid DESC LIMIT 100").fetchall()
        result = []
        for row in rows:
            document = dict(row)
            document.pop("claim", None)
            document.pop("idempotency", None)
            document["request"] = json.loads(document["request"])
            if document["result"] is not None:
                if (
                    hashlib.sha256(document["result"].encode()).hexdigest()
                    != document["result_hash"]
                ):
                    raise ValueError("RESEARCH_RESULT_CORRUPT")
                document["result"] = json.loads(document["result"])
            result.append(document)
        return result
