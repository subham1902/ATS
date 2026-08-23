"""Stable string-enum convention for ATS contracts.

Domain enum members are intentionally deferred to their owning A02 contracts.
"""

from enum import StrEnum


class ATSStringEnum(StrEnum):
    """Base for closed enums whose durable representation is their string value."""


__all__ = ["ATSStringEnum"]
