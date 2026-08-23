"""Machine-readable M0.8 catalogue-row and concrete-field coverage evidence."""

from __future__ import annotations

import json
from pathlib import Path

from ats.contracts.domain import DOMAIN_CONTRACTS

MANIFEST_PATH = Path(__file__).with_name("field_coverage.json")


def test_field_coverage_manifest_matches_models() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = manifest["contracts"]
    assert set(entries) == {contract.__name__ for contract in DOMAIN_CONTRACTS}
    for contract in DOMAIN_CONTRACTS:
        entry = entries[contract.__name__]
        assert entry["concrete_fields"] == list(contract.model_fields)


def test_all_catalogue_rows_and_concrete_fields_are_accounted_for() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = manifest["contracts"].values()
    assert sum(entry["catalogue_rows"] for entry in entries) == 274
    assert sum(len(entry["concrete_fields"]) for entry in entries) == 307
    for entry in entries:
        compound_expansion = sum(len(fields) - 1 for fields in entry["compound_rows"].values())
        assert entry["catalogue_rows"] + compound_expansion == len(entry["concrete_fields"])
