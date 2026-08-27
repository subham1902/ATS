"""Closed Upstox V3 market-data feed failures."""

from ats.contracts.enums import ATSStringEnum


class UpstoxFeedErrorCode(ATSStringEnum):
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    NOT_CONNECTED = "NOT_CONNECTED"
    ALREADY_CONNECTED = "ALREADY_CONNECTED"
    EMPTY_SUBSCRIPTION = "EMPTY_SUBSCRIPTION"
    UNKNOWN_INSTRUMENT_KEY = "UNKNOWN_INSTRUMENT_KEY"
    DUPLICATE_INSTRUMENT_KEY = "DUPLICATE_INSTRUMENT_KEY"
    MALFORMED_FRAME = "MALFORMED_FRAME"
    PROTOBUF_DECODER_REQUIRED = "PROTOBUF_DECODER_REQUIRED"
    UNSUPPORTED_MODE = "UNSUPPORTED_MODE"
    CONNECTION_CLOSED = "CONNECTION_CLOSED"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    RECEIVE_TIMEOUT = "RECEIVE_TIMEOUT"
    RESYNC_INCOMPLETE = "RESYNC_INCOMPLETE"
    RECONCILIATION_GAP = "RECONCILIATION_GAP"


class UpstoxFeedError(RuntimeError):
    """Explicit feed failure whose text never carries credentials or raw payloads."""

    def __init__(self, code: UpstoxFeedErrorCode, message: str):
        self.code = code
        super().__init__(f"{code.value}: {message}")


__all__ = ["UpstoxFeedError", "UpstoxFeedErrorCode"]
