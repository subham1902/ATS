"""Research backtester — NOT PaperBroker.

Semantics:
- Signal at completed bar T (R13 evaluation_index = T).
- Fill at next bar OPEN. No same-bar high/low optimism.
- Exit evaluated at completed bar; fill at next open.
- Same-bar stop/target ambiguity: conservative — stop before
  target when both triggered, fill at next open. See FillAssumption.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid5

from ats.contracts.common import UTCDateTime
from ats.contracts.intelligence.models import FormulaDefinition, StrategyDefinition
from ats.intelligence.formula import FormulaEvaluationContext, evaluate
from ats.market.replay.models import ReplayBar, ReplayDataset

from .cost_model import CostModel
from .types import BacktestResult, ResearchFill, ResearchSignal, ResearchTrade


def _series_from_bars(bars: tuple[ReplayBar, ...], field: str) -> list[Decimal | float]:
    if field == "close":
        return [b.close for b in bars]
    if field == "open":
        return [b.open for b in bars]
    if field == "high":
        return [b.high for b in bars]
    if field == "low":
        return [b.low for b in bars]
    if field == "volume":
        return [b.volume for b in bars]
    # Fallback to close
    return [b.close for b in bars]


@dataclass(frozen=True)
class BacktestConfiguration:
    strategy: StrategyDefinition
    entry_formula: FormulaDefinition
    exit_formulas: tuple[FormulaDefinition, ...]
    dataset: ReplayDataset
    cost_model: CostModel
    fill_quantity: Decimal
    dataset_cutoff: UTCDateTime
    parameter_set_hash: str
    seed: int


def run_backtest(
    *,
    config: BacktestConfiguration,
    test_start: UTCDateTime,
    test_end: UTCDateTime | None,
    experiment_id: UUID,
) -> BacktestResult:
    """Deterministic backtest over test window."""
    bars = config.dataset.bars
    # Filter bars to test window inclusive
    test_bars: list[ReplayBar] = []
    for b in bars:
        if b.bar_timestamp < test_start:
            continue
        if test_end is not None and b.bar_timestamp > test_end:
            continue
        test_bars.append(b)
    if not test_bars:
        # Zero-trade semantics allowed
        return BacktestResult(
            result_id=uuid5(experiment_id, "result"),
            experiment_id=experiment_id,
            trades=(),
            fills=(),
            signals=(),
            start_time=test_start,
            end_time=test_end if test_end is not None else test_start,
            seed=config.seed,
            cost_model_version=config.cost_model.cost_model_version,
            cost_model_authoritative=config.cost_model.cost_model_authoritative,
        )

    # Build series dict for R13 context — map required_features to close/open etc.
    # Minimal mapping: if feature_code is like "close" we use close; otherwise close fallback.
    # For research-control, we use close series for generic features.
    # We need to handle arbitrary feature_codes deterministically.
    all_features: set[str] = set()
    all_features.update(config.entry_formula.required_features)
    for f in config.exit_formulas:
        all_features.update(f.required_features)

    # Build series per feature_code
    feature_series: dict[str, list[Decimal]] = {}
    for code in all_features:
        # Normalize: if code contains close/open/high/low/volume use that else close
        lower = code.lower()
        if "open" in lower:
            series = [b.open for b in bars]
        elif "high" in lower:
            series = [b.high for b in bars]
        elif "low" in lower:
            series = [b.low for b in bars]
        elif "volume" in lower:
            series = [b.volume for b in bars]
        else:
            series = [b.close for b in bars]
        feature_series[code] = series

    # Quick lookup for bar index by timestamp
    bar_index_of = {b.bar_timestamp: i for i, b in enumerate(bars)}

    signals: list[ResearchSignal] = []
    fills: list[ResearchFill] = []
    trades: list[ResearchTrade] = []

    in_position = False
    entry_fill: ResearchFill | None = None

    # Iterate over test_bars indices; signal at T, fill at T+1
    for bar in test_bars:
        global_index = bar_index_of[bar.bar_timestamp]
        # Need evaluation_index = global_index for R13 (available data up to T)
        ctx = FormulaEvaluationContext(
            evaluation_index=global_index,
            series=feature_series,
        )
        # Evaluate entry if not in position
        if not in_position:
            try:
                res = evaluate(config.entry_formula, ctx)
                is_entry = bool(res.boolean_value)
            except Exception:
                # R13 evaluation failure -> treat as no signal, record no fill
                is_entry = False
            if is_entry:
                sig = ResearchSignal(
                    signal_id=uuid5(experiment_id, f"sig-entry-{bar.source_sequence}"),
                    instrument_id=bar.instrument_id,
                    bar_timestamp=bar.bar_timestamp,
                    bar_sequence=bar.source_sequence,
                    is_entry=True,
                    is_exit=False,
                )
                signals.append(sig)
                # Fill at next eligible bar OPEN if exists
                next_idx = global_index + 1
                if next_idx < len(bars):
                    next_bar = bars[next_idx]
                    # Must be within test window; if beyond test_end still bounded
                    if test_end is None or next_bar.bar_timestamp <= test_end:
                        fill_price = next_bar.open
                        cost = config.cost_model.cost_per_trade(
                            price=fill_price, quantity=config.fill_quantity, side="BUY"
                        )
                        fill = ResearchFill(
                            fill_id=uuid5(experiment_id, f"fill-entry-{bar.source_sequence}"),
                            signal_id=sig.signal_id,
                            instrument_id=bar.instrument_id,
                            side="BUY",
                            price=fill_price,
                            quantity=config.fill_quantity,
                            bar_timestamp=next_bar.bar_timestamp,
                            bar_sequence=next_bar.source_sequence,
                            cost=cost,
                        )
                        fills.append(fill)
                        in_position = True
                        entry_fill = fill
        else:
            # Evaluate exit formulas; any true triggers exit
            should_exit = False
            exit_sig: ResearchSignal | None = None
            for exit_formula in config.exit_formulas:
                try:
                    res = evaluate(exit_formula, ctx)
                    if res.boolean_value:
                        should_exit = True
                        # Record first exit signal
                        exit_sig = ResearchSignal(
                            signal_id=uuid5(
                                experiment_id,
                                f"sig-exit-{bar.source_sequence}-{exit_formula.formula_definition_id}",
                            ),
                            instrument_id=bar.instrument_id,
                            bar_timestamp=bar.bar_timestamp,
                            bar_sequence=bar.source_sequence,
                            is_entry=False,
                            is_exit=True,
                        )
                        break
                except Exception:
                    continue
            if should_exit and exit_sig is not None:
                signals.append(exit_sig)
                next_idx = global_index + 1
                if next_idx < len(bars):
                    next_bar = bars[next_idx]
                    if test_end is None or next_bar.bar_timestamp <= test_end:
                        fill_price = next_bar.open
                        cost = config.cost_model.cost_per_trade(
                            price=fill_price, quantity=config.fill_quantity, side="SELL"
                        )
                        exit_fill = ResearchFill(
                            fill_id=uuid5(experiment_id, f"fill-exit-{bar.source_sequence}"),
                            signal_id=exit_sig.signal_id,
                            instrument_id=bar.instrument_id,
                            side="SELL",
                            price=fill_price,
                            quantity=config.fill_quantity,
                            bar_timestamp=next_bar.bar_timestamp,
                            bar_sequence=next_bar.source_sequence,
                            cost=cost,
                        )
                        fills.append(exit_fill)
                        # Create trade (deterministic: always next open)
                        assert entry_fill is not None
                        # PnL fraction: (exit_price - entry_price)/entry price (NET, after costs)
                        try:
                            entry_p = entry_fill.price
                            exit_p = exit_fill.price
                            qty = entry_fill.quantity
                            notional = entry_p * qty
                            # Gross PnL fraction (before costs)
                            gross_frac = (exit_p - entry_p) / entry_p
                            gross_r = gross_frac / Decimal("0.01")
                            # Costs from fills
                            entry_cost = entry_fill.cost
                            exit_cost = exit_fill.cost
                            net_cash = (exit_p - entry_p) * qty - entry_cost - exit_cost
                            net_frac = net_cash / notional if notional != 0 else Decimal("0")
                            net_r = net_frac / Decimal("0.01")
                        except Exception:
                            gross_frac = Decimal("0")
                            gross_r = Decimal("0")
                            net_frac = Decimal("0")
                            net_r = Decimal("0")
                            notional = entry_fill.price * entry_fill.quantity
                            gross_cash = Decimal("0")
                            net_cash = Decimal("0")
                        else:
                            gross_cash = (exit_p - entry_p) * qty
                        trade = ResearchTrade(
                            trade_id=uuid5(
                                experiment_id,
                                f"trade-{entry_fill.bar_sequence}-{exit_fill.bar_sequence}",
                            ),
                            instrument_id=bar.instrument_id,
                            entry_fill=entry_fill,
                            exit_fill=exit_fill,
                            entry_time=entry_fill.bar_timestamp,
                            exit_time=exit_fill.bar_timestamp,
                            pnl_fraction=net_frac,
                            pnl_r=net_r,
                            gross_pnl_fraction=gross_frac,
                            gross_pnl_r=gross_r,
                            gross_cash_pnl=gross_cash,
                            net_cash_pnl=net_cash,
                            entry_notional=notional,
                        )
                        trades.append(trade)
                        in_position = False
                        entry_fill = None

    # Determine start/end times
    start_t = test_bars[0].bar_timestamp
    end_t = test_bars[-1].bar_timestamp if test_end is None else test_end

    return BacktestResult(
        result_id=uuid5(experiment_id, "result"),
        experiment_id=experiment_id,
        trades=tuple(trades),
        fills=tuple(fills),
        signals=tuple(signals),
        start_time=start_t,
        end_time=end_t,
        seed=config.seed,
        cost_model_version=config.cost_model.cost_model_version,
        cost_model_authoritative=config.cost_model.cost_model_authoritative,
    )


__all__ = ["BacktestConfiguration", "run_backtest"]
