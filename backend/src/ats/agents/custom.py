"""Operator-supplied custom strategies: register, sandbox, deploy.

This is the "I want to test my own strategy" path. An operator submits Python
source defining a signal function, the system validates it in a sandbox,
backtests it on real data, and only lets it be assigned to an agent once it has
proved out-of-sample edge.

Safety model
------------
* Custom code is **never** executed by the live worker until it has passed
  validation *and* cleared the deployment gate.
* The live gate chain re-applies cost, risk and portfolio checks to a custom
  strategy exactly as it does to a built-in one. A custom strategy is not a way
  around the economics.
* Source is retained verbatim for audit, with a content hash so a later edit is
  detectable.

Strategy contract
-----------------
A custom strategy is a callable with this shape::

    def my_strategy(bars, *, tick_size=0.01, **kwargs) -> StrategySignal

``bars`` is a list of :class:`~ats.agents.features.Bar`. Return a
``StrategySignal`` (or ``None`` to abstain). The simplest useful form::

    from ats.agents.strategies import StrategySignal
    from ats.agents.features import atr_geometry

    def my_strategy(bars, *, tick_size=0.01, **kwargs):
        if len(bars) < 50:
            return None
        closes = [b.close for b in bars]
        if closes[-1] > closes[-2] and closes[-2] > closes[-3]:
            geom = atr_geometry(bars, atr_multiplier=1.5, risk_reward=2.0, tick_size=tick_size)
            return StrategySignal(
                strategy_id="X01_MY_STRAT",
                direction="LONG",
                confidence=0.7,
                regime="CUSTOM",
                rationale="three-bar momentum",
                geometry=geom,
            )
        return None
"""

from __future__ import annotations

import ast
import hashlib
import logging
import textwrap
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ats.agents.strategies import StrategySignal, register_family, unregister_family

LOGGER = logging.getLogger(__name__)

#: Module namespace made available to custom strategy source.
CUSTOM_NAMESPACE: dict[str, Any] = {
    "StrategySignal": StrategySignal,
}

#: Constructors injected into the execution namespace of custom code.
BANNED_CALLS = frozenset(
    {
        "eval", "exec", "compile", "__import__", "open", "input",
        "globals", "locals", "vars", "breakpoint", "exit", "quit",
    }
)

#: Bare-name identifiers rejected outright; these are the usual escape hatches.
BANNED_NAMES = frozenset({"__builtins__", "__subclasses__", "__globals__", "__code__"})


class StrategyValidationError(ValueError):
    """Raised when custom strategy source is malformed or unsafe."""


@dataclass
class CustomStrategy:
    """One registered custom strategy."""

    name: str
    source: str
    description: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    origin: str = "operator"
    registered_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    source_hash: str = ""
    validation: dict[str, Any] = field(default_factory=dict)
    status: str = "REGISTERED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "params": self.params,
            "origin": self.origin,
            "registered_at": self.registered_at,
            "source_hash": self.source_hash,
            "status": self.status,
            "validation": self.validation,
            "source": self.source,
        }


def hash_source(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def _check_safety(source: str) -> None:
    """Static checks on custom source before it is ever compiled.

    This is a defence-in-depth measure, not a security boundary. A determined
    operator with code execution already owns the process. The goal is to catch
    accidents and obvious escapes, and to make the risk of running unreviewed
    code explicit rather than hidden.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise StrategyValidationError(f"Syntax error: {e}") from e

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BANNED_CALLS:
                raise StrategyValidationError(
                    f"Call to '{node.func.id}' is not permitted in custom strategies"
                )
        if isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            raise StrategyValidationError(
                f"Use of '{node.id}' is not permitted in custom strategies"
            )
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise StrategyValidationError(
                f"Access to dunder attribute '{node.attr}' is not permitted"
            )


def _extract_function(source: str, name: str) -> Any:
    """Compile the source and return the named top-level function."""
    namespace: dict[str, Any] = dict(CUSTOM_NAMESPACE)
    try:
        # Imports are permitted - strategies legitimately need math and the ATS
        # feature layer. The dangerous surface (eval/exec/open/__import__) is
        # blocked by the AST check above, so the runtime builtin set can be
        # narrow while still exposing `__import__` for the import statement.
        safe_builtins = {
            "abs": abs, "min": min, "max": max, "sum": sum, "len": len,
            "range": range, "enumerate": enumerate, "zip": zip, "list": list,
            "dict": dict, "tuple": tuple, "set": set, "sorted": sorted,
            "reversed": reversed, "any": any, "all": all, "round": round,
            "float": float, "int": int, "bool": bool, "str": str,
            "True": True, "False": False, "None": None,
            "__import__": __import__,
        }
        code = compile(source, f"<custom:{name}>", "exec")
        exec(code, {"__builtins__": safe_builtins}, namespace)  # noqa: S102
    except Exception as e:
        raise StrategyValidationError(f"Could not load strategy: {e}") from e

    fn = namespace.get(name)
    if fn is None or not callable(fn):
        raise StrategyValidationError(
            f"Source must define a top-level function named '{name}'"
        )
    return fn


@dataclass
class CustomRegistry:
    """Registry of operator-supplied strategies."""

    _strategies: dict[str, CustomStrategy] = field(default_factory=dict)
    _functions: dict[str, Any] = field(default_factory=dict, repr=False)

    def register(
        self,
        *,
        name: str,
        source: str,
        description: str = "",
        params: dict[str, Any] | None = None,
    ) -> CustomStrategy:
        """Validate and register custom strategy source."""
        clean = name.strip()
        if not clean:
            raise StrategyValidationError("Strategy name is required")

        src = textwrap.dedent(source).strip()
        _check_safety(src)
        _extract_function(src, clean)  # proves it loads and is callable

        strategy = CustomStrategy(
            name=clean,
            source=src,
            description=description,
            params=params or {},
            source_hash=hash_source(src),
            status="REGISTERED",
        )
        self._strategies[clean] = strategy
        register_family(clean, self._make_signal_fn(clean))
        LOGGER.info("Custom strategy '%s' registered (hash=%s)", clean, strategy.source_hash)
        return strategy

    def _make_signal_fn(self, name: str) -> Any:
        """Wrap a custom function so it satisfies the strategy contract.

        The user's source is compiled **once** and the resulting function is
        reused. Re-executing on every tick would be slow and, more importantly,
        would discard any module-level state the author set up at import time.
        """
        from ats.agents.strategies import _no_signal

        registry = self

        def _resolve() -> Any:
            return registry._functions.get(name)

        def runner(bars: list[Any], **kwargs: Any) -> Any:
            from ats.agents.features import atr_geometry
            from ats.agents.strategies import StrategySignal

            fn = _resolve()
            if fn is None:
                fn = _extract_function(registry._strategies[name].source, name)
                registry._functions[name] = fn
            params = dict(registry._strategies[name].params)
            params.update(kwargs)
            try:
                result = fn(bars, **params)
            except Exception as e:
                return _no_signal(name, "CUSTOM_ERROR", f"Custom strategy raised: {e}")
            if result is None:
                return _no_signal(name, "CUSTOM_ABSTAIN", "Custom strategy declined to signal")
            if isinstance(result, StrategySignal):
                return result
            if isinstance(result, str) and result in ("LONG", "SHORT"):
                geom = atr_geometry(
                    bars, atr_multiplier=1.5, risk_reward=2.0, tick_size=0.01
                )
                return StrategySignal(
                    strategy_id=name,
                    direction=result,
                    confidence=0.5,
                    regime="CUSTOM",
                    rationale=f"Custom strategy '{name}' signalled {result}",
                    geometry=geom,
                )
            return _no_signal(name, "CUSTOM_INVALID", "Custom strategy returned an invalid signal")

        return runner

    def get(self, name: str) -> CustomStrategy | None:
        return self._strategies.get(name)

    def names(self) -> list[str]:
        return sorted(self._strategies)

    def remove(self, name: str) -> bool:
        removed = self._strategies.pop(name, None) is not None
        if removed:
            unregister_family(name)
        return removed

    def list(self) -> list[dict[str, Any]]:
        return [s.as_dict() for s in self._strategies.values()]


_REGISTRY: CustomRegistry | None = None


def get_custom_registry() -> CustomRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = CustomRegistry()
    return _REGISTRY


__all__ = [
    "CustomRegistry",
    "CustomStrategy",
    "StrategyValidationError",
    "get_custom_registry",
    "hash_source",
]
