"""Closed strike-window selection failures."""

from ats.contracts.enums import ATSStringEnum


class StrikeWindowErrorCode(ATSStringEnum):
    MALFORMED_EXPIRY = "MALFORMED_EXPIRY"
    EXPIRED_WINDOW = "EXPIRED_WINDOW"
    NO_LISTED_STRIKES = "NO_LISTED_STRIKES"
    INSUFFICIENT_PAIRED_STRIKES = "INSUFFICIENT_PAIRED_STRIKES"
    DUPLICATE_CONTRACT_SIDE = "DUPLICATE_CONTRACT_SIDE"
    MASTER_VALIDATION_FAILED = "MASTER_VALIDATION_FAILED"


class StrikeWindowError(ValueError):
    """Explicit fail-closed strike-window construction error."""

    def __init__(self, code: StrikeWindowErrorCode, message: str):
        self.code = code
        super().__init__(f"{code.value}: {message}")


__all__ = ["StrikeWindowError", "StrikeWindowErrorCode"]
