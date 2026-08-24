from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from ats.market.derivatives.contract_master import ContractMasterManifest

HEADER = (
    b"exchange,segment,underlying,instrument_type,trading_symbol,instrument_id,expiry,"
    b"strike,option_type,lot_size,tick_size,quantity_freeze_limit,tradable,contract_version\n"
)
ROWS = (
    b"NSE,NFO,NIFTY,OPTIDX,NIFTY26SEP25000CE,10001,2026-09-01,25000,CE,65,0.05,"
    b"1800,TRUE,NSE-20260824\n",
    b"NSE,NFO,NIFTY,OPTIDX,NIFTY26SEP25000PE,10002,2026-09-01,25000,PE,65,0.05,"
    b"1800,TRUE,NSE-20260824\n",
    b"NSE,NFO,BANKNIFTY,FUTIDX,BANKNIFTY26SEPFUT,30002,2026-09-29,,,30,0.05,"
    b"900,TRUE,NSE-20260824\n",
)


def content(*rows: bytes) -> bytes:
    return HEADER + b"".join(rows or ROWS)


def manifest(raw: bytes, *, as_of: datetime | None = None) -> ContractMasterManifest:
    return ContractMasterManifest(
        schema_version="1.0",
        master_id=UUID("00000000-0000-0000-0000-000000000501"),
        master_version="NSE-20260824",
        source="NSE_CONTRACT_EXPORT",
        as_of_time=as_of or datetime(2026, 8, 24, 3, 30, tzinfo=UTC),
        row_count=raw.count(b"\n") - 1,
        content_sha256=sha256(raw).hexdigest(),
    )
