"""Unrouted commissioning boundary for the small-account DEMO research candidate.

This development component is not an autonomous runtime. Its fact collector must
be a trusted account-wide broker reconciler, never an API/agent payload. Missing
UTC period baselines or incomplete deal history make commissioning unavailable.
No terminal initialization, credentials, SDK RPC, or public order API lives here.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from threading import RLock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ats.execution.external import (
    AccountFacts,
    ExternalAdapter,
    ExternalIntent,
    ExternalLedger,
    RiskProfile,
)


class DemoApproval(BaseModel):
    """Immutable local operator decision; identity/evidence references contain no secrets."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    approval_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    authority: Literal["A3_EXTERNAL_DEMO"] = "A3_EXTERNAL_DEMO"
    session_identity_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    operator_consent_reference: str = Field(min_length=1)
    strategy_id: str = Field(pattern=r"^XAU-[0-9]{3,}$")
    strategy_version: int = Field(ge=1)
    research_preset_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    broker_symbol: str = Field(min_length=1)
    tested_starting_equity: Decimal = Field(gt=0)
    minimum_current_equity: Decimal = Field(gt=0)
    maximum_current_equity: Decimal = Field(gt=0)
    risk_fraction: Decimal = Field(gt=0, le=Decimal("0.02"))
    daily_budget_fraction: Decimal = Field(default=Decimal("0.025"), gt=0, le=Decimal("0.03"))
    monthly_budget_fraction: Decimal = Field(default=Decimal("0.06"), gt=0, le=Decimal("0.08"))
    margin_fraction: Decimal = Field(default=Decimal("0.30"), gt=0, le=Decimal("0.30"))
    maximum_volume: Decimal = Field(gt=0)
    roundtrip_cost_per_lot: Decimal = Field(ge=0)
    maximum_entries_per_day: int = Field(default=3, ge=1, le=3)
    maximum_losing_trades_per_day: int = Field(default=2, ge=1, le=2)
    reentry_delay_seconds: int = Field(default=900, ge=900)
    expires_at: datetime

    @model_validator(mode="after")
    def check_capital_and_expiry(self) -> DemoApproval:
        if not (
            self.minimum_current_equity
            <= self.tested_starting_equity
            <= self.maximum_current_equity
        ):
            raise ValueError("INVALID_APPROVED_CAPITAL_RANGE")
        if self.expires_at.tzinfo is None:
            raise ValueError("UTC_APPROVAL_EXPIRY_REQUIRED")
        return self


class PeriodBook(BaseModel):
    """Verified start-period equity and net realized P&L, including costs and swap.

    The reconciler must include every account strategy/manual trade and reject
    unknown historical timezone, missing history, cash-flow ambiguity, or baselines.
    Successful syntax validation alone does not prove these historical observations.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    utc_day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    utc_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    starting_day_equity: Decimal = Field(gt=0)
    starting_month_equity: Decimal = Field(gt=0)
    net_booked_day: Decimal
    net_booked_month: Decimal
    entries_today: int = Field(ge=0)
    losing_trades_today: int = Field(ge=0)
    last_close_at: datetime | None
    observed_at: datetime
    evidence_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    complete_history: Literal[True]
    verified_baselines: Literal[True]
    verified_historical_utc: Literal[True]


class CommissionedFacts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    account: AccountFacts
    periods: PeriodBook
    session_identity_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    research_preset_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    verified_proposal_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    funded_equity: Decimal = Field(gt=0)
    current_equity: Decimal = Field(gt=0)
    account_wide_flat: Literal[True]
    no_pending_orders: Literal[True]


class DemoApprovalStore:
    """Append-only approvals plus explicit revocation; never inferred from execution consent."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS approvals (approval_id TEXT PRIMARY KEY, "
                "account_id TEXT NOT NULL, document TEXT NOT NULL, document_hash TEXT NOT NULL, "
                "revoked INTEGER NOT NULL DEFAULT 0)"
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

    def approve(self, approval: DemoApproval) -> None:
        approval = DemoApproval.model_validate(approval.model_dump())
        if approval.expires_at.tzinfo is None:
            raise ValueError("UTC_APPROVAL_EXPIRY_REQUIRED")
        document = approval.model_dump_json()
        with self._db() as db:
            try:
                db.execute(
                    "INSERT INTO approvals(approval_id,account_id,document,document_hash) "
                    "VALUES(?,?,?,?)",
                    (
                        approval.approval_id,
                        approval.account_id,
                        document,
                        hashlib.sha256(document.encode()).hexdigest(),
                    ),
                )
            except sqlite3.IntegrityError:
                raise ValueError("IMMUTABLE_APPROVAL_ID_ALREADY_EXISTS") from None

    def revoke(self, approval_id: str) -> None:
        with self._db() as db:
            db.execute("UPDATE approvals SET revoked=1 WHERE approval_id=?", (approval_id,))

    def get(self, approval_id: str) -> DemoApproval:
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM approvals WHERE approval_id=?", (approval_id,)
            ).fetchone()
        if row is None or row["revoked"]:
            raise ValueError("OPERATOR_APPROVAL_REQUIRED")
        if hashlib.sha256(row["document"].encode()).hexdigest() != row["document_hash"]:
            raise ValueError("OPERATOR_APPROVAL_CORRUPT")
        return DemoApproval.model_validate_json(row["document"])


def commissioned_risk(
    intent: ExternalIntent, approval: DemoApproval, facts: CommissionedFacts, now: datetime
) -> RiskProfile:
    """Strictest-wins cash envelopes; profits offset net booked period losses."""
    account, periods = facts.account, facts.periods
    offset = now.utcoffset()
    if (
        now.tzinfo is None
        or offset is None
        or offset.total_seconds() != 0
        or approval.expires_at.tzinfo is None
        or approval.expires_at <= now
    ):
        raise ValueError("OPERATOR_APPROVAL_EXPIRED")
    if (
        approval.account_id != intent.account_id
        or account.account_id != intent.account_id
        or facts.session_identity_hash != approval.session_identity_hash
        or facts.research_preset_hash != approval.research_preset_hash
        or facts.verified_proposal_hash
        != hashlib.sha256(intent.model_dump_json().encode()).hexdigest()
        or approval.broker_symbol != intent.broker_symbol
        or account.mode != "DEMO"
        or intent.strategy_id != approval.strategy_id
        or intent.strategy_version != approval.strategy_version
    ):
        raise ValueError("DEMO_APPROVAL_SCOPE_MISMATCH")
    if (
        facts.funded_equity != approval.tested_starting_equity
        or not approval.minimum_current_equity
        <= facts.current_equity
        <= approval.maximum_current_equity
    ):
        raise ValueError("ACCOUNT_CAPITAL_OUTSIDE_RESEARCH_APPROVAL")
    if (
        account.positions != 0
        or account.open_risk != 0
        or account.strategy_risk != 0
        or account.daily_loss != max(Decimal(0), -periods.net_booked_day)
        or account.monthly_loss != max(Decimal(0), -periods.net_booked_month)
        or periods.utc_day != now.strftime("%Y-%m-%d")
        or periods.utc_month != now.strftime("%Y-%m")
        or periods.observed_at.tzinfo is None
        or not 0 <= (now - periods.observed_at).total_seconds() <= 5
    ):
        raise ValueError("COMPLETE_FRESH_FLAT_RECONCILIATION_REQUIRED")
    if (
        periods.entries_today >= approval.maximum_entries_per_day
        or periods.losing_trades_today >= approval.maximum_losing_trades_per_day
    ):
        raise ValueError("DAILY_REENTRY_LIMIT")
    if periods.last_close_at is not None and (
        periods.last_close_at.tzinfo is None
        or (now - periods.last_close_at).total_seconds() < approval.reentry_delay_seconds
    ):
        raise ValueError("REENTRY_DELAY")
    daily_remaining = (
        periods.starting_day_equity * approval.daily_budget_fraction + periods.net_booked_day
    )
    monthly_remaining = (
        periods.starting_month_equity * approval.monthly_budget_fraction + periods.net_booked_month
    )
    maximum_risk = min(
        facts.current_equity * approval.risk_fraction, daily_remaining, monthly_remaining
    )
    if maximum_risk <= 0 or intent.risk_cash > maximum_risk:
        raise ValueError("PERIOD_OR_TRADE_RISK_BUDGET")
    if intent.risk_cash < (
        account.observed_risk_cash + intent.volume * approval.roundtrip_cost_per_lot
    ):
        raise ValueError("STOP_AND_COST_RISK_UNDERSTATED")
    if intent.margin_cash > facts.current_equity * approval.margin_fraction:
        raise ValueError("MARGIN_ALLOCATION_LIMIT")
    # ExternalLedger reserves against this cash envelope. Period proofs, not its
    # legacy non-negative daily-loss input, calculate the available net budget.
    return RiskProfile(
        version=approval.approval_id,
        max_trade_risk=maximum_risk,
        max_daily_loss=account.daily_loss + daily_remaining,
        max_monthly_loss=account.monthly_loss + monthly_remaining,
        max_open_risk=maximum_risk,
        max_volume=approval.maximum_volume,
        max_positions=1,
        max_strategy_risk=maximum_risk,
    )


class DemoExecutionSupervisor:
    """Internal dispatch only; caller must supply a commissioned isolated adapter.

    No factory is wired into account service, console, agents, or runtime. Accepted
    or ambiguous ledger entries block all following entries until a future trusted
    deal/position reconciler resolves their lifecycle; this component never guesses.
    """

    def __init__(
        self,
        approvals: DemoApprovalStore,
        ledger: ExternalLedger,
        observe: Callable[[ExternalIntent], CommissionedFacts],
        adapter: ExternalAdapter,
        clock: Callable[[], datetime],
    ) -> None:
        self._approvals, self._ledger = approvals, ledger
        self._observe, self._adapter, self._clock = observe, adapter, clock
        self._lock = RLock()

    def dispatch(self, approval_id: str, intent: ExternalIntent) -> dict[str, object]:
        with self._lock:
            approval = self._approvals.get(approval_id)
            facts = CommissionedFacts.model_validate(self._observe(intent).model_dump())
            now = self._clock()
            risk = commissioned_risk(intent, approval, facts, now)
            execution_id = self._ledger.reserve(intent, facts.account, risk, now)
            # Persist first, then refresh consent, reconciliation and broker economics.
            approval = self._approvals.get(approval_id)
            facts = CommissionedFacts.model_validate(self._observe(intent).model_dump())
            now = self._clock()
            refreshed_risk = commissioned_risk(intent, approval, facts, now)
            return self._ledger.dispatch(
                execution_id, facts.account, refreshed_risk, now, self._adapter
            )
