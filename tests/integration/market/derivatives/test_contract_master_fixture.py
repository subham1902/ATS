from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from ats.market.derivatives.contract_master import (
    ContractMasterManifest,
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
    normalize_contract_master,
    select_tradable_contracts,
)

FIXTURE = Path(__file__).parent / "fixtures" / "nse_index_derivatives_20260824.csv"
FIXTURE_SHA256 = "666d290cef9bae1944afb0d77283688a9b679bcb9d1d91ec30f1690b107b3b9e"


def test_nse_reference_fixture_supports_target_universe() -> None:
    raw = FIXTURE.read_bytes()
    assert sha256(raw).hexdigest() == FIXTURE_SHA256
    manifest = ContractMasterManifest(
        schema_version="1.0",
        master_id=UUID("00000000-0000-0000-0000-000000000601"),
        master_version="NSE-20260824",
        source="NSE_CONTRACT_EXPORT_TEST_FIXTURE",
        as_of_time=datetime(2026, 8, 24, 3, 30, tzinfo=UTC),
        row_count=6,
        content_sha256=sha256(raw).hexdigest(),
    )
    master = normalize_contract_master(manifest=manifest, content=raw)
    for underlying in DerivativeUnderlying:
        for option_type in OptionType:
            selected = select_tradable_contracts(
                master,
                evaluation_time=manifest.as_of_time,
                maximum_age_ms=1,
                underlying=underlying,
                instrument_type=DerivativeInstrumentType.OPTIDX,
                option_type=option_type,
            )
            assert len(selected) == 1
    assert {
        item.lot_size
        for item in master.instruments
        if item.underlying is DerivativeUnderlying.NIFTY
    } == {65}
    assert {
        item.lot_size
        for item in master.instruments
        if item.underlying is DerivativeUnderlying.BANKNIFTY
    } == {30}
