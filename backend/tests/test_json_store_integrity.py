"""Corrupt durable JSON must never become empty valid state followed by overwrite."""

from pathlib import Path

import pytest
from ats.agents import managed as managed_domain
from ats.persistence import json_files

CORRUPT = '[{"trade_id": "t1", "pnl": 12.5},\n {"trade_id": "t2" "pnl": }'  # truncated / invalid


def _preserved(directory: Path) -> list[Path]:
    return [p for p in directory.iterdir() if ".corrupt-" in p.name]


def test_read_json_or_quarantine_outcomes(tmp_path):
    path = tmp_path / "s.json"
    assert json_files.read_json_or_quarantine(path).missing
    path.write_text('{"a": 1}', encoding="utf-8")
    assert json_files.read_json_or_quarantine(path).data == {"a": 1}
    path.write_text(CORRUPT, encoding="utf-8")
    bad = json_files.read_json_or_quarantine(path)
    assert bad.degraded and not bad.blocked and bad.quarantined_to is not None
    assert not path.exists()
    assert bad.quarantined_to.read_text(encoding="utf-8") == CORRUPT


def test_unmovable_corrupt_file_blocks_saves_instead_of_overwriting(tmp_path, monkeypatch):
    path = tmp_path / "managed.json"
    path.write_text(CORRUPT, encoding="utf-8")

    def refuse(*_a, **_k):
        raise PermissionError("locked")

    monkeypatch.setattr(json_files.os, "replace", refuse)
    store = managed_domain.ManagedAgentStore(path=path)
    assert store.degraded and store.quarantined_to is None
    store.create(name="Fresh")  # in-memory only; the save must be refused
    assert path.read_text(encoding="utf-8") == CORRUPT


@pytest.mark.parametrize("payload", ['{"agents": "nope"}', '{"agents": [{"bad": 1}]}'])
def test_managed_store_schema_mismatch_is_preserved(tmp_path, payload):
    path = tmp_path / "managed.json"
    path.write_text(payload, encoding="utf-8")
    store = managed_domain.ManagedAgentStore(path=path)
    assert store.degraded
    assert _preserved(tmp_path)[0].read_text(encoding="utf-8") == payload
