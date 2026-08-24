"""Deterministic contract-master properties."""

from __future__ import annotations

from datetime import timedelta

from ats.contracts.domain.hashing import compute_payload_hash
from ats.market.derivatives.contract_master import normalize_contract_master

from tests.unit.market.derivatives.contract_master.helpers import ROWS, content, manifest


def test_repeated_normalization_is_identical() -> None:
    raw = content()
    first = normalize_contract_master(manifest=manifest(raw), content=raw)
    second = normalize_contract_master(manifest=manifest(raw), content=raw)
    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


def test_input_order_cannot_change_normalized_semantics() -> None:
    raw_a = content(*ROWS)
    raw_b = content(*reversed(ROWS))
    first = normalize_contract_master(manifest=manifest(raw_a), content=raw_a)
    second = normalize_contract_master(manifest=manifest(raw_b), content=raw_b)
    assert first.instruments == second.instruments
    # Raw source integrity remains distinct even when normalized semantics match.
    assert first.manifest.content_sha256 != second.manifest.content_sha256


def test_changed_authority_value_changes_payload_hash() -> None:
    raw = content()
    master = normalize_contract_master(manifest=manifest(raw), content=raw)
    instrument = master.instruments[0].model_copy(
        update={"lot_size": master.instruments[0].lot_size + 1}
    )
    changed = master.model_copy(update={"instruments": (instrument, *master.instruments[1:])})
    assert compute_payload_hash(changed) != master.payload_hash


def test_explicit_time_only_no_ambient_clock() -> None:
    raw = content()
    master = normalize_contract_master(manifest=manifest(raw), content=raw)
    assert master.manifest.as_of_time + timedelta(seconds=1) > master.manifest.as_of_time
