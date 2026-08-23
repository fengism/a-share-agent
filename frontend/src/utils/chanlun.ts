/**
 * 缠论（ChanLun）技术分析 —— 纯前端 TypeScript 移植。
 *
 * 移植自 easy_tdx/chanlun（Python）：K线包含合并 → 分型识别 → 笔 →
 * 中枢 → 三类买卖点。锚点全部记录原始 K 线的 date，便于直接叠加到
 * lightweight-charts 时间轴。算法保持与参考实现一致的简化语义。
 */

import type { KlineItem } from "../types/stock";

export type FxType = "ding" | "di";
export type Direction = "up" | "down";
export type MmdType = "1buy" | "2buy" | "3buy" | "1sell" | "2sell" | "3sell";

export interface ChanConfig {
  /** "new"=分型间至少1根独立缠论K线，"old"=至少3根，"simple"=顶底交替即可 */
  biType: "new" | "old" | "simple";
  /** 中枢最少重叠笔数 */
  zsMinLines: number;
  /** 严格分型：中间K线高低必须严格超过两侧 */
  fxStrict: boolean;
}

export const DEFAULT_CHAN_CONFIG: ChanConfig = {
  biType: "new",
  zsMinLines: 3,
  fxStrict: true,
};

/** 包含处理后的缠论 K 线。 */
export interface ChanKline {
  /** 原始 K 线列表中的下标（合并后指向最后一根） */
  dataIndex: number;
  /** 在缠论 K 线列表中的下标 */
  index: number;
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  /** 合并了几根原始 K 线 */
  mergedCount: number;
}

/** 分型。 */
export interface Fractal {
  fxType: FxType;
  /** 分型中间缠论 K 线 */
  mid: ChanKline;
  /** 构成分型的三根缠论 K 线 [左, 中, 右] */
  leftIndex: number;
  rightIndex: number;
  /** 分型值：顶取 high，底取 low */
  val: number;
  index: number;
}

/** 笔：相邻顶底分型连接而成。 */
export interface Bi {
  start: Fractal;
  end: Fractal;
  direction: Direction;
  index: number;
  high: number;
  low: number;
}

/** 中枢：至少 zsMinLines 笔的价格重叠区间。 */
export interface Zs {
  lineCount: number;
  zg: number;
  zd: number;
  gg: number;
  dd: number;
  /** 首笔起始分型日期 */
  startDate: string;
  /** 末笔结束分型日期 */
  endDate: string;
  done: boolean;
  index: number;
}

/** 买卖点。 */
export interface Mmd {
  mmdType: MmdType;
  /** 触发笔（锚定用） */
  biIndex: number;
  date: string;
  val: number;
  msg: string;
}

export interface ChanlunResult {
  fractals: Fractal[];
  bis: Bi[];
  zss: Zs[];
  mmds: Mmd[];
}

// ── K 线包含合并 ─────────────────────────────────────────────────────────

function isIncluded(a: ChanKline, b: ChanKline): boolean {
  return a.high >= b.high && a.low <= b.low;
}

export function mergeKlines(items: KlineItem[]): ChanKline[] {
  if (!items.length) return [];
  const result: ChanKline[] = [{
    dataIndex: 0,
    index: 0,
    date: items[0].date,
    open: items[0].open,
    close: items[0].close,
    high: items[0].high,
    low: items[0].low,
    mergedCount: 1,
  }];
  for (let i = 1; i < items.length; i += 1) {
    const k = items[i];
    const prev = result[result.length - 1];
    const candidate: ChanKline = {
      dataIndex: i, index: -1, date: k.date,
      open: k.open, close: k.close, high: k.high, low: k.low, mergedCount: 1,
    };
    if (isIncluded(prev, candidate) || isIncluded(candidate, prev)) {
      // 方向：与前一缠论K线高点比较；首根按前一根阴阳判断（与参考实现一致）
      let direction: Direction;
      if (result.length >= 2) {
        direction = prev.high > result[result.length - 2].high ? "up" : "down";
      } else {
        direction = prev.close >= prev.open ? "up" : "down";
      }
      if (direction === "up") {
        prev.high = Math.max(prev.high, candidate.high);
        prev.low = Math.max(prev.low, candidate.low);
      } else {
        prev.high = Math.min(prev.high, candidate.high);
        prev.low = Math.min(prev.low, candidate.low);
      }
      prev.dataIndex = i;
      prev.date = k.date;
      prev.open = k.open;
      prev.close = k.close;
      prev.mergedCount += 1;
    } else {
      result.push({ ...candidate, index: result.length });
    }
  }
  return result;
}

// ── 分型识别 ─────────────────────────────────────────────────────────────

export function findFractals(
  cklines: ChanKline[],
  config: ChanConfig = DEFAULT_CHAN_CONFIG,
): Fractal[] {
  const fractals: Fractal[] = [];
  for (let i = 0; i + 2 < cklines.length; i += 1) {
    const left = cklines[i];
    const mid = cklines[i + 1];
    const right = cklines[i + 2];
    const isDing = config.fxStrict
      ? mid.high > left.high && mid.high > right.high
      : mid.high >= left.high && mid.high >= right.high;
    const isDi = config.fxStrict
      ? mid.low < left.low && mid.low < right.low
      : mid.low <= left.low && mid.low <= right.low;
    if (isDing && isDi) continue;
    if (isDing) {
      fractals.push({
        fxType: "ding", mid, leftIndex: left.index, rightIndex: right.index,
        val: mid.high, index: fractals.length,
      });
    } else if (isDi) {
      fractals.push({
        fxType: "di", mid, leftIndex: left.index, rightIndex: right.index,
        val: mid.low, index: fractals.length,
      });
    }
  }
  return fractals;
}

// ── 笔计算 ───────────────────────────────────────────────────────────────

function canFormBi(start: Fractal, end: Fractal, config: ChanConfig): boolean {
  if (start.fxType === end.fxType) return false;
  if (config.biType === "simple") return true;
  // 分型由三根缠论K线组成，独立K线数 = end.left - start.right + 1
  const gap = end.leftIndex - start.rightIndex + 1;
  return gap >= (config.biType === "old" ? 3 : 1);
}

export function findBis(
  fractals: Fractal[],
  config: ChanConfig = DEFAULT_CHAN_CONFIG,
): Bi[] {
  if (fractals.length < 2) return [];
  const bis: Bi[] = [];
  let startFx = fractals[0];
  let pendingOpposite: Fractal | null = null;

  for (let i = 1; i < fractals.length; i += 1) {
    const fx = fractals[i];
    if (fx.fxType === startFx.fxType) {
      // 同类型取更极端；存在 pending 异类型分型时不替换，避免分型陷阱
      if (pendingOpposite) continue;
      if (startFx.fxType === "ding" && fx.val > startFx.val) startFx = fx;
      else if (startFx.fxType === "di" && fx.val < startFx.val) startFx = fx;
      continue;
    }
    if (canFormBi(startFx, fx, config)) {
      bis.push({
        start: startFx,
        end: fx,
        direction: startFx.fxType === "di" ? "up" : "down",
        index: bis.length,
        high: Math.max(startFx.val, fx.val),
        low: Math.min(startFx.val, fx.val),
      });
      startFx = fx;
      pendingOpposite = null;
    } else {
      pendingOpposite = fx;
    }
  }
  return bis;
}

// ── 中枢计算 ─────────────────────────────────────────────────────────────

export function findZss(
  bis: Bi[],
  config: ChanConfig = DEFAULT_CHAN_CONFIG,
): Zs[] {
  if (bis.length < 3) return [];
  const zss: Zs[] = [];
  let current: {
    lineCount: number; zg: number; zd: number; gg: number; dd: number;
    startDate: string; endDate: string;
  } | null = null;

  const closeCurrent = (done: boolean) => {
    if (current && current.lineCount >= config.zsMinLines) {
      zss.push({ ...current, done, index: zss.length });
    }
  };

  for (const bi of bis) {
    if (current === null) {
      current = {
        lineCount: 1, zg: bi.high, zd: bi.low, gg: bi.high, dd: bi.low,
        startDate: bi.start.mid.date, endDate: bi.end.mid.date,
      };
      continue;
    }
    const overlapHigh = Math.min(current.zg, bi.high);
    const overlapLow = Math.max(current.zd, bi.low);
    if (overlapHigh > overlapLow) {
      current.lineCount += 1;
      current.zg = overlapHigh;
      current.zd = overlapLow;
      current.gg = Math.max(current.gg, bi.high);
      current.dd = Math.min(current.dd, bi.low);
      current.endDate = bi.end.mid.date;
    } else {
      closeCurrent(true);
      current = {
        lineCount: 1, zg: bi.high, zd: bi.low, gg: bi.high, dd: bi.low,
        startDate: bi.start.mid.date, endDate: bi.end.mid.date,
      };
    }
  }
  closeCurrent(false);
  return zss;
}

// ── 买卖点识别 ───────────────────────────────────────────────────────────

function forceDecreasing(bi: Bi, bis: Bi[]): boolean {
  for (let j = bi.index - 1; j >= 0; j -= 1) {
    const prev = bis[j];
    if (prev.direction === bi.direction) {
      const currRange = bi.high - bi.low;
      const prevRange = prev.high - prev.low;
      return bi.direction === "down"
        ? currRange < prevRange && bi.low < prev.low
        : currRange < prevRange && bi.high > prev.high;
    }
  }
  return false;
}

export function findMmds(bis: Bi[], zss: Zs[]): Mmd[] {
  if (bis.length < 2 || zss.length === 0) return [];
  const mmds: Mmd[] = [];

  for (const bi of bis) {
    for (let z = zss.length - 1; z >= 0; z -= 1) {
      const zs = zss[z];
      let mmd: Mmd | null = null;
      if (bi.direction === "down") {
        if (bi.low < zs.zd && forceDecreasing(bi, bis)) {
          mmd = {
            mmdType: "1buy", biIndex: bi.index, date: bi.end.mid.date, val: bi.end.val,
            msg: `中枢下方力度衰减，一类买点 (l=${bi.low.toFixed(2)} < zd=${zs.zd.toFixed(2)})`,
          };
        } else if (bi.low > zs.zd && bi.low > zs.dd && bi.index >= 2) {
          const prevDown = bis[bi.index - 2];
          if (prevDown.direction === "down" && bi.low > prevDown.low) {
            mmd = {
              mmdType: "2buy", biIndex: bi.index, date: bi.end.mid.date, val: bi.end.val,
              msg: `回调不创新低，二类买点 (l=${bi.low.toFixed(2)})`,
            };
          }
        } else if (bi.low > zs.zg && bi.low > zs.zd) {
          mmd = {
            mmdType: "3buy", biIndex: bi.index, date: bi.end.mid.date, val: bi.end.val,
            msg: `回调不破中枢上沿，三类买点 (l=${bi.low.toFixed(2)} > zg=${zs.zg.toFixed(2)})`,
          };
        }
      } else {
        if (bi.high > zs.zg && forceDecreasing(bi, bis)) {
          mmd = {
            mmdType: "1sell", biIndex: bi.index, date: bi.end.mid.date, val: bi.end.val,
            msg: `中枢上方力度衰减，一类卖点 (h=${bi.high.toFixed(2)} > zg=${zs.zg.toFixed(2)})`,
          };
        } else if (bi.high < zs.zg && bi.high < zs.gg && bi.index >= 2) {
          const prevUp = bis[bi.index - 2];
          if (prevUp.direction === "up" && bi.high < prevUp.high) {
            mmd = {
              mmdType: "2sell", biIndex: bi.index, date: bi.end.mid.date, val: bi.end.val,
              msg: `反弹不创新高，二类卖点 (h=${bi.high.toFixed(2)})`,
            };
          }
        } else if (bi.high < zs.zd) {
          mmd = {
            mmdType: "3sell", biIndex: bi.index, date: bi.end.mid.date, val: bi.end.val,
            msg: `反弹不破中枢下沿，三类卖点 (h=${bi.high.toFixed(2)} < zd=${zs.zd.toFixed(2)})`,
          };
        }
      }
      if (mmd) {
        mmds.push(mmd);
        break;
      }
    }
  }
  return mmds;
}

// ── 主入口 ───────────────────────────────────────────────────────────────

export function analyzeChanlun(
  items: KlineItem[],
  config: ChanConfig = DEFAULT_CHAN_CONFIG,
): ChanlunResult {
  const cklines = mergeKlines(items);
  const fractals = findFractals(cklines, config);
  const bis = findBis(fractals, config);
  const zss = findZss(bis, config);
  const mmds = findMmds(bis, zss);
  return { fractals, bis, zss, mmds };
}

export const MMD_LABELS: Record<MmdType, string> = {
  "1buy": "一买",
  "2buy": "二买",
  "3buy": "三买",
  "1sell": "一卖",
  "2sell": "二卖",
  "3sell": "三卖",
};
