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


class CapitalAccountNotFoundError(PersistenceError):
    pass


class InsufficientCapitalError(PersistenceError):
    pass


class CapitalReservationStateError(PersistenceError):
    pass


class DuplicateCapitalReservationError(PersistenceError):
    pass


__all__ = [
    "CapitalAccountNotFoundError",
    "CapitalReservationStateError",
    "DuplicateCapitalReservationError",
    "DuplicateAggregateSequenceError",
    "DuplicateEventIdError",
    "DuplicateIdempotencyKeyError",
    "IntegrityViolationError",
    "InsufficientCapitalError",
    "PersistenceError",
    "TokenConsumeError",
    "TransactionConflictError",
    "UnsupportedStoredEventError",
]
