"""Transactional account registry and redacted account administration audit."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from ats.market.metatrader.accounts import MetaTraderAccount
from ats.market.metatrader.control_config import AccountControlConfig


class AccountRegistry:
    def __init__(self, root: Path) -> None:
        self.path = root / "accounts.sqlite3"
        root.mkdir(parents=True, exist_ok=True)
        with self._transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, "
                "terminal_key TEXT UNIQUE, record TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS control_configs (account_id TEXT NOT NULL, "
                "revision INTEGER NOT NULL, document TEXT NOT NULL, "
                "PRIMARY KEY(account_id,revision))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS audit (sequence INTEGER PRIMARY KEY, "
                "account_id TEXT NOT NULL, action TEXT NOT NULL, occurred_at TEXT NOT NULL)"
            )

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def terminal_key(account: MetaTraderAccount) -> str | None:
        if account.platform == "MT4" or account.terminal_path is None:
            return None
        return str(Path(account.terminal_path).resolve()).casefold()

    def save(self, account: MetaTraderAccount, action: str) -> None:
        record = account.model_dump(mode="json")
        record["credential_reference"] = account.credential_reference
        with self._transaction() as db:
            try:
                db.execute(
                    "INSERT INTO accounts VALUES (?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET record=excluded.record",
                    (account.account_id, self.terminal_key(account), json.dumps(record)),
                )
            except sqlite3.IntegrityError:
                raise ValueError("TERMINAL_ALREADY_ASSIGNED_TO_ANOTHER_ACCOUNT") from None
            db.execute(
                "INSERT INTO audit (account_id, action, occurred_at) VALUES (?, ?, ?)",
                (account.account_id, action, datetime.now(UTC).isoformat()),
            )

    def list(self) -> tuple[MetaTraderAccount, ...]:
        with self._transaction() as db:
            rows = db.execute("SELECT record FROM accounts ORDER BY id").fetchall()
        return tuple(MetaTraderAccount.model_validate_json(row[0]) for row in rows)

    def get(self, account_id: str) -> MetaTraderAccount:
        with self._transaction() as db:
            row = db.execute("SELECT record FROM accounts WHERE id=?", (account_id,)).fetchone()
        if row is None:
            raise KeyError("ACCOUNT_NOT_FOUND")
        return MetaTraderAccount.model_validate_json(row[0])

    def control_config(self, account_id: str) -> AccountControlConfig | None:
        self.get(account_id)
        with self._transaction() as db:
            row = db.execute(
                "SELECT document FROM control_configs WHERE account_id=? "
                "ORDER BY revision DESC LIMIT 1",
                (account_id,),
            ).fetchone()
        return AccountControlConfig.model_validate_json(row[0]) if row else None

    def configure(
        self, account_id: str, config: AccountControlConfig, expected_revision: int
    ) -> None:
        with self._transaction() as db:
            row = db.execute("SELECT record FROM accounts WHERE id=?", (account_id,)).fetchone()
            if row is None:
                raise KeyError("ACCOUNT_NOT_FOUND")
            latest = (
                db.execute(
                    "SELECT MAX(revision) FROM control_configs WHERE account_id=?", (account_id,)
                ).fetchone()[0]
                or 0
            )
            if latest != expected_revision or config.revision != latest + 1:
                raise ValueError("CONFIGURATION_REVISION_CONFLICT")
            account = MetaTraderAccount.model_validate_json(row[0])
            account = account.model_copy(
                update={
                    "allowed_strategy_ids": tuple(
                        a.strategy_id for a in config.assignments if a.enabled
                    ),
                    "risk_profile_id": f"{account_id}:risk:{config.revision}",
                    "execution_enabled": False,
                    "updated_at": datetime.now(UTC),
                }
            )
            record = account.model_dump(mode="json")
            record["credential_reference"] = account.credential_reference
            db.execute(
                "INSERT INTO control_configs VALUES (?,?,?)",
                (account_id, config.revision, config.model_dump_json()),
            )
            db.execute("UPDATE accounts SET record=? WHERE id=?", (json.dumps(record), account_id))
            db.execute(
                "INSERT INTO audit(account_id,action,occurred_at) VALUES (?,?,?)",
                (
                    account_id,
                    f"CONFIGURATION_REVISION_{config.revision}",
                    datetime.now(UTC).isoformat(),
                ),
            )
