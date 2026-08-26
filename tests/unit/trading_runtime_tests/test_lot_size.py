from __future__ import annotations

from decimal import Decimal

import pytest
from ats.trading_runtime.lot_size import LotSizeError, LotSizeRegistry


def test_lot_size_defaults() -> None:
    registry = LotSizeRegistry()
    assert registry.lot_size_for("NIFTY") == 25
    assert registry.lot_size_for("BANKNIFTY") == 15
    assert registry.lot_size_for("NIFTY:CE:24500:2026-09-04") == 25
    assert registry.lot_size_for("BANKNIFTY_PE_50000") == 15


def test_lot_size_validation_success() -> None:
    registry = LotSizeRegistry()
    registry.validate_quantity("NIFTY", Decimal("25"))
    registry.validate_quantity("NIFTY", Decimal("50"))
    registry.validate_quantity("NIFTY", Decimal("100"))
    registry.validate_quantity("BANKNIFTY", Decimal("15"))
    registry.validate_quantity("BANKNIFTY", Decimal("45"))


def test_lot_size_validation_failures() -> None:
    registry = LotSizeRegistry()
    with pytest.raises(LotSizeError, match="not a multiple of lot size"):
        registry.validate_quantity("NIFTY", Decimal("10"))

    with pytest.raises(LotSizeError, match="not a multiple of lot size"):
        registry.validate_quantity("BANKNIFTY", Decimal("25"))

    with pytest.raises(LotSizeError, match="must be positive"):
        registry.validate_quantity("NIFTY", Decimal("0"))

    with pytest.raises(LotSizeError, match="not an integer"):
        registry.validate_quantity("NIFTY", Decimal("25.5"))


def test_round_to_lot() -> None:
    registry = LotSizeRegistry()
    assert registry.round_to_lot("NIFTY", Decimal("30")) == Decimal("25")
    assert registry.round_to_lot("NIFTY", Decimal("74")) == Decimal("50")
    assert registry.round_to_lot("BANKNIFTY", Decimal("28")) == Decimal("15")
