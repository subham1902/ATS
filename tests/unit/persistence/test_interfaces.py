from __future__ import annotations

from pathlib import Path

import pytest
from ats.events import ExternalSubmissionState, OutboxState
from ats.persistence.migrations import migration_files, validate_migration_names
from ats.persistence.protocols import (
    AuditRepository,
    CampaignStateRepository,
    CandidateEvidenceRepository,
    EventStore,
    OrderAuthorityRepository,
    OutboxRepository,
    TokenRepository,
)
from ats.portfolio.persistence import PositionRepository


def test_explicit_durable_states_include_unknown_submission() -> None:
    assert tuple(OutboxState) == (
        OutboxState.PENDING,
        OutboxState.DISPATCHING,
        OutboxState.DISPATCHED,
        OutboxState.FAILED,
    )
    assert ExternalSubmissionState.UNKNOWN.value == "UNKNOWN"


def test_repositories_are_narrow_protocols() -> None:
    protocols = (
        EventStore,
        OutboxRepository,
        TokenRepository,
        CampaignStateRepository,
        PositionRepository,
        CandidateEvidenceRepository,
        OrderAuthorityRepository,
        AuditRepository,
    )
    assert all(getattr(protocol, "_is_protocol", False) for protocol in protocols)


def test_migration_discovery_is_deterministic() -> None:
    directory = Path("backend/migrations")
    paths = migration_files(directory)
    validate_migration_names(paths)
    assert [path.name for path in paths] == [
        "0001_iba_r17_evidence_store.sql",
        "0002_portfolio_capital_reservations.sql",
        "0003_position_reduction_authority_evidence.sql",
    ]


def test_duplicate_migration_versions_rejected(tmp_path: Path) -> None:
    paths = (tmp_path / "0001_a.sql", tmp_path / "0001_b.sql")
    with pytest.raises(ValueError, match="duplicate"):
        validate_migration_names(paths)
