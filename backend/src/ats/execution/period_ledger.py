"""Account-wide realized budgets; internal evidence only, no financial authority.

Inputs must come from a trusted reconciler. SDK history success alone does not
prove coverage or the timezone of historical broker timestamps. A baseline is an
observed boundary equity snapshot, never today's balance extrapolated backwards.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def utc_timestamps(self) -> EvidenceModel:
        for value in self.__dict__.values():
            if isinstance(value, datetime) and (
                value.tzinfo is None or value.utcoffset() != timedelta(0)
            ):
                raise ValueError("VERIFIED_UTC_REQUIRED")
        return self


class PeriodBaseline(EvidenceModel):
    account_id: str = Field(min_length=1)
    session_identity_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    currency: str = Field(min_length=1)
    boundary: datetime
    balance: Decimal
    equity: Decimal = Field(gt=0)
    source_evidence_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def midnight(self) -> PeriodBaseline:
        if any(
            (
                self.boundary.hour,
                self.boundary.minute,
                self.boundary.second,
                self.boundary.microsecond,
            )
        ):
            raise ValueError("EXACT_UTC_PERIOD_BOUNDARY_REQUIRED")
        return self


class BookedDeal(EvidenceModel):
    deal_id: str = Field(min_length=1)
    timestamp: datetime
    kind: Literal["TRADE", "CASH_FLOW", "UNKNOWN"]
    profit: Decimal
    commission: Decimal
    swap: Decimal
    fee: Decimal
    # Include every symbol/manual trade. Instrument specialization must not hide
    # external exposure or losses in account risk accounting.
    symbol: str | None

    @property
    def net(self) -> Decimal:
        return self.profit + self.commission + self.swap + self.fee


class DealHistory(EvidenceModel):
    account_id: str = Field(min_length=1)
    session_identity_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    currency: str = Field(min_length=1)
    observed_at: datetime
    coverage_start: datetime
    coverage_end: datetime
    complete_account_history: bool
    historical_utc_verified: bool
    timezone_evidence_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    observed_balance: Decimal
    balance_tolerance: Decimal = Field(ge=0, le=Decimal("0.01"))
    deals: tuple[BookedDeal, ...]

    @model_validator(mode="after")
    def coverage(self) -> DealHistory:
        if self.coverage_start > self.coverage_end or self.coverage_end > self.observed_at:
            raise ValueError("INVALID_HISTORY_COVERAGE")
        seen: set[str] = set()
        for deal in self.deals:
            if deal.deal_id in seen:
                raise ValueError("DUPLICATE_BROKER_DEAL")
            seen.add(deal.deal_id)
            if not self.coverage_start <= deal.timestamp <= self.coverage_end:
                raise ValueError("DEAL_OUTSIDE_COVERAGE")
        return self


class PeriodBudget(EvidenceModel):
    account_id: str
    state: Literal["VERIFIED_BUDGET", "UNKNOWN"]
    reason_codes: tuple[str, ...]
    evidence_hash: str | None
    observed_at: datetime | None = None
    currency: str | None = None
    starting_day_equity: Decimal | None = None
    starting_month_equity: Decimal | None = None
    net_booked_day: Decimal | None = None
    net_booked_month: Decimal | None = None
    cash_flows_month: Decimal | None = None
    daily_remaining: Decimal | None = None
    monthly_remaining: Decimal | None = None
    grants_authority: Literal[False] = False


def document_hash(document: str) -> str:
    return hashlib.sha256(document.encode()).hexdigest()


class BrokerPeriodLedger:
    """Immutable snapshots and baselines, hash checked on every budget read.

    Corrections must be explicitly reviewed; new snapshots changing an already
    observed deal cannot silently reset risk history. No console/agent route can
    supply these facts, and this component never submits an order.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS period_baselines ("
                "account_id TEXT, boundary TEXT, document TEXT, hash TEXT, "
                "PRIMARY KEY(account_id,boundary))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS history_snapshots ("
                "sequence INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT, "
                "document TEXT, hash TEXT)"
            )

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

    @staticmethod
    def _checked(row: sqlite3.Row) -> str:
        document = str(row["document"])
        if document_hash(document) != row["hash"]:
            raise ValueError("PERIOD_EVIDENCE_CORRUPT")
        return document

    def record_baseline(self, baseline: PeriodBaseline) -> None:
        baseline = PeriodBaseline.model_validate(baseline.model_dump())
        document = baseline.model_dump_json()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM period_baselines WHERE account_id=? AND boundary=?",
                (baseline.account_id, baseline.boundary.isoformat()),
            ).fetchone()
            if row is not None:
                if self._checked(row) != document:
                    raise ValueError("IMMUTABLE_PERIOD_BASELINE_CONFLICT")
                return
            db.execute(
                "INSERT INTO period_baselines VALUES(?,?,?,?)",
                (
                    baseline.account_id,
                    baseline.boundary.isoformat(),
                    document,
                    document_hash(document),
                ),
            )

    def record_history(self, history: DealHistory) -> str:
        history = DealHistory.model_validate(history.model_dump())
        document = history.model_dump_json()
        digest = document_hash(document)
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT * FROM history_snapshots WHERE account_id=? ORDER BY sequence DESC LIMIT 1",
                (history.account_id,),
            ).fetchone()
            if prior is not None:
                old = DealHistory.model_validate_json(self._checked(prior))
                if (
                    old.session_identity_hash != history.session_identity_hash
                    or old.currency != history.currency
                ):
                    raise ValueError("PERIOD_ACCOUNT_IDENTITY_CHANGED")
                if old.observed_at > history.observed_at:
                    raise ValueError("HISTORY_OBSERVATION_REGRESSION")
                current = {d.deal_id: d for d in history.deals}
                for deal in old.deals:
                    if history.coverage_start <= deal.timestamp <= history.coverage_end:
                        if current.get(deal.deal_id) != deal:
                            raise ValueError("BROKER_HISTORY_CORRECTION_REQUIRES_REVIEW")
                if prior["hash"] == digest:
                    return digest
            db.execute(
                "INSERT INTO history_snapshots(account_id,document,hash) VALUES(?,?,?)",
                (history.account_id, document, digest),
            )
        return digest

    def budget(
        self, account_id: str, now: datetime, daily_fraction: Decimal, monthly_fraction: Decimal
    ) -> PeriodBudget:
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("UTC_BUDGET_TIME_REQUIRED")
        if not (
            daily_fraction.is_finite()
            and monthly_fraction.is_finite()
            and 0 < daily_fraction <= Decimal(".03")
            and 0 < monthly_fraction <= Decimal(".08")
        ):
            raise ValueError("INVALID_PERIOD_LOSS_LIMITS")
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month = day.replace(day=1)
        reasons: list[str] = []
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM history_snapshots WHERE account_id=? ORDER BY sequence DESC LIMIT 1",
                (account_id,),
            ).fetchone()
            baseline_rows = [
                db.execute(
                    "SELECT * FROM period_baselines WHERE account_id=? AND boundary=?",
                    (account_id, stamp.isoformat()),
                ).fetchone()
                for stamp in (day, month)
            ]
            if row is None or any(b is None for b in baseline_rows):
                return PeriodBudget(
                    account_id=account_id,
                    state="UNKNOWN",
                    reason_codes=("PERIOD_HISTORY_OR_BASELINE_REQUIRED",),
                    evidence_hash=None,
                )
            history = DealHistory.model_validate_json(self._checked(row))
            baselines = [
                PeriodBaseline.model_validate_json(self._checked(b))
                for b in baseline_rows
                if b is not None
            ]
        if not 0 <= (now - history.observed_at).total_seconds() <= 5:
            reasons.append("FRESH_HISTORY_REQUIRED")
        if (
            not history.complete_account_history
            or history.coverage_start > month
            or history.coverage_end != history.observed_at
        ):
            reasons.append("COMPLETE_ACCOUNT_HISTORY_REQUIRED")
        if not history.historical_utc_verified:
            reasons.append("HISTORICAL_UTC_EVIDENCE_REQUIRED")
        if any(
            b.session_identity_hash != history.session_identity_hash
            or b.currency != history.currency
            for b in baselines
        ):
            reasons.append("PERIOD_BASELINE_IDENTITY_MISMATCH")
        deals = [d for d in history.deals if month <= d.timestamp <= history.observed_at]
        if any(d.kind == "UNKNOWN" for d in deals):
            reasons.append("UNKNOWN_BROKER_DEAL_KIND")
        if (
            abs(
                baselines[1].balance
                + sum((d.net for d in deals), Decimal(0))
                - history.observed_balance
            )
            > history.balance_tolerance
        ):
            reasons.append("BROKER_BALANCE_RECONCILIATION_REQUIRED")
        expected_day_balance = baselines[1].balance + sum(
            (d.net for d in deals if d.timestamp < day), Decimal(0)
        )
        if abs(expected_day_balance - baselines[0].balance) > history.balance_tolerance:
            reasons.append("DAY_BASELINE_BALANCE_RECONCILIATION_REQUIRED")
        if reasons:
            return PeriodBudget(
                account_id=account_id,
                state="UNKNOWN",
                reason_codes=tuple(reasons),
                evidence_hash=None,
            )
        trades = [d for d in deals if d.kind == "TRADE"]
        net_month = sum((d.net for d in trades), Decimal(0))
        net_day = sum((d.net for d in trades if d.timestamp >= day), Decimal(0))
        cash_flows = sum((d.net for d in deals if d.kind == "CASH_FLOW"), Decimal(0))
        digest = document_hash(
            "|".join([history.model_dump_json()] + [b.model_dump_json() for b in baselines])
        )
        return PeriodBudget(
            account_id=account_id,
            state="VERIFIED_BUDGET",
            reason_codes=(),
            evidence_hash=digest,
            observed_at=history.observed_at,
            currency=history.currency,
            starting_day_equity=baselines[0].equity,
            starting_month_equity=baselines[1].equity,
            net_booked_day=net_day,
            net_booked_month=net_month,
            cash_flows_month=cash_flows,
            daily_remaining=baselines[0].equity * daily_fraction + net_day,
            monthly_remaining=baselines[1].equity * monthly_fraction + net_month,
        )
