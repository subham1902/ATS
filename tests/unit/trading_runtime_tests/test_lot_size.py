from __future__ import annotations

from decimal import Decimal

import pytest
from ats.trading_runtime.lot_size import LotSizeError, LotSizeRegistry


def fixture_registry() -> LotSizeRegistry:
    value = LotSizeRegistry()
    value.register("NIFTY", 25)
    value.register("BANKNIFTY", 15)
    return value


def test_registry_has_no_static_production_fallback() -> None:
    empty = LotSizeRegistry()
    with pytest.raises(LotSizeError, match="provider-derived"):
        empty.lot_size_for("NIFTY")


def test_lot_size_validation_success() -> None:
    registry = fixture_registry()
    registry.validate_quantity("NIFTY", Decimal("25"))
    registry.validate_quantity("NIFTY", Decimal("50"))
    registry.validate_quantity("NIFTY", Decimal("100"))
    registry.validate_quantity("BANKNIFTY", Decimal("15"))
    registry.validate_quantity("BANKNIFTY", Decimal("45"))


def test_lot_size_validation_failures() -> None:
    registry = fixture_registry()
    with pytest.raises(LotSizeError, match="not a multiple of lot size"):
        registry.validate_quantity("NIFTY", Decimal("10"))

    with pytest.raises(LotSizeError, match="not a multiple of lot size"):
        registry.validate_quantity("BANKNIFTY", Decimal("25"))

    with pytest.raises(LotSizeError, match="must be positive"):
        registry.validate_quantity("NIFTY", Decimal("0"))

    with pytest.raises(LotSizeError, match="not an integer"):
        registry.validate_quantity("NIFTY", Decimal("25.5"))


def test_round_to_lot() -> None:
    registry = fixture_registry()
    assert registry.round_to_lot("NIFTY", Decimal("30")) == Decimal("25")
    assert registry.round_to_lot("NIFTY", Decimal("74")) == Decimal("50")
    assert registry.round_to_lot("BANKNIFTY", Decimal("28")) == Decimal("15")
