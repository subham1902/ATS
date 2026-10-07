import type { UTCTimestamp } from "lightweight-charts";
// ATR v1: first TR is high-low; seed the SMA of the first period TRs.
// Warmup remains null. Subsequent ATR=(prior*(period-1)+TR)/period.
export function wilderAtr(bars: { high: number; low: number; close: number }[], period = 14): (number | null)[] {
  if (!Number.isInteger(period) || period < 1) throw new Error("INVALID_ATR_PERIOD");
  let sum = 0;
  let previous: number | null = null;
  return bars.map((bar, index) => {
    const tr =
      index === 0
        ? bar.high - bar.low
        : Math.max(
            bar.high - bar.low,
            Math.abs(bar.high - bars[index - 1].close),
            Math.abs(bar.low - bars[index - 1].close),
          );
    if (index < period) sum += tr;
    if (index < period - 1) return null;
    previous = previous === null ? sum / period : (previous * (period - 1) + tr) / period;
    return previous;
  });
}
export function computeEma(bars: { time: UTCTimestamp; close: number }[], period: number) {
  if (!bars || bars.length < 2) return [];
  const k = 2 / (period + 1);
  let ema = bars[0].close;
  return bars.map((b, i) => {
    if (i === 0) return { time: b.time, value: b.close };
    ema = b.close * k + ema * (1 - k);
    return { time: b.time, value: parseFloat(ema.toFixed(2)) };
  });
}

export function computeVwap(
  bars: { time: UTCTimestamp; high: number; low: number; close: number }[],
  volumes: { value: number | null }[],
) {
  if (!bars || bars.length === 0) return [];
  let cumVol = 0;
  let cumTypVol = 0;
  // Bars with unknown volume contribute nothing: VWAP is computed over
  // observed volume only, never over a filled-in default.
  return bars.map((b, i) => {
    const vol = volumes[i]?.value ?? null;
    const typPrice = (b.high + b.low + b.close) / 3;
    if (vol !== null && vol > 0) {
      cumVol += vol;
      cumTypVol += typPrice * vol;
    }
    const vwap = cumVol > 0 ? cumTypVol / cumVol : null;
    return { time: b.time, value: vwap === null ? null : parseFloat(vwap.toFixed(2)) };
  });
}

export function computeBollingerBands(bars: { time: UTCTimestamp; close: number }[], period = 20, stdDevMult = 2) {
  const upper: { time: UTCTimestamp; value: number }[] = [];
  const mid: { time: UTCTimestamp; value: number }[] = [];
  const lower: { time: UTCTimestamp; value: number }[] = [];

  if (!bars || bars.length === 0) return { upper, mid, lower };

  for (let i = 0; i < bars.length; i++) {
    if (i < period - 1) {
      mid.push({ time: bars[i].time, value: bars[i].close });
      upper.push({ time: bars[i].time, value: bars[i].close });
      lower.push({ time: bars[i].time, value: bars[i].close });
      continue;
    }
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sum += bars[j].close;
    }
    const sma = sum / period;
    let varSum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      varSum += Math.pow(bars[j].close - sma, 2);
    }
    const stdDev = Math.sqrt(varSum / period);
    mid.push({ time: bars[i].time, value: parseFloat(sma.toFixed(2)) });
    upper.push({ time: bars[i].time, value: parseFloat((sma + stdDevMult * stdDev).toFixed(2)) });
    lower.push({ time: bars[i].time, value: parseFloat((sma - stdDevMult * stdDev).toFixed(2)) });
  }

  return { upper, mid, lower };
}

export function computeRsi(bars: { close: number }[], period = 14): number | null {
  if (!bars || bars.length < period + 1) return null;
  let gains = 0;
  let losses = 0;

  for (let i = 1; i <= period; i++) {
    const diff = bars[i].close - bars[i - 1].close;
    if (diff >= 0) gains += diff;
    else losses += Math.abs(diff);
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;

  for (let i = period + 1; i < bars.length; i++) {
    const diff = bars[i].close - bars[i - 1].close;
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? Math.abs(diff) : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
  }

  if (avgLoss === 0) return 100.0;
  const rs = avgGain / avgLoss;
  return parseFloat((100 - 100 / (1 + rs)).toFixed(1));
}

export function computeSuperTrend(
  bars: { time: UTCTimestamp; high: number; low: number; close: number }[],
  period = 10,
  multiplier = 3,
): { data: { time: UTCTimestamp; value: number }[]; isBullish: boolean } {
  if (!bars || bars.length < period) return { data: [], isBullish: true };
  const result: { time: UTCTimestamp; value: number }[] = [];
  let prevUpper = 0;
  let prevLower = 0;
  let prevSuperTrend = 0;
  let trend = 1;
  const atrValues = wilderAtr(bars, period);

  for (let i = 0; i < bars.length; i++) {
    const b = bars[i];
    const atr = atrValues[i];
    if (atr === null) continue;

    const hl2 = (b.high + b.low) / 2;
    const basicUpper = hl2 + multiplier * atr;
    const basicLower = hl2 - multiplier * atr;

    if (result.length === 0) {
      prevUpper = basicUpper;
      prevLower = basicLower;
      prevSuperTrend = basicLower;
      result.push({ time: b.time, value: parseFloat(prevSuperTrend.toFixed(2)) });
      continue;
    }

    const finalUpper = basicUpper < prevUpper || bars[i - 1].close > prevUpper ? basicUpper : prevUpper;
    const finalLower = basicLower > prevLower || bars[i - 1].close < prevLower ? basicLower : prevLower;

    if (prevSuperTrend === prevUpper) {
      trend = b.close > finalUpper ? 1 : -1;
    } else {
      trend = b.close < finalLower ? -1 : 1;
    }

    const superTrend = trend === 1 ? finalLower : finalUpper;
    result.push({ time: b.time, value: parseFloat(superTrend.toFixed(2)) });

    prevUpper = finalUpper;
    prevLower = finalLower;
    prevSuperTrend = superTrend;
  }

  return { data: result, isBullish: trend === 1 };
}

export function convertToHeikinAshi(
  bars: { time: UTCTimestamp; open: number; high: number; low: number; close: number }[],
) {
  if (!bars || bars.length === 0) return [];
  const haBars: { time: UTCTimestamp; open: number; high: number; low: number; close: number }[] = [];
  let prevHaOpen = bars[0].open;
  let prevHaClose = bars[0].close;

  for (let i = 0; i < bars.length; i++) {
    const b = bars[i];
    const haClose = (b.open + b.high + b.low + b.close) / 4;
    const haOpen = i === 0 ? (b.open + b.close) / 2 : (prevHaOpen + prevHaClose) / 2;
    const haHigh = Math.max(b.high, haOpen, haClose);
    const haLow = Math.min(b.low, haOpen, haClose);

    haBars.push({
      time: b.time,
      open: parseFloat(haOpen.toFixed(2)),
      high: parseFloat(haHigh.toFixed(2)),
      low: parseFloat(haLow.toFixed(2)),
      close: parseFloat(haClose.toFixed(2)),
    });

    prevHaOpen = haOpen;
    prevHaClose = haClose;
  }
  return haBars;
}

export function computeAtr(bars: { high: number; low: number; close: number }[], period = 14): number | null {
  return wilderAtr(bars, period).at(-1) ?? null;
}

export function computeTrendChannel(bars: { time: UTCTimestamp; high: number; low: number; close: number }[]) {
  if (!bars || bars.length < 15) return { support: [], resistance: [] };
  const slice = bars.slice(-35);
  const n = slice.length;
  let sumX = 0;
  let sumY = 0;
  let sumXY = 0;
  let sumX2 = 0;
  slice.forEach((b, i) => {
    sumX += i;
    sumY += b.close;
    sumXY += i * b.close;
    sumX2 += i * i;
  });
  const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;

  let maxUp = 0;
  let maxDown = 0;
  slice.forEach((b, i) => {
    const mid = intercept + slope * i;
    const diffUp = b.high - mid;
    const diffDown = mid - b.low;
    if (diffUp > maxUp) maxUp = diffUp;
    if (diffDown > maxDown) maxDown = diffDown;
  });

  const support = slice.map((b, i) => ({
    time: b.time,
    value: parseFloat((intercept + slope * i - maxDown * 0.75).toFixed(2)),
  }));
  const resistance = slice.map((b, i) => ({
    time: b.time,
    value: parseFloat((intercept + slope * i + maxUp * 0.75).toFixed(2)),
  }));

  return { support, resistance };
}

// -------------------------------------------------------------
// Main LiveChart Component
// -------------------------------------------------------------
