"""Corrupt durable JSON must never become empty valid state followed by overwrite."""

from pathlib import Path

import pytest
from ats.agents import managed as managed_domain
from ats.agents.roster import Roster
from ats.agents.trade_ledger import UpstoxLiveTradeLedger
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


def test_trade_ledger_preserves_a_corrupt_file_and_does_not_overwrite_it(tmp_path):
    path = tmp_path / "ledger.json"
    path.write_text(CORRUPT, encoding="utf-8")
    ledger = UpstoxLiveTradeLedger(ledger_path=path)
    assert ledger.degraded and ledger.quarantined_to is not None
    ledger._save_to_disk()  # what the next recorded trade would do
    preserved = _preserved(tmp_path)
    assert len(preserved) == 1
    assert preserved[0].read_text(encoding="utf-8") == CORRUPT


def test_trade_ledger_wrong_schema_is_also_preserved(tmp_path):
    path = tmp_path / "ledger.json"
    path.write_text('[{"unexpected": "shape"}]', encoding="utf-8")
    ledger = UpstoxLiveTradeLedger(ledger_path=path)
    assert ledger.degraded
    assert _preserved(tmp_path)[0].read_text(encoding="utf-8") == '[{"unexpected": "shape"}]'


def test_trade_ledger_missing_file_is_a_normal_first_run(tmp_path):
    ledger = UpstoxLiveTradeLedger(ledger_path=tmp_path / "none.json")
    assert not ledger.degraded
    assert _preserved(tmp_path) == []


def test_roster_preserves_a_corrupt_file(tmp_path):
    path = tmp_path / "roster.json"
    path.write_text('{"agents": [ {', encoding="utf-8")
    roster = Roster.load(path)
    assert roster.degraded
    roster.save()
    preserved = _preserved(tmp_path)
    assert len(preserved) == 1
    assert preserved[0].read_text(encoding="utf-8") == '{"agents": [ {'


def test_roster_round_trips_when_healthy(tmp_path):
    path = tmp_path / "roster.json"
    Roster(path=path).save()
    assert path.exists() and not Roster.load(path).degraded


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
