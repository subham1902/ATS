"""Causal quote replay using the same price-only strategy function as forward research.

Not an execution authority. Sparse tick bars describe observed quotes, never a
complete exchange tape. No volume is synthesized for price-only calculations.
"""

from __future__ import annotations

import hashlib
from collections import deque
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from ats.datasets.ingestion import XauUsdDatasetStore
from ats.strategies.definitions import evaluate_strategy
from ats.strategies.features import Bar
from ats.strategies.operating_system import StrategyRecord, document_hash
from ats.strategies.research_jobs import ResearchJob
from ats.trading_runtime.xauusd_costs import XAUUSDExecutionModel

METHOD = "CAUSAL-QUOTE-V1"
SUPPORTED = frozenset({"donchian", "tsmom", "zscore", "regime_gate", "atr_expansion"})
PARAMETERS = frozenset(
    {"tick_size", "quantity", "commission", "slippage", "latency_ms", "bar_seconds"}
)


def execution_model(job: ResearchJob) -> XAUUSDExecutionModel:
    if job.method_version != METHOD or job.cost_model_version != "QUOTE-COST-V1":
        raise ValueError("UNSUPPORTED_RESEARCH_METHOD_OR_COSTS")
    if set(job.parameters) != PARAMETERS:
        raise ValueError("EXPLICIT_RESEARCH_ASSUMPTIONS_REQUIRED")
    for key, value in job.parameters.items():
        if isinstance(value, bool) or not isinstance(value, int | float | str):
            raise ValueError("INVALID_RESEARCH_PARAMETER")
        number = Decimal(str(value))
        if not number.is_finite() or number < 0:
            raise ValueError("INVALID_RESEARCH_PARAMETER")
        if key in {"tick_size", "quantity"} and number <= 0:
            raise ValueError("INVALID_RESEARCH_PARAMETER")
    if job.parameters["bar_seconds"] not in {60, 300, 900, 3600}:
        raise ValueError("UNSUPPORTED_RESEARCH_BAR_INTERVAL")
    latency = Decimal(str(job.parameters["latency_ms"]))
    if latency != latency.to_integral_value() or latency > 60000:
        raise ValueError("INVALID_LATENCY")
    return XAUUSDExecutionModel(
        version=job.cost_model_version,
        spread_source="OBSERVED_BID_ASK",
        commission_per_unit=Decimal(str(job.parameters["commission"])),
        slippage_price=Decimal(str(job.parameters["slippage"])),
        latency_ms=int(latency),
        price_source="BID_ASK",
        position_sizing="EXPLICIT_FIXED_PRICE_UNITS_NOT_BROKER_LOTS",
        session_policy="UTC_DAY_FLAT_NO_NEW_ENTRY_FINAL_60_SECONDS",
        rollover_per_unit=None,
        overnight_holding=False,
        weekend_gap_policy="NO_WEEKEND_HOLD",
        liquidity_assumption="UNLIMITED_AT_NEXT_OBSERVED_QUOTE_NO_DEPTH_AVAILABLE",
    )


def verify_job(job: ResearchJob, record: StrategyRecord, datasets: XauUsdDatasetStore) -> None:
    execution_model(job)
    if record.definition_id not in SUPPORTED or record.status == "RETIRED":
        raise ValueError("UNSUPPORTED_RESEARCH_RECIPE")
    manifest = datasets.get(job.dataset_id)
    if manifest["normalized_hash"] != job.dataset_hash or manifest["status"] != "RESEARCH_ONLY":
        raise ValueError("PROVENANCE_MISMATCH")
    if manifest["timeframe"] is not None or manifest["price_basis"] != "BID_ASK":
        raise ValueError("OBSERVED_BID_ASK_TICKS_REQUIRED")
    if manifest["normalized_row_count"] > job.budget_rows:
        raise ValueError("BUDGET_EXCEEDED")


def run_quote_research(
    job: ResearchJob, record: StrategyRecord, datasets: XauUsdDatasetStore
) -> dict[str, Any]:
    verify_job(job, record, datasets)
    costs = execution_model(job)
    interval = int(job.parameters["bar_seconds"])
    quantity = Decimal(str(job.parameters["quantity"]))
    tick_size = float(job.parameters["tick_size"])
    bars: deque[Bar] = deque(maxlen=200)
    current: Bar | None = None
    pending: tuple[Any, Any, float] | None = None
    position: dict[str, Any] | None = None
    trades: list[dict[str, Any]] = []
    latest_signal: dict[str, Any] | None = None
    previous: Any = None
    count = 0
    for observation in datasets.replay(job.dataset_id):
        count += 1
        if count > job.budget_rows:
            raise ValueError("BUDGET_EXCEEDED")
        if observation.bid is None or observation.ask is None:
            raise ValueError("OBSERVED_SPREAD_UNAVAILABLE")
        if previous is not None and observation.timestamp <= previous:
            raise ValueError("QUOTE_ORDER_NOT_STRICT")
        if previous is not None and observation.timestamp.date() != previous.date() and position:
            raise ValueError("UNPRICED_OVERNIGHT_GAP")
        previous = observation.timestamp
        # Exit uses executable liquidation-side quotes, never a fabricated OHLC path.
        if position is not None:
            liquidate = observation.bid if position["direction"] == "LONG" else observation.ask
            sign = Decimal(1) if position["direction"] == "LONG" else Decimal(-1)
            hit_stop = sign * (liquidate - position["stop"]) <= 0
            hit_target = sign * (liquidate - position["target"]) >= 0
            day_flat = observation.timestamp.hour == 23 and observation.timestamp.minute == 59
            if hit_stop or hit_target or day_flat:
                side: Literal["BUY", "SELL"] = "SELL" if sign == 1 else "BUY"
                exit_price = costs.crossing_price(
                    side=side, bid=observation.bid, ask=observation.ask
                )
                pnl = sign * (exit_price - position["entry"]) * quantity
                pnl -= costs.commission_per_unit * quantity * 2
                trades.append(
                    {
                        "entry_time": position["time"].isoformat(),
                        "exit_time": observation.timestamp.isoformat(),
                        "direction": position["direction"],
                        "entry": str(position["entry"]),
                        "exit": str(exit_price),
                        "stop": str(position["stop"]),
                        "target": str(position["target"]),
                        "net_pnl": str(pnl),
                        "net_R": str(pnl / (position["risk"] * quantity)),
                        "exit_reason": "STOP"
                        if hit_stop
                        else "TARGET"
                        if hit_target
                        else "UTC_DAY_FLAT",
                    }
                )
                if len(trades) > 10000:
                    raise ValueError("BUDGET_EXCEEDED")
                position = None
        if pending is not None and position is None:
            signal, signal_time, reference = pending
            if (observation.timestamp - signal_time).total_seconds() * 1000 >= costs.latency_ms:
                pending = None
                if (
                    observation.timestamp.date() == signal_time.date()
                    and observation.timestamp.hour < 23
                ):
                    geometry = signal.geometry
                    assert geometry is not None
                    side = "BUY" if signal.direction == "LONG" else "SELL"
                    entry = costs.crossing_price(
                        side=side, bid=observation.bid, ask=observation.ask
                    )
                    sign = Decimal(1) if side == "BUY" else Decimal(-1)
                    stop = Decimal(str(reference)) - sign * Decimal(str(geometry.stop_points))
                    target = Decimal(str(reference)) + sign * Decimal(str(geometry.target_points))
                    valid = stop < entry < target if side == "BUY" else target < entry < stop
                    if valid:
                        position = {
                            "direction": signal.direction,
                            "entry": entry,
                            "stop": stop,
                            "target": target,
                            "risk": abs(entry - stop),
                            "time": observation.timestamp,
                        }
        bucket = int(observation.timestamp.timestamp() // interval) * interval
        price = float(observation.bid)
        if current is not None and bucket != current.timestamp:
            bars.append(current)
            if position is None and pending is None:
                signal = evaluate_strategy(record.definition_id, list(bars), tick_size=tick_size)
                latest_signal = {
                    **signal.as_dict(),
                    "strategy_id": record.strategy_id,
                    "strategy_version": record.version,
                    "timestamp": observation.timestamp.isoformat(),
                    "empirical_probability": None,
                    "probability_source": "PROBABILITY_UNKNOWN",
                    "trade_horizon": record.trade_horizon,
                    "status": "RESEARCH_ONLY_NOT_EXECUTION_ELIGIBLE",
                }
                if signal.has_signal and signal.geometry is not None:
                    pending = (signal, observation.timestamp, current.close)
            current = None
        if current is None:
            current = Bar(bucket, price, price, price, price, volume=float("nan"))
        else:
            current.high, current.low = max(current.high, price), min(current.low, price)
            current.close = price
    pnls = [Decimal(t["net_pnl"]) for t in trades]
    gains = sum((p for p in pnls if p > 0), Decimal(0))
    losses = -sum((p for p in pnls if p < 0), Decimal(0))
    equity = peak = drawdown = Decimal(0)
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {
        "method_version": METHOD,
        "strategy_id": record.strategy_id,
        "strategy_version": record.version,
        "strategy_hash": document_hash(record),
        "engine_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "dataset_id": job.dataset_id,
        "dataset_hash": job.dataset_hash,
        "parameters": job.parameters,
        "costs": costs.model_dump(mode="json"),
        "row_count": count,
        "trade_count": len(trades),
        "trades": trades,
        "net_pnl": str(sum(pnls, Decimal(0))),
        "max_drawdown_cash": str(drawdown),
        "win_rate": sum(p > 0 for p in pnls) / len(pnls) if pnls else None,
        "profit_factor": str(gains / losses) if losses else None,
        "sharpe": None,
        "holdout_status": "NOT_RUN",
        "walk_forward_status": "NOT_RUN",
        "open_position": {k: str(v) for k, v in position.items()} if position else None,
        "latest_signal": latest_signal,
        "authority": "RESEARCH_ONLY",
        "limitations": [
            "SPARSE_BROKER_QUOTE_BARS",
            "NO_DEPTH_OR_FILL_CAPACITY_PROOF",
            "NO_CALIBRATED_PROBABILITY",
            "NO_PROMOTION_AUTHORITY",
        ],
    }
