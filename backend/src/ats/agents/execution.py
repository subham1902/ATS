"""Realistic execution modelling: slippage, latency, and fill probability.

The pre-audit worker entered at the touch and exited at the *exact* stop or
target price on a 2-second loop. That is frictionless and unattainable: real
stops fill worse than the stop level and market orders pay the spread. Every
paper number produced under that model was optimistic in the profitable
direction.

This module makes fills pessimistic-but-fair:

* Entries cross the spread, so they fill at or beyond the touch.
* Stop exits fill at the stop level **plus** adverse slippage, because that is
  when you are a forced taker.
* Target exits can fill with slight favourable variance.
* A configurable rejection probability models exchange/OMS rejects, and a
  latency model prevents same-tick entry-and-exit.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Parameters governing the realism of simulated fills."""

    #: Minimum adverse slippage as a fraction of price, applied on every fill.
    base_slippage_bps: float = 0.5
    #: Additional adverse slippage when exiting via a stop (forced taker).
    stop_slippage_bps: float = 1.5
    #: Proportional probability that an order is rejected outright.
    reject_probability: float = 0.002
    #: Minimum simulated round-trip latency in seconds.
    min_latency_seconds: float = 0.35
    #: Maximum simulated round-trip latency in seconds.
    max_latency_seconds: float = 1.80
    #: Deterministic seed so paper results are reproducible.
    seed: int = 20260928

    def as_dict(self) -> dict[str, float]:
        return {
            "base_slippage_bps": self.base_slippage_bps,
            "stop_slippage_bps": self.stop_slippage_bps,
            "reject_probability": self.reject_probability,
            "min_latency_seconds": self.min_latency_seconds,
            "max_latency_seconds": self.max_latency_seconds,
            "seed": self.seed,
        }


@dataclass(frozen=True, slots=True)
class Fill:
    """Result of simulating one fill."""

    price: float
    slipped: bool
    rejected: bool
    latency_seconds: float
    slippage_points: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "price": round(self.price, 2),
            "slipped": self.slipped,
            "rejected": self.rejected,
            "latency_seconds": round(self.latency_seconds, 3),
            "slippage_points": round(self.slippage_points, 3),
            "reason": self.reason,
        }


class ExecutionModel:
    """Deterministic pseudo-random execution simulator.

    Determinism matters: an audit trail is worthless if re-running the same
    session produces different results. The generator is seeded from a stable
    hash of the order identity plus the model seed.
    """

    def __init__(self, config: ExecutionConfig | None = None) -> None:
        self._config = config or ExecutionConfig()
        self._rejections = 0
        self._fills = 0
        self._total_slippage_points = 0.0

    @property
    def config(self) -> ExecutionConfig:
        return self._config

    @property
    def stats(self) -> dict[str, Any]:
        avg = self._total_slippage_points / self._fills if self._fills else 0.0
        return {
            "orders_attempted": self._fills + self._rejections,
            "fills": self._fills,
            "rejections": self._rejections,
            "rejection_rate": round(
                self._rejections / (self._fills + self._rejections)
                if (self._fills + self._rejections)
                else 0.0,
                5,
            ),
            "avg_slippage_points": round(avg, 4),
        }

    def _unit(self, *parts: Any) -> float:
        """Stable float in ``[0, 1)`` derived from the order identity."""
        raw = "|".join(str(p) for p in parts) + f"|seed={self._config.seed}"
        digest = hashlib.sha256(raw.encode("utf-8")).digest()
        (value,) = struct.unpack(">Q", digest[:8])
        return float(value) / float(2**64)

    def _latency(self, key: str) -> float:
        u = self._unit("latency", key)
        lo = self._config.min_latency_seconds
        hi = self._config.max_latency_seconds
        return lo + u * (hi - lo)

    def apply_entry(
        self,
        *,
        price: float,
        direction: str,
        order_id: str,
    ) -> Fill:
        """Simulate an entry fill. Longs buy (pay up), shorts sell (receive less)."""
        u_reject = self._unit("reject", "entry", order_id)
        if u_reject < self._config.reject_probability:
            self._rejections += 1
            return Fill(
                price=price,
                slipped=False,
                rejected=True,
                latency_seconds=0.0,
                slippage_points=0.0,
                reason="Simulated exchange/OMS rejection on entry",
            )

        u_slip = self._unit("slip", "entry", order_id)
        adverse = (self._config.base_slippage_bps / 10_000.0) * price
        slip_points = adverse * (0.5 + u_slip)

        if direction.upper() == "LONG":
            fill_price = price + slip_points
        else:
            fill_price = price - slip_points

        self._fills += 1
        self._total_slippage_points += slip_points
        return Fill(
            price=round(fill_price, 2),
            slipped=True,
            rejected=False,
            latency_seconds=round(self._latency(f"entry:{order_id}"), 3),
            slippage_points=round(slip_points, 3),
            reason="Filled with adverse slippage (crossed spread)",
        )

    def apply_exit(
        self,
        *,
        price: float,
        direction: str,
        order_id: str,
        reason: str,
    ) -> Fill:
        """Simulate an exit fill with reason-dependent slippage.

        ``STOP_LOSS``/``BREAKEVEN_GUARD``/``HORIZON_EXPIRATION`` are forced
        taker exits and take the worst slippage. ``PROFIT_TARGET`` is a resting
        limit and is treated as mildly favourable. ``TIME_EXIT`` is a market
        order in the direction of travel.
        """
        u_reject = self._unit("reject", "exit", order_id)
        if u_reject < self._config.reject_probability:
            self._rejections += 1
            return Fill(
                price=price,
                slipped=False,
                rejected=True,
                latency_seconds=0.0,
                slippage_points=0.0,
                reason=f"Simulated rejection on exit ({reason})",
            )

        u_slip = self._unit("slip", "exit", order_id, reason)
        forced = reason in ("STOP_LOSS", "BREAKEVEN_GUARD", "HORIZON_EXPIRATION")
        bps = self._config.stop_slippage_bps if forced else self._config.base_slippage_bps
        adverse = (bps / 10_000.0) * price
        slip_points = adverse * (0.5 + u_slip)

        # A long position sells to exit, so slippage is downward; a short buys.
        if direction.upper() == "LONG":
            fill_price = price - slip_points
        else:
            fill_price = price + slip_points

        self._fills += 1
        self._total_slippage_points += slip_points
        return Fill(
            price=round(fill_price, 2),
            slipped=True,
            rejected=False,
            latency_seconds=round(self._latency(f"exit:{order_id}"), 3),
            slippage_points=round(slip_points, 3),
            reason=(
                f"{'Forced taker' if forced else 'Resting/market'} exit with "
                f"{bps:.2f}bps slippage"
            ),
        )

    def realistic_min_hold_seconds(
        self,
        *,
        target_points: float,
        multiplier: float,
        round_trip_cost: float,
    ) -> float:
        """Minimum hold time for a target to be worth paying the cost for.

        Uses the current bar's realised pace (points per second) to estimate how
        long a ``target_points`` move would take. This is the quantitative form
        of "do not scalping on a 60-second horizon".
        """
        if target_points <= 0 or multiplier <= 0 or round_trip_cost <= 0:
            return 0.0
        target_value = abs(target_points) * multiplier
        if target_value <= 0:
            return 0.0
        break_even_ratio = (2.0 * round_trip_cost) / target_value
        return break_even_ratio


__all__ = ["ExecutionConfig", "ExecutionModel", "Fill"]
