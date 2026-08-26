"""Real PostgreSQL recovery for additive runtime position authority evidence."""

from __future__ import annotations

from uuid import UUID

from ats.persistence import connect_postgres
from ats.persistence.postgres import PostgresTransactionManager
from ats.trading_runtime.position_authority import PositionAuthorityRecord, PositionAuthorityStore

from tests.unit.contracts.domain.fixtures import make_contracts

pytest_plugins = ("tests.integration.persistence.conftest",)


def _record() -> PositionAuthorityRecord:
    values = make_contracts()
    return PositionAuthorityRecord(
        position=values["Position"],
        fills=(values["Fill"],),
        entry_candidate_id=UUID("80000000-0000-0000-0000-000000000001"),
        entry_candidate_hash="a" * 64,
        entry_context_id=UUID("80000000-0000-0000-0000-000000000002"),
        entry_context_hash="b" * 64,
        entry_risk_decision_id=UUID("80000000-0000-0000-0000-000000000003"),
        entry_risk_decision_hash="c" * 64,
        entry_token_id=UUID("80000000-0000-0000-0000-000000000004"),
        entry_order_intent_id=UUID("80000000-0000-0000-0000-000000000005"),
        entry_order_intent_hash="d" * 64,
        reservation_id=UUID("80000000-0000-0000-0000-000000000006"),
        campaign_id=UUID("80000000-0000-0000-0000-000000000007"),
        campaign_version=1,
        entry_system_state_version=1,
        constraints_hash="e" * 64,
    )


def test_position_authority_record_recovers_from_real_postgres(
    postgres_dsn: str, pg_connection: object
) -> None:
    _ = pg_connection
    manager = PostgresTransactionManager(lambda: connect_postgres(postgres_dsn))
    store = PositionAuthorityStore(manager)
    record = _record()
    store.persist_open(record)
    recovered = store.recover_open()
    assert len(recovered) == 1
    assert recovered[0].position.position_id == record.position.position_id
    assert recovered[0].entry_order_intent_hash == record.entry_order_intent_hash
    assert recovered[0].fills[0].fill_id == record.fills[0].fill_id
