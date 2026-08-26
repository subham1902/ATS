"""Lot-size registry and validation for NSE derivative instruments.

NIFTY lot = 25, BANKNIFTY lot = 15 (as of 2026).  Wrong lot sizes cause
exchange rejection (live) or meaningless paper results.  This module
enforces that all order quantities are exact multiples of the underlying
lot size.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


class LotSizeError(ValueError):
    """Raised when a quantity violates lot-size constraints."""


_DEFAULT_LOT_SIZES: dict[str, int] = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
}


@dataclass
class LotSizeRegistry:
    """Maps instrument root symbols to their exchange-mandated lot sizes."""

    _lot_sizes: dict[str, int] = field(default_factory=lambda: dict(_DEFAULT_LOT_SIZES))

    def register(self, instrument_root: str, lot_size: int) -> None:
        if lot_size <= 0:
            raise LotSizeError(f"lot_size must be positive, got {lot_size}")
        self._lot_sizes[instrument_root.upper()] = lot_size

    def lot_size_for(self, instrument_id: str) -> int:
        """Return the lot size for an instrument id.

        Instrument ids may be full qualified (``NIFTY:CE:24500:2026-09-04``)
        or bare root (``NIFTY``).  The root is extracted as the prefix before
        the first colon or underscore.
        """
        root = _extract_root(instrument_id)
        lot = self._lot_sizes.get(root)
        if lot is None:
            raise LotSizeError(
                f"no lot size registered for root '{root}' (from instrument_id '{instrument_id}')"
            )
        return lot

    def validate_quantity(self, instrument_id: str, quantity: Decimal) -> None:
        """Raise :class:`LotSizeError` if *quantity* is not an exact multiple of the lot size."""
        lot = self.lot_size_for(instrument_id)
        qty_int = int(quantity)
        if Decimal(qty_int) != quantity:
            raise LotSizeError(
                f"quantity {quantity} is not an integer for instrument '{instrument_id}'"
            )
        if qty_int <= 0:
            raise LotSizeError(f"quantity must be positive, got {qty_int} for '{instrument_id}'")
        if qty_int % lot != 0:
            raise LotSizeError(
                f"quantity {qty_int} is not a multiple of lot size {lot} "
                f"for instrument root '{_extract_root(instrument_id)}'"
            )

    def round_to_lot(self, instrument_id: str, quantity: Decimal) -> Decimal:
        """Round *quantity* down to the nearest valid lot size."""
        lot = self.lot_size_for(instrument_id)
        qty_int = int(quantity)
        rounded = (qty_int // lot) * lot
        return Decimal(rounded)


def _extract_root(instrument_id: str) -> str:
    """Extract the root symbol from an instrument id."""
    for sep in (":", "_"):
        if sep in instrument_id:
            return instrument_id.split(sep, 1)[0].upper()
    return instrument_id.upper()


__all__ = ["LotSizeError", "LotSizeRegistry"]
