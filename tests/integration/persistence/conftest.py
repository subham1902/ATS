from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from ats.persistence.migrations import apply_migrations

DSN_VARIABLE = "ATS_TEST_POSTGRES_DSN"
MIGRATIONS = Path(__file__).parents[3] / "backend" / "migrations"


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    dsn = os.environ.get(DSN_VARIABLE)
    if dsn is None:
        pytest.skip(f"{DSN_VARIABLE} is required for PostgreSQL integration tests")
    return dsn


@pytest.fixture(scope="session", autouse=True)
def migrated_database(postgres_dsn: str) -> None:
    psycopg = pytest.importorskip("psycopg")
    connection = psycopg.connect(postgres_dsn)
    try:
        apply_migrations(connection, MIGRATIONS)
    finally:
        connection.close()


@pytest.fixture()
def pg_connection(postgres_dsn: str, migrated_database: None) -> Iterator[Any]:
    psycopg = pytest.importorskip("psycopg")
    connection = psycopg.connect(postgres_dsn)
    tables = (
        "capital_reservation",
        "portfolio_capital_account",
        "outbox_records",
        "position_reduction_authority_evidence",
        "order_authority_evidence",
        "autonomy_token_state",
        "event_records",
        "candidate_evidence",
        "risk_decision_evidence",
        "advisory_evidence",
        "campaign_state",
        "position_state",
        "audit_records",
    )
    connection.execute(f"TRUNCATE {','.join(tables)} CASCADE")
    connection.commit()
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()
