"""Temporal safety, numeric safety, decimal boundaries, determinism, nesting."""

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
    DivisionByZeroError,
    InsufficientWarmupError,
    OutputKindMismatchError,
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


def test_future_data_protection_lag() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=1, series={"close": [1.0, 2.0, 10.0]})
    f = make_formula(feat("close", lag=2), "FINITE_FLOAT")
    with pytest.raises(InsufficientWarmupError):
        evaluate(f, ctx)


def test_future_data_not_accessible_long_series() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=2, series={"close": [1.0, 2.0, 3.0, 100.0, 100.0]})
    f = make_formula(op(FormulaOperator.SMA, feat("close"), lit_int(3)), "FINITE_FLOAT")
    assert evaluate(f, ctx).float_value == pytest.approx(2.0)


def test_nested_ast() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=4, series={"close": [1.0, 2.0, 3.0, 4.0, 5.0]})
    inner = op(FormulaOperator.ADD, feat("close"), op(FormulaOperator.SMA, feat("close"), lit_int(3)))
    outer = op(FormulaOperator.GT, inner, lit_int(6))
    f = make_formula(outer, "BOOLEAN", "ENTRY_FILTER")
    assert evaluate(f, ctx).boolean_value is True


def test_max_depth_realistic() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=0, series={"x": [1.0]})
    node: FormulaNode = lit_int(1)
    for _ in range(9):
        node = op(FormulaOperator.ADD, node, lit_int(1))
    f = make_formula(node, "FINITE_FLOAT")
    assert f.ast_depth == 10
    assert evaluate(f, ctx).float_value == 10.0


def test_warmup_enforcement() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=0, series={"close": [1.0]})
    f = make_formula(op(FormulaOperator.SMA, feat("close"), lit_int(2)), "FINITE_FLOAT")
    with pytest.raises(InsufficientWarmupError):
        evaluate(f, ctx)


def test_decimal_output_preserved() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=0, series={"p": [Decimal("1.5")]})
    f = make_formula(lit_decimal("1.500"), "DECIMAL")
    r = evaluate(f, ctx)
    assert isinstance(r.decimal_value, Decimal)
    assert r.decimal_value == Decimal("1.500")


def test_decimal_output_float_conversion() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=0, series={"x": [1.0]})
    f = make_formula(op(FormulaOperator.ADD, lit_int(1), lit_int(2)), "DECIMAL")
    r = evaluate(f, ctx)
    assert r.decimal_value == Decimal("3")


def test_finite_float_rejects_bool() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=0, series={"x": [1.0]})
    f = make_formula(lit_bool(True), "FINITE_FLOAT")
    with pytest.raises(OutputKindMismatchError):
        evaluate(f, ctx)


def test_nan_rejected_in_series() -> None:
    with pytest.raises(ValueError):
        FormulaEvaluationContext(evaluation_index=0, series={"close": [float("nan")]})


def test_inf_rejected_in_literal() -> None:
    with pytest.raises(Exception):
        lit_float(float("inf"))


def test_division_zero_indicator() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=2, series={"flat": [1.0, 1.0, 1.0]})
    f = make_formula(op(FormulaOperator.ZSCORE, feat("flat"), lit_int(3)), "FINITE_FLOAT")
    with pytest.raises(DivisionByZeroError):
        evaluate(f, ctx)


def test_deterministic_repeat() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=4, series={"close": [1.0, 2.0, 3.0, 4.0, 5.0]})
    f = make_formula(op(FormulaOperator.EMA, feat("close"), lit_int(3)), "FINITE_FLOAT")
    r1 = evaluate(f, ctx)
    r2 = evaluate(f, ctx)
    assert r1.float_value == r2.float_value


def test_arbitrary_code_impossibility() -> None:
    import pathlib
    import re

    src = pathlib.Path("backend/src/ats/intelligence/formula/evaluator.py").read_text()
    # Strip docstring line to avoid false positives from documentation
    src_code = re.sub(r'""".*?"""', "", src, flags=re.DOTALL)
    for banned in ["eval(", "exec(", "compile("]:
        assert banned not in src_code, f"banned {banned} found"
    assert "importlib" not in src_code
    assert "subprocess" not in src_code


def test_lag_zero_is_current() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=2, series={"close": [10.0, 20.0, 30.0, 999.0]})
    f = make_formula(feat("close", lag=0), "FINITE_FLOAT")
    assert evaluate(f, ctx).float_value == 30.0
    f1 = make_formula(feat("close", lag=1), "FINITE_FLOAT")
    assert evaluate(f1, ctx).float_value == 20.0
    f2 = make_formula(feat("close", lag=2), "FINITE_FLOAT")
    assert evaluate(f2, ctx).float_value == 10.0


def test_output_kind_mismatch_boolean_vs_float() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=0, series={"x": [1.0]})
    f = make_formula(lit_int(1), "BOOLEAN", "ENTRY_FILTER")
    with pytest.raises(OutputKindMismatchError):
        evaluate(f, ctx)
