from decimal import Decimal

import pytest
from ats.market.domain import UnsupportedInstrument
from ats.trading_runtime.lot_size import LotSizeError, LotSizeRegistry

from tests.unit.market.xauusd import instrument


def test_unknown_metadata_fails_closed():
    with pytest.raises(LotSizeError, match="METADATA_UNKNOWN"):
        LotSizeRegistry().validate_quantity("XAUUSD", Decimal("1"))


def test_observed_volume_constraints():
    metadata = instrument().model_copy(
        update={
            "volume_min": Decimal(".01"),
            "volume_max": Decimal("100"),
            "volume_step": Decimal(".01"),
        }
    )
    registry = LotSizeRegistry(metadata)
    registry.validate_quantity("XAUUSD", Decimal(".03"))
    for quantity in (Decimal("0"), Decimal(".015"), Decimal("101")):
        with pytest.raises(LotSizeError):
            registry.validate_quantity("XAUUSD", quantity)
    with pytest.raises(UnsupportedInstrument):
        registry.validate_quantity("EURUSD", Decimal(".01"))


def test_rounding_uses_broker_step():
    registry = LotSizeRegistry(instrument().model_copy(update={"volume_step": Decimal(".01")}))
    assert registry.round_to_lot("XAUUSD", Decimal(".037")) == Decimal(".03")
