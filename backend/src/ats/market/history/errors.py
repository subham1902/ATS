"""Closed historical-truth failure taxonomy for as-of information gating."""

from __future__ import annotations

from ats.contracts.enums import ATSStringEnum


class HistoricalTruthErrorCode(ATSStringEnum):
    """Deterministic failure codes guarding genuine information availability."""

    BAD_TIME_SEMANTICS = "BAD_TIME_SEMANTICS"
    UNREALISTIC_SAME_BAR_AVAILABILITY = "UNREALISTIC_SAME_BAR_AVAILABILITY"
    DUPLICATE_OBSERVATION_IDENTITY = "DUPLICATE_OBSERVATION_IDENTITY"
    CONFLICTING_OBSERVATION_KEYS = "CONFLICTING_OBSERVATION_KEYS"
    MISSING_INTERVAL = "MISSING_INTERVAL"
    INVALID_OHLC = "INVALID_OHLC"
    CROSSED_QUOTE = "CROSSED_QUOTE"
    LOCKED_QUOTE = "LOCKED_QUOTE"
    INVALID_EXPIRY_RELATIONSHIP = "INVALID_EXPIRY_RELATIONSHIP"
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
    STALE_OBSERVATION = "STALE_OBSERVATION"
    SUPERSEDED_TARGET_MISSING = "SUPERSEDED_TARGET_MISSING"
    REVISION_ORDER_INVALID = "REVISION_ORDER_INVALID"
    REVISION_IDENTITY_MISMATCH = "REVISION_IDENTITY_MISMATCH"
    REVISION_CYCLE = "REVISION_CYCLE"
    PAYLOAD_HASH_MISMATCH = "PAYLOAD_HASH_MISMATCH"
    FUTURE_INFORMATION_NOT_AVAILABLE = "FUTURE_INFORMATION_NOT_AVAILABLE"
    HISTORY_REPLAY_MISALIGNED = "HISTORY_REPLAY_MISALIGNED"


class HistoricalTruthError(ValueError):
    """Explicit fail-closed historical-truth violation."""

    def __init__(self, code: HistoricalTruthErrorCode, message: str) -> None:
        self.code = code
        super().__init__(f"{code.value}: {message}")


class FutureInformationError(HistoricalTruthError):
    """Raised when a consumer requests information not yet available at time T."""


__all__ = ["FutureInformationError", "HistoricalTruthError", "HistoricalTruthErrorCode"]
