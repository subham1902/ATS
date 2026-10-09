"""Pure account-wide comparison. Observation is never authorization or retry.

An absent position does not prove an order failed or a trade closed. Durable
execution/deal reconciliation remains required before releasing reservations.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from ats.execution.period_ledger import EvidenceModel, document_hash


class Exposure(EvidenceModel):
    broker_id: str = Field(min_length=1)
    kind: Literal["POSITION", "PENDING_ORDER"]
    symbol: str = Field(min_length=1)
    side: Literal["BUY", "SELL"]
    volume: Decimal = Field(gt=0)
    sl: Decimal = Field(ge=0)
    tp: Decimal = Field(ge=0)


class OwnedExposure(EvidenceModel):
    execution_id: str = Field(min_length=1)
    strategy_id: str = Field(pattern=r"^XAU-[0-9]{3,}$")
    strategy_version: int = Field(ge=1)
    exposure: Exposure


class ExpectedAccount(EvidenceModel):
    account_id: str = Field(min_length=1)
    session_identity_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    mode: Literal["DEMO", "LIVE"]
    broker_symbol: str = Field(min_length=1)
    exposures: tuple[OwnedExposure, ...]
    unresolved_execution_ids: tuple[str, ...]

    @model_validator(mode="after")
    def unique_ownership(self) -> ExpectedAccount:
        keys = [(e.exposure.kind, e.exposure.broker_id) for e in self.exposures]
        if len(keys) != len(set(keys)):
            raise ValueError("AMBIGUOUS_BROKER_EXPOSURE_OWNERSHIP")
        if any(e.exposure.symbol != self.broker_symbol for e in self.exposures):
            raise ValueError("OWNED_EXPOSURE_SYMBOL_MISMATCH")
        return self


class ObservedAccount(EvidenceModel):
    account_id: str = Field(min_length=1)
    session_identity_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    mode: Literal["DEMO", "LIVE", "UNKNOWN"]
    observed_at: datetime
    connected: bool
    complete_account_snapshot: bool
    exposures: tuple[Exposure, ...]

    @model_validator(mode="after")
    def unique_broker_ids(self) -> ObservedAccount:
        keys = [(e.kind, e.broker_id) for e in self.exposures]
        if len(keys) != len(set(keys)):
            raise ValueError("DUPLICATE_BROKER_EXPOSURE")
        return self


class ReconciliationResult(EvidenceModel):
    account_id: str
    state: Literal["SNAPSHOT_MATCHED", "RECONCILIATION_REQUIRED", "UNKNOWN"]
    reason_codes: tuple[str, ...]
    evidence_hash: str
    releases_reservations: Literal[False] = False
    grants_authority: Literal[False] = False


def reconcile_account(
    expected: ExpectedAccount, observed: ObservedAccount, now: datetime
) -> ReconciliationResult:
    expected = ExpectedAccount.model_validate(expected.model_dump())
    observed = ObservedAccount.model_validate(observed.model_dump())
    digest = document_hash(expected.model_dump_json() + "|" + observed.model_dump_json())
    unknown: list[str] = []
    mismatch: list[str] = []
    if now.tzinfo is None or now.utcoffset() != observed.observed_at.utcoffset():
        raise ValueError("UTC_RECONCILIATION_TIME_REQUIRED")
    if expected.account_id != observed.account_id:
        unknown.append("ACCOUNT_IDENTITY_MISMATCH")
    if expected.session_identity_hash != observed.session_identity_hash:
        unknown.append("AUTHENTICATED_SESSION_MISMATCH")
    if observed.mode == "UNKNOWN" or observed.mode != expected.mode:
        unknown.append("ACCOUNT_MODE_MISMATCH")
    if not observed.connected or not observed.complete_account_snapshot:
        unknown.append("COMPLETE_CONNECTED_SNAPSHOT_REQUIRED")
    if not 0 <= (now - observed.observed_at).total_seconds() <= 5:
        unknown.append("FRESH_ACCOUNT_SNAPSHOT_REQUIRED")
    if expected.unresolved_execution_ids:
        mismatch.append("UNRESOLVED_BROKER_ACK_OR_EXECUTION")
    wanted = {(e.exposure.kind, e.exposure.broker_id): e.exposure for e in expected.exposures}
    actual = {(e.kind, e.broker_id): e for e in observed.exposures}
    if actual.keys() - wanted.keys():
        mismatch.append("UNOWNED_ACCOUNT_EXPOSURE")
    if wanted.keys() - actual.keys():
        mismatch.append("EXPECTED_EXPOSURE_MISSING")
    for key in actual.keys() & wanted.keys():
        if actual[key] != wanted[key]:
            mismatch.append("BROKER_VOLUME_SIDE_SYMBOL_OR_PROTECTION_MISMATCH")
    reasons = tuple(dict.fromkeys(unknown + mismatch))
    return ReconciliationResult(
        account_id=expected.account_id,
        state="UNKNOWN"
        if unknown
        else "RECONCILIATION_REQUIRED"
        if mismatch
        else "SNAPSHOT_MATCHED",
        reason_codes=reasons,
        evidence_hash=digest,
    )
