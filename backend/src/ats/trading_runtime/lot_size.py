"""Broker-observed XAUUSD volume constraints; unknown metadata fails closed."""

from decimal import ROUND_FLOOR, Decimal

from ats.market.domain import InstrumentMetadata, require_xauusd


class LotSizeError(ValueError):
    pass


class LotSizeRegistry:
    def __init__(self, metadata: InstrumentMetadata | None = None) -> None:
        self.metadata = metadata

    def lot_size_for(self, instrument_id: str) -> Decimal:
        require_xauusd(instrument_id)
        if self.metadata is None:
            raise LotSizeError("BROKER_VOLUME_METADATA_UNKNOWN")
        return self.metadata.volume_step

    def validate_quantity(self, instrument_id: str, quantity: Decimal) -> None:
        step = self.lot_size_for(instrument_id)
        assert self.metadata is not None
        if (
            quantity < self.metadata.volume_min
            or quantity > self.metadata.volume_max
            or quantity % step
        ):
            raise LotSizeError("QUANTITY_VIOLATES_BROKER_VOLUME_CONSTRAINTS")

    def round_to_lot(self, instrument_id: str, quantity: Decimal) -> Decimal:
        step = self.lot_size_for(instrument_id)
        return (quantity / step).to_integral_value(rounding=ROUND_FLOOR) * step
