"""Provider-authoritative live option evidence for the A2 paper scanner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid5

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState
from ats.contracts.hashing import canonical_sha256
from ats.market.derivatives.contract_master import (
    ContractMaster,
    ContractMasterManifest,
    DerivativeInstrument,
    DerivativeUnderlying,
)
from ats.market.derivatives.option_chain import (
    GreeksMethod,
    OptionChainBuildContext,
    OptionChainQualityPolicy,
    OptionChainState,
    OptionQuoteInput,
    build_option_chain,
)
from ats.market.derivatives.providers.models import SourceFreshness
from ats.market.feeds.upstox_v3.runtime_feed import UpstoxV3RuntimeFeed

_MASTER_NAMESPACE = UUID("1ff00932-a409-5df1-b476-3d08d23ef25f")
_CHAIN_NAMESPACE = UUID("ea57428a-d3c1-57ce-b8c0-88c9cbfc2959")
_IST = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")


@dataclass(frozen=True)
class LiveOptionEvidence:
    contract_master: ContractMaster
    option_chain: OptionChainState
    provider_key_by_instrument_id: dict[str, str]
    tick_size_by_instrument_id: dict[str, Decimal]


def build_live_option_evidence(
    *,
    feed: UpstoxV3RuntimeFeed,
    underlying: str,
    underlying_price: Decimal,
    evaluation_time: UTCDateTime,
    maximum_quote_age_ms: int,
) -> LiveOptionEvidence | None:
    """Build one fresh chain from the currently subscribed provider universe."""

    resolved_underlying = DerivativeUnderlying(underlying)
    references = tuple(
        item for item in feed.reference_contracts if item.underlying is resolved_underlying
    )
    if not references:
        return None

    master, provider_keys, tick_sizes = _contract_master(references)
    expiry = min(item.expiry for item in references)
    eligible = tuple(item for item in references if item.expiry == expiry)
    strikes = tuple(sorted({item.strike for item in eligible if item.strike is not None}))
    if not strikes:
        return None
    atm_strike = min(strikes, key=lambda strike: abs(strike - underlying_price))

    inputs: list[OptionQuoteInput] = []
    freshness = feed.board.evaluate(evaluation_time)
    by_provider_key = {item.provider_instrument_key: item for item in eligible}
    for provider_key, contract in by_provider_key.items():
        if freshness.get(provider_key) is not SourceFreshness.FRESH:
            continue
        update = feed.latest(provider_key)
        if update is None:
            continue
        timestamps = tuple(
            stamp for stamp in update.decision_critical_timestamps() if stamp is not None
        )
        if not timestamps:
            continue
        quote_time = min(timestamps)
        age_ms = int((evaluation_time - quote_time).total_seconds() * 1000)
        if age_ms < 0 or age_ms > maximum_quote_age_ms:
            continue
        instrument_id = str(contract.instrument_id).upper()
        inputs.append(
            OptionQuoteInput(
                instrument_id=instrument_id,
                quote_time=quote_time,
                bid=update.bid_price,
                ask=update.ask_price,
                bid_qty=update.bid_quantity,
                ask_qty=update.ask_quantity,
                last_price=update.last_traded_price,
                volume=update.volume,
                open_interest=update.open_interest,
                change_in_oi=update.open_interest_change,
                implied_volatility=update.implied_volatility,
                delta=update.delta,
                gamma=update.gamma,
                theta=update.theta,
                vega=update.vega,
                greeks_method=GreeksMethod(update.greeks_method),
                greeks_method_version=update.greeks_method_version,
                source_quality_state=DataQualityState.GOOD,
            )
        )
    if not inputs:
        return None

    expiry_time = datetime.combine(
        date.fromisoformat(expiry), time(hour=15, minute=30), tzinfo=_IST
    ).astimezone(UTC)
    context = OptionChainBuildContext(
        chain_id=uuid5(
            _CHAIN_NAMESPACE,
            f"{underlying}:{expiry}:{evaluation_time.isoformat()}",
        ),
        underlying=resolved_underlying,
        expiry=expiry,
        underlying_price=underlying_price,
        atm_strike=atm_strike,
        as_of_time=evaluation_time,
        data_cutoff=evaluation_time,
        expiry_time=expiry_time,
        source_id="UPSTOX_V3_LIVE",
        source_version="3.0.0",
        policy=OptionChainQualityPolicy(
            maximum_master_age_ms=86_400_000,
            maximum_quote_age_ms=maximum_quote_age_ms,
            maximum_spread_fraction=Decimal("0.05"),
            minimum_top_quantity=1,
            minimum_volume=0,
            minimum_open_interest=0,
            atm_tolerance_fraction=Decimal("0.0025"),
        ),
    )
    chain = build_option_chain(
        contract_master=master,
        context=context,
        inputs=tuple(inputs),
    )
    return LiveOptionEvidence(
        contract_master=master,
        option_chain=chain,
        provider_key_by_instrument_id=provider_keys,
        tick_size_by_instrument_id=tick_sizes,
    )


def _contract_master(
    references: tuple[object, ...],
) -> tuple[ContractMaster, dict[str, str], dict[str, Decimal]]:
    source_as_of = max(item.source_as_of for item in references)  # type: ignore[attr-defined]
    content_hash = canonical_sha256(
        sorted(item.contract_hash for item in references)  # type: ignore[attr-defined]
    )
    manifest = ContractMasterManifest(
        schema_version="1.0",
        master_id=uuid5(_MASTER_NAMESPACE, content_hash),
        master_version=content_hash[:16],
        source="UPSTOX_REFERENCE_AUTHORITY",
        as_of_time=source_as_of,
        row_count=len(references),
        content_sha256=content_hash,
    )
    instruments: list[DerivativeInstrument] = []
    provider_keys: dict[str, str] = {}
    tick_sizes: dict[str, Decimal] = {}
    for item in references:
        instrument_id = str(item.instrument_id).upper()  # type: ignore[attr-defined]
        provider_keys[instrument_id] = item.provider_instrument_key  # type: ignore[attr-defined]
        tick_sizes[instrument_id] = item.tick_size  # type: ignore[attr-defined]
        instruments.append(
            DerivativeInstrument(
                exchange=item.exchange,  # type: ignore[attr-defined]
                segment=item.segment,  # type: ignore[attr-defined]
                underlying=item.underlying,  # type: ignore[attr-defined]
                instrument_type=item.instrument_type,  # type: ignore[attr-defined]
                trading_symbol=item.provider_trading_symbol,  # type: ignore[attr-defined]
                instrument_id=instrument_id,
                expiry=item.expiry,  # type: ignore[attr-defined]
                strike=item.strike,  # type: ignore[attr-defined]
                option_type=item.option_type,  # type: ignore[attr-defined]
                lot_size=item.lot_size,  # type: ignore[attr-defined]
                tick_size=item.tick_size,  # type: ignore[attr-defined]
                quantity_freeze_limit=item.freeze_quantity,  # type: ignore[attr-defined]
                tradable=item.tradable,  # type: ignore[attr-defined]
                contract_version=item.contract_hash[:16],  # type: ignore[attr-defined]
                source=manifest.source,
                as_of_time=source_as_of,
            )
        )
    master = ContractMaster(
        schema_version="1.0",
        manifest=manifest,
        instruments=tuple(sorted(instruments, key=lambda item: item.instrument_id)),
        payload_hash="0" * 64,
    )
    return (
        master.model_copy(update={"payload_hash": compute_payload_hash(master)}),
        provider_keys,
        tick_sizes,
    )


__all__ = ["LiveOptionEvidence", "build_live_option_evidence"]
