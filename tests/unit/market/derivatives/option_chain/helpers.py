from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from ats.contracts.domain.types import DataQualityState
from ats.market.derivatives.contract_master import (
    ContractMaster,
    ContractMasterManifest,
    DerivativeUnderlying,
    normalize_contract_master,
)
from ats.market.derivatives.option_chain import (
    GreeksMethod,
    OptionChainBuildContext,
    OptionChainQualityPolicy,
    OptionQuoteInput,
)

AS_OF = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
EXPIRY_TIME = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
HEADER = (
    b"exchange,segment,underlying,instrument_type,trading_symbol,instrument_id,expiry,"
    b"strike,option_type,lot_size,tick_size,quantity_freeze_limit,tradable,contract_version\n"
)
ROWS = (
    b"NSE,NFO,NIFTY,OPTIDX,NIFTY24900CE,C1,2026-09-01,24900,CE,65,0.05,1800,TRUE,V1\n",
    b"NSE,NFO,NIFTY,OPTIDX,NIFTY25000CE,C2,2026-09-01,25000,CE,65,0.05,1800,TRUE,V1\n",
    b"NSE,NFO,NIFTY,OPTIDX,NIFTY25000PE,P2,2026-09-01,25000,PE,65,0.05,1800,TRUE,V1\n",
    b"NSE,NFO,NIFTY,OPTIDX,NIFTY25100PE,P3,2026-09-01,25100,PE,65,0.05,1800,TRUE,V1\n",
)


def master() -> ContractMaster:
    raw = HEADER + b"".join(ROWS)
    manifest = ContractMasterManifest(
        schema_version="1.0",
        master_id=UUID("00000000-0000-0000-0000-000000000701"),
        master_version="V1",
        source="TEST",
        as_of_time=AS_OF,
        row_count=4,
        content_sha256=sha256(raw).hexdigest(),
    )
    return normalize_contract_master(manifest=manifest, content=raw)


def policy() -> OptionChainQualityPolicy:
    return OptionChainQualityPolicy(
        maximum_master_age_ms=60_000,
        maximum_quote_age_ms=1_000,
        maximum_spread_fraction=Decimal("0.05"),
        minimum_top_quantity=10,
        minimum_volume=100,
        minimum_open_interest=100,
        atm_tolerance_fraction=Decimal("0.002"),
    )


def context() -> OptionChainBuildContext:
    return OptionChainBuildContext(
        chain_id=UUID("00000000-0000-0000-0000-000000000702"),
        underlying=DerivativeUnderlying.NIFTY,
        expiry="2026-09-01",
        underlying_price=Decimal("25000"),
        atm_strike=Decimal("25000"),
        as_of_time=AS_OF,
        data_cutoff=AS_OF,
        expiry_time=EXPIRY_TIME,
        source_id="TEST_FEED",
        source_version="V1",
        policy=policy(),
    )


def quote(instrument_id: str, **updates: object) -> OptionQuoteInput:
    values: dict[str, object] = {
        "instrument_id": instrument_id,
        "quote_time": AS_OF,
        "bid": Decimal("99"),
        "ask": Decimal("101"),
        "bid_qty": 100,
        "ask_qty": 100,
        "last_price": Decimal("100"),
        "volume": 1000,
        "open_interest": 2000,
        "change_in_oi": 100,
        "implied_volatility": 0.20,
        "delta": 0.50 if instrument_id.startswith("C") else -0.50,
        "gamma": 0.001,
        "theta": -2.0,
        "vega": 5.0,
        "greeks_method": GreeksMethod.SOURCE_PROVIDED,
        "greeks_method_version": "FEED-V1",
        "source_quality_state": DataQualityState.GOOD,
    }
    values.update(updates)
    return OptionQuoteInput(**values)
