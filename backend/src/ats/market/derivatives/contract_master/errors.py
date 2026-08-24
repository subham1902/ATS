"""Closed contract-master failure taxonomy."""

from __future__ import annotations

from ats.contracts.enums import ATSStringEnum


class ContractMasterErrorCode(ATSStringEnum):
    CONTENT_HASH_MISMATCH = "CONTENT_HASH_MISMATCH"
    INVALID_ENCODING = "INVALID_ENCODING"
    INVALID_HEADER = "INVALID_HEADER"
    INVALID_ROW = "INVALID_ROW"
    ROW_COUNT_MISMATCH = "ROW_COUNT_MISMATCH"
    DUPLICATE_INSTRUMENT_ID = "DUPLICATE_INSTRUMENT_ID"
    DUPLICATE_TRADING_SYMBOL = "DUPLICATE_TRADING_SYMBOL"
    DUPLICATE_CONTRACT = "DUPLICATE_CONTRACT"
    PAYLOAD_HASH_MISMATCH = "PAYLOAD_HASH_MISMATCH"
    FUTURE_MASTER = "FUTURE_MASTER"
    STALE_MASTER = "STALE_MASTER"


class ContractMasterError(ValueError):
    """Explicit fail-closed normalization or use error."""

    def __init__(
        self, code: ContractMasterErrorCode, message: str, *, row_number: int | None = None
    ):
        self.code = code
        self.row_number = row_number
        location = "" if row_number is None else f" at row {row_number}"
        super().__init__(f"{code.value}{location}: {message}")


__all__ = ["ContractMasterError", "ContractMasterErrorCode"]
