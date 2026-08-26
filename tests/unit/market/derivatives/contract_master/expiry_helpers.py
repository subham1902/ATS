from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from ats.market.derivatives.contract_master import (
    ContractMaster,
    ContractMasterManifest,
    normalize_contract_master,
)

AS_OF = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)

HEADER = (
    b"exchange,segment,underlying,instrument_type,trading_symbol,instrument_id,expiry,"
    b"strike,option_type,lot_size,tick_size,quantity_freeze_limit,tradable,contract_version\n"
)


def opt_row(
    strike: str,
    option_type: str,
    expiry: str,
    *,
    instrument_id: str,
    lot_size: str = "65",
    freeze: str = "1800",
    tick: str = "0.05",
    tradable: str = "TRUE",
    symbol: str | None = None,
) -> bytes:
    symbol = symbol or f"NIFTY{expiry.replace('-', '')}{strike}{option_type}"
    return (
        f"NSE,NFO,NIFTY,OPTIDX,{symbol},{instrument_id},{expiry},{strike},{option_type},"
        f"{lot_size},{tick},{freeze},{tradable},NSE-TEST-V1\n".encode()
    )


def fut_row(expiry: str, *, instrument_id: str) -> bytes:
    return (
        f"NSE,NFO,NIFTY,FUTIDX,NIFTYFUT,{instrument_id},{expiry},,,75,0.05,900,TRUE,"
        f"NSE-TEST-V1\n".encode()
    )


EXPIRY_ROWS = (
    opt_row("25000", "CE", "2026-08-25", instrument_id="E1C"),
    opt_row("25000", "PE", "2026-08-25", instrument_id="E1P"),
    opt_row("25000", "CE", "2026-09-01", instrument_id="W1C"),
    opt_row("25000", "PE", "2026-09-01", instrument_id="W1P"),
    opt_row("25000", "CE", "2026-09-29", instrument_id="M1C"),
    opt_row("25000", "PE", "2026-09-29", instrument_id="M1P"),
    opt_row("25000", "CE", "2026-10-27", instrument_id="X1C"),
    opt_row("25000", "PE", "2026-10-27", instrument_id="X1P"),
    fut_row("2026-09-29", instrument_id="FUT1"),
)


def master(rows: tuple[bytes, ...] = EXPIRY_ROWS, *, as_of: datetime = AS_OF) -> ContractMaster:
    raw = HEADER + b"".join(rows)
    manifest = ContractMasterManifest(
        schema_version="1.0",
        master_id=UUID("00000000-0000-0000-0000-000000000801"),
        master_version="D08-TEST-V1",
        source="TEST_ONLY_NSE_EXPORT_SHAPE",
        as_of_time=as_of,
        row_count=raw.count(b"\n") - 1,
        content_sha256=sha256(raw).hexdigest(),
    )
    return normalize_contract_master(manifest=manifest, content=raw)
