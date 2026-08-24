"""Stable persistence boundary errors."""


class PersistenceError(RuntimeError):
    """Base persistence failure."""


class DuplicateEventIdError(PersistenceError):
    pass


class DuplicateAggregateSequenceError(PersistenceError):
    pass


class DuplicateIdempotencyKeyError(PersistenceError):
    pass


class IntegrityViolationError(PersistenceError):
    pass


class UnsupportedStoredEventError(PersistenceError):
    pass


class TransactionConflictError(PersistenceError):
    pass


class TokenConsumeError(PersistenceError):
    pass


__all__ = [
    "DuplicateAggregateSequenceError",
    "DuplicateEventIdError",
    "DuplicateIdempotencyKeyError",
    "IntegrityViolationError",
    "PersistenceError",
    "TokenConsumeError",
    "TransactionConflictError",
    "UnsupportedStoredEventError",
]
