"""Dynamic NIFTY/BANKNIFTY option-universe construction for the live A2 feed.

The universe is derived purely from reference-contract evidence (the contract
master / normalized provider records). No expiry weekday, lot size, strike step,
or tick size is ever hard-coded in the live path: every economic fact is read
from the supplied ``NormalizedDerivativeContract`` records.

A deterministic fixture generator is provided for offline/replay acceptance so
the full transport -> decode -> normalized -> freshness -> runtime chain can be
proven without a live exchange session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta, timezone
from decimal import Decimal
from typing import Final
from uuid import UUID, uuid5

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.types import PositiveDecimal, PositiveInt
from ats.contracts.hashing import canonical_sha256
from ats.market.derivatives.active_window.engine import build_active_option_window
from ats.market.derivatives.active_window.models import ActiveWindowPolicy
from ats.market.derivatives.contract_master import (
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
)
from ats.market.derivatives.normalization import NormalizedDerivativeContract
from ats.market.feeds.upstox_v3.config import FeedMode
from ats.market.feeds.upstox_v3.instrument_keys import (
    BANKNIFTY_INDEX_FEED_KEY,
    NIFTY_INDEX_FEED_KEY,
)

_IST = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
_CONTRACT_NAMESPACE = UUID("9db40a8c-7562-5651-9c1e-95bd174624b5")

DEFAULT_WINDOW_SIZE: Final[int] = 2
DEFAULT_MAXIMUM_MASTER_AGE_MS: Final[int] = 86_400_000
DEFAULT_MAXIMUM_QUOTE_AGE_MS: Final[int] = 2_000


@dataclass(frozen=True)
class OptionUniverseSubscription:
    """One concrete subscription target derived from reference evidence."""

    instrument_key: str
    ats_identity: str
    mode: FeedMode
    underlying: str
    instrument_kind: str  # "INDEX" | "OPTION"
    option_type: str | None = None
    strike: Decimal | None = None
    expiry: str | None = None
    lot_size: int | None = None
    tick_size: Decimal | None = None


def _nearest_future_expiry(
    contracts: tuple[NormalizedDerivativeContract, ...],
    underlying: DerivativeUnderlying,
    as_of: UTCDateTime,
) -> str:
    local_date = as_of.astimezone(_IST).date().isoformat()
    candidates = [
        c.expiry
        for c in contracts
        if c.underlying is underlying
        and c.instrument_type is DerivativeInstrumentType.OPTIDX
        and c.strike is not None
        and c.option_type is not None
    ]
    if not candidates:
        raise ValueError(f"no OPTIDX contracts available for {underlying}")
    future = [e for e in candidates if e >= local_date]
    chosen = min(future) if future else min(candidates)
    return chosen


def build_dynamic_option_universe(
    *,
    contracts: tuple[NormalizedDerivativeContract, ...],
    spots: dict[str, Decimal],
    as_of: UTCDateTime,
    window_size: int = DEFAULT_WINDOW_SIZE,
    mode: FeedMode = FeedMode.LTPC,
    maximum_master_age_ms: int = DEFAULT_MAXIMUM_MASTER_AGE_MS,
    maximum_quote_age_ms: int = DEFAULT_MAXIMUM_QUOTE_AGE_MS,
) -> tuple[OptionUniverseSubscription, ...]:
    """Build the live 22-subscription universe from reference truth.

    Produces NIFTY + BANKNIFTY index keys and, for each underlying, the
    ATM +/- ``window_size`` CE/PE pairs (5 strikes * 2 = 10 options each).
    """

    subscriptions: list[OptionUniverseSubscription] = []

    index_map = {
        "NIFTY": NIFTY_INDEX_FEED_KEY,
        "BANKNIFTY": BANKNIFTY_INDEX_FEED_KEY,
    }
    for underlying_name, index_key in index_map.items():
        subscriptions.append(
            OptionUniverseSubscription(
                instrument_key=index_key,
                ats_identity=underlying_name,
                mode=FeedMode.LTPC,
                underlying=underlying_name,
                instrument_kind="INDEX",
            )
        )

    for underlying_name, spot in spots.items():
        underlying = DerivativeUnderlying(underlying_name)
        expiry = _nearest_future_expiry(contracts, underlying, as_of)
        policy = ActiveWindowPolicy(
            window_size=window_size,
            expiry=expiry,
            maximum_master_age_ms=maximum_master_age_ms,
            maximum_quote_age_ms=maximum_quote_age_ms,
        )
        window = build_active_option_window(
            contracts=contracts,
            underlying=underlying,
            underlying_price=spot,
            as_of_time=as_of,
            policy=policy,
        )
        for pair in window.pairs:
            ce = _spec_for_key(contracts, pair.ce_provider_instrument_key)
            pe = _spec_for_key(contracts, pair.pe_provider_instrument_key)
            subscriptions.append(
                OptionUniverseSubscription(
                    instrument_key=pair.ce_provider_instrument_key,
                    ats_identity=pair.ce_provider_instrument_key.replace("|", "_"),
                    mode=mode,
                    underlying=underlying_name,
                    instrument_kind="OPTION",
                    option_type="CE",
                    strike=pair.strike,
                    expiry=expiry,
                    lot_size=ce.lot_size if ce else None,
                    tick_size=ce.tick_size if ce else None,
                )
            )
            subscriptions.append(
                OptionUniverseSubscription(
                    instrument_key=pair.pe_provider_instrument_key,
                    ats_identity=pair.pe_provider_instrument_key.replace("|", "_"),
                    mode=mode,
                    underlying=underlying_name,
                    instrument_kind="OPTION",
                    option_type="PE",
                    strike=pair.strike,
                    expiry=expiry,
                    lot_size=pe.lot_size if pe else None,
                    tick_size=pe.tick_size if pe else None,
                )
            )

    return tuple(subscriptions)


def _spec_for_key(
    contracts: tuple[NormalizedDerivativeContract, ...], key: str
) -> NormalizedDerivativeContract | None:
    for c in contracts:
        if c.provider_instrument_key == key:
            return c
    return None


def fixture_contract_master(
    *,
    underlying: str,
    spot: Decimal,
    expiry: str,
    strike_step: PositiveDecimal,
    lot_size: PositiveInt,
    tick_size: Decimal,
    half_width_strikes: int,
    as_of: UTCDateTime,
    provider: str = "UPSTOX",
) -> tuple[NormalizedDerivativeContract, ...]:
    """Deterministic reference-evidence fixture for one underlying.

    Explicit static economics are permitted here ONLY because this is a test
    fixture; the live path never calls this generator.
    """

    underlying_enum = DerivativeUnderlying(underlying)
    atm = _round_to_step(spot, strike_step)
    contracts: list[NormalizedDerivativeContract] = []
    for offset in range(-half_width_strikes, half_width_strikes + 1):
        strike = atm + strike_step * offset
        if strike <= 0:
            continue
        for option_type in (OptionType.CE, OptionType.PE):
            key = f"NSE_FO|{underlying}{_expiry_tag(expiry)}{int(strike)}{option_type.value}"
            values = {
                "schema_version": "1.0",
                "instrument_id": uuid5(_CONTRACT_NAMESPACE, key),
                "exchange": "NSE",
                "segment": "NSE_FO",
                "underlying": underlying_enum,
                "instrument_type": DerivativeInstrumentType.OPTIDX,
                "expiry": expiry,
                "strike": strike,
                "option_type": option_type,
                "lot_size": lot_size,
                "tick_size": tick_size,
                "freeze_quantity": lot_size * 30,
                "weekly": True,
                "tradable": True,
                "provider": provider,
                "provider_underlying": underlying,
                "provider_instrument_key": key,
                "provider_exchange_token": f"TK{int(strike)}{option_type.value}",
                "provider_trading_symbol": key.split("|", 1)[1],
                "source_as_of": as_of,
                "provider_source_hash": "0" * 64,
                "reference_source_hash": "0" * 64,
            }
            values["contract_hash"] = canonical_sha256(values)
            contracts.append(NormalizedDerivativeContract.model_validate(values))
    return tuple(sorted(contracts, key=lambda c: c.provider_instrument_key))


def _round_to_step(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value() * step


def _expiry_tag(expiry: str) -> str:
    # 2026-09-24 -> 24SEP26
    year, month, day = expiry.split("-")
    month_abbr = [
        "JAN",
        "FEB",
        "MAR",
        "APR",
        "MAY",
        "JUN",
        "JUL",
        "AUG",
        "SEP",
        "OCT",
        "NOV",
        "DEC",
    ]
    return f"{day}{month_abbr[int(month) - 1]}{year[2:]}"


__all__ = [
    "DEFAULT_MAXIMUM_MASTER_AGE_MS",
    "DEFAULT_MAXIMUM_QUOTE_AGE_MS",
    "DEFAULT_WINDOW_SIZE",
    "OptionUniverseSubscription",
    "build_dynamic_option_universe",
    "fixture_contract_master",
]
