export interface MacdPoint<TTime> {
  time: TTime;
  dif: number;
  dea: number;
  macd: number;
}

export interface MacdResult<TTime> {
  dif: { time: TTime; value: number }[];
  dea: { time: TTime; value: number }[];
  macd: { time: TTime; value: number; color?: string }[];
}

export interface KdjResult<TTime> {
  k: { time: TTime; value: number }[];
  d: { time: TTime; value: number }[];
  j: { time: TTime; value: number }[];
}

export interface RsiResult<TTime> {
  rsi6: { time: TTime; value: number }[];
  rsi12: { time: TTime; value: number }[];
  rsi24: { time: TTime; value: number }[];
}

/**
 * 计算同花顺/通达信标准 MACD (12, 26, 9)
 * EMA12: 平滑指数 2/(12+1)
 * EMA26: 平滑指数 2/(26+1)
 * DIF = EMA12 - EMA26
 * DEA = EMA(DIF, 9), 平滑指数 2/(9+1)
 * MACD 柱 = (DIF - DEA) * 2
 */
export function calculateMACD<T extends { close: number; date?: unknown; time?: unknown }>(
  data: T[],
  fastPeriod = 12,
  slowPeriod = 26,
  signalPeriod = 9,
): MacdResult<T["date"] | T["time"]> {
  const dif: { time: T["date"] | T["time"]; value: number }[] = [];
  const dea: { time: T["date"] | T["time"]; value: number }[] = [];
  const macd: { time: T["date"] | T["time"]; value: number }[] = [];

  if (data.length === 0) return { dif, dea, macd };

  let emaFast = data[0].close;
  let emaSlow = data[0].close;
  let deaVal = 0;

  const fastK = 2 / (fastPeriod + 1);
  const slowK = 2 / (slowPeriod + 1);
  const signalK = 2 / (signalPeriod + 1);

  for (let i = 0; i < data.length; i++) {
    const time = data[i].date ?? data[i].time;
    const close = data[i].close;

    if (i === 0) {
      emaFast = close;
      emaSlow = close;
      deaVal = 0;
    } else {
      emaFast = close * fastK + emaFast * (1 - fastK);
      emaSlow = close * slowK + emaSlow * (1 - slowK);
    }

    const difVal = emaFast - emaSlow;
    if (i === 0) {
      deaVal = difVal;
    } else {
      deaVal = difVal * signalK + deaVal * (1 - signalK);
    }
    const macdVal = (difVal - deaVal) * 2;

    dif.push({ time, value: Number(difVal.toFixed(2)) });
    dea.push({ time, value: Number(deaVal.toFixed(2)) });
    macd.push({ time, value: Number(macdVal.toFixed(2)) });
  }

  return { dif, dea, macd };
}

/**
 * 计算同花顺/通达信标准 KDJ (9, 3, 3)
 * RSV = (Close - LowestLow9) / (HighestHigh9 - LowestLow9) * 100
 * K = (2/3) * PrevK + (1/3) * RSV  (初值 50)
 * D = (2/3) * PrevD + (1/3) * K    (初值 50)
 * J = 3 * K - 2 * D
 */
export function calculateKDJ<T extends { close: number; high: number; low: number; date?: unknown; time?: unknown }>(
  data: T[],
  period = 9,
  m1 = 3,
  m2 = 3,
): KdjResult<T["date"] | T["time"]> {
  const k: { time: T["date"] | T["time"]; value: number }[] = [];
  const d: { time: T["date"] | T["time"]; value: number }[] = [];
  const j: { time: T["date"] | T["time"]; value: number }[] = [];

  if (data.length === 0) return { k, d, j };

  let prevK = 50;
  let prevD = 50;

  for (let i = 0; i < data.length; i++) {
    const time = data[i].date ?? data[i].time;
    const start = Math.max(0, i - period + 1);
    let lowMin = data[start].low;
    let highMax = data[start].high;

    for (let s = start + 1; s <= i; s++) {
      if (data[s].low < lowMin) lowMin = data[s].low;
      if (data[s].high > highMax) highMax = data[s].high;
    }

    const rsv = highMax === lowMin ? 50 : ((data[i].close - lowMin) / (highMax - lowMin)) * 100;
    const kVal = (rsv + (m1 - 1) * prevK) / m1;
    const dVal = (kVal + (m2 - 1) * prevD) / m2;
    const jVal = 3 * kVal - 2 * dVal;

    prevK = kVal;
    prevD = dVal;

    k.push({ time, value: Number(kVal.toFixed(2)) });
    d.push({ time, value: Number(dVal.toFixed(2)) });
    j.push({ time, value: Number(jVal.toFixed(2)) });
  }

  return { k, d, j };
}

/**
 * 辅助计算 SMA(X, N, M): SMA_i = (M * X_i + (N - M) * SMA_{i-1}) / N
 */
function calculateSMA(values: number[], n: number, m: number): number[] {
  const res: number[] = [];
  let prev = 0;
  for (let i = 0; i < values.length; i++) {
    if (i === 0) {
      prev = values[0];
    } else {
      prev = (m * values[i] + (n - m) * prev) / n;
    }
    res.push(prev);
  }
  return res;
}

/**
 * 计算同花顺/通达信标准 RSI (6, 12, 24)
 * LC = REF(CLOSE, 1)
 * MAX_CHG = MAX(CLOSE - LC, 0)
 * ABS_CHG = ABS(CLOSE - LC)
 * RSI = SMA(MAX_CHG, N, 1) / SMA(ABS_CHG, N, 1) * 100
 */
export function calculateRSI<T extends { close: number; date?: unknown; time?: unknown }>(
  data: T[],
  periods = [6, 12, 24] as const,
): RsiResult<T["date"] | T["time"]> {
  const rsi6: { time: T["date"] | T["time"]; value: number }[] = [];
  const rsi12: { time: T["date"] | T["time"]; value: number }[] = [];
  const rsi24: { time: T["date"] | T["time"]; value: number }[] = [];

  if (data.length === 0) return { rsi6, rsi12, rsi24 };

  const maxChg: number[] = [0];
  const absChg: number[] = [0];

  for (let i = 1; i < data.length; i++) {
    const diff = data[i].close - data[i - 1].close;
    maxChg.push(Math.max(diff, 0));
    absChg.push(Math.abs(diff));
  }

  const computeForPeriod = (period: number) => {
    const smaMax = calculateSMA(maxChg, period, 1);
    const smaAbs = calculateSMA(absChg, period, 1);
    const list: { time: T["date"] | T["time"]; value: number }[] = [];
    for (let i = 0; i < data.length; i++) {
      const time = data[i].date ?? data[i].time;
      const absVal = smaAbs[i];
      const val = absVal === 0 ? 50 : (smaMax[i] / absVal) * 100;
      list.push({ time, value: Number(val.toFixed(2)) });
    }
    return list;
  };

  return {
    rsi6: computeForPeriod(periods[0]),
    rsi12: computeForPeriod(periods[1]),
    rsi24: computeForPeriod(periods[2]),
  };
}
