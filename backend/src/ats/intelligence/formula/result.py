"""Typed result matching FormulaOutputKind."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True, slots=True)
class FormulaResult:
    kind: Literal["BOOLEAN", "FINITE_FLOAT", "DECIMAL"]
    boolean_value: bool | None = None
    float_value: float | None = None
    decimal_value: Decimal | None = None

    def __post_init__(self) -> None:
        # Validate kind matches supplied value
        import math

        if self.kind == "BOOLEAN":
            if (
                self.boolean_value is None
                or self.float_value is not None
                or self.decimal_value is not None
            ):
                raise ValueError("BOOLEAN result requires boolean_value only")
            if type(self.boolean_value) is not bool:
                raise ValueError("BOOLEAN requires bool")
        elif self.kind == "FINITE_FLOAT":
            if (
                self.float_value is None
                or self.boolean_value is not None
                or self.decimal_value is not None
            ):
                raise ValueError("FINITE_FLOAT requires float_value only")
            if type(self.float_value) is not float:
                raise ValueError("FINITE_FLOAT requires float")
            if not math.isfinite(self.float_value):
                raise ValueError("FINITE_FLOAT must be finite")
        elif self.kind == "DECIMAL":
            if (
                self.decimal_value is None
                or self.boolean_value is not None
                or self.float_value is not None
            ):
                raise ValueError("DECIMAL requires decimal_value only")
            if not isinstance(self.decimal_value, Decimal):
                raise ValueError("DECIMAL requires Decimal")
            if not self.decimal_value.is_finite():
                raise ValueError("DECIMAL must be finite")
        else:
            raise ValueError(f"unknown kind {self.kind}")

    @property
    def value(self) -> bool | float | Decimal:
        if self.kind == "BOOLEAN":
            return self.boolean_value  # type: ignore[return-value]
        if self.kind == "FINITE_FLOAT":
            return self.float_value  # type: ignore[return-value]
        return self.decimal_value  # type: ignore[return-value]


__all__ = ["FormulaResult"]
