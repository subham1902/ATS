"""Deterministic recursive evaluator for frozen IBA Formula DSL.

- No eval/exec/compile/importlib/subprocess/filesystem/network
- Explicit operator dispatch map
- Respects lag semantics, temporal safety, arity, type, numeric safety
"""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation

from ats.contracts.intelligence.models import FormulaDefinition
from ats.contracts.intelligence.types import (
    FormulaNode,
    FormulaNodeKind,
    FormulaOperator,
    FormulaOutputKind,
)

from .context import FormulaEvaluationContext
from .errors import (
    ArityError,
    DivisionByZeroError,
    FormulaEvaluationError,
    NumericSafetyError,
    OutputKindMismatchError,
    TypeError_,
)
from .result import FormulaResult

# frozen arity map: operator -> (min_args, max_args) where max None = variadic
# For AND/OR, spec says >=2
_ARITY: dict[FormulaOperator, tuple[int, int | None]] = {
    FormulaOperator.ADD: (2, 2),
    FormulaOperator.SUB: (2, 2),
    FormulaOperator.MUL: (2, 2),
    FormulaOperator.DIV: (2, 2),
    FormulaOperator.GT: (2, 2),
    FormulaOperator.GTE: (2, 2),
    FormulaOperator.LT: (2, 2),
    FormulaOperator.LTE: (2, 2),
    FormulaOperator.EQ: (2, 2),
    FormulaOperator.AND: (2, None),
    FormulaOperator.OR: (2, None),
    FormulaOperator.NOT: (1, 1),
    FormulaOperator.SMA: (2, 2),
    FormulaOperator.EMA: (2, 2),
    FormulaOperator.ATR: (4, 4),
    FormulaOperator.ROC: (2, 2),
    FormulaOperator.RSI: (2, 2),
    FormulaOperator.VWAP: (3, 3),
    FormulaOperator.ZSCORE: (2, 2),
    FormulaOperator.SLOPE: (2, 2),
    FormulaOperator.PERCENTILE: (3, 3),
    FormulaOperator.ROLLING_STD: (2, 2),
    FormulaOperator.ROLLING_CORR: (3, 3),
}

# Type aliases for internal values
Scalar = bool | float | Decimal | int


def _check_finite_scalar(v: Scalar) -> None:
    if isinstance(v, float):
        if not math.isfinite(v):
            raise NumericSafetyError("non-finite float intermediate")
    elif isinstance(v, Decimal):
        if not v.is_finite():
            raise NumericSafetyError("non-finite Decimal intermediate")


def _to_float(v: Scalar) -> float:
    if isinstance(v, bool):
        raise TypeError_("bool not numeric")
    if isinstance(v, int) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, float):
        if not math.isfinite(v):
            raise NumericSafetyError("non-finite float")
        return v
    raise TypeError_(f"cannot convert {v!r} to float")


def _to_decimal(v: Scalar) -> Decimal:
    if isinstance(v, bool):
        raise TypeError_("bool not decimal")
    if isinstance(v, Decimal):
        return v
    if isinstance(v, int) and not isinstance(v, bool):
        return Decimal(v)
    if isinstance(v, float):
        if not math.isfinite(v):
            raise NumericSafetyError("non-finite float to Decimal")
        return Decimal(str(v))
    raise TypeError_(f"cannot convert {v!r} to Decimal")


def _ensure_arity(op: FormulaOperator, n: int) -> None:
    lo, hi = _ARITY[op]
    if hi is None:
        if n < lo:
            raise ArityError(f"{op} requires at least {lo} args, got {n}")
    else:
        if n != lo or n != hi:
            if n < lo or n > hi:
                raise ArityError(f"{op} requires {lo} args, got {n}")


# Import indicators lazily to avoid cycle
from . import indicators as _ind  # noqa: E402


def _eval_node(node: FormulaNode, ctx: FormulaEvaluationContext) -> Scalar:
    if node.node_kind is FormulaNodeKind.LITERAL:
        if node.literal_bool is not None:
            return node.literal_bool
        if node.literal_int is not None:
            return node.literal_int
        if node.literal_float is not None:
            flt: float = node.literal_float
            if not math.isfinite(flt):
                raise NumericSafetyError("literal float non-finite")
            return flt
        if node.literal_decimal is not None:
            dec: Decimal = node.literal_decimal
            if not dec.is_finite():
                raise NumericSafetyError("literal decimal non-finite")
            return dec
        raise TypeError_("invalid literal node")
    if node.node_kind is FormulaNodeKind.FEATURE:
        assert node.feature_code is not None
        assert node.lag_bars is not None
        return ctx.get_value(node.feature_code, node.lag_bars)
    # OPERATOR
    assert node.operator is not None
    op = node.operator
    args = node.arguments
    _ensure_arity(op, len(args))

    # Dispatch explicitly - no dynamic lookup
    if op is FormulaOperator.ADD:
        a = _eval_node(args[0], ctx)
        b = _eval_node(args[1], ctx)
        if isinstance(a, Decimal) or isinstance(b, Decimal):
            da = _to_decimal(a)
            db = _to_decimal(b)
            res = da + db
            _check_finite_scalar(res)
            return res
        fa = _to_float(a)
        fb = _to_float(b)
        res_f = fa + fb
        if not math.isfinite(res_f):
            raise NumericSafetyError("ADD overflow")
        return res_f
    if op is FormulaOperator.SUB:
        a = _eval_node(args[0], ctx)
        b = _eval_node(args[1], ctx)
        if isinstance(a, Decimal) or isinstance(b, Decimal):
            da = _to_decimal(a)
            db = _to_decimal(b)
            res = da - db
            _check_finite_scalar(res)
            return res
        fa = _to_float(a)
        fb = _to_float(b)
        res_f = fa - fb
        if not math.isfinite(res_f):
            raise NumericSafetyError("SUB overflow")
        return res_f
    if op is FormulaOperator.MUL:
        a = _eval_node(args[0], ctx)
        b = _eval_node(args[1], ctx)
        if isinstance(a, Decimal) or isinstance(b, Decimal):
            da = _to_decimal(a)
            db = _to_decimal(b)
            res = da * db
            _check_finite_scalar(res)
            return res
        fa = _to_float(a)
        fb = _to_float(b)
        res_f = fa * fb
        if not math.isfinite(res_f):
            raise NumericSafetyError("MUL overflow")
        return res_f
    if op is FormulaOperator.DIV:
        a = _eval_node(args[0], ctx)
        b = _eval_node(args[1], ctx)
        if isinstance(a, Decimal) or isinstance(b, Decimal):
            da = _to_decimal(a)
            db = _to_decimal(b)
            if db == Decimal(0):
                raise DivisionByZeroError("division by zero")
            try:
                res = da / db
            except (InvalidOperation, DivisionByZeroError) as e:
                raise DivisionByZeroError(str(e)) from e
            _check_finite_scalar(res)
            return res
        fa = _to_float(a)
        fb = _to_float(b)
        if fb == 0.0:
            raise DivisionByZeroError("division by zero")
        res_f = fa / fb
        if not math.isfinite(res_f):
            raise NumericSafetyError("DIV non-finite")
        return res_f
    if op in (
        FormulaOperator.GT,
        FormulaOperator.GTE,
        FormulaOperator.LT,
        FormulaOperator.LTE,
        FormulaOperator.EQ,
    ):
        a = _eval_node(args[0], ctx)
        b = _eval_node(args[1], ctx)
        if op is FormulaOperator.EQ:
            if isinstance(a, bool) or isinstance(b, bool):
                if type(a) is not bool or type(b) is not bool:
                    raise TypeError_("EQ bool requires both bool")
                return bool(a) == bool(b)
            if isinstance(a, Decimal) or isinstance(b, Decimal):
                da = _to_decimal(a)
                db = _to_decimal(b)
                return da == db
            fa = _to_float(a)
            fb = _to_float(b)
            return fa == fb
        if isinstance(a, bool) or isinstance(b, bool):
            raise TypeError_(f"{op} requires numeric operands")
        if isinstance(a, Decimal) or isinstance(b, Decimal):
            da = _to_decimal(a)
            db = _to_decimal(b)
            if op is FormulaOperator.GT:
                return da > db
            if op is FormulaOperator.GTE:
                return da >= db
            if op is FormulaOperator.LT:
                return da < db
            if op is FormulaOperator.LTE:
                return da <= db
        else:
            fa = _to_float(a)
            fb = _to_float(b)
            if op is FormulaOperator.GT:
                return fa > fb
            if op is FormulaOperator.GTE:
                return fa >= fb
            if op is FormulaOperator.LT:
                return fa < fb
            if op is FormulaOperator.LTE:
                return fa <= fb
        raise TypeError_("unreachable comparison")
    if op is FormulaOperator.AND:
        vals: list[bool] = []
        for arg in args:
            v = _eval_node(arg, ctx)
            if type(v) is not bool:
                raise TypeError_("AND requires bool operands")
            vals.append(v)
        return all(vals)
    if op is FormulaOperator.OR:
        vals_or: list[bool] = []
        for arg in args:
            v = _eval_node(arg, ctx)
            if type(v) is not bool:
                raise TypeError_("OR requires bool operands")
            vals_or.append(v)
        return any(vals_or)
    if op is FormulaOperator.NOT:
        v = _eval_node(args[0], ctx)
        if type(v) is not bool:
            raise TypeError_("NOT requires bool")
        return not v

    # Indicators: validate argument forms deterministically.
    # Series args must be FEATURE nodes; window/percentile args must be
    # LITERAL int/float. VWAP price/volume as FEATURE. Prevents nesting
    # that complicates temporal semantics; composition via outer ops.
    # Document: indicators take feature + window literals.

    def _require_feature(node: FormulaNode) -> str:
        if node.node_kind is not FormulaNodeKind.FEATURE or node.feature_code is None:
            raise TypeError_(f"{op} series argument must be FEATURE node")
        if node.lag_bars != 0:
            raise TypeError_(f"{op} series feature lag must be 0 (use window)")
        return node.feature_code

    def _require_int_literal(node: FormulaNode) -> int:
        if node.node_kind is not FormulaNodeKind.LITERAL or node.literal_int is None:
            raise TypeError_(f"{op} window must be integer literal")
        if node.literal_int <= 0:
            from .errors import InvalidWindowError

            raise InvalidWindowError(f"window must be >0 got {node.literal_int}")
        return node.literal_int

    def _require_percentile_literal(node: FormulaNode) -> float:
        if node.node_kind is not FormulaNodeKind.LITERAL:
            raise TypeError_(f"{op} percentile must be literal")
        if node.literal_float is not None:
            vv: float = node.literal_float
            if not math.isfinite(vv):
                raise NumericSafetyError("percentile non-finite")
            return vv
        if node.literal_int is not None:
            return float(node.literal_int)
        if node.literal_decimal is not None:
            return float(node.literal_decimal)
        raise TypeError_(f"{op} percentile literal must be numeric")

    if op is FormulaOperator.SMA:
        f_code = _require_feature(args[0])
        window = _require_int_literal(args[1])
        return _ind.sma(ctx, f_code, window)
    if op is FormulaOperator.EMA:
        f_code = _require_feature(args[0])
        window = _require_int_literal(args[1])
        return _ind.ema(ctx, f_code, window)
    if op is FormulaOperator.ATR:
        high = _require_feature(args[0])
        low = _require_feature(args[1])
        close = _require_feature(args[2])
        window = _require_int_literal(args[3])
        return _ind.atr(ctx, high, low, close, window)
    if op is FormulaOperator.ROC:
        f_code = _require_feature(args[0])
        window = _require_int_literal(args[1])
        return _ind.roc(ctx, f_code, window)
    if op is FormulaOperator.RSI:
        f_code = _require_feature(args[0])
        window = _require_int_literal(args[1])
        return _ind.rsi(ctx, f_code, window)
    if op is FormulaOperator.VWAP:
        price = _require_feature(args[0])
        volume = _require_feature(args[1])
        window = _require_int_literal(args[2])
        return _ind.vwap(ctx, price, volume, window)
    if op is FormulaOperator.ZSCORE:
        f_code = _require_feature(args[0])
        window = _require_int_literal(args[1])
        return _ind.zscore(ctx, f_code, window)
    if op is FormulaOperator.SLOPE:
        f_code = _require_feature(args[0])
        window = _require_int_literal(args[1])
        return _ind.slope(ctx, f_code, window)
    if op is FormulaOperator.PERCENTILE:
        f_code = _require_feature(args[0])
        window = _require_int_literal(args[1])
        perc = _require_percentile_literal(args[2])
        return _ind.percentile(ctx, f_code, window, perc)
    if op is FormulaOperator.ROLLING_STD:
        f_code = _require_feature(args[0])
        window = _require_int_literal(args[1])
        return _ind.rolling_std(ctx, f_code, window)
    if op is FormulaOperator.ROLLING_CORR:
        a_code = _require_feature(args[0])
        b_code = _require_feature(args[1])
        window = _require_int_literal(args[2])
        return _ind.rolling_corr(ctx, a_code, b_code, window)

    raise FormulaEvaluationError(f"unknown operator {op}")


def evaluate(formula: FormulaDefinition, ctx: FormulaEvaluationContext) -> FormulaResult:
    """Evaluate formula at ctx.evaluation_index deterministically.

    - Respects max_lag/warmup is responsibility of caller but we enforce via ctx.
    - Returns typed FormulaResult matching formula.output_kind.
    - Raises FormulaEvaluationError subclasses on failure; never returns NaN/Inf.
    """
    # Temporal guard: lookback/warmup vs available data is enforced by get_window etc.
    # Also guard that evaluation_index doesn't exceed available series lengths already
    # (ctx validates finite). Additional check: if ctx.evaluation_index > max len-1 ?
    raw: Scalar = _eval_node(formula.ast, ctx)
    # Coerce to declared output kind
    kind = formula.output_kind
    if kind is FormulaOutputKind.BOOLEAN:
        if type(raw) is not bool:
            raise OutputKindMismatchError(f"expected BOOLEAN got {type(raw).__name__} {raw!r}")
        return FormulaResult(kind="BOOLEAN", boolean_value=raw)
    if kind is FormulaOutputKind.FINITE_FLOAT:
        if isinstance(raw, bool):
            raise OutputKindMismatchError("bool not finite float")
        float_val: float
        if isinstance(raw, int) and not isinstance(raw, bool):
            float_val = float(raw)
        elif isinstance(raw, Decimal):
            float_val = float(raw)
        elif isinstance(raw, float):
            float_val = raw
        else:
            raise OutputKindMismatchError(f"expected FINITE_FLOAT got {type(raw).__name__}")
        if not math.isfinite(float_val):
            raise NumericSafetyError("FINITE_FLOAT non-finite")
        return FormulaResult(kind="FINITE_FLOAT", float_value=float_val)
    if kind is FormulaOutputKind.DECIMAL:
        if isinstance(raw, bool):
            raise OutputKindMismatchError("bool not decimal")
        if isinstance(raw, float):
            if not math.isfinite(raw):
                raise NumericSafetyError("non-finite float to DECIMAL")
            dec = Decimal(str(raw))
            if not dec.is_finite():
                raise NumericSafetyError("non-finite decimal")
            return FormulaResult(kind="DECIMAL", decimal_value=dec)
        if isinstance(raw, int) and not isinstance(raw, bool):
            return FormulaResult(kind="DECIMAL", decimal_value=Decimal(raw))
        if isinstance(raw, Decimal):
            if not raw.is_finite():
                raise NumericSafetyError("non-finite decimal")
            return FormulaResult(kind="DECIMAL", decimal_value=raw)
        raise OutputKindMismatchError(f"expected DECIMAL got {type(raw).__name__}")
    raise OutputKindMismatchError(f"unknown output kind {kind}")


__all__ = ["evaluate"]
