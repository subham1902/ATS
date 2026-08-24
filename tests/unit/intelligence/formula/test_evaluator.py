"""Unit tests for 23 operators: valid, edge, arity, type."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from ats.contracts.intelligence.models import FormulaDefinition
from ats.contracts.intelligence.types import (
    FormulaNode,
    FormulaNodeKind,
    FormulaOperator,
    FormulaOutputKind,
    FormulaPurpose,
    StrategyOrigin,
)
from ats.intelligence.formula import FormulaEvaluationContext
from ats.intelligence.formula.errors import (
    ArityError,
    DivisionByZeroError,
    InsufficientWarmupError,
    InvalidPercentileError,
    InvalidWindowError,
    TypeError_,
)
from ats.intelligence.formula.evaluator import evaluate


def lit_int(v: int) -> FormulaNode:
    return FormulaNode(
        node_kind=FormulaNodeKind.LITERAL,
        operator=None,
        arguments=(),
        feature_code=None,
        lag_bars=None,
        literal_decimal=None,
        literal_float=None,
        literal_int=v,
        literal_bool=None,
    )


def lit_float(v: float) -> FormulaNode:
    return FormulaNode(
        node_kind=FormulaNodeKind.LITERAL,
        operator=None,
        arguments=(),
        feature_code=None,
        lag_bars=None,
        literal_decimal=None,
        literal_float=v,
        literal_int=None,
        literal_bool=None,
    )


def lit_decimal(v: str) -> FormulaNode:
    return FormulaNode(
        node_kind=FormulaNodeKind.LITERAL,
        operator=None,
        arguments=(),
        feature_code=None,
        lag_bars=None,
        literal_decimal=Decimal(v),
        literal_float=None,
        literal_int=None,
        literal_bool=None,
    )


def lit_bool(v: bool) -> FormulaNode:
    return FormulaNode(
        node_kind=FormulaNodeKind.LITERAL,
        operator=None,
        arguments=(),
        feature_code=None,
        lag_bars=None,
        literal_decimal=None,
        literal_float=None,
        literal_int=None,
        literal_bool=v,
    )


def feat(code: str, lag: int = 0) -> FormulaNode:
    return FormulaNode(
        node_kind=FormulaNodeKind.FEATURE,
        operator=None,
        arguments=(),
        feature_code=code,
        lag_bars=lag,
        literal_decimal=None,
        literal_float=None,
        literal_int=None,
        literal_bool=None,
    )


def op(operator: FormulaOperator, *args: FormulaNode) -> FormulaNode:
    return FormulaNode(
        node_kind=FormulaNodeKind.OPERATOR,
        operator=operator,
        arguments=tuple(args),
        feature_code=None,
        lag_bars=None,
        literal_decimal=None,
        literal_float=None,
        literal_int=None,
        literal_bool=None,
    )


def make_formula(ast: FormulaNode, output_kind: str, purpose: str = "FEATURE") -> FormulaDefinition:
    def meta(node: FormulaNode) -> tuple[int, int, int, set[str]]:
        child = [meta(a) for a in node.arguments]
        depth = 1 + max((c[0] for c in child), default=0)
        count = 1 + sum(c[1] for c in child)
        lag = max([node.lag_bars or 0, *(c[2] for c in child)])
        feats: set[str] = set().union(*(c[3] for c in child)) if child else set()
        if node.node_kind is FormulaNodeKind.FEATURE and node.feature_code:
            feats.add(node.feature_code)
        return depth, count, lag, feats

    depth, count, lag, feats = meta(ast)
    return FormulaDefinition(
        schema_version="1.0",
        formula_definition_id=uuid4(),
        formula_version=1,
        name="test",
        purpose=FormulaPurpose(purpose),
        output_kind=FormulaOutputKind(output_kind),
        timeframe="M01",
        lookback_bars=max(lag, 5),
        warmup_bars=0,
        ast=ast,
        ast_depth=depth,
        node_count=count,
        max_lag_bars=lag,
        required_features=tuple(sorted(feats)),
        parameters=(),
        source_instruction_hash="a" * 64,
        origin=StrategyOrigin.HUMAN,
        created_at=datetime.now(UTC),
        payload_hash="b" * 64,
    )


def ctx_simple() -> FormulaEvaluationContext:
    return FormulaEvaluationContext(
        evaluation_index=4,
        series={
            "close": [1.0, 2.0, 3.0, 4.0, 5.0],
            "high": [2.0, 3.0, 4.0, 5.0, 6.0],
            "low": [0.5, 1.0, 1.5, 2.0, 2.5],
            "price": [10.0, 11.0, 12.0, 13.0, 14.0],
            "volume": [100.0, 200.0, 150.0, 300.0, 250.0],
            "a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "b": [5.0, 4.0, 3.0, 2.0, 1.0],
            "flat": [1.0, 1.0, 1.0, 1.0, 1.0],
        },
    )


# --- Arithmetic ---
def test_add_valid() -> None:
    f = make_formula(op(FormulaOperator.ADD, lit_int(2), lit_int(3)), "FINITE_FLOAT")
    r = evaluate(f, ctx_simple())
    assert r.float_value == 5.0


def test_add_decimal_preserved() -> None:
    f = make_formula(op(FormulaOperator.ADD, lit_decimal("1.5"), lit_decimal("2.5")), "DECIMAL")
    r = evaluate(f, ctx_simple())
    assert r.decimal_value == Decimal("4.0")


def test_add_wrong_arity() -> None:
    f = make_formula(op(FormulaOperator.ADD, lit_int(1)), "FINITE_FLOAT")
    with pytest.raises(ArityError):
        evaluate(f, ctx_simple())


def test_add_bad_type() -> None:
    f = make_formula(op(FormulaOperator.ADD, lit_bool(True), lit_int(1)), "FINITE_FLOAT")
    with pytest.raises(TypeError_):
        evaluate(f, ctx_simple())


def test_sub_valid() -> None:
    f = make_formula(op(FormulaOperator.SUB, lit_int(5), lit_int(3)), "FINITE_FLOAT")
    assert evaluate(f, ctx_simple()).float_value == 2.0


def test_sub_wrong_arity() -> None:
    f = make_formula(op(FormulaOperator.SUB, lit_int(1), lit_int(2), lit_int(3)), "FINITE_FLOAT")
    with pytest.raises(ArityError):
        evaluate(f, ctx_simple())


def test_mul_valid() -> None:
    f = make_formula(op(FormulaOperator.MUL, lit_int(4), lit_int(3)), "FINITE_FLOAT")
    assert evaluate(f, ctx_simple()).float_value == 12.0


def test_mul_bad_type_bool() -> None:
    f = make_formula(op(FormulaOperator.MUL, lit_bool(True), lit_int(2)), "FINITE_FLOAT")
    with pytest.raises(TypeError_):
        evaluate(f, ctx_simple())


def test_div_valid() -> None:
    f = make_formula(op(FormulaOperator.DIV, lit_int(10), lit_int(2)), "FINITE_FLOAT")
    assert evaluate(f, ctx_simple()).float_value == 5.0


def test_div_by_zero() -> None:
    f = make_formula(op(FormulaOperator.DIV, lit_int(10), lit_int(0)), "FINITE_FLOAT")
    with pytest.raises(DivisionByZeroError):
        evaluate(f, ctx_simple())


def test_div_wrong_arity() -> None:
    f = make_formula(op(FormulaOperator.DIV, lit_int(1)), "FINITE_FLOAT")
    with pytest.raises(ArityError):
        evaluate(f, ctx_simple())


# --- Comparisons ---
def test_gt_valid() -> None:
    f = make_formula(op(FormulaOperator.GT, lit_int(5), lit_int(3)), "BOOLEAN", "ENTRY_FILTER")
    assert evaluate(f, ctx_simple()).boolean_value is True


def test_gt_edge_equal_false() -> None:
    f = make_formula(op(FormulaOperator.GT, lit_int(3), lit_int(3)), "BOOLEAN", "ENTRY_FILTER")
    assert evaluate(f, ctx_simple()).boolean_value is False


def test_gt_wrong_arity() -> None:
    f = make_formula(op(FormulaOperator.GT, lit_int(1)), "BOOLEAN", "ENTRY_FILTER")
    with pytest.raises(ArityError):
        evaluate(f, ctx_simple())


def test_gt_bad_type_bool() -> None:
    f = make_formula(op(FormulaOperator.GT, lit_bool(True), lit_bool(False)), "BOOLEAN", "ENTRY_FILTER")
    with pytest.raises(TypeError_):
        evaluate(f, ctx_simple())


def test_gte_valid() -> None:
    f = make_formula(op(FormulaOperator.GTE, lit_int(3), lit_int(3)), "BOOLEAN", "ENTRY_FILTER")
    assert evaluate(f, ctx_simple()).boolean_value is True


def test_lt_valid() -> None:
    f = make_formula(op(FormulaOperator.LT, lit_int(2), lit_int(3)), "BOOLEAN", "ENTRY_FILTER")
    assert evaluate(f, ctx_simple()).boolean_value is True


def test_lte_valid() -> None:
    f = make_formula(op(FormulaOperator.LTE, lit_int(3), lit_int(3)), "BOOLEAN", "ENTRY_FILTER")
    assert evaluate(f, ctx_simple()).boolean_value is True


def test_eq_valid_numeric() -> None:
    f = make_formula(op(FormulaOperator.EQ, lit_int(3), lit_int(3)), "BOOLEAN", "ENTRY_FILTER")
    assert evaluate(f, ctx_simple()).boolean_value is True


def test_eq_valid_bool() -> None:
    f = make_formula(op(FormulaOperator.EQ, lit_bool(True), lit_bool(True)), "BOOLEAN", "ENTRY_FILTER")
    assert evaluate(f, ctx_simple()).boolean_value is True


def test_eq_bad_mixed_bool_numeric() -> None:
    f = make_formula(op(FormulaOperator.EQ, lit_bool(True), lit_int(1)), "BOOLEAN", "ENTRY_FILTER")
    with pytest.raises(TypeError_):
        evaluate(f, ctx_simple())


# --- Logical ---
def test_and_valid() -> None:
    f = make_formula(op(FormulaOperator.AND, lit_bool(True), lit_bool(True)), "BOOLEAN", "ENTRY_FILTER")
    assert evaluate(f, ctx_simple()).boolean_value is True


def test_and_variadic() -> None:
    f = make_formula(
        op(FormulaOperator.AND, lit_bool(True), lit_bool(True), lit_bool(False)), "BOOLEAN", "ENTRY_FILTER"
    )
    assert evaluate(f, ctx_simple()).boolean_value is False


def test_and_wrong_arity_one() -> None:
    f = make_formula(op(FormulaOperator.AND, lit_bool(True)), "BOOLEAN", "ENTRY_FILTER")
    with pytest.raises(ArityError):
        evaluate(f, ctx_simple())


def test_and_bad_type() -> None:
    f = make_formula(op(FormulaOperator.AND, lit_int(1), lit_bool(True)), "BOOLEAN", "ENTRY_FILTER")
    with pytest.raises(TypeError_):
        evaluate(f, ctx_simple())


def test_or_valid() -> None:
    f = make_formula(op(FormulaOperator.OR, lit_bool(False), lit_bool(True)), "BOOLEAN", "ENTRY_FILTER")
    assert evaluate(f, ctx_simple()).boolean_value is True


def test_or_bad_type() -> None:
    f = make_formula(op(FormulaOperator.OR, lit_int(1), lit_bool(True)), "BOOLEAN", "ENTRY_FILTER")
    with pytest.raises(TypeError_):
        evaluate(f, ctx_simple())


def test_not_valid() -> None:
    f = make_formula(op(FormulaOperator.NOT, lit_bool(False)), "BOOLEAN", "ENTRY_FILTER")
    assert evaluate(f, ctx_simple()).boolean_value is True


def test_not_wrong_arity() -> None:
    f = make_formula(op(FormulaOperator.NOT, lit_bool(True), lit_bool(False)), "BOOLEAN", "ENTRY_FILTER")
    with pytest.raises(ArityError):
        evaluate(f, ctx_simple())


def test_not_bad_type() -> None:
    f = make_formula(op(FormulaOperator.NOT, lit_int(1)), "BOOLEAN", "ENTRY_FILTER")
    with pytest.raises(TypeError_):
        evaluate(f, ctx_simple())


# --- Indicators ---
def test_sma_valid() -> None:
    f = make_formula(op(FormulaOperator.SMA, feat("close"), lit_int(3)), "FINITE_FLOAT")
    assert evaluate(f, ctx_simple()).float_value == pytest.approx(4.0)


def test_sma_insufficient_warmup() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=1, series={"close": [1.0, 2.0, 3.0]})
    f = make_formula(op(FormulaOperator.SMA, feat("close"), lit_int(5)), "FINITE_FLOAT")
    with pytest.raises(InsufficientWarmupError):
        evaluate(f, ctx)


def test_sma_wrong_arity() -> None:
    f = make_formula(op(FormulaOperator.SMA, feat("close")), "FINITE_FLOAT")
    with pytest.raises(ArityError):
        evaluate(f, ctx_simple())


def test_sma_bad_type_series_not_feature() -> None:
    f = make_formula(op(FormulaOperator.SMA, lit_int(1), lit_int(2)), "FINITE_FLOAT")
    with pytest.raises(TypeError_):
        evaluate(f, ctx_simple())


def test_ema_valid() -> None:
    f = make_formula(op(FormulaOperator.EMA, feat("close"), lit_int(3)), "FINITE_FLOAT")
    r = evaluate(f, ctx_simple())
    assert isinstance(r.float_value, float)
    assert math.isfinite(r.float_value)  # type: ignore[arg-type]


def test_ema_bad_window_zero() -> None:
    f = make_formula(op(FormulaOperator.EMA, feat("close"), lit_int(0)), "FINITE_FLOAT")
    with pytest.raises(InvalidWindowError):
        evaluate(f, ctx_simple())


def test_atr_valid() -> None:
    f = make_formula(
        op(FormulaOperator.ATR, feat("high"), feat("low"), feat("close"), lit_int(3)), "FINITE_FLOAT"
    )
    r = evaluate(f, ctx_simple())
    assert math.isfinite(r.float_value)  # type: ignore[arg-type]


def test_atr_wrong_arity() -> None:
    f = make_formula(op(FormulaOperator.ATR, feat("high"), feat("low"), lit_int(3)), "FINITE_FLOAT")
    with pytest.raises(ArityError):
        evaluate(f, ctx_simple())


def test_roc_valid() -> None:
    f = make_formula(op(FormulaOperator.ROC, feat("close"), lit_int(1)), "FINITE_FLOAT")
    assert evaluate(f, ctx_simple()).float_value == pytest.approx(25.0)


def test_roc_div_zero() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=1, series={"close": [0.0, 1.0]})
    f = make_formula(op(FormulaOperator.ROC, feat("close"), lit_int(1)), "FINITE_FLOAT")
    with pytest.raises(DivisionByZeroError):
        evaluate(f, ctx)


def test_rsi_valid() -> None:
    f = make_formula(op(FormulaOperator.RSI, feat("close"), lit_int(3)), "FINITE_FLOAT")
    r = evaluate(f, ctx_simple())
    assert 0 <= r.float_value <= 100  # type: ignore[operator]


def test_rsi_warmup_error() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=1, series={"close": [1.0, 2.0]})
    f = make_formula(op(FormulaOperator.RSI, feat("close"), lit_int(14)), "FINITE_FLOAT")
    with pytest.raises(InsufficientWarmupError):
        evaluate(f, ctx)


def test_vwap_valid() -> None:
    f = make_formula(op(FormulaOperator.VWAP, feat("price"), feat("volume"), lit_int(3)), "FINITE_FLOAT")
    r = evaluate(f, ctx_simple())
    assert math.isfinite(r.float_value)  # type: ignore[arg-type]


def test_vwap_zero_volume() -> None:
    ctx = FormulaEvaluationContext(
        evaluation_index=2, series={"price": [1.0, 2.0, 3.0], "volume": [0.0, 0.0, 0.0]}
    )
    f = make_formula(op(FormulaOperator.VWAP, feat("price"), feat("volume"), lit_int(3)), "FINITE_FLOAT")
    with pytest.raises(DivisionByZeroError):
        evaluate(f, ctx)


def test_zscore_valid() -> None:
    f = make_formula(op(FormulaOperator.ZSCORE, feat("close"), lit_int(3)), "FINITE_FLOAT")
    r = evaluate(f, ctx_simple())
    assert math.isfinite(r.float_value)  # type: ignore[arg-type]


def test_zscore_std_zero() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=2, series={"flat": [1.0, 1.0, 1.0]})
    f = make_formula(op(FormulaOperator.ZSCORE, feat("flat"), lit_int(3)), "FINITE_FLOAT")
    with pytest.raises(DivisionByZeroError):
        evaluate(f, ctx)


def test_slope_valid() -> None:
    f = make_formula(op(FormulaOperator.SLOPE, feat("close"), lit_int(3)), "FINITE_FLOAT")
    r = evaluate(f, ctx_simple())
    assert r.float_value == pytest.approx(1.0)


def test_percentile_valid() -> None:
    f = make_formula(op(FormulaOperator.PERCENTILE, feat("close"), lit_int(5), lit_int(50)), "FINITE_FLOAT")
    r = evaluate(f, ctx_simple())
    assert r.float_value == pytest.approx(3.0)


def test_percentile_invalid_p() -> None:
    f = make_formula(op(FormulaOperator.PERCENTILE, feat("close"), lit_int(3), lit_float(150.0)), "FINITE_FLOAT")
    with pytest.raises(InvalidPercentileError):
        evaluate(f, ctx_simple())


def test_percentile_wrong_arity() -> None:
    f = make_formula(op(FormulaOperator.PERCENTILE, feat("close"), lit_int(3)), "FINITE_FLOAT")
    with pytest.raises(ArityError):
        evaluate(f, ctx_simple())


def test_rolling_std_valid() -> None:
    f = make_formula(op(FormulaOperator.ROLLING_STD, feat("close"), lit_int(3)), "FINITE_FLOAT")
    r = evaluate(f, ctx_simple())
    assert r.float_value == pytest.approx(0.8164965809, rel=1e-5)


def test_rolling_std_zero_var() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=2, series={"flat": [1.0, 1.0, 1.0]})
    f = make_formula(op(FormulaOperator.ROLLING_STD, feat("flat"), lit_int(3)), "FINITE_FLOAT")
    assert evaluate(f, ctx).float_value == pytest.approx(0.0)


def test_rolling_corr_valid() -> None:
    f = make_formula(op(FormulaOperator.ROLLING_CORR, feat("a"), feat("b"), lit_int(5)), "FINITE_FLOAT")
    r = evaluate(f, ctx_simple())
    assert r.float_value == pytest.approx(-1.0)


def test_rolling_corr_zero_std() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=2, series={"a": [1.0, 1.0, 1.0], "b": [1.0, 2.0, 3.0]})
    f = make_formula(op(FormulaOperator.ROLLING_CORR, feat("a"), feat("b"), lit_int(3)), "FINITE_FLOAT")
    with pytest.raises(DivisionByZeroError):
        evaluate(f, ctx)


def test_rolling_corr_wrong_arity() -> None:
    f = make_formula(op(FormulaOperator.ROLLING_CORR, feat("a"), feat("b")), "FINITE_FLOAT")
    with pytest.raises(ArityError):
        evaluate(f, ctx_simple())
