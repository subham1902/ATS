"""Durable runtime projection for a filled position and its immutable entry lineage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from ats.contracts import canonical_sha256
from ats.contracts.domain.models import Fill, Position
from ats.persistence import TransactionManager
from ats.persistence.types import StateSnapshot


class PositionAuthorityIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class PositionAuthorityRecord:
    position: Position
    fills: tuple[Fill, ...]
    entry_candidate_id: UUID
    entry_candidate_hash: str
    entry_context_id: UUID
    entry_context_hash: str
    entry_risk_decision_id: UUID
    entry_risk_decision_hash: str
    entry_token_id: UUID
    entry_order_intent_id: UUID
    entry_order_intent_hash: str
    reservation_id: UUID
    campaign_id: UUID
    campaign_version: int
    entry_system_state_version: int
    constraints_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "position": self.position.model_dump(mode="json"),
            "fills": [item.model_dump(mode="json") for item in self.fills],
            "entry": {
                "candidate_id": str(self.entry_candidate_id),
                "candidate_hash": self.entry_candidate_hash,
                "context_id": str(self.entry_context_id),
                "context_hash": self.entry_context_hash,
                "risk_decision_id": str(self.entry_risk_decision_id),
                "risk_decision_hash": self.entry_risk_decision_hash,
                "token_id": str(self.entry_token_id),
                "order_intent_id": str(self.entry_order_intent_id),
                "order_intent_hash": self.entry_order_intent_hash,
                "reservation_id": str(self.reservation_id),
                "campaign_id": str(self.campaign_id),
                "campaign_version": self.campaign_version,
                "system_state_version": self.entry_system_state_version,
                "constraints_hash": self.constraints_hash,
            },
            "reductions": [],
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> PositionAuthorityRecord:
        try:
            entry = cast(dict[str, Any], payload["entry"])
            return cls(
                position=Position.model_validate_json(json.dumps(payload["position"])),
                fills=tuple(
                    Fill.model_validate_json(json.dumps(item)) for item in payload["fills"]
                ),
                entry_candidate_id=UUID(entry["candidate_id"]),
                entry_candidate_hash=entry["candidate_hash"],
                entry_context_id=UUID(entry["context_id"]),
                entry_context_hash=entry["context_hash"],
                entry_risk_decision_id=UUID(entry["risk_decision_id"]),
                entry_risk_decision_hash=entry["risk_decision_hash"],
                entry_token_id=UUID(entry["token_id"]),
                entry_order_intent_id=UUID(entry["order_intent_id"]),
                entry_order_intent_hash=entry["order_intent_hash"],
                reservation_id=UUID(entry["reservation_id"]),
                campaign_id=UUID(entry["campaign_id"]),
                campaign_version=int(entry["campaign_version"]),
                entry_system_state_version=int(entry["system_state_version"]),
                constraints_hash=entry["constraints_hash"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PositionAuthorityIntegrityError("invalid position authority record") from exc


class PositionAuthorityStore:
    def __init__(self, transactions: TransactionManager) -> None:
        self._transactions = transactions

    def persist_open(self, record: PositionAuthorityRecord) -> None:
        payload = record.payload()
        snapshot = StateSnapshot(
            identifier=str(record.position.position_id),
            version=1,
            state="OPEN",
            payload=payload,
            payload_hash=canonical_sha256(payload),
            updated_at=record.position.updated_at,
            external_state="CONFIRMED",
        )
        with self._transactions.transaction() as transaction:
            transaction.positions.save(snapshot, expected_version=None)

    def recover_open(self) -> tuple[PositionAuthorityRecord, ...]:
        with self._transactions.transaction() as transaction:
            snapshots = transaction.positions.list_by_state("OPEN")
        return tuple(PositionAuthorityRecord.from_payload(item.payload) for item in snapshots)


__all__ = ["PositionAuthorityIntegrityError", "PositionAuthorityRecord", "PositionAuthorityStore"]
