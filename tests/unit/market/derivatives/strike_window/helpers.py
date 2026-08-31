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
EXPIRY = "2026-09-01"

HEADER = (
    b"exchange,segment,underlying,instrument_type,trading_symbol,instrument_id,expiry,"
    b"strike,option_type,lot_size,tick_size,quantity_freeze_limit,tradable,contract_version\n"
)


def opt_row(
    strike: str,
    option_type: str,
    *,
    expiry: str = EXPIRY,
    lot_size: str = "65",
    freeze: str | None = "1800",
    tick: str = "0.05",
    tradable: str = "TRUE",
) -> bytes:
    instrument_id = f"K{strike}{option_type}"
    symbol = f"NIFTY{expiry.replace('-', '')}{strike}{option_type}"
    freeze_field = "" if freeze is None else freeze
    return (
        f"NSE,NFO,NIFTY,OPTIDX,{symbol},{instrument_id},{expiry},{strike},{option_type},"
        f"{lot_size},{tick},{freeze_field},{tradable},NSE-TEST-V1\n".encode()
    )


def rows_for(strikes: tuple[str, ...], **kwargs: object) -> tuple[bytes, ...]:
    rows: list[bytes] = []
    for strike in strikes:
        rows.append(opt_row(strike, "CE", **kwargs))  # type: ignore[arg-type]
        rows.append(opt_row(strike, "PE", **kwargs))  # type: ignore[arg-type]
    return tuple(rows)


IRREGULAR_STRIKES = ("24300", "24500", "24750", "25000", "25050", "25300", "25550")


def master(rows: tuple[bytes, ...], *, as_of: datetime = AS_OF) -> ContractMaster:
    raw = HEADER + b"".join(rows)
    manifest = ContractMasterManifest(
        schema_version="1.0",
        master_id=UUID("00000000-0000-0000-0000-000000000802"),
        master_version="D08-STRIKE-V1",
        source="TEST_ONLY_NSE_EXPORT_SHAPE",
        as_of_time=as_of,
        row_count=raw.count(b"\n") - 1,
        content_sha256=sha256(raw).hexdigest(),
    )
    return normalize_contract_master(manifest=manifest, content=raw)


def policy(window_size: int):
    from ats.market.derivatives.strike_window import StrikeWindowPolicy

    return StrikeWindowPolicy(
        window_size=window_size,
        expiry=EXPIRY,
        maximum_master_age_ms=86_400_000,
    )
