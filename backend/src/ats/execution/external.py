"""Separate external account authority, durable reservation and single-use dispatch.

Paper tokens are not accepted here. Not wired to autonomous runtime until an
independent strategy eligibility verifier and physical commissioning pass.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RiskProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    version: str = Field(min_length=1)
    max_trade_risk: Decimal = Field(gt=0)
    max_daily_loss: Decimal = Field(gt=0)
    max_monthly_loss: Decimal = Field(gt=0)
    max_open_risk: Decimal = Field(gt=0)
    max_volume: Decimal = Field(gt=0)
    max_positions: int = Field(gt=0)
    max_strategy_risk: Decimal = Field(gt=0)


class ExternalIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    version: Literal["EXTERNAL-INTENT-V1"] = "EXTERNAL-INTENT-V1"
    account_id: str = Field(min_length=1)
    strategy_id: str = Field(pattern=r"^XAU-[0-9]{3,}$")
    strategy_version: int = Field(ge=1)
    signal_id: str = Field(min_length=1)
    canonical_symbol: Literal["XAUUSD"] = "XAUUSD"
    broker_symbol: str = Field(min_length=1)
    side: Literal["BUY", "SELL"]
    volume: Decimal = Field(gt=0)
    entry: Decimal = Field(gt=0)
    sl: Decimal = Field(gt=0)
    tp: Decimal = Field(gt=0)
    risk_cash: Decimal = Field(gt=0)
    margin_cash: Decimal = Field(gt=0)
    max_deviation_points: int = Field(ge=0, le=1000)
    expires_at: datetime
    idempotency: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def geometry(self) -> ExternalIntent:
        if self.expires_at.tzinfo is None:
            raise ValueError("UTC_EXPIRY_REQUIRED")
        if not (
            self.sl < self.entry < self.tp if self.side == "BUY" else self.tp < self.entry < self.sl
        ):
            raise ValueError("INVALID_ORDER_GEOMETRY")
        return self


class AccountFacts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    account_id: str
    broker_symbol: str
    mode: Literal["DEMO", "LIVE", "UNKNOWN"]
    execution_enabled: bool
    connected: bool
    reconciled: bool
    strategy_eligible: bool
    eligible_strategy_version: int = Field(ge=1)
    allowed_strategy_ids: tuple[str, ...]
    killed: bool
    quote_time: datetime
    snapshot_time: datetime
    free_margin: Decimal = Field(ge=0)
    daily_loss: Decimal = Field(ge=0)
    monthly_loss: Decimal = Field(ge=0)
    open_risk: Decimal = Field(ge=0)
    strategy_risk: Decimal = Field(ge=0)
    positions: int = Field(ge=0)
    volume_min: Decimal = Field(gt=0)
    volume_max: Decimal = Field(gt=0)
    volume_step: Decimal = Field(gt=0)
    tick_size: Decimal = Field(gt=0)
    observed_risk_cash: Decimal = Field(gt=0)
    observed_margin_cash: Decimal = Field(gt=0)


def assess(intent: ExternalIntent, facts: AccountFacts, risk: RiskProfile, now: datetime) -> None:
    if now.tzinfo is None or intent.expires_at <= now:
        raise ValueError("EXTERNAL_AUTHORITY_EXPIRED")
    if intent.account_id != facts.account_id or intent.broker_symbol != facts.broker_symbol:
        raise ValueError("ACCOUNT_OR_SYMBOL_MISMATCH")
    if (
        facts.mode == "UNKNOWN"
        or not all(
            (facts.execution_enabled, facts.connected, facts.reconciled, facts.strategy_eligible)
        )
        or facts.killed
    ):
        raise ValueError("EXTERNAL_NEW_RISK_BLOCKED")
    if intent.strategy_id not in facts.allowed_strategy_ids:
        raise ValueError("STRATEGY_NOT_ASSIGNED")
    if intent.strategy_version != facts.eligible_strategy_version:
        raise ValueError("STRATEGY_VERSION_NOT_ELIGIBLE")
    for stamp in (facts.quote_time, facts.snapshot_time):
        if stamp.tzinfo is None or not 0 <= (now - stamp).total_seconds() <= 5:
            raise ValueError("FRESH_ACCOUNT_AND_MARKET_REQUIRED")
    if intent.volume < facts.volume_min or intent.volume > min(facts.volume_max, risk.max_volume):
        raise ValueError("VOLUME_LIMIT")
    if intent.volume % facts.volume_step or any(
        price % facts.tick_size for price in (intent.entry, intent.sl, intent.tp)
    ):
        raise ValueError("BROKER_GRID_MISMATCH")
    if (
        intent.risk_cash < facts.observed_risk_cash
        or intent.margin_cash < facts.observed_margin_cash
    ):
        raise ValueError("UNDERSTATED_RISK_OR_MARGIN")
    if (
        intent.risk_cash > risk.max_trade_risk
        or facts.daily_loss + intent.risk_cash > risk.max_daily_loss
        or facts.monthly_loss + intent.risk_cash > risk.max_monthly_loss
        or facts.open_risk + intent.risk_cash > risk.max_open_risk
        or facts.strategy_risk + intent.risk_cash > risk.max_strategy_risk
        or facts.positions >= risk.max_positions
        or facts.free_margin < intent.margin_cash
    ):
        raise ValueError("ACCOUNT_RISK_LIMIT")


class ExternalAdapter(Protocol):
    def submit(self, intent: ExternalIntent) -> dict[str, Any]: ...


class ExternalLedger:
    """Persist before dispatch; ambiguous outcomes never free reservations or retry.

    Caller facts must come from trusted observed snapshots, not an API payload.
    Reconciliation remains a separate commissioning requirement; UNKNOWN blocks.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS executions (
                execution_id TEXT PRIMARY KEY, account_id TEXT NOT NULL,
                idempotency TEXT NOT NULL, intent TEXT NOT NULL, intent_hash TEXT NOT NULL,
                mode TEXT NOT NULL, authority TEXT NOT NULL, risk_version TEXT NOT NULL,
                state TEXT NOT NULL, result TEXT, created_at TEXT NOT NULL,
                UNIQUE(account_id,idempotency))""")
            columns = {row["name"] for row in db.execute("PRAGMA table_info(executions)")}
            if "risk_hash" not in columns:
                db.execute("ALTER TABLE executions ADD COLUMN risk_hash TEXT")

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(
        self, intent: ExternalIntent, facts: AccountFacts, risk: RiskProfile, now: datetime
    ) -> str:
        intent = ExternalIntent.model_validate(intent.model_dump())
        facts = AccountFacts.model_validate(facts.model_dump())
        risk = RiskProfile.model_validate(risk.model_dump())
        assess(intent, facts, risk, now)
        document = intent.model_dump_json()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT * FROM executions WHERE account_id=? AND idempotency=?",
                (intent.account_id, intent.idempotency),
            ).fetchone()
            if prior:
                if prior["intent"] != document:
                    raise ValueError("EXTERNAL_IDEMPOTENCY_CONFLICT")
                return str(prior["execution_id"])
            outstanding = db.execute(
                "SELECT intent FROM executions WHERE account_id=? "
                "AND state IN ('RESERVED','SUBMITTING','UNKNOWN','ACCEPTED')",
                (intent.account_id,),
            ).fetchall()
            # Existing accepted orders must reconcile before new risk. No double counting guess.
            if any(
                db.execute(
                    "SELECT 1 FROM executions WHERE account_id=? AND state=?",
                    (intent.account_id, state),
                ).fetchone()
                for state in ("SUBMITTING", "UNKNOWN", "ACCEPTED")
            ):
                raise ValueError("RECONCILIATION_REQUIRED")
            reserved = [ExternalIntent.model_validate_json(row["intent"]) for row in outstanding]
            if (
                facts.open_risk
                + sum((r.risk_cash for r in reserved), Decimal(0))
                + intent.risk_cash
                > risk.max_open_risk
                or facts.positions + len(reserved) >= risk.max_positions
                or sum((r.margin_cash for r in reserved), Decimal(0)) + intent.margin_cash
                > facts.free_margin
                or facts.strategy_risk
                + sum(
                    (r.risk_cash for r in reserved if r.strategy_id == intent.strategy_id),
                    Decimal(0),
                )
                + intent.risk_cash
                > risk.max_strategy_risk
                or facts.daily_loss
                + sum((r.risk_cash for r in reserved), Decimal(0))
                + intent.risk_cash
                > risk.max_daily_loss
                or facts.monthly_loss
                + sum((r.risk_cash for r in reserved), Decimal(0))
                + intent.risk_cash
                > risk.max_monthly_loss
            ):
                raise ValueError("RESERVATION_LIMIT")
            execution_id = "EXE-" + uuid4().hex
            scope = "A3_EXTERNAL_DEMO" if facts.mode == "DEMO" else "A4_EXTERNAL_LIVE"
            db.execute(
                "INSERT INTO executions "
                "(execution_id,account_id,idempotency,intent,intent_hash,mode,authority,"
                "risk_version,state,result,created_at,risk_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    execution_id,
                    intent.account_id,
                    intent.idempotency,
                    document,
                    hashlib.sha256(document.encode()).hexdigest(),
                    facts.mode,
                    scope,
                    risk.version,
                    "RESERVED",
                    None,
                    now.isoformat(),
                    hashlib.sha256(risk.model_dump_json().encode()).hexdigest(),
                ),
            )
            return execution_id

    def dispatch(
        self,
        execution_id: str,
        facts: AccountFacts,
        risk: RiskProfile,
        now: datetime,
        adapter: ExternalAdapter,
    ) -> dict[str, Any]:
        facts = AccountFacts.model_validate(facts.model_dump())
        risk = RiskProfile.model_validate(risk.model_dump())
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM executions WHERE execution_id=?", (execution_id,)
            ).fetchone()
            if row is None or row["state"] != "RESERVED":
                raise ValueError("EXTERNAL_AUTHORITY_ALREADY_CONSUMED_OR_UNKNOWN")
            if hashlib.sha256(row["intent"].encode()).hexdigest() != row["intent_hash"]:
                raise ValueError("EXTERNAL_INTENT_CORRUPT")
            intent = ExternalIntent.model_validate_json(row["intent"])
            if (
                facts.mode != row["mode"]
                or row["authority"]
                != ("A3_EXTERNAL_DEMO" if facts.mode == "DEMO" else "A4_EXTERNAL_LIVE")
                or risk.version != row["risk_version"]
                or hashlib.sha256(risk.model_dump_json().encode()).hexdigest() != row["risk_hash"]
            ):
                raise ValueError("EXTERNAL_SCOPE_CHANGED")
            assess(intent, facts, risk, now)
            if db.execute(
                "SELECT 1 FROM executions WHERE account_id=? AND execution_id<>? "
                "AND state IN ('SUBMITTING','UNKNOWN','ACCEPTED')",
                (intent.account_id, execution_id),
            ).fetchone():
                raise ValueError("RECONCILIATION_REQUIRED")
            reserved = [
                ExternalIntent.model_validate_json(other["intent"])
                for other in db.execute(
                    "SELECT intent FROM executions WHERE account_id=? AND state='RESERVED' "
                    "AND execution_id<>?",
                    (intent.account_id, execution_id),
                )
            ]
            if (
                facts.open_risk
                + intent.risk_cash
                + sum((other.risk_cash for other in reserved), Decimal(0))
                > risk.max_open_risk
                or facts.daily_loss
                + intent.risk_cash
                + sum((other.risk_cash for other in reserved), Decimal(0))
                > risk.max_daily_loss
                or facts.monthly_loss
                + intent.risk_cash
                + sum((other.risk_cash for other in reserved), Decimal(0))
                > risk.max_monthly_loss
                or facts.free_margin
                < intent.margin_cash + sum((other.margin_cash for other in reserved), Decimal(0))
                or facts.positions + len(reserved) + 1 > risk.max_positions
                or facts.strategy_risk
                + intent.risk_cash
                + sum(
                    (
                        other.risk_cash
                        for other in reserved
                        if other.strategy_id == intent.strategy_id
                    ),
                    Decimal(0),
                )
                > risk.max_strategy_risk
            ):
                raise ValueError("RESERVATION_LIMIT")
            db.execute(
                "UPDATE executions SET state='SUBMITTING' WHERE execution_id=?", (execution_id,)
            )
        try:
            result = adapter.submit(intent)
            state = result.get("state")
            if state not in {"ACCEPTED", "REJECTED"}:
                state = "UNKNOWN"
            encoded = json.dumps(result, sort_keys=True, allow_nan=False)
        except Exception:
            state, encoded = "UNKNOWN", '{"state":"UNKNOWN","reason":"BROKER_OUTCOME_UNKNOWN"}'
        with self._db() as db:
            db.execute(
                "UPDATE executions SET state=?,result=? WHERE execution_id=?",
                (state, encoded, execution_id),
            )
        return {"execution_id": execution_id, "state": state, "result": json.loads(encoded)}

    def list(self) -> list[dict[str, Any]]:
        with self._db() as db:
            return [
                dict(row)
                for row in db.execute("SELECT * FROM executions ORDER BY rowid DESC LIMIT 100")
            ]
