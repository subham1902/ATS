"""Deterministic evaluation errors for IBA-R13. Never emits NaN/Inf."""

from __future__ import annotations


class FormulaEvaluationError(Exception):
    """Base for all deterministic evaluator failures."""


class ArityError(FormulaEvaluationError):
    pass


class TypeError_(FormulaEvaluationError):
    pass


class DivisionByZeroError(FormulaEvaluationError):
    pass


class InsufficientWarmupError(FormulaEvaluationError):
    pass


class EmptyWindowError(FormulaEvaluationError):
    pass


class InvalidWindowError(FormulaEvaluationError):
    pass


class InvalidPercentileError(FormulaEvaluationError):
    pass


class NumericSafetyError(FormulaEvaluationError):
    pass


class FutureDataAccessError(FormulaEvaluationError):
    pass


class UnknownFeatureError(FormulaEvaluationError):
    pass


class OutputKindMismatchError(FormulaEvaluationError):
    pass


__all__ = [
    "ArityError",
    "DivisionByZeroError",
    "EmptyWindowError",
    "FormulaEvaluationError",
    "FutureDataAccessError",
    "InsufficientWarmupError",
    "InvalidPercentileError",
    "InvalidWindowError",
    "NumericSafetyError",
    "OutputKindMismatchError",
    "TypeError_",
    "UnknownFeatureError",
]
