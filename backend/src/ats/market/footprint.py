"""Broker quote footprint proxy: counts, never fabricated executed volume/depth."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from decimal import ROUND_FLOOR, Decimal
from typing import Any

from ats.market.observations import MarketObservation


def footprint_proxy(
    observations: Iterable[MarketObservation], tick_size: Decimal
) -> dict[str, Any]:
    if not tick_size.is_finite() or tick_size <= 0:
        raise ValueError("OBSERVED_TICK_SIZE_REQUIRED")
    counts: Counter[Decimal] = Counter()
    up: Counter[Decimal] = Counter()
    down: Counter[Decimal] = Counter()
    previous: Decimal | None = None
    spreads: list[Decimal] = []
    for tick in observations:
        price = tick.chart_price
        if price is None:
            continue
        level = (price / tick_size).to_integral_value(rounding=ROUND_FLOOR) * tick_size
        counts[level] += 1
        if previous is not None:
            if price > previous:
                up[level] += 1
            elif price < previous:
                down[level] += 1
        previous = price
        if tick.ask is not None and tick.bid is not None:
            spreads.append(tick.ask - tick.bid)
    return {
        "provenance": "BROKER_TICK_PROXY",
        "direction": "INFERRED_AGGRESSOR",
        "inference_method": "QUOTE_PRICE_CHANGE_V1",
        "volume_basis": "OBSERVATION_COUNT",
        "levels": [
            {"price": str(p), "tick_count": n, "up_ticks": up[p], "down_ticks": down[p]}
            for p, n in sorted(counts.items())
        ],
        "poc_tick_count": str(max(counts, key=lambda p: (counts[p], -p))) if counts else None,
        "spread_min": str(min(spreads)) if spreads else None,
        "spread_max": str(max(spreads)) if spreads else None,
        "executed_buy_volume": None,
        "executed_sell_volume": None,
        "order_book_imbalance": None,
        "global_order_flow": None,
    }
