import { describe, expect, it } from "vitest";
import {
  analyzeChanlun,
  findBis,
  findFractals,
  findMmds,
  findZss,
  mergeKlines,
} from "./chanlun";
import type { KlineItem } from "../types/stock";

function k(date: string, open: number, close: number, high: number, low: number): KlineItem {
  return { date, open, close, high, low, volume: 100, amount: 100, amplitude: null, turnover_pct: null, change_pct: null };
}

function mk(o: number, c: number, h: number, l: number, date = "2026-01-01"): KlineItem {
  return k(date, o, c, h, l);
}

describe("mergeKlines", () => {
  it("无包含关系时逐根保留", () => {
    const items = [mk(1, 2, 2, 1), mk(2, 3, 3, 2), mk(3, 4, 4, 3)];
    const result = mergeKlines(items);
    expect(result).toHaveLength(3);
    expect(result[2].dataIndex).toBe(2);
  });

  it("向上方向合并取高高", () => {
    // 第二根被第一根包含（5>=4 且 1<=2），方向 up → high=max, low=max
    const items = [mk(1, 2, 5, 1), mk(2, 3, 4, 2), mk(6, 7, 7, 6, "2026-01-02")];
    const result = mergeKlines(items);
    expect(result).toHaveLength(2);
    expect(result[0].high).toBe(5);
    expect(result[0].low).toBe(2);
    expect(result[0].mergedCount).toBe(2);
  });

  it("向下方向合并取低低", () => {
    // 前一根为阴线（close<open）→ 方向 down → min/min
    const items = [mk(3, 2, 5, 1), mk(2, 3, 4, 2), mk(1, 0.5, 1, 0.5, "2026-01-02")];
    const result = mergeKlines(items);
    expect(result).toHaveLength(2);
    expect(result[0].high).toBe(4);
    expect(result[0].low).toBe(1);
  });
});

describe("findFractals", () => {
  it("识别顶分型和底分型并交替", () => {
    // 构造 上-顶-下-底-上 的走势
    const ck = mergeKlines([
      mk(1, 2, 2, 1), mk(2, 3, 3, 2), mk(3, 5, 5, 3),
      mk(5, 4, 5, 4), mk(4, 2, 4, 2), mk(2, 1, 2, 1),
      mk(1, 2, 2, 1), mk(2, 3, 3, 2),
    ]);
    const fxs = findFractals(ck);
    expect(fxs.length).toBeGreaterThanOrEqual(2);
    expect(fxs[0].fxType).toBe("ding");
    expect(fxs.some((fx) => fx.fxType === "di")).toBe(true);
  });
});

describe("findBis", () => {
  it("顶底交替且间距足够时成笔", () => {
    const ck = mergeKlines([
      mk(1, 2, 2, 1), mk(2, 4, 4, 2), mk(4, 6, 6, 4),
      mk(6, 7, 7, 6), mk(7, 5, 7, 5), mk(5, 3, 5, 3),
      mk(3, 1, 3, 1), mk(1, 2, 2, 1), mk(2, 3, 3, 2),
    ]);
    const fxs = findFractals(ck);
    const bis = findBis(fxs);
    expect(bis.length).toBeGreaterThanOrEqual(1);
    for (const bi of bis) {
      expect(bi.start.fxType).not.toBe(bi.end.fxType);
      expect(bi.direction).toBe(bi.start.fxType === "di" ? "up" : "down");
      expect(bi.high).toBeGreaterThanOrEqual(bi.low);
    }
  });
});

describe("findZss", () => {
  it("重叠笔形成中枢且区间正确", () => {
    // 手工构造笔列表（绕过分型，直接测中枢算法）
    const fx = (type: "ding" | "di", val: number, date: string) => ({
      fxType: type, mid: { dataIndex: 0, index: 0, date, open: val, close: val, high: val, low: val, mergedCount: 1 },
      leftIndex: 0, rightIndex: 2, val, index: 0,
    });
    const bi = (i: number, s: number, e: number, d: "up" | "down") => ({
      start: fx(d === "up" ? "di" : "ding", s, `2026-01-0${i + 1}`),
      end: fx(d === "up" ? "ding" : "di", e, `2026-01-0${i + 2}`),
      direction: d, index: i, high: Math.max(s, e), low: Math.min(s, e),
    });
    // 三笔互相重叠于 [3,5]
    const bis = [bi(0, 1, 5, "up"), bi(1, 5, 3, "down"), bi(2, 3, 6, "up"), bi(3, 6, 3, "down")];
    const zss = findZss(bis);
    expect(zss.length).toBeGreaterThanOrEqual(1);
    expect(zss[0].zg).toBeLessThanOrEqual(5);
    expect(zss[0].zd).toBeGreaterThanOrEqual(3);
    expect(zss[0].lineCount).toBeGreaterThanOrEqual(3);
  });
});

describe("analyzeChanlun 端到端", () => {
  it("锯齿走势产出笔、中枢与买卖点", () => {
    // 按拐点生成锯齿：相邻K线高低同步抬升/回落（互不包含），
    // 拐点处自然形成顶/底分型
    const waypoints = [10, 16, 13, 18, 13.5, 17.5, 14, 20, 15, 21];
    const items: KlineItem[] = [];
    let day = 0;
    for (let w = 0; w + 1 < waypoints.length; w += 1) {
      const from = waypoints[w];
      const to = waypoints[w + 1];
      const step = (to - from) / 3;
      for (let j = 1; j <= 3; j += 1) {
        day += 1;
        const low = from + step * (j - 1) + Math.sign(step) * 0.05;
        const high = from + step * j;
        const open = (low + high) / 2 - Math.sign(step) * 0.1;
        const close = (low + high) / 2 + Math.sign(step) * 0.1;
        items.push(k(`2026-02-${String(day).padStart(2, "0")}`, open, close, high, low));
      }
    }
    const result = analyzeChanlun(items);
    expect(result.bis.length).toBeGreaterThanOrEqual(5);
    expect(result.zss.length).toBeGreaterThanOrEqual(1);
    const zs = result.zss[0];
    expect(zs.zg).toBeGreaterThan(zs.zd);
    expect(zs.lineCount).toBeGreaterThanOrEqual(3);
    for (const mmd of result.mmds) {
      expect(["1buy", "2buy", "3buy", "1sell", "2sell", "3sell"]).toContain(mmd.mmdType);
      expect(mmd.date).toBeTruthy();
    }
  });

  it("数据不足时返回空结果", () => {
    const result = analyzeChanlun([mk(1, 2, 2, 1)]);
    expect(result.bis).toHaveLength(0);
    expect(result.zss).toHaveLength(0);
    expect(result.mmds).toHaveLength(0);
  });
});

describe("findMmds", () => {
  it("无中枢时无买卖点", () => {
    expect(findMmds([], [])).toHaveLength(0);
  });
});
