# ATS Live Incremental Candle Engine Specification

## 1. Engine Objectives
The `IncrementalCandleEngine` transforms continuous high-frequency price and volume observations into structured multi-timeframe candles without rebuilding historical bars on every tick.

## 2. Supported Intervals
- **Sub-Minute Derived Bars**: `1s DERIVED`, `5s DERIVED`, `15s DERIVED` (Clearly labelled `is_derived=True` and `source="ATS-DERIVED"`).
- **Intraday Exchange-Aligned Bars**: `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `1d`.

## 3. Mathematical Invariants
Every generated candle strictly satisfies:
1. $High \ge Open$
2. $High \ge Close$
3. $Low \le Open$
4. $Low \le Close$
5. $High \ge Low$
6. $Volume \ge 0$

## 4. Volume Delta Derivation
Rather than naively summing trade quantities, ATS uses cumulative volume traded today ($VTT$):
$$\Delta V_t = \max(0, VTT_t - VTT_{t-1})$$
- **On Startup / Reconnect**: $VTT_{t-1}$ is initialized to the current $VTT_t$ without synthesizing trade volume. This guarantees zero volume double-counting across disconnects and re-subscriptions.
- **On Session Reset**: If $VTT_t < VTT_{t-1}$, the engine logs a counter reset warning, sets volume delta to 0, and marks the candle's volume status as `PARTIAL` rather than fabricating values.

## 5. Open Interest (OI) State Observation
Open interest is treated as a state gauge, never an accumulated sum. The active candle tracks the latest authoritative provider OI:
$$OI_{\text{candle}} = OI_{\text{latest}}$$

## 6. Boundary Sealing Lifecycle
```
Observation t in Bucket B_n:
  - If B_n == B_{active}:
      active.high = max(active.high, ltp)
      active.low = min(active.low, ltp)
      active.close = ltp
      active.volume += delta_volume
      active.tick_count += 1
      emit CandleUpdate
  - If B_n > B_{active}:
      active.final = True
      push active to closed_history
      emit CandleClosed
      active = new_candle(open=ltp, high=ltp, low=ltp, close=ltp, volume=delta_volume)
      emit CandleUpdate
```
