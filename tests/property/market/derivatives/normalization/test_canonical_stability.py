"""Canonical identity must be stable across provider token churn.

Provider-internal keys (instrument key + exchange token) are rotation-prone.
The canonical ``instrument_id`` and ``contract_hash`` must depend only on the
real instrument attributes, never on the provider's internal identifiers.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from decimal import Decimal

from ats.market.derivatives.normalization import (
    ProviderInstrumentRecord,
    ReferenceInstrumentRecord,
    UnderlyingAlias,
    normalize_contracts,
)
from ats.market.derivatives.normalization.models import (
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
)

EXPIRY = "2026-08-27"
SOURCE_AS_OF = datetime(2026, 8, 24, 3, 45, tzinfo=UTC)


def _reference() -> ReferenceInstrumentRecord:
    return ReferenceInstrumentRecord(
        reference_id="REF-NIFTY26AUG25000CE",
        exchange="NSE",
        segment="NFO",
        underlying=DerivativeUnderlying.NIFTY,
        instrument_type=DerivativeInstrumentType.OPTIDX,
        expiry=EXPIRY,
        strike=Decimal("25000"),
        option_type=OptionType.CE,
        lot_size=50,
        freeze_quantity=1800,
        effective_at=SOURCE_AS_OF,
        source_hash="b" * 64,
    )


def _provider(*, key: str, token: str) -> ProviderInstrumentRecord:
    return ProviderInstrumentRecord(
        provider="UPSTOX",
        provider_instrument_key=key,
        provider_exchange_token=token,
        provider_underlying="NIFTY",
        exchange="NSE",
        segment="NFO",
        trading_symbol="NIFTY26AUG25000CE",
        instrument_type=DerivativeInstrumentType.OPTIDX,
        expiry=EXPIRY,
        strike=Decimal("25000"),
        option_type=OptionType.CE,
        lot_size=50,
        tick_size=Decimal("0.05"),
        freeze_quantity=1800,
        weekly=True,
        tradable=True,
        source_as_of=SOURCE_AS_OF,
        source_hash="a" * 64,
    )


class TestCanonicalIdentityStability:
    def test_rotating_provider_keys_keep_same_instrument_id(self) -> None:
        rng = random.Random(20260824)
        alias = UnderlyingAlias(
            provider_underlying="NIFTY", canonical_underlying=DerivativeUnderlying.NIFTY
        )
        baseline = None
        for index in range(40):
            key = f"NSE_FO|ROTATED_TOKEN_{index:04d}"
            token = str(rng.randint(100000, 999999))
            result = normalize_contracts(
                provider_records=(_provider(key=key, token=token),),
                reference_records=(_reference(),),
                aliases=(alias,),
            )
            assert result.issues == ()
            instrument_id = result.contracts[0].instrument_id
            if baseline is None:
                baseline = instrument_id
            else:
                assert instrument_id == baseline, f"identity drift at rotation {index}"

    def test_provider_key_token_change_keeps_canonical_id_but_is_provider_scoped(self) -> None:
        rng = random.Random(99)
        alias = UnderlyingAlias(
            provider_underlying="NIFTY", canonical_underlying=DerivativeUnderlying.NIFTY
        )
        baseline_id = None
        seen_hashes = set()
        for _index in range(25):
            result = normalize_contracts(
                provider_records=(
                    _provider(
                        key=f"NSE_FO|K{rng.randint(0, 10**9)}",
                        token=str(rng.randint(0, 10**9)),
                    ),
                ),
                reference_records=(_reference(),),
                aliases=(alias,),
            )
            instrument_id = result.contracts[0].instrument_id
            if baseline_id is None:
                baseline_id = instrument_id
            else:
                assert instrument_id == baseline_id
            seen_hashes.add(result.contracts[0].contract_hash)
        # The provider-scoped hash must vary with the provider key/token.
        assert len(seen_hashes) > 1

    def test_expiry_change_does_change_instrument_id(self) -> None:
        alias = UnderlyingAlias(
            provider_underlying="NIFTY", canonical_underlying=DerivativeUnderlying.NIFTY
        )

        def instrument_id_for(expiry: str) -> str:
            provider = _provider(key="NSE_FO|A", token="1")
            provider = provider.model_copy(update={"expiry": expiry})
            reference = _reference().model_copy(update={"expiry": expiry})
            return (
                normalize_contracts(
                    provider_records=(provider,),
                    reference_records=(reference,),
                    aliases=(alias,),
                )
                .contracts[0]
                .instrument_id
            )

        base = instrument_id_for("2026-08-27")
        other = instrument_id_for("2026-09-24")
        assert base != other
