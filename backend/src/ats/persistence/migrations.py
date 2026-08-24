"""Minimal deterministic PostgreSQL migration runner."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .protocols import Connection


def migration_files(directory: Path) -> tuple[Path, ...]:
    return tuple(sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql")))


def apply_migrations(connection: Connection, directory: Path) -> tuple[str, ...]:
    """Apply every unapplied migration atomically, returning applied versions."""

    cursor = connection.cursor()
    applied_now: list[str] = []
    try:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version text PRIMARY KEY, "
            "applied_at timestamptz NOT NULL DEFAULT clock_timestamp())"
        )
        cursor.execute("SELECT version FROM schema_migrations")
        applied = {str(row[0]) for row in cursor.fetchall()}
        for path in migration_files(directory):
            version = path.name.split("_", 1)[0]
            if version in applied:
                continue
            cursor.execute(path.read_text(encoding="utf-8"))
            cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            applied_now.append(version)
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        cursor.close()
    return tuple(applied_now)


def validate_migration_names(paths: Iterable[Path]) -> None:
    versions = [path.name.split("_", 1)[0] for path in paths]
    if len(versions) != len(set(versions)):
        raise ValueError("duplicate migration version")
    if any(len(version) != 4 or not version.isdecimal() for version in versions):
        raise ValueError("migration versions must contain four decimal digits")


__all__ = ["apply_migrations", "migration_files", "validate_migration_names"]
