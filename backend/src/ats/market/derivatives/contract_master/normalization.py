"""Deterministic normalization of the ATS canonical contract-master CSV."""

from __future__ import annotations

import csv
import io
import re
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from ats.contracts.domain.hashing import compute_payload_hash

from .errors import ContractMasterError, ContractMasterErrorCode
from .models import (
    ContractMaster,
    ContractMasterManifest,
    DerivativeInstrument,
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
)

CSV_FIELDS = (
    "exchange",
    "segment",
    "underlying",
    "instrument_type",
    "trading_symbol",
    "instrument_id",
    "expiry",
    "strike",
    "option_type",
    "lot_size",
    "tick_size",
    "quantity_freeze_limit",
    "tradable",
    "contract_version",
)
_POSITIVE_INTEGER = re.compile(r"^[1-9][0-9]*$")


def _positive_int(value: str, field: str) -> int:
    if _POSITIVE_INTEGER.fullmatch(value) is None:
        raise ValueError(f"{field} must be a positive base-10 integer")
    return int(value)


def _decimal(value: str, field: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field} is not a decimal") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{field} must be finite and positive")
    return parsed


def _optional_positive_int(value: str, field: str) -> int | None:
    return None if value == "" else _positive_int(value, field)


def _option_type(value: str) -> OptionType | None:
    return None if value == "" else OptionType(value)


def _strike(value: str) -> Decimal | None:
    return None if value == "" else _decimal(value, "strike")


def _tradable(value: str) -> bool:
    if value == "TRUE":
        return True
    if value == "FALSE":
        return False
    raise ValueError("tradable must be TRUE or FALSE")


def _instrument_from_row(
    row: dict[str, str | None], manifest: ContractMasterManifest
) -> DerivativeInstrument:
    if any(value is None for value in row.values()):
        raise ValueError("row has missing columns")
    values = {key: value if value is not None else "" for key, value in row.items()}
    return DerivativeInstrument(
        exchange=values["exchange"],
        segment=values["segment"],
        underlying=DerivativeUnderlying(values["underlying"]),
        instrument_type=DerivativeInstrumentType(values["instrument_type"]),
        trading_symbol=values["trading_symbol"],
        instrument_id=values["instrument_id"],
        expiry=values["expiry"],
        strike=_strike(values["strike"]),
        option_type=_option_type(values["option_type"]),
        lot_size=_positive_int(values["lot_size"], "lot_size"),
        tick_size=_decimal(values["tick_size"], "tick_size"),
        quantity_freeze_limit=_optional_positive_int(
            values["quantity_freeze_limit"], "quantity_freeze_limit"
        ),
        tradable=_tradable(values["tradable"]),
        contract_version=values["contract_version"],
        source=manifest.source,
        as_of_time=manifest.as_of_time,
    )


def normalize_contract_master(
    *, manifest: ContractMasterManifest, content: bytes
) -> ContractMaster:
    """Verify raw bytes and normalize only the explicit canonical CSV schema."""

    actual_hash = sha256(content).hexdigest()
    if actual_hash != manifest.content_sha256:
        raise ContractMasterError(
            ContractMasterErrorCode.CONTENT_HASH_MISMATCH,
            "raw export does not match manifest",
        )
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ContractMasterError(
            ContractMasterErrorCode.INVALID_ENCODING, "content must be strict UTF-8"
        ) from exc

    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    if tuple(reader.fieldnames or ()) != CSV_FIELDS:
        raise ContractMasterError(
            ContractMasterErrorCode.INVALID_HEADER,
            f"expected columns {CSV_FIELDS!r}",
        )

    instruments: list[DerivativeInstrument] = []
    try:
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ContractMasterError(
                    ContractMasterErrorCode.INVALID_ROW,
                    "row has unexpected extra columns",
                    row_number=row_number,
                )
            try:
                instruments.append(_instrument_from_row(row, manifest))
            except (ValueError, KeyError) as exc:
                raise ContractMasterError(
                    ContractMasterErrorCode.INVALID_ROW,
                    str(exc),
                    row_number=row_number,
                ) from exc
    except csv.Error as exc:
        raise ContractMasterError(ContractMasterErrorCode.INVALID_ROW, str(exc)) from exc

    if len(instruments) != manifest.row_count:
        raise ContractMasterError(
            ContractMasterErrorCode.ROW_COUNT_MISMATCH,
            f"expected {manifest.row_count}, got {len(instruments)}",
        )
    _validate_unique(instruments)
    ordered = tuple(sorted(instruments, key=_sort_key))
    master = ContractMaster(
        schema_version="1.0",
        manifest=manifest,
        instruments=ordered,
        payload_hash="0" * 64,
    )
    return master.model_copy(update={"payload_hash": compute_payload_hash(master)})


def _sort_key(instrument: DerivativeInstrument) -> tuple[str, ...]:
    return (
        instrument.exchange,
        instrument.segment,
        instrument.underlying.value,
        instrument.instrument_type.value,
        instrument.expiry,
        "" if instrument.strike is None else str(instrument.strike),
        "" if instrument.option_type is None else instrument.option_type.value,
        instrument.instrument_id,
    )


def _validate_unique(instruments: list[DerivativeInstrument]) -> None:
    instrument_ids: set[str] = set()
    symbols: set[str] = set()
    semantic_keys: set[tuple[object, ...]] = set()
    for instrument in instruments:
        if instrument.instrument_id in instrument_ids:
            raise ContractMasterError(
                ContractMasterErrorCode.DUPLICATE_INSTRUMENT_ID,
                instrument.instrument_id,
            )
        if instrument.trading_symbol in symbols:
            raise ContractMasterError(
                ContractMasterErrorCode.DUPLICATE_TRADING_SYMBOL,
                instrument.trading_symbol,
            )
        semantic_key = instrument.semantic_key()
        if semantic_key in semantic_keys:
            raise ContractMasterError(
                ContractMasterErrorCode.DUPLICATE_CONTRACT,
                instrument.trading_symbol,
            )
        instrument_ids.add(instrument.instrument_id)
        symbols.add(instrument.trading_symbol)
        semantic_keys.add(semantic_key)


__all__ = ["CSV_FIELDS", "normalize_contract_master"]
