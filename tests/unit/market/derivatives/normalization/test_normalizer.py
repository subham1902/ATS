from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from ats.market.derivatives.contract_master import (
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
)
from ats.market.derivatives.normalization import (
    ProviderInstrumentRecord,
    ReferenceCheckCode,
    ReferenceInstrumentRecord,
    UnderlyingAlias,
    normalize_contracts,
)

T0 = datetime(2026, 8, 24, tzinfo=UTC)
HASH = "a" * 64


def provider(**changes: object) -> ProviderInstrumentRecord:
    values = {
        "provider": "UPSTOX",
        "provider_instrument_key": "NSE_FO|123",
        "provider_exchange_token": "123",
        "provider_underlying": "NIFTY 50",
        "exchange": "NSE",
        "segment": "FO",
        "trading_symbol": "TEST_ONLY_NIFTY_CE",
        "instrument_type": DerivativeInstrumentType.OPTIDX,
        "expiry": "2026-08-25",
        "strike": Decimal("25000"),
        "option_type": OptionType.CE,
        "lot_size": 65,
        "tick_size": Decimal("0.05"),
        "freeze_quantity": 1800,
        "weekly": True,
        "tradable": True,
        "source_as_of": T0,
        "source_hash": HASH,
    }
    values.update(changes)
    return ProviderInstrumentRecord.model_validate(values)


def reference(**changes: object) -> ReferenceInstrumentRecord:
    values = {
        "reference_id": "NSE_TEST_ONLY_1",
        "exchange": "NSE",
        "segment": "FO",
        "underlying": DerivativeUnderlying.NIFTY,
        "instrument_type": DerivativeInstrumentType.OPTIDX,
        "expiry": "2026-08-25",
        "strike": Decimal("25000"),
        "option_type": OptionType.CE,
        "lot_size": 65,
        "freeze_quantity": 1800,
        "effective_at": T0,
        "source_hash": "b" * 64,
    }
    values.update(changes)
    return ReferenceInstrumentRecord.model_validate(values)


ALIASES = (
    UnderlyingAlias(
        provider_underlying="NIFTY 50", canonical_underlying=DerivativeUnderlying.NIFTY
    ),
)


def test_normalizes_with_provider_alias_outside_canonical_identity() -> None:
    result = normalize_contracts(
        provider_records=(provider(),), reference_records=(reference(),), aliases=ALIASES
    )
    assert not result.issues
    assert result.contracts[0].provider_instrument_key == "NSE_FO|123"
    changed = normalize_contracts(
        provider_records=(provider(provider_exchange_token="reused"),),
        reference_records=(reference(),),
        aliases=ALIASES,
    )
    assert changed.contracts[0].instrument_id == result.contracts[0].instrument_id


def test_normalization_is_deterministic() -> None:
    first = normalize_contracts(
        provider_records=(provider(),), reference_records=(reference(),), aliases=ALIASES
    )
    second = normalize_contracts(
        provider_records=(provider(),), reference_records=(reference(),), aliases=ALIASES
    )
    assert first.model_dump_json() == second.model_dump_json()
    assert first.contracts[0].contract_hash == second.contracts[0].contract_hash


@pytest.mark.parametrize(
    ("field", "value"), (("lot_size", 66), ("freeze_quantity", 1700), ("expiry", "2026-09-01"))
)
def test_critical_reference_mismatch_excludes_contract(field: str, value: object) -> None:
    result = normalize_contracts(
        provider_records=(provider(**{field: value}),),
        reference_records=(reference(),),
        aliases=ALIASES,
    )
    assert not result.contracts
    assert result.issues[0].code is ReferenceCheckCode.REFERENCE_MISMATCH
    assert result.issues[0].fields == (field,)


def test_missing_reference_excludes_contract() -> None:
    result = normalize_contracts(
        provider_records=(provider(),), reference_records=(), aliases=ALIASES
    )
    assert result.issues[0].code is ReferenceCheckCode.REFERENCE_CONTRACT_MISSING


def test_duplicate_provider_identity_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate provider_instrument_key"):
        normalize_contracts(
            provider_records=(provider(), provider()),
            reference_records=(reference(),),
            aliases=ALIASES,
        )


def test_duplicate_canonical_contract_rejected_even_with_new_provider_key() -> None:
    with pytest.raises(ValueError, match="duplicate canonical provider contract"):
        normalize_contracts(
            provider_records=(provider(), provider(provider_instrument_key="NSE_FO|456")),
            reference_records=(reference(),),
            aliases=ALIASES,
        )


def test_banknifty_future_has_no_option_fields_or_synthetic_strike() -> None:
    bank_aliases = (
        UnderlyingAlias(
            provider_underlying="NIFTY BANK",
            canonical_underlying=DerivativeUnderlying.BANKNIFTY,
        ),
    )
    provider_future = provider(
        provider_instrument_key="NSE_FO|BANK-FUT",
        provider_underlying="NIFTY BANK",
        trading_symbol="TEST_ONLY_BANKNIFTY_FUT",
        instrument_type=DerivativeInstrumentType.FUTIDX,
        strike=None,
        option_type=None,
    )
    reference_future = reference(
        reference_id="NSE_TEST_ONLY_BANK_FUT",
        underlying=DerivativeUnderlying.BANKNIFTY,
        instrument_type=DerivativeInstrumentType.FUTIDX,
        strike=None,
        option_type=None,
    )
    result = normalize_contracts(
        provider_records=(provider_future,),
        reference_records=(reference_future,),
        aliases=bank_aliases,
    )
    assert result.contracts[0].underlying is DerivativeUnderlying.BANKNIFTY
    assert result.contracts[0].strike is None
    assert result.contracts[0].option_type is None


def test_provider_alias_change_cannot_change_exchange_authority_values() -> None:
    result = normalize_contracts(
        provider_records=(
            provider(
                provider_exchange_token="EDGE-ALIAS-2",
                trading_symbol="TEST_ONLY_PROVIDER_RENAMED",
            ),
        ),
        reference_records=(reference(),),
        aliases=ALIASES,
    )
    contract = result.contracts[0]
    assert contract.lot_size == 65
    assert contract.freeze_quantity == 1800
    assert contract.provider_exchange_token == "EDGE-ALIAS-2"
