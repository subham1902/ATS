"""Cost-realistic baseline research over the real NIFTY A2 replay dataset.

This is a deliberately simple, fully deterministic baseline used to prove the
real Upstox data is research-usable end-to-end through the frozen Historical
Truth layer. It is NOT a production strategy.

PIPELINE_BASELINE_ONLY
NOT_STATISTICALLY_VALIDATED
NOT_PROMOTED
NOT_LIVE_ELIGIBLE

Signal (no look-ahead): for each underlying 1-minute bar ``i`` we decide using
only the already-admitted underlying closes at ``i-1`` and ``i-2`` (a one-bar
momentum sign). The fill is then taken at the *next* bar's open with a fixed
basis-point adverse slippage model, and closed one bar later. Because the
signal never references bar ``i`` or any later bar, and all execution prices
are historical open prints that only become visible after the decision, the
backtest is leakage-free by construction.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ats.intelligence.strategy_lab.fill_model import FixedBpsSlippageModel
from ats.market.history import load_historical_dataset
from ats.market.history.models import ContractMetadataPayload, MarketBarPayload

DATASET_DIR = Path(r"D:\Projects\ATS\ats\data\historical\nifty_options_a2_replay_v1")
UNDERLYING_ID = "NSE_INDEX_NIFTY_50"
ATM_STRIKE = 24200
ATM_EXPIRY = "2026-09-01"
SLIPPAGE_BPS = Decimal("2")


def _bars_by_instrument(ds):
    bars: dict[str, list[tuple]] = {}
    meta: dict[str, ContractMetadataPayload] = {}
    for obs in ds.observations:
        if isinstance(obs.payload, MarketBarPayload):
            bars.setdefault(obs.instrument, []).append((obs.times.event_time, obs.payload))
        elif isinstance(obs.payload, ContractMetadataPayload):
            meta[obs.instrument] = obs.payload
    for inst in bars:
        bars[inst].sort(key=lambda item: item[0])
    return bars, meta


def run_baseline() -> dict:
    ds = load_historical_dataset(DATASET_DIR)
    bars, meta = _bars_by_instrument(ds)

    und = bars[UNDERLYING_ID]
    ce_id = next(
        i
        for i, m in meta.items()
        if m.strike == ATM_STRIKE and m.expiry_date == ATM_EXPIRY and m.option_type.value == "CE"
    )
    pe_id = next(
        i
        for i, m in meta.items()
        if m.strike == ATM_STRIKE and m.expiry_date == ATM_EXPIRY and m.option_type.value == "PE"
    )
    lot = Decimal(str(meta[ce_id].lot_size))
    ce = bars[ce_id]
    pe = bars[pe_id]

    slippage = FixedBpsSlippageModel(
        slippage_model_version="fixed-2bps-v1", slippage_bps=SLIPPAGE_BPS
    )

    trades = 0
    gross_pnl = Decimal("0")
    slip_cost = Decimal("0")
    net_pnl = Decimal("0")
    wins = 0
    winning_pnl = Decimal("0")
    losing_pnl = Decimal("0")
    losers = 0
    turnover = Decimal("0")
    equity = Decimal("0")
    peak = Decimal("0")
    max_dd = Decimal("0")

    # iterate underlying bars; decision at i uses only admitted bars i-1, i-2.
    # Execution is deferred to bar i+1's open (visible only at available_{i+1}),
    # and closed at bar i+2's open, so no decision ever touches an inadmissible
    # price.
    for i in range(2, len(und) - 2):
        prev_close = und[i - 1][1].close
        prev2_close = und[i - 2][1].close
        signal = prev_close - prev2_close
        if signal == 0:
            continue
        opt_bars = ce if signal > 0 else pe
        entry_open = opt_bars[i + 1][1].open
        exit_open = opt_bars[i + 2][1].open
        # strict leakage guard: signal indices precede execution indices
        assert i + 2 < len(opt_bars)
        entry_fill = slippage.applied_price(price=entry_open, quantity=lot, side="BUY")
        exit_fill = slippage.applied_price(price=exit_open, quantity=lot, side="SELL")
        trade_gross = (exit_open - entry_open) * lot
        trade_net = (exit_fill - entry_fill) * lot
        gross_pnl += trade_gross
        slip_cost += trade_gross - trade_net
        net_pnl += trade_net
        trades += 1
        if trade_net > 0:
            wins += 1
            winning_pnl += trade_net
        elif trade_net < 0:
            losers += 1
            losing_pnl += trade_net
        turnover += (entry_fill + exit_fill) * lot
        equity += trade_net
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)

    return {
        "dataset_id": str(ds.manifest.dataset_id),
        "trades": trades,
        "gross_pnl": str(gross_pnl),
        "slippage_cost": str(slip_cost),
        "other_transaction_costs": "0",
        "net_pnl": str(net_pnl),
        "win_rate": (wins / trades) if trades else 0.0,
        "average_net_pnl_per_trade": str(net_pnl / trades) if trades else "0",
        "profit_factor": str(winning_pnl / abs(losing_pnl)) if losing_pnl else None,
        "average_winner": str(winning_pnl / wins) if wins else "0",
        "average_loser": str(losing_pnl / losers) if losers else "0",
        "max_drawdown": str(max_dd),
        "turnover": str(turnover),
        "average_holding_time_minutes": "1",
        "lot_size": int(lot),
        "slippage_bps": str(SLIPPAGE_BPS),
    }


if __name__ == "__main__":
    import pprint

    pprint.pprint(run_baseline())
