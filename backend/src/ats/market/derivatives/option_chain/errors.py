"""Closed option-chain normalization failures."""

from ats.contracts.enums import ATSStringEnum


class OptionChainErrorCode(ATSStringEnum):
    EMPTY_CHAIN = "EMPTY_CHAIN"
    UNKNOWN_CONTRACT = "UNKNOWN_CONTRACT"
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
    DUPLICATE_QUOTE = "DUPLICATE_QUOTE"
    FUTURE_QUOTE = "FUTURE_QUOTE"
    STALE_QUOTE = "STALE_QUOTE"
    CROSSED_MARKET = "CROSSED_MARKET"
    EXPIRY_TIME_MISMATCH = "EXPIRY_TIME_MISMATCH"
    EXPIRED_CHAIN = "EXPIRED_CHAIN"
    GREEKS_METHOD_MISMATCH = "GREEKS_METHOD_MISMATCH"


class OptionChainError(ValueError):
    def __init__(self, code: OptionChainErrorCode, message: str):
        self.code = code
        super().__init__(f"{code.value}: {message}")


__all__ = ["OptionChainError", "OptionChainErrorCode"]
