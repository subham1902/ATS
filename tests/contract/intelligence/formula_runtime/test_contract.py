"""Contract tests for runtime: output kind, dispatch map, no hidden ops."""

from __future__ import annotations

from ats.contracts.intelligence.types import FormulaOperator
from ats.intelligence.formula.evaluator import _ARITY


def test_operator_matrix_23() -> None:
    assert len(_ARITY) == 23
    expected = {
        "ADD",
        "SUB",
        "MUL",
        "DIV",
        "GT",
        "GTE",
        "LT",
        "LTE",
        "EQ",
        "AND",
        "OR",
        "NOT",
        "SMA",
        "EMA",
        "ATR",
        "ROC",
        "RSI",
        "VWAP",
        "ZSCORE",
        "SLOPE",
        "PERCENTILE",
        "ROLLING_STD",
        "ROLLING_CORR",
    }
    assert {k.value for k in _ARITY} == expected


def test_arity_frozen() -> None:
    assert _ARITY[FormulaOperator.ADD] == (2, 2)
    assert _ARITY[FormulaOperator.NOT] == (1, 1)
    assert _ARITY[FormulaOperator.AND][0] == 2 and _ARITY[FormulaOperator.AND][1] is None
    assert _ARITY[FormulaOperator.ATR] == (4, 4)
    assert _ARITY[FormulaOperator.PERCENTILE] == (3, 3)


def test_no_extra_operator() -> None:
    import pathlib
    import re

    src = pathlib.Path("backend/src/ats/intelligence/formula/evaluator.py").read_text()
    src_code = re.sub(r'""".*?"""', "", src, flags=re.DOTALL)
    assert "eval(" not in src_code
    assert "exec(" not in src_code
    assert "importlib" not in src_code
