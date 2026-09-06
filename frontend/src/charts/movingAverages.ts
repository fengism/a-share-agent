export interface MaPoint {
  time: unknown;
  value: number;
}

export function calculateMA<T extends { close: number; date?: unknown; time?: unknown }>(
  data: T[],
  period: number,
): { time: T["date"] | T["time"]; value: number }[] {
  const result: { time: T["date"] | T["time"]; value: number }[] = [];
  let sum = 0;
  for (let i = 0; i < data.length; i++) {
    sum += data[i].close;
    if (i >= period) {
      sum -= data[i - period].close;
    }
    if (i >= period - 1) {
      const time = data[i].date ?? data[i].time;
      result.push({
        time,
        value: Number((sum / period).toFixed(2)),
      });
    }
  }
  return result;
}

export function calculateMAVOL<T extends { amount?: number | null; volume?: number | null; date?: unknown; time?: unknown }>(
  data: T[],
  period: number,
): { time: T["date"] | T["time"]; value: number }[] {
  const result: { time: T["date"] | T["time"]; value: number }[] = [];
  let sum = 0;
  for (let i = 0; i < data.length; i++) {
    const val = data[i].amount ?? data[i].volume ?? 0;
    sum += val;
    if (i >= period) {
      const prevVal = data[i - period].amount ?? data[i - period].volume ?? 0;
      sum -= prevVal;
    }
    if (i >= period - 1) {
      const time = data[i].date ?? data[i].time;
      result.push({
        time,
        value: Number((sum / period).toFixed(2)),
      });
    }
  }
  return result;
}

export interface BollResult<TTime> {
  mid: { time: TTime; value: number }[];
  upper: { time: TTime; value: number }[];
  lower: { time: TTime; value: number }[];
}

export function calculateBOLL<T extends { close: number; date?: unknown; time?: unknown }>(
  data: T[],
  period = 20,
  multiplier = 2,
): BollResult<T["date"] | T["time"]> {
  const mid: { time: T["date"] | T["time"]; value: number }[] = [];
  const upper: { time: T["date"] | T["time"]; value: number }[] = [];
  const lower: { time: T["date"] | T["time"]; value: number }[] = [];

  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1);
    const mean = slice.reduce((acc, cur) => acc + cur.close, 0) / period;
    const variance = slice.reduce((acc, cur) => acc + Math.pow(cur.close - mean, 2), 0) / period;
    const stdDev = Math.sqrt(variance);

    const time = data[i].date ?? data[i].time;
    const midVal = Number(mean.toFixed(2));
    const upVal = Number((mean + multiplier * stdDev).toFixed(2));
    const dnVal = Number((mean - multiplier * stdDev).toFixed(2));

    mid.push({ time, value: midVal });
    upper.push({ time, value: upVal });
    lower.push({ time, value: dnVal });
  }

  return { mid, upper, lower };
}

export const MA_CONFIGS = [
  { key: "ma5", name: "MA5", period: 5, color: "#f0b90b" },
  { key: "ma10", name: "MA10", period: 10, color: "#1890ff" },
  { key: "ma20", name: "MA20", period: 20, color: "#9254de" },
  { key: "ma30", name: "MA30", period: 30, color: "#13c2c2" },
  { key: "ma60", name: "MA60", period: 60, color: "#ff7a45" },
] as const;

export const MAVOL_CONFIGS = [
  { key: "vol5", name: "VOL5", period: 5, color: "#f0b90b" },
  { key: "vol10", name: "VOL10", period: 10, color: "#1890ff" },
] as const;
