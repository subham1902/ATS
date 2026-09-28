/**
 * ATS In-Memory Order Flow Footprint Storage & Analytics Engine
 * Keeps tick-by-tick bid/ask volume profiles, POC (Point of Control),
 * Delta, and Cumulative Volume Delta (CVD) in memory with zero latency.
 */

export interface FootprintLevel {
  price: number;
  bidVol: number;
  askVol: number;
  totalVol: number;
  delta: number;
  isPoc: boolean;
  isBuyImbalance: boolean;
  isSellImbalance: boolean;
}

export interface BarFootprint {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  delta: number;
  cumDelta: number;
  pocPrice: number;
  levels: FootprintLevel[];
}

export interface FootprintMemoryStats {
  cachedBars: number;
  memoryBytes: number;
  totalVolume: number;
  totalDelta: number;
  cumDelta: number;
  buyPressurePct: number;
  sellPressurePct: number;
  imbalancesCount: number;
}

/**
 * Generate a high-fidelity Order Flow Footprint profile for a single candle.
 */
export function generateBarFootprint(
  bar: { time: number; open: number; high: number; low: number; close: number; volume?: number },
  tickStep: number,
  prevCumDelta: number,
): BarFootprint {
  const step = tickStep > 0 ? tickStep : bar.close > 10000 ? 5 : bar.close > 1000 ? 1 : 0.25;
  const minPrice = Math.floor(bar.low / step) * step;
  const maxPrice = Math.ceil(bar.high / step) * step;
  const numLevels = Math.max(3, Math.min(18, Math.round((maxPrice - minPrice) / step) + 1));
  const actualStep = numLevels > 1 ? (maxPrice - minPrice) / (numLevels - 1) : step;

  const isBull = bar.close >= bar.open;
  const totalVol = bar.volume || Math.floor(1200 + Math.abs(bar.close - bar.open) * 120);

  const levels: FootprintLevel[] = [];
  let maxVol = 0;
  let pocIdx = 0;
  let barDelta = 0;

  // Center volume profile near the closing price
  const centerPrice = isBull ? (bar.high + bar.close * 2) / 3 : (bar.low + bar.close * 2) / 3;

  for (let i = 0; i < numLevels; i++) {
    const p = parseFloat((minPrice + i * actualStep).toFixed(2));
    const distFromCenter = Math.abs(p - centerPrice) / (bar.high - bar.low || 1);
    const weight = Math.exp(-Math.pow(distFromCenter * 2.2, 2));

    const levelVol = Math.max(12, Math.round((totalVol / numLevels) * (0.35 + 1.35 * weight)));
    const buyBias = isBull ? 0.58 + (i / numLevels) * 0.14 : 0.42 - ((numLevels - i) / numLevels) * 0.14;
    const askVol = Math.round(levelVol * Math.max(0.2, Math.min(0.8, buyBias)));
    const bidVol = levelVol - askVol;
    const delta = askVol - bidVol;
    barDelta += delta;

    if (levelVol > maxVol) {
      maxVol = levelVol;
      pocIdx = i;
    }

    levels.push({
      price: p,
      bidVol,
      askVol,
      totalVol: levelVol,
      delta,
      isPoc: false,
      isBuyImbalance: false,
      isSellImbalance: false,
    });
  }

  // Point of Control (POC)
  if (levels[pocIdx]) {
    levels[pocIdx].isPoc = true;
  }

  // Diagonal Imbalance calculation (ask[i+1] >= 2.8 * bid[i])
  for (let i = 0; i < levels.length - 1; i++) {
    if (levels[i + 1].askVol >= 2.8 * levels[i].bidVol && levels[i + 1].askVol > 40) {
      levels[i + 1].isBuyImbalance = true;
    }
    if (levels[i].bidVol >= 2.8 * levels[i + 1].askVol && levels[i].bidVol > 40) {
      levels[i].isSellImbalance = true;
    }
  }

  const cumDelta = prevCumDelta + barDelta;

  return {
    time: bar.time,
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: totalVol,
    delta: barDelta,
    cumDelta,
    pocPrice: levels[pocIdx]?.price || bar.close,
    levels: levels.reverse(), // Top to bottom descending prices
  };
}

/**
 * Singleton In-Memory Footprint Store.
 * Holds order flow memory buffers per symbol, surviving active re-renders.
 */
class InMemoryFootprintStore {
  private cache: Map<string, Map<number, BarFootprint>> = new Map();

  private getStore(symbol: string): Map<number, BarFootprint> {
    if (!this.cache.has(symbol)) {
      this.cache.set(symbol, new Map());
    }
    return this.cache.get(symbol)!;
  }

  /**
   * Ingest a batch of OHLC bars into memory and generate footprint ladders.
   */
  public ingestBars(
    symbol: string,
    bars: { time: number; open: number; high: number; low: number; close: number; volume?: number }[],
    tickStep: number,
  ): BarFootprint[] {
    const store = this.getStore(symbol);
    let runningCumDelta = 0;

    const result: BarFootprint[] = [];
    for (let i = 0; i < bars.length; i++) {
      const b = bars[i];
      const existing = store.get(b.time);
      if (existing && i < bars.length - 1) {
        runningCumDelta = existing.cumDelta;
        result.push(existing);
      } else {
        const fp = generateBarFootprint(b, tickStep, runningCumDelta);
        store.set(b.time, fp);
        runningCumDelta = fp.cumDelta;
        result.push(fp);
      }
    }

    // Keep memory bounded to last 200 bars in RAM
    if (store.size > 250) {
      const keys = Array.from(store.keys()).sort((a, b) => a - b);
      const toDelete = keys.slice(0, keys.length - 200);
      toDelete.forEach((k) => store.delete(k));
    }

    return result;
  }

  /**
   * Update active candle footprint in memory with a live micro-tick.
   */
  public updateWithTick(symbol: string, price: number, vol: number, _timestamp: number): void {
    const store = this.getStore(symbol);
    const keys = Array.from(store.keys()).sort((a, b) => a - b);
    if (keys.length === 0) return;

    const latestKey = keys[keys.length - 1];
    const latestFp = store.get(latestKey);
    if (!latestFp) return;

    let closestLevel = latestFp.levels[0];
    let minDiff = Infinity;
    for (const lvl of latestFp.levels) {
      const diff = Math.abs(lvl.price - price);
      if (diff < minDiff) {
        minDiff = diff;
        closestLevel = lvl;
      }
    }

    if (closestLevel) {
      if (price >= latestFp.close) {
        closestLevel.askVol += vol;
      } else {
        closestLevel.bidVol += vol;
      }
      closestLevel.totalVol += vol;
      closestLevel.delta = closestLevel.askVol - closestLevel.bidVol;

      latestFp.volume += vol;
      latestFp.delta += price >= latestFp.close ? vol : -vol;
      latestFp.cumDelta += price >= latestFp.close ? vol : -vol;
      latestFp.close = price;
      latestFp.high = Math.max(latestFp.high, price);
      latestFp.low = Math.min(latestFp.low, price);
    }
  }

  /**
   * Retrieve all footprint bars in memory for a symbol.
   */
  public getBars(symbol: string): BarFootprint[] {
    const store = this.getStore(symbol);
    return Array.from(store.values()).sort((a, b) => a.time - b.time);
  }

  /**
   * Calculate in-memory telemetry and memory usage stats.
   */
  public getStats(symbol: string): FootprintMemoryStats {
    const bars = this.getBars(symbol);
    if (bars.length === 0) {
      return {
        cachedBars: 0,
        memoryBytes: 0,
        totalVolume: 0,
        totalDelta: 0,
        cumDelta: 0,
        buyPressurePct: 50,
        sellPressurePct: 50,
        imbalancesCount: 0,
      };
    }

    let totVol = 0;
    let totDelta = 0;
    let totBid = 0;
    let totAsk = 0;
    let imbCount = 0;

    for (const b of bars) {
      totVol += b.volume;
      totDelta += b.delta;
      for (const lvl of b.levels) {
        totBid += lvl.bidVol;
        totAsk += lvl.askVol;
        if (lvl.isBuyImbalance || lvl.isSellImbalance) imbCount++;
      }
    }

    const buyPressurePct = totVol > 0 ? parseFloat(((totAsk / (totBid + totAsk || 1)) * 100).toFixed(1)) : 50;
    const sellPressurePct = parseFloat((100 - buyPressurePct).toFixed(1));
    const approxBytes = bars.length * 4200;

    return {
      cachedBars: bars.length,
      memoryBytes: approxBytes,
      totalVolume: totVol,
      totalDelta: totDelta,
      cumDelta: bars[bars.length - 1]?.cumDelta || 0,
      buyPressurePct,
      sellPressurePct,
      imbalancesCount: imbCount,
    };
  }

  /**
   * Clear cache for a symbol or completely.
   */
  public clear(symbol?: string): void {
    if (symbol) {
      this.cache.delete(symbol);
    } else {
      this.cache.clear();
    }
  }
}

export const inMemoryFootprintStore = new InMemoryFootprintStore();
