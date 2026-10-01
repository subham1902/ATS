"""Canonical strategy-identity resolution.

A strategy is identified by its full ID (``S02_TSMOM``). The leading ``S02`` is
*not* an identity: ``S02_TSMOM`` and ``S02_MICRO_TICK`` share it, and the
registry's own bare ``S02`` is a different, STRAT-04 registration-order ID.
Reducing an ID to its prefix silently attributed one strategy's score and live
performance to another, so every lookup goes through here and is exact.

Legacy short aliases are allowed only when listed explicitly in
``STRATEGY_ID_ALIASES``, and each alias must map to exactly one full ID.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

#: Explicit legacy aliases -> canonical full ID. Intentionally empty: no short
#: alias is currently authorised. Adding one is a deliberate, reviewed act.
STRATEGY_ID_ALIASES: Mapping[str, str] = {}


class AmbiguousStrategyId(ValueError):
    """A short/partial ID matches more than one known strategy."""


def resolve_strategy_id(
    requested: str,
    known: Iterable[str],
    *,
    aliases: Mapping[str, str] = STRATEGY_ID_ALIASES,
) -> str | None:
    """Return the canonical ID for ``requested``, or ``None`` if unknown.

    Exact full-ID match wins. An explicit alias resolves only if its target is
    known. A bare prefix shared by several known IDs raises
    :class:`AmbiguousStrategyId` (fail closed); a prefix is never resolved by
    picking one of its matches.
    """

    ids = set(known)
    if requested in ids:
        return requested
    target = aliases.get(requested)
    if target is not None:
        return target if target in ids else None
    siblings = sorted(k for k in ids if k.startswith(f"{requested}_"))
    if len(siblings) > 1:
        raise AmbiguousStrategyId(
            f"Strategy id {requested!r} is ambiguous; use a full id: {siblings}"
        )
    return None


__all__ = ["STRATEGY_ID_ALIASES", "AmbiguousStrategyId", "resolve_strategy_id"]
