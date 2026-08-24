from __future__ import annotations

from datetime import datetime
from hashlib import sha256

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.market.derivatives.contract_master import (
    ContractMasterError,
    ContractMasterErrorCode,
    DerivativeInstrument,
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
    normalize_contract_master,
)

from .helpers import ROWS, content, manifest


def test_normalizes_and_orders_deterministically() -> None:
    raw = content(*reversed(ROWS))
    master = normalize_contract_master(manifest=manifest(raw), content=raw)
    assert len(master.instruments) == 3
    assert master.instruments[0].underlying is DerivativeUnderlying.BANKNIFTY
    assert master.payload_hash == compute_payload_hash(master)


def test_model_values_come_from_source_rows() -> None:
    raw = content()
    master = normalize_contract_master(manifest=manifest(raw), content=raw)
    nifty_call = next(item for item in master.instruments if item.option_type is OptionType.CE)
    assert nifty_call.lot_size == 65
    assert str(nifty_call.tick_size) == "0.05"
    assert nifty_call.quantity_freeze_limit == 1800


def test_bad_content_hash_fails_closed() -> None:
    raw = content()
    bad_manifest = manifest(raw).model_copy(update={"content_sha256": "0" * 64})
    with pytest.raises(ContractMasterError) as caught:
        normalize_contract_master(manifest=bad_manifest, content=raw)
    assert caught.value.code is ContractMasterErrorCode.CONTENT_HASH_MISMATCH


@pytest.mark.parametrize(
    ("replacement", "expected"),
    [
        (b",0,0.05,", ContractMasterErrorCode.INVALID_ROW),
        (b",65,0,", ContractMasterErrorCode.INVALID_ROW),
        (b",65,NaN,", ContractMasterErrorCode.INVALID_ROW),
        (b",65,Infinity,", ContractMasterErrorCode.INVALID_ROW),
        (b",65,0.05,1800,YES,", ContractMasterErrorCode.INVALID_ROW),
    ],
)
def test_invalid_authority_values_rejected(
    replacement: bytes, expected: ContractMasterErrorCode
) -> None:
    raw = content(ROWS[0].replace(b",65,0.05,1800,TRUE,", replacement))
    with pytest.raises(ContractMasterError) as caught:
        normalize_contract_master(manifest=manifest(raw), content=raw)
    assert caught.value.code is expected


def test_wrong_header_rejected() -> None:
    raw = content().replace(b"exchange,", b"venue,", 1)
    with pytest.raises(ContractMasterError) as caught:
        normalize_contract_master(manifest=manifest(raw), content=raw)
    assert caught.value.code is ContractMasterErrorCode.INVALID_HEADER


def test_row_count_mismatch_rejected() -> None:
    raw = content()
    bad_manifest = manifest(raw).model_copy(update={"row_count": 99})
    with pytest.raises(ContractMasterError) as caught:
        normalize_contract_master(manifest=bad_manifest, content=raw)
    assert caught.value.code is ContractMasterErrorCode.ROW_COUNT_MISMATCH


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [
        (b",10002,", b",10001,", ContractMasterErrorCode.DUPLICATE_INSTRUMENT_ID),
        (
            b"NIFTY26SEP25000PE",
            b"NIFTY26SEP25000CE",
            ContractMasterErrorCode.DUPLICATE_TRADING_SYMBOL,
        ),
    ],
)
def test_duplicate_identifiers_rejected(
    old: bytes, new: bytes, code: ContractMasterErrorCode
) -> None:
    raw = content(ROWS[0], ROWS[1].replace(old, new))
    with pytest.raises(ContractMasterError) as caught:
        normalize_contract_master(manifest=manifest(raw), content=raw)
    assert caught.value.code is code


def test_duplicate_semantic_contract_rejected() -> None:
    duplicate = ROWS[1].replace(b"25000PE", b"25000PE-ALT").replace(b",10002,", b",10009,")
    duplicate = duplicate.replace(b",PE,", b",CE,")
    raw = content(ROWS[0], duplicate)
    with pytest.raises(ContractMasterError) as caught:
        normalize_contract_master(manifest=manifest(raw), content=raw)
    assert caught.value.code is ContractMasterErrorCode.DUPLICATE_CONTRACT


def test_option_shape_and_expired_tradable_rejected() -> None:
    missing_strike = content(ROWS[0].replace(b",25000,CE,", b",,CE,"))
    with pytest.raises(ContractMasterError):
        normalize_contract_master(manifest=manifest(missing_strike), content=missing_strike)

    expired = content(ROWS[0].replace(b"2026-09-01", b"2026-08-23"))
    with pytest.raises(ContractMasterError):
        normalize_contract_master(manifest=manifest(expired), content=expired)


def test_futures_cannot_carry_option_fields() -> None:
    malformed = content(ROWS[2].replace(b"2026-09-29,,,", b"2026-09-29,55000,CE,"))
    with pytest.raises(ContractMasterError):
        normalize_contract_master(manifest=manifest(malformed), content=malformed)


def test_strict_models_reject_extra_and_naive_time() -> None:
    raw = content()
    instrument = normalize_contract_master(manifest=manifest(raw), content=raw).instruments[0]
    with pytest.raises(ValueError):
        DerivativeInstrument(**instrument.model_dump(), unexpected=True)
    with pytest.raises(ValueError):
        manifest(raw, as_of=datetime(2026, 8, 24))


def test_input_bytes_are_not_modified() -> None:
    raw = content()
    before = sha256(raw).hexdigest()
    normalize_contract_master(manifest=manifest(raw), content=raw)
    assert sha256(raw).hexdigest() == before


def test_current_scope_rejects_non_nse_and_unknown_products() -> None:
    wrong_exchange = content(ROWS[0].replace(b"NSE,NFO", b"BSE,BFO"))
    with pytest.raises(ContractMasterError):
        normalize_contract_master(manifest=manifest(wrong_exchange), content=wrong_exchange)
    unknown_product = content(ROWS[0].replace(b",OPTIDX,", b",OPTSTK,"))
    with pytest.raises(ContractMasterError):
        normalize_contract_master(manifest=manifest(unknown_product), content=unknown_product)


def test_futures_shape_is_supported() -> None:
    raw = content(ROWS[2])
    future = normalize_contract_master(manifest=manifest(raw), content=raw).instruments[0]
    assert future.instrument_type is DerivativeInstrumentType.FUTIDX
    assert future.strike is None
    assert future.option_type is None
