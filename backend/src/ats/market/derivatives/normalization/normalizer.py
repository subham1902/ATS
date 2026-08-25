"""Deterministic NSE-authority versus provider-mirror reconciliation."""

from __future__ import annotations

from uuid import UUID, uuid5

from ats.contracts.hashing import canonical_sha256
from ats.market.derivatives.contract_master import DerivativeUnderlying

from .models import (
    ContractNormalizationResult,
    NormalizedDerivativeContract,
    ProviderInstrumentRecord,
    ReferenceCheckCode,
    ReferenceInstrumentRecord,
    ReferenceIssue,
    UnderlyingAlias,
)

_CONTRACT_NAMESPACE = UUID("309256c0-c63d-5d0d-bf9c-2b945eb30c3e")


def normalize_contracts(
    *,
    provider_records: tuple[ProviderInstrumentRecord, ...],
    reference_records: tuple[ReferenceInstrumentRecord, ...],
    aliases: tuple[UnderlyingAlias, ...],
) -> ContractNormalizationResult:
    alias_map = _unique_map(aliases, "provider_underlying")
    _ensure_unique(provider_records, "provider_instrument_key")
    reference_map = {_identity(item): item for item in reference_records}
    if len(reference_map) != len(reference_records):
        raise ValueError("duplicate canonical reference contract")
    contracts: list[NormalizedDerivativeContract] = []
    issues: list[ReferenceIssue] = []
    canonical_seen: set[tuple[object, ...]] = set()
    for provider in provider_records:
        alias = alias_map.get(provider.provider_underlying)
        if alias is None:
            raise ValueError("provider underlying has no registered canonical alias")
        identity = _provider_identity(provider, alias.canonical_underlying)
        if identity in canonical_seen:
            raise ValueError("duplicate canonical provider contract")
        canonical_seen.add(identity)
        reference = reference_map.get(identity)
        if reference is None:
            expiry_candidates = [
                item
                for item in reference_records
                if _identity_without_expiry(item) == _identity_without_expiry(identity)
            ]
            if len(expiry_candidates) == 1:
                issues.append(_issue(provider, ReferenceCheckCode.REFERENCE_MISMATCH, ("expiry",)))
                continue
            issues.append(
                _issue(provider, ReferenceCheckCode.REFERENCE_CONTRACT_MISSING, ("contract",))
            )
            continue
        mismatches = tuple(
            name
            for name in ("lot_size", "freeze_quantity", "expiry")
            if getattr(provider, name) != getattr(reference, name)
        )
        if mismatches:
            issues.append(_issue(provider, ReferenceCheckCode.REFERENCE_MISMATCH, mismatches))
            continue
        contracts.append(_normalized(provider, reference, alias.canonical_underlying))
    return ContractNormalizationResult(contracts=tuple(contracts), issues=tuple(issues))


def _normalized(
    provider: ProviderInstrumentRecord,
    reference: ReferenceInstrumentRecord,
    underlying: DerivativeUnderlying,
) -> NormalizedDerivativeContract:
    identity = _provider_identity(provider, underlying)
    values = {
        "schema_version": "1.0",
        "instrument_id": uuid5(_CONTRACT_NAMESPACE, "|".join(map(str, identity))),
        "exchange": reference.exchange,
        "segment": reference.segment,
        "underlying": underlying,
        "instrument_type": reference.instrument_type,
        "expiry": reference.expiry,
        "strike": reference.strike,
        "option_type": reference.option_type,
        "lot_size": reference.lot_size,
        "tick_size": provider.tick_size,
        "freeze_quantity": reference.freeze_quantity,
        "weekly": provider.weekly,
        "tradable": provider.tradable,
        "provider": provider.provider,
        "provider_underlying": provider.provider_underlying,
        "provider_instrument_key": provider.provider_instrument_key,
        "provider_exchange_token": provider.provider_exchange_token,
        "provider_trading_symbol": provider.trading_symbol,
        "source_as_of": provider.source_as_of,
        "provider_source_hash": provider.source_hash,
        "reference_source_hash": reference.source_hash,
    }
    values["contract_hash"] = canonical_sha256(values)
    return NormalizedDerivativeContract.model_validate(values)


def _identity(item: ReferenceInstrumentRecord) -> tuple[object, ...]:
    return (
        item.exchange,
        item.segment,
        item.underlying,
        item.instrument_type,
        item.expiry,
        item.strike,
        item.option_type,
    )


def _provider_identity(
    item: ProviderInstrumentRecord, underlying: DerivativeUnderlying
) -> tuple[object, ...]:
    return (
        item.exchange,
        item.segment,
        underlying,
        item.instrument_type,
        item.expiry,
        item.strike,
        item.option_type,
    )


def _identity_without_expiry(
    item: ReferenceInstrumentRecord | tuple[object, ...],
) -> tuple[object, ...]:
    identity = _identity(item) if isinstance(item, ReferenceInstrumentRecord) else item
    return (*identity[:4], *identity[5:])


def _issue(
    provider: ProviderInstrumentRecord,
    code: ReferenceCheckCode,
    fields: tuple[str, ...],
) -> ReferenceIssue:
    return ReferenceIssue(
        code=code, provider_instrument_key=provider.provider_instrument_key, fields=fields
    )


def _unique_map(items: tuple[UnderlyingAlias, ...], field: str) -> dict[str, UnderlyingAlias]:
    result = {str(getattr(item, field)): item for item in items}
    if len(result) != len(items):
        raise ValueError(f"duplicate {field}")
    return result


def _ensure_unique(items: tuple[ProviderInstrumentRecord, ...], field: str) -> None:
    values = [getattr(item, field) for item in items]
    if len(set(values)) != len(values):
        raise ValueError(f"duplicate {field}")


__all__ = ["normalize_contracts"]
