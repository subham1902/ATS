from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from ats.persistence import InsufficientCapitalError, PostgresTransaction, connect_postgres

from tests.integration.persistence.test_capital_reservations import (
    PORTFOLIO_ID,
    account,
    request,
)


def test_concurrent_reservations_cannot_oversubscribe(postgres_dsn: str) -> None:
    psycopg = pytest.importorskip("psycopg")
    setup = psycopg.connect(postgres_dsn)
    try:
        setup.execute("TRUNCATE capital_reservation,portfolio_capital_account CASCADE")
        setup.commit()
        with PostgresTransaction(setup, close_connection=False) as transaction:
            transaction.capital.create_account(account())
    finally:
        setup.close()

    def attempt(index: int) -> str:
        connection = connect_postgres(postgres_dsn)
        try:
            with PostgresTransaction(connection) as transaction:
                transaction.capital.reserve(request(index))
            return "RESERVED"
        except InsufficientCapitalError:
            return "DENIED"

    with ThreadPoolExecutor(max_workers=3) as executor:
        outcomes = tuple(executor.map(attempt, (1, 2, 3)))
    assert outcomes.count("RESERVED") == 2
    assert outcomes.count("DENIED") == 1

    verify = psycopg.connect(postgres_dsn)
    try:
        with PostgresTransaction(verify, close_connection=False) as transaction:
            current = transaction.capital.get_account(PORTFOLIO_ID)
    finally:
        verify.close()
    assert current is not None
    assert current.reserved_capital == Decimal("400000")
    assert current.available_capital == Decimal("100000")
