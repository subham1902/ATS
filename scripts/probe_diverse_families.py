"""Validate the diverse signal families on real historical data.

Standalone probe used to select the default roster. Uses the same IS/OOS split
and cost model as ``scripts.validate_strategies`` but runs only the families in
``ats.agents.families`` so the default four are chosen by evidence.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from ats.agents.families import DIVERSE_FAMILIES  # noqa: E402

from scripts.validate_strategies import (  # noqa: E402
    _mandate_params,
    load_bars,
    resolve_data_path,
    simulate,
)

#: Bar sizes suited to each family's natural lookback.
BAR_SECONDS = {
    "hurst_regime": 300.0,
    "moment_skew": 300.0,
    "volume_divergence": 300.0,
    "squeeze": 300.0,
    "close_location": 300.0,
    "session_seasonality": 300.0,
}


def main() -> None:
    data = resolve_data_path()
    print(f"Data: {data}")
    results = {}
    for name in DIVERSE_FAMILIES:
        bar = BAR_SECONDS[name]
        bars = load_bars(data, limit=250_000, bar_seconds=bar)
        split = int(len(bars) * 0.7)
        params = _mandate_params("TACTICAL_INTRADAY")
        common = {
            "agent": name,
            "family": name,
            "signal_source": name,
            **params,
        }
        oos = simulate(bars=bars[split:], seed=11, **common)
        results[name] = oos
        print(
            f"{name:22s} OOS trades={oos.trades:5d} win%={oos.win_rate:5.1f} "
            f"net={oos.net_points:9.1f} expct={oos.expectancy:7.3f} "
            f"pf={oos.profit_factor:5.2f} verdict={oos.verdict}"
        )

    print()
    print("Deployable:", [n for n, r in results.items() if r.deployable] or "NONE")
    # Persist bars count for sanity.
    print("bars loaded @300s:", len(load_bars(data, limit=250_000, bar_seconds=300.0)))


if __name__ == "__main__":
    main()
