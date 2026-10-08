"""Durable strategy lineages. Definitions and research never confer order authority."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrategyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    strategy_id: str = Field(pattern=r"^XAU-[0-9]{3,}$")
    version: int = Field(ge=1)
    definition_id: str
    name: str = Field(min_length=1)
    canonical_symbol: Literal["XAUUSD"] = "XAUUSD"
    status: Literal[
        "DRAFT",
        "RESEARCH",
        "CANDIDATE",
        "PAPER",
        "DEMO",
        "MICRO_LIVE",
        "ACTIVE",
        "PAUSED",
        "RETIRED",
    ] = "RESEARCH"
    hypothesis: str | None = None
    direction: Literal["LONG", "SHORT", "BOTH"] | None = None
    trade_horizon: Literal["SCALP", "INTRADAY", "SWING", "POSITION"] | None = None
    timeframes: tuple[str, ...] = ()
    entry_rules: str | None = None
    exit_rules: str | None = None
    stop_loss_logic: str | None = None
    take_profit_logic: str | None = None
    position_sizing: str | None = None
    sessions: tuple[str, ...] = ()
    required_features: tuple[str, ...] = ()
    required_data: tuple[str, ...] = ()
    known_failure_modes: tuple[str, ...] = ()
    datasets_tested: tuple[str, ...] = ()
    backtest_results: tuple[str, ...] = ()
    walk_forward_results: tuple[str, ...] = ()
    holdout_results: tuple[str, ...] = ()
    paper_results: tuple[str, ...] = ()
    demo_results: tuple[str, ...] = ()
    live_results: tuple[str, ...] = ()
    entry_quality_stats: dict[str, float] | None = None
    exit_quality_stats: dict[str, float] | None = None
    last_validated_at: datetime | None = None


def document_hash(record: StrategyRecord) -> str:
    return hashlib.sha256(record.model_dump_json().encode()).hexdigest()


class StrategyStore:
    """Append-only versions and AUTOINCREMENT tombstones prevent ID reuse.

    Promotions deliberately fail closed until an independent evidence verifier
    is wired. Populating result strings is not proof of validation.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS lineages (
                    number INTEGER PRIMARY KEY AUTOINCREMENT,
                    definition_id TEXT UNIQUE NOT NULL
                );
                CREATE TABLE IF NOT EXISTS versions (
                    strategy_id TEXT NOT NULL, version INTEGER NOT NULL,
                    document TEXT NOT NULL, hash TEXT NOT NULL,
                    created_at TEXT NOT NULL, reason TEXT NOT NULL,
                    PRIMARY KEY(strategy_id, version)
                );
            """)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _decode(row: tuple[Any, ...] | None) -> StrategyRecord:
        if row is None:
            raise KeyError("STRATEGY_NOT_FOUND")
        record = StrategyRecord.model_validate_json(row[0])
        if document_hash(record) != row[1]:
            raise ValueError("STRATEGY_VERSION_CORRUPT")
        return record

    def get(self, strategy_id: str, version: int | None = None) -> StrategyRecord:
        # Exact lookup only; SQL equality never resolves a short prefix.
        with self._connect() as db:
            if version is None:
                row = db.execute(
                    "SELECT document,hash FROM versions WHERE strategy_id=? "
                    "ORDER BY version DESC LIMIT 1",
                    (strategy_id,),
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT document,hash FROM versions WHERE strategy_id=? AND version=?",
                    (strategy_id, version),
                ).fetchone()
        return self._decode(row)

    def list(self) -> list[StrategyRecord]:
        with self._connect() as db:
            rows = db.execute("""
                SELECT v.document,v.hash FROM versions v
                WHERE v.version=(SELECT MAX(w.version) FROM versions w
                    WHERE w.strategy_id=v.strategy_id)
                ORDER BY v.strategy_id
            """).fetchall()
        return [self._decode(row) for row in rows]

    @staticmethod
    def _append(db: sqlite3.Connection, record: StrategyRecord, reason: str) -> None:
        db.execute(
            "INSERT INTO versions VALUES(?,?,?,?,?,?)",
            (
                record.strategy_id,
                record.version,
                record.model_dump_json(),
                document_hash(record),
                datetime.now(UTC).isoformat(),
                reason,
            ),
        )

    def register(self, definition_id: str, name: str) -> StrategyRecord:
        if not definition_id.strip() or not name.strip():
            raise ValueError("STRATEGY_DEFINITION_REQUIRED")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT number FROM lineages WHERE definition_id=?", (definition_id,)
            ).fetchone()
            if row:
                strategy_id = f"XAU-{row[0]:03d}"
                return self._decode(
                    db.execute(
                        "SELECT document,hash FROM versions WHERE strategy_id=? "
                        "ORDER BY version DESC LIMIT 1",
                        (strategy_id,),
                    ).fetchone()
                )
            cursor = db.execute("INSERT INTO lineages(definition_id) VALUES(?)", (definition_id,))
            record = StrategyRecord(
                strategy_id=f"XAU-{cursor.lastrowid:03d}",
                version=1,
                definition_id=definition_id,
                name=name,
            )
            self._append(db, record, "CLEAN_ROOM_REGISTRATION")
            return record

    def revise(self, record: StrategyRecord, *, expected_version: int, reason: str) -> None:
        record = StrategyRecord.model_validate(record.model_dump())
        if not reason.strip():
            raise ValueError("VERSION_REASON_REQUIRED")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = self._decode(
                db.execute(
                    "SELECT document,hash FROM versions WHERE strategy_id=? "
                    "ORDER BY version DESC LIMIT 1",
                    (record.strategy_id,),
                ).fetchone()
            )
            if previous.version != expected_version or record.version != expected_version + 1:
                raise ValueError("STRATEGY_VERSION_CONFLICT")
            if record.definition_id != previous.definition_id or previous.status == "RETIRED":
                raise ValueError("IMMUTABLE_STRATEGY_LINEAGE")
            if record.status != previous.status and record.status not in {"PAUSED", "RETIRED"}:
                raise ValueError("INDEPENDENT_VALIDATION_REQUIRED")
            evidence_fields = (
                "datasets_tested",
                "backtest_results",
                "walk_forward_results",
                "holdout_results",
                "paper_results",
                "demo_results",
                "live_results",
                "entry_quality_stats",
                "exit_quality_stats",
                "last_validated_at",
            )
            if any(getattr(record, key) != getattr(previous, key) for key in evidence_fields):
                raise ValueError("EVIDENCE_VERIFIER_REQUIRED")
            self._append(db, record, reason)

    def export_workspace(self, root: Path) -> None:
        """Human-readable projection; never loaded as performance authority."""
        root.mkdir(parents=True, exist_ok=True)
        records = self.list()
        (root / "STRATEGY_INDEX.yaml").write_text(
            json.dumps([r.model_dump(mode="json") for r in records], indent=2) + "\n",
            encoding="utf-8",
        )  # JSON is a YAML subset, avoiding another parser dependency.
        for record in records:
            directory = root / record.strategy_id
            (directory / "evidence").mkdir(parents=True, exist_ok=True)
            (directory / "STRATEGY.md").write_text(
                f"# {record.strategy_id}: {record.name}\n\n"
                f"Definition: `{record.definition_id}`. Version: {record.version}. "
                f"Status: {record.status}.\n\n"
                "Unspecified rules remain UNKNOWN. No XAUUSD validation or edge is established.\n",
                encoding="utf-8",
            )
            for name in (
                "RESEARCH",
                "VALIDATION",
                "PERFORMANCE",
                "ENTRY_EXIT_ANALYSIS",
                "VERSIONS",
            ):
                target = directory / f"{name}.md"
                if not target.exists():
                    target.write_text(
                        f"# {record.strategy_id} {name}\n\n"
                        "NOT_RUN. No performance evidence or promotion authority.\n",
                        encoding="utf-8",
                    )
