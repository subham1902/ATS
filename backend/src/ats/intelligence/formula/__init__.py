"""Safe formula runtime — IBA-R13 bounded execution."""

from .context import FormulaEvaluationContext
from .errors import (
    ArityError,
    DivisionByZeroError,
    EmptyWindowError,
    FormulaEvaluationError,
    FutureDataAccessError,
    InsufficientWarmupError,
    InvalidPercentileError,
    InvalidWindowError,
    NumericSafetyError,
    OutputKindMismatchError,
    TypeError_,
    UnknownFeatureError,
)
from .evaluator import evaluate
from .result import FormulaResult

__all__ = [
    "ArityError",
    "DivisionByZeroError",
    "EmptyWindowError",
    "FormulaEvaluationContext",
    "FormulaEvaluationError",
    "FormulaResult",
    "FutureDataAccessError",
    "InsufficientWarmupError",
    "InvalidPercentileError",
    "InvalidWindowError",
    "NumericSafetyError",
    "OutputKindMismatchError",
    "TypeError_",
    "UnknownFeatureError",
    "evaluate",
]
