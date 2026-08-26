"""Provider instrument-key grammar and NIFTY/BANKNIFTY underlying key mapping.

Derivative keys always come from source data (the provider BOD export or the
normalized provider alias); this module only validates their documented
``EXCHANGE_SEGMENT|IDENTIFIER`` grammar. Index keys for the two research
underlyings are public provider endpoint identifiers configured explicitly
here so underlying feeds can be mapped without inventing any market value.
"""

from __future__ import annotations

import re

from ats.contracts.domain.types import NonEmptyStr

from .errors import UpstoxFeedError, UpstoxFeedErrorCode

_KEY_GRAMMAR = re.compile(r"^[A-Z][A-Z0-9_]*\|[^|\s][^|]*$")

NIFTY_INDEX_FEED_KEY = "NSE_INDEX|NIFTY 50"
BANKNIFTY_INDEX_FEED_KEY = "NSE_INDEX|NIFTY BANK"


def validate_feed_key(key: str) -> str:
    if not isinstance(key, str) or _KEY_GRAMMAR.fullmatch(key) is None:
        raise UpstoxFeedError(
            UpstoxFeedErrorCode.MALFORMED_FRAME,
            f"instrument key {key!r} violates the EXCHANGE_SEGMENT|IDENTIFIER grammar",
        )
    return key


def index_feed_key(underlying: NonEmptyStr) -> str:
    """Map an ATS canonical underlying to its public index feed identifier."""

    mapping = {
        "NIFTY": NIFTY_INDEX_FEED_KEY,
        "BANKNIFTY": BANKNIFTY_INDEX_FEED_KEY,
    }
    try:
        return mapping[underlying]
    except KeyError as exc:
        raise UpstoxFeedError(
            UpstoxFeedErrorCode.UNKNOWN_INSTRUMENT_KEY,
            f"no configured feed key for underlying {underlying}",
        ) from exc


def segment_of(key: str) -> str:
    validate_feed_key(key)
    return key.split("|", 1)[0]


__all__ = [
    "BANKNIFTY_INDEX_FEED_KEY",
    "NIFTY_INDEX_FEED_KEY",
    "index_feed_key",
    "segment_of",
    "validate_feed_key",
]
