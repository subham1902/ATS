"""Lot-size validation populated only from current instrument-reference evidence."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal


class LotSizeError(ValueError):
    """Raised when a quantity violates lot-size constraints."""


@dataclass
class LotSizeRegistry:
    """Maps exact instrument identities to provider-supplied lot sizes.

    An empty registry is deliberately unusable for new risk. Tests may register
    fixture values explicitly; production must populate it from InstrumentSpec.
    """

    _lot_sizes: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_instrument_specs(cls, specs: Iterable[object]) -> LotSizeRegistry:
        registry = cls()
        for spec in specs:
            key = getattr(spec, "instrument_key", None)
            lot_size = getattr(spec, "lot_size", None)
            if not isinstance(key, str) or not isinstance(lot_size, int):
                raise LotSizeError("instrument spec lacks a valid key or lot size")
            registry.register(key, lot_size)
        return registry

    def register(self, instrument_root: str, lot_size: int) -> None:
        if lot_size <= 0:
            raise LotSizeError(f"lot_size must be positive, got {lot_size}")
        key = instrument_root.strip()
        if not key:
            raise LotSizeError("instrument identity must not be empty")
        self._lot_sizes[key] = lot_size

    def lot_size_for(self, instrument_id: str) -> int:
        """Return the lot size for an instrument id.

        Instrument ids may be full qualified (``NIFTY:CE:24500:2026-09-04``)
        or bare root (``NIFTY``).  The root is extracted as the prefix before
        the first colon or underscore.
        """
        lot = self._lot_sizes.get(instrument_id)
        if lot is None:
            raise LotSizeError(
                f"no provider-derived lot size registered for instrument '{instrument_id}'"
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
                f"for instrument '{instrument_id}'"
            )

    def round_to_lot(self, instrument_id: str, quantity: Decimal) -> Decimal:
        """Round *quantity* down to the nearest valid lot size."""
        lot = self.lot_size_for(instrument_id)
        qty_int = int(quantity)
        rounded = (qty_int // lot) * lot
        return Decimal(rounded)


__all__ = ["LotSizeError", "LotSizeRegistry"]
