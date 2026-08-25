"""Frozen classification of hot-memory, pre-action durability, and audit transitions."""

from __future__ import annotations

from enum import StrEnum

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain.types import NonEmptyStr


class RuntimeTransition(StrEnum):
    MARKET_STATE_UPDATE = "MARKET_STATE_UPDATE"
    CANDIDATE = "CANDIDATE"
    A04_DECISION = "A04_DECISION"
    CAPITAL_RESERVATION = "CAPITAL_RESERVATION"
    TOKEN_CONSUMPTION = "TOKEN_CONSUMPTION"
    ORDER_SUBMISSION_START = "ORDER_SUBMISSION_START"
    BROKER_ACKNOWLEDGEMENT = "BROKER_ACKNOWLEDGEMENT"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILL = "FILL"
    CANCEL = "CANCEL"
    REJECTION = "REJECTION"
    KILL_SWITCH = "KILL_SWITCH"
    SESSION_HALT = "SESSION_HALT"


class DurabilityRequirement(StrEnum):
    HOT_MEMORY_ONLY_ALLOWED = "HOT_MEMORY_ONLY_ALLOWED"
    MINIMAL_DURABILITY_REQUIRED_BEFORE_EXTERNAL_ACTION = (
        "MINIMAL_DURABILITY_REQUIRED_BEFORE_EXTERNAL_ACTION"
    )


class DurabilityClassification(ATSBaseModel):
    transition: RuntimeTransition
    requirement: DurabilityRequirement
    async_full_audit_allowed: bool
    reconstruction_source: NonEmptyStr


def execution_durability_matrix() -> tuple[DurabilityClassification, ...]:
    memory_only = {
        RuntimeTransition.MARKET_STATE_UPDATE,
        RuntimeTransition.CANDIDATE,
    }
    return tuple(
        DurabilityClassification(
            transition=transition,
            requirement=(
                DurabilityRequirement.HOT_MEMORY_ONLY_ALLOWED
                if transition in memory_only
                else DurabilityRequirement.MINIMAL_DURABILITY_REQUIRED_BEFORE_EXTERNAL_ACTION
            ),
            async_full_audit_allowed=True,
            reconstruction_source=(
                "MARKET_SOURCE_REPLAY"
                if transition is RuntimeTransition.MARKET_STATE_UPDATE
                else "DETERMINISTIC_RECOMPUTATION"
                if transition is RuntimeTransition.CANDIDATE
                else "R17_TRANSACTIONAL_EVIDENCE"
            ),
        )
        for transition in RuntimeTransition
    )


__all__ = [
    "DurabilityClassification",
    "DurabilityRequirement",
    "RuntimeTransition",
    "execution_durability_matrix",
]
