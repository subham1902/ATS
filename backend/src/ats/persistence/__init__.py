"""PostgreSQL evidence store and transactional repository boundary."""

from .errors import (
    DuplicateAggregateSequenceError,
    DuplicateEventIdError,
    DuplicateIdempotencyKeyError,
    IntegrityViolationError,
    PersistenceError,
    TokenConsumeError,
    TransactionConflictError,
    UnsupportedStoredEventError,
)
from .postgres import PostgresTransaction, PostgresTransactionManager, connect_postgres
from .protocols import (
    AdvisoryEvidenceRepository,
    AuditRepository,
    CampaignStateRepository,
    CandidateEvidenceRepository,
    EventStore,
    OrderAuthorityRepository,
    OutboxRepository,
    RiskDecisionEvidenceRepository,
    TokenRepository,
    Transaction,
    TransactionManager,
)
from .types import AuditRecord, EvidenceRecord, OrderAuthorityRecord, StateSnapshot, StoredToken

__all__ = [
    "AdvisoryEvidenceRepository",
    "AuditRecord",
    "AuditRepository",
    "CampaignStateRepository",
    "CandidateEvidenceRepository",
    "DuplicateAggregateSequenceError",
    "DuplicateEventIdError",
    "DuplicateIdempotencyKeyError",
    "EventStore",
    "EvidenceRecord",
    "IntegrityViolationError",
    "OrderAuthorityRecord",
    "OrderAuthorityRepository",
    "OutboxRepository",
    "PersistenceError",
    "PostgresTransaction",
    "PostgresTransactionManager",
    "RiskDecisionEvidenceRepository",
    "StateSnapshot",
    "StoredToken",
    "TokenConsumeError",
    "TokenRepository",
    "Transaction",
    "TransactionConflictError",
    "TransactionManager",
    "UnsupportedStoredEventError",
    "connect_postgres",
]
