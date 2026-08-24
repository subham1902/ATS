"""Minimal bounded evaluation context.

Temporal safety: lag 0 = current completed observation at evaluation_index.
lag N >0 = past. No future offset exists. Access beyond evaluation_index
is prohibited and raises FutureDataAccessError.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class FormulaEvaluationContext:
    """Bounded series inputs required for a single evaluation point.

    Attributes:
        evaluation_index: inclusive cutoff index; 0-based. No reads > index.
        series: mapping feature_code -> bounded sequence (oldest at 0,
                newest at len-1). Must have len > evaluation_index.
    """

    evaluation_index: int
    series: Mapping[str, Sequence[float | Decimal | int]]

    def __post_init__(self) -> None:
        if self.evaluation_index < 0:
            raise ValueError("evaluation_index must be >=0")
        # Validate finiteness eagerly, prevent NaN/Inf crossing API.
        for code, seq in self.series.items():
            if not seq:
                continue
            for v in seq:
                if isinstance(v, float):
                    if not math.isfinite(v):
                        raise ValueError(f"series {code} contains non-finite float")
                elif isinstance(v, Decimal):
                    if not v.is_finite():
                        raise ValueError(f"series {code} contains non-finite Decimal")
                elif isinstance(v, int) and not isinstance(v, bool):
                    # ints are finite by construction
                    pass
                else:
                    raise ValueError(f"series {code} contains unsupported type {type(v)}")

    def get_value(self, feature_code: str, lag_bars: int) -> float | Decimal | int | bool:
        """Return scalar at evaluation_index - lag_bars with temporal guard."""
        if lag_bars < 0:
            raise ValueError("lag_bars must be >=0")
        target = self.evaluation_index - lag_bars
        if target < 0:
            from .errors import InsufficientWarmupError

            raise InsufficientWarmupError(
                f"lag {lag_bars} beyond start at index {self.evaluation_index}"
            )
        seq = self.series.get(feature_code)
        if seq is None:
            from .errors import UnknownFeatureError

            raise UnknownFeatureError(f"unknown feature {feature_code}")
        if target > self.evaluation_index:
            from .errors import FutureDataAccessError

            raise FutureDataAccessError("future access beyond evaluation_index")
        if target >= len(seq):
            from .errors import InsufficientWarmupError

            raise InsufficientWarmupError(f"series {feature_code} too short for index {target}")
        # Also guard that evaluation_index itself is < len(seq)
        if self.evaluation_index >= len(seq):
            from .errors import InsufficientWarmupError

            raise InsufficientWarmupError(f"series {feature_code} too short for evaluation_index")
        val = seq[target]
        # Final finite check
        if isinstance(val, float) and not math.isfinite(val):
            from .errors import NumericSafetyError

            raise NumericSafetyError("NaN/Inf in series value")
        if isinstance(val, Decimal) and not val.is_finite():
            from .errors import NumericSafetyError

            raise NumericSafetyError("non-finite Decimal in series")
        return val

    def get_window(self, feature_code: str, window: int) -> list[float]:
        """Return window values ending at evaluation_index inclusive as floats.

        Converts Decimal/int to float for indicator math; preserves determinism.
        Enforces temporal safety and warmup.
        """
        if window <= 0:
            from .errors import InvalidWindowError

            raise InvalidWindowError(f"window must be >0 got {window}")
        if window > self.evaluation_index + 1:
            from .errors import InsufficientWarmupError

            raise InsufficientWarmupError(f"insufficient warmup for window {window}")
        seq = self.series.get(feature_code)
        if seq is None:
            from .errors import UnknownFeatureError

            raise UnknownFeatureError(f"unknown feature {feature_code}")
        if self.evaluation_index >= len(seq):
            from .errors import InsufficientWarmupError

            raise InsufficientWarmupError("series too short")
        start = self.evaluation_index - window + 1
        if start < 0:
            from .errors import InsufficientWarmupError

            raise InsufficientWarmupError("insufficient warmup")
        out: list[float] = []
        for i in range(start, self.evaluation_index + 1):
            v = seq[i]
            if isinstance(v, float):
                if not math.isfinite(v):
                    from .errors import NumericSafetyError

                    raise NumericSafetyError("NaN/Inf in window")
                out.append(v)
            elif isinstance(v, Decimal):
                if not v.is_finite():
                    from .errors import NumericSafetyError

                    raise NumericSafetyError("non-finite Decimal in window")
                out.append(float(v))
            elif isinstance(v, int) and not isinstance(v, bool):
                out.append(float(v))
            else:
                from .errors import TypeError_

                raise TypeError_(f"non-numeric value in window: {v!r}")
        return out


__all__ = ["FormulaEvaluationContext"]
