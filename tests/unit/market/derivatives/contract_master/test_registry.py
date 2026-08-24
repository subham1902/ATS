from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from ats.market.derivatives.contract_master import (
    ContractMasterError,
    ContractMasterErrorCode,
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
    normalize_contract_master,
    select_tradable_contracts,
    validate_master_for_use,
)

from .helpers import content, manifest


def test_selects_long_option_universe_by_explicit_metadata() -> None:
    raw = content()
    master = normalize_contract_master(manifest=manifest(raw), content=raw)
    selected = select_tradable_contracts(
        master,
        evaluation_time=master.manifest.as_of_time,
        maximum_age_ms=1,
        underlying=DerivativeUnderlying.NIFTY,
        instrument_type=DerivativeInstrumentType.OPTIDX,
        option_type=OptionType.CE,
    )
    assert len(selected) == 1
    assert selected[0].option_type is OptionType.CE


def test_stale_future_and_tampered_master_fail_closed() -> None:
    raw = content()
    master = normalize_contract_master(manifest=manifest(raw), content=raw)
    with pytest.raises(ContractMasterError) as stale:
        validate_master_for_use(
            master,
            evaluation_time=master.manifest.as_of_time + timedelta(milliseconds=2),
            maximum_age_ms=1,
        )
    assert stale.value.code is ContractMasterErrorCode.STALE_MASTER

    with pytest.raises(ContractMasterError) as future:
        validate_master_for_use(
            master,
            evaluation_time=master.manifest.as_of_time - timedelta(microseconds=1),
            maximum_age_ms=1,
        )
    assert future.value.code is ContractMasterErrorCode.FUTURE_MASTER

    tampered = master.model_copy(update={"instruments": tuple(reversed(master.instruments))})
    with pytest.raises(ContractMasterError) as changed:
        validate_master_for_use(
            tampered,
            evaluation_time=master.manifest.as_of_time,
            maximum_age_ms=1,
        )
    assert changed.value.code is ContractMasterErrorCode.PAYLOAD_HASH_MISMATCH


@pytest.mark.parametrize("maximum_age_ms", [0, -1, True])
def test_invalid_freshness_configuration_rejected(maximum_age_ms: int) -> None:
    raw = content()
    master = normalize_contract_master(manifest=manifest(raw), content=raw)
    with pytest.raises(ValueError):
        validate_master_for_use(
            master,
            evaluation_time=datetime(2026, 8, 24, 3, 30, tzinfo=UTC),
            maximum_age_ms=maximum_age_ms,
        )
