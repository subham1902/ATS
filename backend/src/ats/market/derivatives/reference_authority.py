"""Fail-closed derivative reference authority over provider-derived contract evidence."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid5

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import NonEmptyStr, PositiveDecimal, PositiveInt, Sha256
from ats.contracts.hashing import canonical_sha256

from .active_window import ActiveOptionWindow, ActiveWindowPolicy, build_active_option_window
from .contract_master import (
    ContractMaster,
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
    select_nearest_expiry,
    validate_master_for_use,
)
from .normalization import NormalizedDerivativeContract, ProviderInstrumentRecord

_SPEC_NAMESPACE = UUID("76664021-6112-5c6d-96bc-e343957849ac")
_PROVIDER_CONTRACT_NAMESPACE = UUID("9db40a8c-7562-5651-9c1e-95bd174624b5")


class DerivativeInstrumentSpec(ATSBaseModel):
    schema_version: Literal["1.0"]
    instrument_spec_id: UUID
    instrument_key: NonEmptyStr
    exchange: NonEmptyStr
    segment: NonEmptyStr
    underlying: DerivativeUnderlying
    instrument_type: DerivativeInstrumentType
    option_type: OptionType | None
    strike: PositiveDecimal | None
    expiry: NonEmptyStr
    lot_size: PositiveInt
    tick_size: PositiveDecimal
    trading_symbol: NonEmptyStr
    freeze_quantity: PositiveInt | None
    source: NonEmptyStr
    source_as_of: UTCDateTime
    retrieved_at: UTCDateTime
    freshness: Literal["FRESH"]
    provenance_hash: Sha256
    payload_hash: Sha256


class InstrumentReferenceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Derivative reference unavailable: {code}")


class InstrumentReferenceAuthority:
    def __init__(
        self,
        *,
        contracts: tuple[NormalizedDerivativeContract, ...],
        retrieved_at: UTCDateTime,
        maximum_age: timedelta,
    ) -> None:
        if maximum_age.total_seconds() <= 0:
            raise ValueError("maximum_age must be positive")
        self._contracts = contracts
        self._retrieved_at = retrieved_at
        self._maximum_age = maximum_age
        self._by_key = {item.provider_instrument_key: item for item in contracts}
        if len(self._by_key) != len(contracts):
            raise InstrumentReferenceError("DUPLICATE_INSTRUMENT_KEY")

    @property
    def contracts(self) -> tuple[NormalizedDerivativeContract, ...]:
        """Return the immutable provider-normalized reference set."""
        return self._contracts

    def resolve(self, instrument_key: str, *, as_of: UTCDateTime) -> DerivativeInstrumentSpec:
        try:
            contract = self._by_key[instrument_key]
        except KeyError as error:
            raise InstrumentReferenceError("INSTRUMENT_NOT_LISTED") from error
        if contract.source_as_of > as_of or self._retrieved_at > as_of:
            raise InstrumentReferenceError("REFERENCE_FROM_FUTURE")
        if as_of - contract.source_as_of > self._maximum_age:
            raise InstrumentReferenceError("REFERENCE_STALE")
        if not contract.tradable:
            raise InstrumentReferenceError("INSTRUMENT_NOT_TRADABLE")
        values = {
            "schema_version": "1.0",
            "instrument_spec_id": uuid5(_SPEC_NAMESPACE, contract.contract_hash),
            "instrument_key": contract.provider_instrument_key,
            "exchange": contract.exchange,
            "segment": contract.segment,
            "underlying": contract.underlying,
            "instrument_type": contract.instrument_type,
            "option_type": contract.option_type,
            "strike": contract.strike,
            "expiry": contract.expiry,
            "lot_size": contract.lot_size,
            "tick_size": contract.tick_size,
            "trading_symbol": contract.provider_trading_symbol,
            "freeze_quantity": contract.freeze_quantity,
            "source": contract.provider,
            "source_as_of": contract.source_as_of,
            "retrieved_at": self._retrieved_at,
            "freshness": "FRESH",
            "provenance_hash": contract.contract_hash,
            "payload_hash": "0" * 64,
        }
        draft = DerivativeInstrumentSpec.model_validate(values)
        return draft.model_copy(update={"payload_hash": compute_payload_hash(draft)})


def build_current_option_window(
    *,
    master: ContractMaster,
    contracts: tuple[NormalizedDerivativeContract, ...],
    underlying: DerivativeUnderlying,
    underlying_price: Decimal,
    as_of: UTCDateTime,
    maximum_master_age_ms: int,
    window_size: int = 2,
) -> ActiveOptionWindow:
    """Choose the nearest actual listed expiry and build a symmetric actual window."""

    validate_master_for_use(master, evaluation_time=as_of, maximum_age_ms=maximum_master_age_ms)
    expiry = select_nearest_expiry(
        master,
        underlying=underlying,
        instrument_type=DerivativeInstrumentType.OPTIDX,
        evaluation_time=as_of,
        maximum_age_ms=maximum_master_age_ms,
    )
    return build_active_option_window(
        contracts=contracts,
        underlying=underlying,
        underlying_price=underlying_price,
        as_of_time=as_of,
        policy=ActiveWindowPolicy(
            expiry=expiry.expiry,
            window_size=window_size,
            maximum_master_age_ms=maximum_master_age_ms,
            maximum_quote_age_ms=maximum_master_age_ms,
        ),
    )


def provider_records_to_reference_contracts(
    records: tuple[ProviderInstrumentRecord, ...],
    *,
    underlying_aliases: dict[str, DerivativeUnderlying],
) -> tuple[NormalizedDerivativeContract, ...]:
    """Bind current provider BOD records without guessing contract economics."""

    contracts: list[NormalizedDerivativeContract] = []
    for record in records:
        underlying = underlying_aliases.get(record.provider_underlying)
        if underlying is None:
            continue
        values = {
            "schema_version": "1.0",
            "instrument_id": uuid5(_PROVIDER_CONTRACT_NAMESPACE, record.provider_instrument_key),
            "exchange": record.exchange,
            "segment": record.segment,
            "underlying": underlying,
            "instrument_type": record.instrument_type,
            "expiry": record.expiry,
            "strike": record.strike,
            "option_type": record.option_type,
            "lot_size": record.lot_size,
            "tick_size": record.tick_size,
            "freeze_quantity": record.freeze_quantity,
            "weekly": record.weekly,
            "tradable": record.tradable,
            "provider": record.provider,
            "provider_underlying": record.provider_underlying,
            "provider_instrument_key": record.provider_instrument_key,
            "provider_exchange_token": record.provider_exchange_token,
            "provider_trading_symbol": record.trading_symbol,
            "source_as_of": record.source_as_of,
            "provider_source_hash": record.source_hash,
            "reference_source_hash": record.source_hash,
        }
        values["contract_hash"] = canonical_sha256(values)
        contracts.append(NormalizedDerivativeContract.model_validate(values))
    if not contracts:
        raise InstrumentReferenceError("NO_SUPPORTED_PROVIDER_CONTRACTS")
    return tuple(sorted(contracts, key=lambda item: item.provider_instrument_key))


__all__ = [
    "DerivativeInstrumentSpec",
    "InstrumentReferenceAuthority",
    "InstrumentReferenceError",
    "build_current_option_window",
    "provider_records_to_reference_contracts",
]
