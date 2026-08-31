"""Property-style determinism and invariant tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

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


def make_formula(ast: FormulaNode, output_kind: str) -> FormulaDefinition:
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
        purpose=FormulaPurpose.FEATURE,
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


def test_determinism_across_repeats() -> None:
    ctx = FormulaEvaluationContext(evaluation_index=3, series={"close": [1.0, 2.0, 3.0, 4.0]})
    f = make_formula(op(FormulaOperator.SMA, feat("close"), lit_int(3)), "FINITE_FLOAT")
    vals = [evaluate(f, ctx).float_value for _ in range(5)]
    assert len(set(vals)) == 1


def test_temporal_invariance_future_not_used() -> None:
    base = [1.0, 2.0, 3.0]
    ctx1 = FormulaEvaluationContext(evaluation_index=2, series={"close": base + [999.0]})
    ctx2 = FormulaEvaluationContext(evaluation_index=2, series={"close": base + [0.0]})
    f = make_formula(op(FormulaOperator.SMA, feat("close"), lit_int(3)), "FINITE_FLOAT")
    assert evaluate(f, ctx1).float_value == evaluate(f, ctx2).float_value


def test_no_randomness_or_clock() -> None:
    import pathlib

    text = pathlib.Path("backend/src/ats/intelligence/formula/evaluator.py").read_text()
    assert "random" not in text.lower()
    assert "datetime.now" not in text
    assert "time.time" not in text
