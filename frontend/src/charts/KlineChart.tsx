import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  ColorType,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type IPriceLine,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
  type BusinessDay,
  type MouseEventParams,
  type CandlestickData,
} from "lightweight-charts";
import type { KlineItem, ChipDistribution } from "../types/stock";
import type { ChanlunResult, MmdType } from "../utils/chanlun";
import { useColors } from "../styles/ui";
import { APP_FONT_FAMILY, APP_FONT_SIZE } from "../theme/typography";
import { createDebouncedResizeHandler, shouldFitChartContent } from "./chartLifecycle";
import { toBusinessDay, hexToRgba } from "./utils";
import { buildKlineTradeMarkers, type KlineTradeMarker } from "./klineMarkers";
import { calculateMA, calculateMAVOL, calculateBOLL, MA_CONFIGS, MAVOL_CONFIGS } from "./movingAverages";
import { calculateMACD, calculateKDJ, calculateRSI } from "./technicalIndicators";
import { VOLUME_PANE_INDEX, PRICE_PANE_RATIO, applyVolumePaneLayout, getChartPaneThemeConfig } from "./chartPaneLayout";

/** 可视区左缘距离第一根 K 线多少根以内触发扩充历史。 */
const LEFT_EDGE_TRIGGER_INDEX = 8;

export type SubIndicatorType = "VOL" | "AMO" | "MACD" | "KDJ" | "RSI";
export type CandleStyleType = "solid" | "hollow";
export type { ChipDistribution } from "../types/stock";

type Props = {
  data: KlineItem[];
  height?: number;
  viewKey?: string;
  tradeMarkers?: KlineTradeMarker[];
  /** 缠论分析结果：叠加笔、中枢区间与买卖点标记 */
  chanlun?: ChanlunResult | null;
  /** 可视区滚动到左缘时回调，用于按需向左扩充更早的历史数据 */
  onReachLeftEdge?: () => void;
  /** 已达到可回溯上限；为 true 时不再触发扩充 */
  historyLimitReached?: boolean;
  /** 是否在可视区自动标注最高价与最低价，默认为 true */
  showHighLowMarkers?: boolean;
  defaultSubIndicator?: SubIndicatorType;
  defaultCandleStyle?: CandleStyleType;
  /** 个股筹码分布数据（含筹码主峰、获利比例与成本区间） */
  chipDistribution?: ChipDistribution | null;
  /** 是否默认开启主图筹码峰线与侧边分布微图 */
  defaultShowChipPeak?: boolean;
  /** 横屏（放大横屏）模式下叠加到 HUD 的工具条，例如周期切换控件 */
  landscapeToolbar?: ReactNode;
};
type ChartItem = Omit<KlineItem, "date"> & { date: BusinessDay; rawDate: string };

interface HoverCandleInfo {
  dateStr: string;
  open: number;
  high: number;
  low: number;
  close: number;
  changePct: number | null;
  amount: number | null;
  volume: number | null;
  turnoverPct?: number | null;
  amplitude?: number | null;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma30: number | null;
  ma60: number | null;
  vol5: number | null;
  vol10: number | null;
  amo5: number | null;
  amo10: number | null;
  bollMid: number | null;
  bollUp: number | null;
  bollDn: number | null;
  dif: number | null;
  dea: number | null;
  macd: number | null;
  k: number | null;
  d: number | null;
  j: number | null;
  rsi6: number | null;
  rsi12: number | null;
  rsi24: number | null;
}

const MMD_MARKER_TEXT: Record<MmdType, string> = {
  "1buy": "①买", "2buy": "②买", "3buy": "③买",
  "1sell": "①卖", "2sell": "②卖", "3sell": "③卖",
};

function buildChanlunMarkers(
  chanlun: ChanlunResult,
  colors: { up: string; down: string },
  validDates: Set<string>,
): SeriesMarker<Time>[] {
  const markers: SeriesMarker<Time>[] = [];
  for (const mmd of chanlun.mmds) {
    const time = toBusinessDay(mmd.date);
    if (!time || !validDates.has(mmd.date)) continue;
    const isBuy = mmd.mmdType.endsWith("buy");
    markers.push({
      time,
      position: isBuy ? "belowBar" : "aboveBar",
      shape: isBuy ? "arrowUp" : "arrowDown",
      color: isBuy ? colors.up : colors.down,
      text: MMD_MARKER_TEXT[mmd.mmdType],
      size: 1,
    });
  }
  return markers;
}

function formatVolume(val: number | null | undefined): string {
  if (val == null || isNaN(val)) return "-";
  if (Math.abs(val) >= 1e8) return `${(val / 1e8).toFixed(2)}亿`;
  if (Math.abs(val) >= 1e4) return `${(val / 1e4).toFixed(2)}万`;
  return val.toFixed(0);
}

function formatAmount(val: number | null | undefined): string {
  if (val == null || isNaN(val)) return "-";
  if (Math.abs(val) >= 1e8) return `${(val / 1e8).toFixed(2)}亿`;
  if (Math.abs(val) >= 1e4) return `${(val / 1e4).toFixed(2)}万`;
  return val.toFixed(0);
}

function renderVolumeRatioBadge(
  val: number | null | undefined,
  maVal: number | null | undefined,
  colors?: { up?: string; down?: string; muted?: string; secondary?: string },
) {
  if (val == null || maVal == null || maVal <= 0 || val <= 0) return null;
  const ratio = val / maVal;
  const upColor = colors?.up ?? "#ef4444";
  const downColor = colors?.down ?? "#10b981";
  const mutedColor = colors?.muted ?? "#888888";
  const secondaryColor = colors?.secondary ?? "#aaaaaa";
  if (ratio >= 2.0) {
    return (
      <span
        title={`量比: ${(ratio * 100).toFixed(0)}% (对比5日均值)`}
        style={{ fontSize: "10px", padding: "0 4px", borderRadius: 2, background: hexToRgba(upColor, 0.15), color: upColor, fontWeight: 700, lineHeight: "14px" }}
      >
        爆量 {ratio.toFixed(1)}x
      </span>
    );
  }
  if (ratio >= 1.3) {
    return (
      <span
        title={`量比: ${(ratio * 100).toFixed(0)}% (对比5日均值)`}
        style={{ fontSize: "10px", padding: "0 4px", borderRadius: 2, background: hexToRgba(upColor, 0.12), color: upColor, fontWeight: 600, lineHeight: "14px" }}
      >
        放量 {ratio.toFixed(1)}x
      </span>
    );
  }
  if (ratio <= 0.6) {
    return (
      <span
        title={`量比: ${(ratio * 100).toFixed(0)}% (对比5日均值)`}
        style={{ fontSize: "10px", padding: "0 4px", borderRadius: 2, background: hexToRgba(downColor, 0.12), color: downColor, fontWeight: 600, lineHeight: "14px" }}
      >
        地量 {ratio.toFixed(1)}x
      </span>
    );
  }
  if (ratio <= 0.8) {
    return (
      <span
        title={`量比: ${(ratio * 100).toFixed(0)}% (对比5日均值)`}
        style={{ fontSize: "10px", padding: "0 4px", borderRadius: 2, background: hexToRgba(mutedColor, 0.15), color: secondaryColor, fontWeight: 500, lineHeight: "14px" }}
      >
        缩量 {ratio.toFixed(1)}x
      </span>
    );
  }
  return (
    <span
      title={`量比: ${(ratio * 100).toFixed(0)}% (对比5日均值)`}
      style={{ fontSize: "10px", padding: "0 3px", borderRadius: 2, color: mutedColor, lineHeight: "14px" }}
    >
      平量
    </span>
  );
}

export default function KlineChart({
  data,
  height = 500,
  viewKey = "default",
  tradeMarkers = [],
  chanlun = null,
  onReachLeftEdge,
  historyLimitReached = false,
  showHighLowMarkers = true,
  defaultSubIndicator = "VOL",
  defaultCandleStyle = "solid",
  chipDistribution,
  defaultShowChipPeak = false,
  landscapeToolbar,
}: Props) {
  const c = useColors();
  const colorsRef = useRef(c);
  colorsRef.current = c;
  const wrapperRef = useRef<HTMLDivElement>(null);
  const chartElRef = useRef<HTMLDivElement>(null);
  const brushRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const maSeriesMapRef = useRef<Map<string, ISeriesApi<"Line">>>(new Map());
  const mavolSeriesMapRef = useRef<Map<string, ISeriesApi<"Line">>>(new Map());
  const bollSeriesRef = useRef<{ mid?: ISeriesApi<"Line">; upper?: ISeriesApi<"Line">; lower?: ISeriesApi<"Line"> }>({});
  const macdSeriesRef = useRef<{ bar?: ISeriesApi<"Histogram">; dif?: ISeriesApi<"Line">; dea?: ISeriesApi<"Line"> }>({});
  const kdjSeriesRef = useRef<{ k?: ISeriesApi<"Line">; d?: ISeriesApi<"Line">; j?: ISeriesApi<"Line"> }>({});
  const rsiSeriesRef = useRef<{ rsi6?: ISeriesApi<"Line">; rsi12?: ISeriesApi<"Line">; rsi24?: ISeriesApi<"Line"> }>({});
  const tradeMarkersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const chanlunSeriesRef = useRef<ISeriesApi<"Line">[]>([]);
  const fittedViewKeyRef = useRef<string | null>(null);
  const onReachLeftEdgeRef = useRef(onReachLeftEdge);
  onReachLeftEdgeRef.current = onReachLeftEdge;
  const leftEdgePendingRef = useRef(false);
  const historyLimitRef = useRef(historyLimitReached);
  historyLimitRef.current = historyLimitReached;
  const anchoredLogicalRangeRef = useRef<{ from: number; to: number; length: number; viewKey: string } | null>(null);
  const rowCountRef = useRef(0);
  const [isZoomed, setIsZoomed] = useState(false);
  const [hoverInfo, setHoverInfo] = useState<HoverCandleInfo | null>(null);
  const [mainOverlay, setMainOverlay] = useState<"MA" | "BOLL" | "NONE">("MA");
  const [subIndicator, setSubIndicator] = useState<SubIndicatorType>(defaultSubIndicator);
  const [candleStyle, setCandleStyle] = useState<CandleStyleType>(defaultCandleStyle);
  const [isLandscape, setIsLandscape] = useState(false);
  const [isRotated, setIsRotated] = useState(false);
  const [showChipPeak, setShowChipPeak] = useState(defaultShowChipPeak);
  const chipPriceLineRef = useRef<IPriceLine | null>(null);

  const toggleLandscape = useCallback(async () => {
    if (!isLandscape) {
      setIsLandscape(true);
      try {
        if (wrapperRef.current && !document.fullscreenElement && wrapperRef.current.requestFullscreen) {
          await wrapperRef.current.requestFullscreen().catch(() => {});
        }
        const scrOrientation = typeof window !== "undefined" ? window.screen?.orientation : undefined;
        if (scrOrientation && "lock" in scrOrientation && typeof (scrOrientation as unknown as { lock: (dir: string) => Promise<void> }).lock === "function") {
          await (scrOrientation as unknown as { lock: (dir: string) => Promise<void> }).lock("landscape").catch(() => {});
        }
      } catch {
        // 优雅降级使用 CSS 沉浸式横屏
      }
    } else {
      setIsLandscape(false);
      setIsRotated(false);
      try {
        if (document.fullscreenElement && document.exitFullscreen) {
          await document.exitFullscreen().catch(() => {});
        }
        const scrOrientation = typeof window !== "undefined" ? window.screen?.orientation : undefined;
        if (scrOrientation && "unlock" in scrOrientation && typeof (scrOrientation as unknown as { unlock: () => void }).unlock === "function") {
          (scrOrientation as unknown as { unlock: () => void }).unlock();
        }
      } catch {
        // ignore
      }
    }
  }, [isLandscape]);

  useEffect(() => {
    const onFullscreenChange = () => {
      if (!document.fullscreenElement && isLandscape) {
        setIsLandscape(false);
        setIsRotated(false);
      }
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", onFullscreenChange);
    };
  }, [isLandscape]);

  // 侧边迷你同花顺 CYQ 筹码分布降采样
  const sortedHistogramSlice = useMemo(() => {
    if (!chipDistribution?.histogram?.length) return [];
    const sorted = [...chipDistribution.histogram].sort((a, b) => b.price - a.price);
    const step = Math.max(1, Math.floor(sorted.length / 24));
    const sampled = [];
    for (let i = 0; i < sorted.length; i += step) {
      sampled.push(sorted[i]);
    }
    return sampled;
  }, [chipDistribution]);

  const maxChipRatio = useMemo(() => {
    if (!sortedHistogramSlice.length) return 1;
    return Math.max(...sortedHistogramSlice.map((item) => item.ratio), 0.001);
  }, [sortedHistogramSlice]);

  const hudRef = useRef<HTMLDivElement>(null);
  const [paneRatio, setPaneRatio] = useState<number>(PRICE_PANE_RATIO);
  const [pane0Height, setPane0Height] = useState<number>(() => Math.floor((height - 32) * PRICE_PANE_RATIO));
  const [rightScaleWidth, setRightScaleWidth] = useState<number>(58);

  const updateLayoutMetrics = () => {
    const chart = chartRef.current;
    if (!chart) return;
    try {
      const h = chart.panes()[0]?.getHeight?.();
      if (h && h > 0) setPane0Height(h);
      const w = chart.priceScale("right", 0)?.width?.();
      if (w && w > 0) setRightScaleWidth(w);
    } catch {
      // ignore
    }
  };

  const handleSeparatorMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    const startY = e.clientY;
    const startRatio = paneRatio;
    const chart = chartRef.current;
    if (!chart) return;
    const hudHeight = hudRef.current?.clientHeight ?? 32;
    const plotHeight = Math.max(100, height - hudHeight);

    const onMouseMove = (moveEvent: MouseEvent) => {
      const deltaY = moveEvent.clientY - startY;
      const deltaRatio = deltaY / plotHeight;
      const newRatio = Math.max(0.4, Math.min(0.85, startRatio + deltaRatio));
      setPaneRatio(newRatio);
      applyVolumePaneLayout(chart, newRatio);
      try {
        const h = chart.panes()[0]?.getHeight?.();
        if (h && h > 0) setPane0Height(h);
      } catch {
        // ignore
      }
    };

    const onMouseUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  };

  const rows = useMemo<ChartItem[]>(
    () => data
      .map((item) => {
        const date = toBusinessDay(item.date);
        return date ? { ...item, date, rawDate: item.date } : null;
      })
      .filter((item): item is ChartItem => item !== null),
    [data]
  );
  rowCountRef.current = rows.length;
  const rowsRef = useRef<ChartItem[]>(rows);
  rowsRef.current = rows;

  const showHighLowMarkersRef = useRef(showHighLowMarkers);
  showHighLowMarkersRef.current = showHighLowMarkers;
  const baseMarkersRef = useRef<SeriesMarker<Time>[]>([]);

  const updateHighLowMarkers = useCallback((logicalRange?: { from: number; to: number } | null) => {
    if (!tradeMarkersRef.current) return;
    const currentRows = rowsRef.current;
    if (!showHighLowMarkersRef.current || currentRows.length === 0) {
      tradeMarkersRef.current.setMarkers(baseMarkersRef.current);
      return;
    }

    const chart = chartRef.current;
    let range = logicalRange ?? chart?.timeScale().getVisibleLogicalRange?.() ?? null;
    if (!range && currentRows.length > 0) {
      const count = Math.min(80, currentRows.length);
      range = { from: currentRows.length - count, to: currentRows.length + 2 };
    }
    if (!range) {
      tradeMarkersRef.current.setMarkers(baseMarkersRef.current);
      return;
    }

    const startIdx = Math.max(0, Math.min(currentRows.length - 1, Math.floor(range.from)));
    const endIdx = Math.max(0, Math.min(currentRows.length - 1, Math.ceil(range.to)));
    if (startIdx > endIdx) {
      tradeMarkersRef.current.setMarkers(baseMarkersRef.current);
      return;
    }

    let maxItem: ChartItem = currentRows[startIdx];
    let minItem: ChartItem = currentRows[startIdx];
    for (let i = startIdx + 1; i <= endIdx; i++) {
      const item = currentRows[i];
      if (item.high > maxItem.high) {
        maxItem = item;
      }
      if (item.low < minItem.low) {
        minItem = item;
      }
    }

    const highLowMarkers: SeriesMarker<Time>[] = [];
    const colors = colorsRef.current;
    if (maxItem) {
      highLowMarkers.push({
        time: maxItem.date,
        position: "aboveBar",
        shape: "arrowDown",
        color: colors.up,
        text: `高 ${maxItem.high.toFixed(2)}`,
        size: 1,
      });
    }
    if (minItem && (minItem !== maxItem || minItem.low !== maxItem.high)) {
      highLowMarkers.push({
        time: minItem.date,
        position: "belowBar",
        shape: "arrowUp",
        color: colors.down,
        text: `低 ${minItem.low.toFixed(2)}`,
        size: 1,
      });
    }

    const timeKey = (time: Time) => {
      const day = time as BusinessDay;
      return `${day.year ?? 0}-${String(day.month ?? 0).padStart(2, "0")}-${String(day.day ?? 0).padStart(2, "0")}`;
    };

    const combined = [...baseMarkersRef.current, ...highLowMarkers].sort((a, b) => {
      const ka = timeKey(a.time);
      const kb = timeKey(b.time);
      if (ka !== kb) return ka < kb ? -1 : 1;
      return (a.position || "").localeCompare(b.position || "");
    });
    tradeMarkersRef.current.setMarkers(combined);
  }, []);

  const updateHighLowMarkersRef = useRef(updateHighLowMarkers);
  updateHighLowMarkersRef.current = updateHighLowMarkers;

  // Precompute MA & MAVOL & BOLL maps for fast crosshair lookup
  const calculations = useMemo(() => {
    const maMaps = new Map<string, Map<string, number>>();
    for (const cfg of MA_CONFIGS) {
      const maPoints = calculateMA(rows, cfg.period);
      const dateMap = new Map<string, number>();
      for (const pt of maPoints) {
        const d = pt.time as BusinessDay;
        const key = `${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`;
        dateMap.set(key, pt.value);
      }
      maMaps.set(cfg.key, dateMap);
    }

    const mavolMaps = new Map<string, Map<string, number>>();
    for (const cfg of MAVOL_CONFIGS) {
      const volPoints = calculateMAVOL(rows, cfg.period, "volume");
      const dateMap = new Map<string, number>();
      for (const pt of volPoints) {
        const d = pt.time as BusinessDay;
        const key = `${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`;
        dateMap.set(key, pt.value);
      }
      mavolMaps.set(cfg.key, dateMap);
    }

    const maamoMaps = new Map<string, Map<string, number>>();
    for (const cfg of MAVOL_CONFIGS) {
      const amoPoints = calculateMAVOL(rows, cfg.period, "amount");
      const dateMap = new Map<string, number>();
      for (const pt of amoPoints) {
        const d = pt.time as BusinessDay;
        const key = `${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`;
        dateMap.set(key, pt.value);
      }
      maamoMaps.set(cfg.key, dateMap);
    }

    const boll = calculateBOLL(rows);
    const bollMidMap = new Map<string, number>();
    const bollUpMap = new Map<string, number>();
    const bollDnMap = new Map<string, number>();
    for (const pt of boll.mid) {
      const d = pt.time as BusinessDay;
      bollMidMap.set(`${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`, pt.value);
    }
    for (const pt of boll.upper) {
      const d = pt.time as BusinessDay;
      bollUpMap.set(`${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`, pt.value);
    }
    for (const pt of boll.lower) {
      const d = pt.time as BusinessDay;
      bollDnMap.set(`${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`, pt.value);
    }

    const macd = calculateMACD(rows);
    const difMap = new Map<string, number>();
    const deaMap = new Map<string, number>();
    const macdMap = new Map<string, number>();
    for (const pt of macd.dif) {
      const d = pt.time as BusinessDay;
      difMap.set(`${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`, pt.value);
    }
    for (const pt of macd.dea) {
      const d = pt.time as BusinessDay;
      deaMap.set(`${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`, pt.value);
    }
    for (const pt of macd.macd) {
      const d = pt.time as BusinessDay;
      macdMap.set(`${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`, pt.value);
    }

    const kdj = calculateKDJ(rows);
    const kMap = new Map<string, number>();
    const dMap = new Map<string, number>();
    const jMap = new Map<string, number>();
    for (const pt of kdj.k) {
      const d = pt.time as BusinessDay;
      kMap.set(`${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`, pt.value);
    }
    for (const pt of kdj.d) {
      const d = pt.time as BusinessDay;
      dMap.set(`${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`, pt.value);
    }
    for (const pt of kdj.j) {
      const d = pt.time as BusinessDay;
      jMap.set(`${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`, pt.value);
    }

    const rsi = calculateRSI(rows);
    const rsi6Map = new Map<string, number>();
    const rsi12Map = new Map<string, number>();
    const rsi24Map = new Map<string, number>();
    for (const pt of rsi.rsi6) {
      const d = pt.time as BusinessDay;
      rsi6Map.set(`${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`, pt.value);
    }
    for (const pt of rsi.rsi12) {
      const d = pt.time as BusinessDay;
      rsi12Map.set(`${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`, pt.value);
    }
    for (const pt of rsi.rsi24) {
      const d = pt.time as BusinessDay;
      rsi24Map.set(`${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`, pt.value);
    }

    const rowMap = new Map<string, { row: ChartItem; prevClose: number | null; changePct: number | null }>();
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      const prev = i > 0 ? rows[i - 1] : null;
      const prevClose = prev ? prev.close : null;
      const changePct = row.change_pct ?? (prevClose && prevClose > 0 ? ((row.close - prevClose) / prevClose) * 100 : null);
      const key = `${row.date.year}-${String(row.date.month).padStart(2, "0")}-${String(row.date.day).padStart(2, "0")}`;
      rowMap.set(key, { row, prevClose, changePct });
    }

    return {
      maMaps, mavolMaps, maamoMaps, boll, bollMidMap, bollUpMap, bollDnMap,
      macd, difMap, deaMap, macdMap,
      kdj, kMap, dMap, jMap,
      rsi, rsi6Map, rsi12Map, rsi24Map,
      rowMap,
    };
  }, [rows]);

  // 建图只依赖 height；指标计算结果通过 ref 读取，避免数据变化时销毁重建整张图。
  const calculationsRef = useRef(calculations);
  calculationsRef.current = calculations;

  const latestInfo = useMemo<HoverCandleInfo | null>(() => {
    if (rows.length === 0) return null;
    const last = rows[rows.length - 1];
    const prev = rows.length > 1 ? rows[rows.length - 2] : null;
    const changePct = last.change_pct ?? (prev && prev.close > 0 ? ((last.close - prev.close) / prev.close) * 100 : null);
    const dateKey = `${last.date.year}-${String(last.date.month).padStart(2, "0")}-${String(last.date.day).padStart(2, "0")}`;
    return {
      dateStr: last.rawDate,
      open: last.open,
      high: last.high,
      low: last.low,
      close: last.close,
      changePct,
      amount: last.amount ?? null,
      volume: last.volume ?? null,
      turnoverPct: last.turnover_pct ?? null,
      amplitude: last.amplitude ?? null,
      ma5: calculations.maMaps.get("ma5")?.get(dateKey) ?? null,
      ma10: calculations.maMaps.get("ma10")?.get(dateKey) ?? null,
      ma20: calculations.maMaps.get("ma20")?.get(dateKey) ?? null,
      ma30: calculations.maMaps.get("ma30")?.get(dateKey) ?? null,
      ma60: calculations.maMaps.get("ma60")?.get(dateKey) ?? null,
      vol5: calculations.mavolMaps.get("vol5")?.get(dateKey) ?? null,
      vol10: calculations.mavolMaps.get("vol10")?.get(dateKey) ?? null,
      amo5: calculations.maamoMaps.get("vol5")?.get(dateKey) ?? null,
      amo10: calculations.maamoMaps.get("vol10")?.get(dateKey) ?? null,
      bollMid: calculations.bollMidMap.get(dateKey) ?? null,
      bollUp: calculations.bollUpMap.get(dateKey) ?? null,
      bollDn: calculations.bollDnMap.get(dateKey) ?? null,
      dif: calculations.difMap.get(dateKey) ?? null,
      dea: calculations.deaMap.get(dateKey) ?? null,
      macd: calculations.macdMap.get(dateKey) ?? null,
      k: calculations.kMap.get(dateKey) ?? null,
      d: calculations.dMap.get(dateKey) ?? null,
      j: calculations.jMap.get(dateKey) ?? null,
      rsi6: calculations.rsi6Map.get(dateKey) ?? null,
      rsi12: calculations.rsi12Map.get(dateKey) ?? null,
      rsi24: calculations.rsi24Map.get(dateKey) ?? null,
    };
  }, [rows, calculations]);

  const activeCandle = hoverInfo ?? latestInfo;

  const selectedIndexRef = useRef<number | null>(null);

  const handleRangeSelect = (range: "1M" | "3M" | "1Y" | "ALL") => {
    const chart = chartRef.current;
    if (!chart || rows.length === 0) return;
    if (range === "ALL") {
      chart.timeScale().fitContent();
      setIsZoomed(false);
      return;
    }
    const barsCount = range === "1M" ? 22 : range === "3M" ? 66 : 250;
    const from = Math.max(0, rows.length - barsCount);
    const to = rows.length + 2;
    chart.timeScale().setVisibleLogicalRange({ from, to });
    setIsZoomed(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (rows.length === 0) return;
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      const currentIdx = selectedIndexRef.current ?? (rows.length - 1);
      const nextIdx = e.key === "ArrowLeft"
        ? Math.max(0, currentIdx - 1)
        : Math.min(rows.length - 1, currentIdx + 1);
      selectedIndexRef.current = nextIdx;
      const target = rows[nextIdx];
      const prev = nextIdx > 0 ? rows[nextIdx - 1] : null;
      const changePct = target.change_pct ?? (prev && prev.close > 0 ? ((target.close - prev.close) / prev.close) * 100 : null);
      const dateKey = `${target.date.year}-${String(target.date.month).padStart(2, "0")}-${String(target.date.day).padStart(2, "0")}`;
      setHoverInfo({
        dateStr: target.rawDate,
        open: target.open,
        high: target.high,
        low: target.low,
        close: target.close,
        changePct,
        amount: target.amount ?? null,
        volume: target.volume ?? null,
        turnoverPct: target.turnover_pct ?? null,
        amplitude: target.amplitude ?? null,
        ma5: calculations.maMaps.get("ma5")?.get(dateKey) ?? null,
        ma10: calculations.maMaps.get("ma10")?.get(dateKey) ?? null,
        ma20: calculations.maMaps.get("ma20")?.get(dateKey) ?? null,
        ma30: calculations.maMaps.get("ma30")?.get(dateKey) ?? null,
        ma60: calculations.maMaps.get("ma60")?.get(dateKey) ?? null,
        vol5: calculations.mavolMaps.get("vol5")?.get(dateKey) ?? null,
        vol10: calculations.mavolMaps.get("vol10")?.get(dateKey) ?? null,
        amo5: calculations.maamoMaps.get("vol5")?.get(dateKey) ?? null,
        amo10: calculations.maamoMaps.get("vol10")?.get(dateKey) ?? null,
        bollMid: calculations.bollMidMap.get(dateKey) ?? null,
        bollUp: calculations.bollUpMap.get(dateKey) ?? null,
        bollDn: calculations.bollDnMap.get(dateKey) ?? null,
        dif: calculations.difMap.get(dateKey) ?? null,
        dea: calculations.deaMap.get(dateKey) ?? null,
        macd: calculations.macdMap.get(dateKey) ?? null,
        k: calculations.kMap.get(dateKey) ?? null,
        d: calculations.dMap.get(dateKey) ?? null,
        j: calculations.jMap.get(dateKey) ?? null,
        rsi6: calculations.rsi6Map.get(dateKey) ?? null,
        rsi12: calculations.rsi12Map.get(dateKey) ?? null,
        rsi24: calculations.rsi24Map.get(dateKey) ?? null,
      });
    } else if (e.key === "Escape") {
      if (isLandscape) {
        e.preventDefault();
        toggleLandscape();
        return;
      }
      selectedIndexRef.current = null;
      setHoverInfo(null);
    }
  };

  useEffect(() => {
    if (!wrapperRef.current || !chartElRef.current || !brushRef.current) return;
    chartRef.current?.remove();
    const colors = colorsRef.current;

    const initialHudHeight = hudRef.current?.clientHeight || 32;
    const chart = createChart(chartElRef.current, {
      width: chartElRef.current.clientWidth,
      height: Math.max(100, height - initialHudHeight),
      layout: {
        background: { type: ColorType.Solid, color: colors.cardBg },
        textColor: colors.textSecondary,
        fontFamily: APP_FONT_FAMILY,
        fontSize: APP_FONT_SIZE.sm,
        attributionLogo: false,
        panes: getChartPaneThemeConfig(colors).panes,
      },
      grid: getChartPaneThemeConfig(colors).grid,
      timeScale: { timeVisible: false, borderColor: colors.border },
      // 价格与成交量各自独立窗格、各自独立量纲，两条轴都放右侧（同花顺/通达信布局）。
      // 左侧轴必须整体关闭：lightweight-charts 5.2.1 判断要不要画轴时只读 0 号窗格的
      // visible，却对所有窗格 ensureNotNull(轴 widget)，单独隐藏非 0 窗格的轴会让每帧
      // draw 抛 "Value is null"，整张图不渲染。
      rightPriceScale: { visible: true, borderColor: colors.border },
      leftPriceScale: { visible: false, borderColor: colors.border },
      crosshair: {
        vertLine: { color: colors.textMuted, labelBackgroundColor: colors.border },
        horzLine: { color: colors.textMuted, labelBackgroundColor: colors.border },
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
      kineticScroll: { touch: true, mouse: false },
      trackingMode: { exitMode: 0 },
    });
    chartRef.current = chart;
    fittedViewKeyRef.current = null;

    const candle = chart.addSeries(CandlestickSeries, {
      upColor: colors.up, downColor: colors.down,
      borderUpColor: colors.up, borderDownColor: colors.down,
      wickUpColor: colors.up, wickDownColor: colors.down,
      priceScaleId: "right",
    });
    candleSeriesRef.current = candle;
    tradeMarkersRef.current = createSeriesMarkers(candle, []);
    chart.priceScale("right", 0).applyOptions({
      borderColor: colors.border,
      scaleMargins: { top: 0.08, bottom: 0.12 },
    });

    // 成交量放到独立的下窗格：与价格量纲差几个数量级，共享一个绘图区会被压成一条线
    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "custom", minMove: 1,
        formatter: (value: number) => Math.abs(value) >= 1e8
          ? `${(value / 1e8).toFixed(2)}亿` : `${(value / 1e4).toFixed(2)}万`,
      },
      priceScaleId: "right",
    }, VOLUME_PANE_INDEX);
    volumeSeriesRef.current = volume;
    chart.priceScale("right", VOLUME_PANE_INDEX).applyOptions({
      borderColor: colors.border,
      scaleMargins: { top: 0.18, bottom: 0 },
    });
    applyVolumePaneLayout(chart, paneRatio);
    updateLayoutMetrics();

    // Initialize MA Line Series
    const maMap = new Map<string, ISeriesApi<"Line">>();
    for (const cfg of MA_CONFIGS) {
      const maLine = chart.addSeries(LineSeries, {
        color: cfg.color,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        priceScaleId: "right",
      });
      maMap.set(cfg.key, maLine);
    }
    maSeriesMapRef.current = maMap;

    // Initialize MAVOL Line Series
    const mavolMap = new Map<string, ISeriesApi<"Line">>();
    for (const cfg of MAVOL_CONFIGS) {
      const volLine = chart.addSeries(LineSeries, {
        color: cfg.color,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        priceScaleId: "right",
      }, VOLUME_PANE_INDEX);
      mavolMap.set(cfg.key, volLine);
    }
    mavolSeriesMapRef.current = mavolMap;

    // Initialize BOLL Series
    const bollMid = chart.addSeries(LineSeries, {
      color: "#f0b90b", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, priceScaleId: "right",
    });
    const bollUp = chart.addSeries(LineSeries, {
      color: "#ff7a45", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, priceScaleId: "right",
    });
    const bollDn = chart.addSeries(LineSeries, {
      color: "#9254de", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, priceScaleId: "right",
    });
    bollSeriesRef.current = { mid: bollMid, upper: bollUp, lower: bollDn };

    // Initialize MACD Series (Pane 1)
    const macdBar = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      priceScaleId: "right",
    }, VOLUME_PANE_INDEX);
    const macdDif = chart.addSeries(LineSeries, {
      color: "#f0b90b", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, priceScaleId: "right",
    }, VOLUME_PANE_INDEX);
    const macdDea = chart.addSeries(LineSeries, {
      color: "#e879f9", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, priceScaleId: "right",
    }, VOLUME_PANE_INDEX);
    macdSeriesRef.current = { bar: macdBar, dif: macdDif, dea: macdDea };

    // Initialize KDJ Series (Pane 1)
    const kdjK = chart.addSeries(LineSeries, {
      color: "#f0b90b", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, priceScaleId: "right",
    }, VOLUME_PANE_INDEX);
    const kdjD = chart.addSeries(LineSeries, {
      color: "#38bdf8", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, priceScaleId: "right",
    }, VOLUME_PANE_INDEX);
    const kdjJ = chart.addSeries(LineSeries, {
      color: "#d946ef", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, priceScaleId: "right",
    }, VOLUME_PANE_INDEX);
    kdjSeriesRef.current = { k: kdjK, d: kdjD, j: kdjJ };

    // Initialize RSI Series (Pane 1)
    const rsi6 = chart.addSeries(LineSeries, {
      color: "#f0b90b", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, priceScaleId: "right",
    }, VOLUME_PANE_INDEX);
    const rsi12 = chart.addSeries(LineSeries, {
      color: "#38bdf8", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, priceScaleId: "right",
    }, VOLUME_PANE_INDEX);
    const rsi24 = chart.addSeries(LineSeries, {
      color: "#c084fc", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, priceScaleId: "right",
    }, VOLUME_PANE_INDEX);
    rsiSeriesRef.current = { rsi6, rsi12, rsi24 };

    const wrapper = wrapperRef.current;
    const brush = brushRef.current;
    const resizeObserver = new ResizeObserver(
      createDebouncedResizeHandler((entry) => {
        const hudHeight = hudRef.current?.clientHeight ?? 32;
        const entryHeight = Math.floor(entry.contentRect.height);
        const plotHeight = entryHeight > 0 ? entryHeight : Math.max(100, height - hudHeight);
        chart.applyOptions({ width: Math.floor(entry.contentRect.width), height: plotHeight });
        applyVolumePaneLayout(chart, paneRatio);
        updateLayoutMetrics();
      })
    );
    resizeObserver.observe(chartElRef.current);
    let startX: number | null = null;

    const resetBrush = () => { brush.style.display = "none"; brush.style.left = "0px"; brush.style.width = "0px"; };

    const handleMouseDown = (event: MouseEvent) => {
      if (event.button !== 0 || !event.shiftKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("button")) return;
      event.preventDefault();
      const rect = wrapper.getBoundingClientRect();
      startX = Math.max(0, Math.min(event.clientX - rect.left, rect.width));
      brush.style.display = "block";
      brush.style.left = `${startX}px`;
      brush.style.width = "0px";
      wrapper.style.cursor = "crosshair";
    };

    const handleMouseMove = (event: MouseEvent) => {
      if (startX == null) return;
      const rect = wrapper.getBoundingClientRect();
      const currentX = Math.max(0, Math.min(event.clientX - rect.left, rect.width));
      brush.style.left = `${Math.min(startX, currentX)}px`;
      brush.style.width = `${Math.abs(currentX - startX)}px`;
    };

    const handleMouseUp = (event: MouseEvent) => {
      if (startX == null) return;
      const rect = wrapper.getBoundingClientRect();
      const endX = Math.max(0, Math.min(event.clientX - rect.left, rect.width));
      const from = Math.min(startX, endX);
      const to = Math.max(startX, endX);
      startX = null;
      resetBrush();
      wrapper.style.cursor = "default";
      if (to - from < 8) return;
      const logicalFrom = chart.timeScale().coordinateToLogical(from);
      const logicalTo = chart.timeScale().coordinateToLogical(to);
      if (logicalFrom == null || logicalTo == null) return;
      chart.timeScale().setVisibleLogicalRange({ from: Math.min(logicalFrom, logicalTo), to: Math.max(logicalFrom, logicalTo) });
      setIsZoomed(true);
    };

    const handleMouseLeave = () => {
      startX = null;
      resetBrush();
      wrapper.style.cursor = "default";
    };
    const handleDoubleClick = () => {
      chart.timeScale().fitContent();
      setIsZoomed(false);
    };

    const handleKeyDownWindow = (event: KeyboardEvent) => {
      if (event.key === "Shift") {
        wrapper.style.cursor = "crosshair";
      }
    };
    const handleKeyUpWindow = (event: KeyboardEvent) => {
      if (event.key === "Shift" && startX == null) {
        wrapper.style.cursor = "default";
      }
    };
    window.addEventListener("keydown", handleKeyDownWindow);
    window.addEventListener("keyup", handleKeyUpWindow);

    const handleCrosshairMove = (param: MouseEventParams<Time>) => {
      if (!param.time || !param.seriesData) {
        if (selectedIndexRef.current === null) {
          setHoverInfo(null);
        }
        return;
      }
      selectedIndexRef.current = null;
      const cData = param.seriesData.get(candle) as CandlestickData<BusinessDay> | undefined;
      const vData = param.seriesData.get(volume) as { value?: number } | undefined;
      if (cData && typeof param.time === "object" && param.time !== null && "year" in param.time) {
        const day = param.time as BusinessDay;
        const dateKey = `${day.year}-${String(day.month).padStart(2, "0")}-${String(day.day).padStart(2, "0")}`;
        const rowInfo = calculationsRef.current.rowMap?.get(dateKey);
        const changePct = rowInfo?.changePct ?? (cData.open > 0 ? ((cData.close - cData.open) / cData.open) * 100 : null);
        const amount = rowInfo?.row.amount ?? vData?.value ?? null;
        const volume = rowInfo?.row.volume ?? null;
        const turnoverPct = rowInfo?.row.turnover_pct ?? null;
        const amplitude = rowInfo?.row.amplitude ?? null;
        setHoverInfo({
          dateStr: rowInfo?.row.rawDate ?? dateKey,
          open: cData.open,
          high: cData.high,
          low: cData.low,
          close: cData.close,
          changePct,
          amount,
          volume,
          turnoverPct,
          amplitude,
          ma5: calculationsRef.current.maMaps.get("ma5")?.get(dateKey) ?? null,
          ma10: calculationsRef.current.maMaps.get("ma10")?.get(dateKey) ?? null,
          ma20: calculationsRef.current.maMaps.get("ma20")?.get(dateKey) ?? null,
          ma30: calculationsRef.current.maMaps.get("ma30")?.get(dateKey) ?? null,
          ma60: calculationsRef.current.maMaps.get("ma60")?.get(dateKey) ?? null,
          vol5: calculationsRef.current.mavolMaps.get("vol5")?.get(dateKey) ?? null,
          vol10: calculationsRef.current.mavolMaps.get("vol10")?.get(dateKey) ?? null,
          amo5: calculationsRef.current.maamoMaps.get("vol5")?.get(dateKey) ?? null,
          amo10: calculationsRef.current.maamoMaps.get("vol10")?.get(dateKey) ?? null,
          bollMid: calculationsRef.current.bollMidMap.get(dateKey) ?? null,
          bollUp: calculationsRef.current.bollUpMap.get(dateKey) ?? null,
          bollDn: calculationsRef.current.bollDnMap.get(dateKey) ?? null,
          dif: calculationsRef.current.difMap.get(dateKey) ?? null,
          dea: calculationsRef.current.deaMap.get(dateKey) ?? null,
          macd: calculationsRef.current.macdMap.get(dateKey) ?? null,
          k: calculationsRef.current.kMap.get(dateKey) ?? null,
          d: calculationsRef.current.dMap.get(dateKey) ?? null,
          j: calculationsRef.current.jMap.get(dateKey) ?? null,
          rsi6: calculationsRef.current.rsi6Map.get(dateKey) ?? null,
          rsi12: calculationsRef.current.rsi12Map.get(dateKey) ?? null,
          rsi24: calculationsRef.current.rsi24Map.get(dateKey) ?? null,
        });
      }
    };

    chart.subscribeCrosshairMove(handleCrosshairMove);

    // 左缘触底：用户滚动/拖拽到最早一根 K 线时，向外层请求更早的数据。
    // 用 ref 记录触底前的逻辑区间，数据补齐后按新增条数平移，保持视窗不跳。
    const handleVisibleRangeChange = (range: { from: number; to: number } | null) => {
      updateHighLowMarkersRef.current(range);

      if (!range || historyLimitRef.current) {
        leftEdgePendingRef.current = false;
        return;
      }
      if (range.from > LEFT_EDGE_TRIGGER_INDEX) {
        leftEdgePendingRef.current = false;
        return;
      }
      if (leftEdgePendingRef.current) return;
      leftEdgePendingRef.current = true;
      anchoredLogicalRangeRef.current = {
        from: range.from,
        to: range.to,
        length: rowCountRef.current,
        viewKey,
      };
      onReachLeftEdgeRef.current?.();
    };
    chart.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleRangeChange);

    wrapper.addEventListener("mousedown", handleMouseDown);
    wrapper.addEventListener("mousemove", handleMouseMove);
    wrapper.addEventListener("mouseup", handleMouseUp);
    wrapper.addEventListener("mouseleave", handleMouseLeave);
    wrapper.addEventListener("dblclick", handleDoubleClick);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("keydown", handleKeyDownWindow);
      window.removeEventListener("keyup", handleKeyUpWindow);
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange);
      wrapper.removeEventListener("mousedown", handleMouseDown);
      wrapper.removeEventListener("mousemove", handleMouseMove);
      wrapper.removeEventListener("mouseup", handleMouseUp);
      wrapper.removeEventListener("mouseleave", handleMouseLeave);
      wrapper.removeEventListener("dblclick", handleDoubleClick);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      maSeriesMapRef.current.clear();
      mavolSeriesMapRef.current.clear();
      bollSeriesRef.current = {};
      macdSeriesRef.current = {};
      kdjSeriesRef.current = {};
      rsiSeriesRef.current = {};
      tradeMarkersRef.current = null;
      chanlunSeriesRef.current = [];
      chipPriceLineRef.current = null;
    };
    // 建图只依赖 height；viewKey 变化由下方数据 effect 负责重置视窗，不应重建图表。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [height]);

  useEffect(() => {
    const chart = chartRef.current;
    const candle = candleSeriesRef.current;
    const volume = volumeSeriesRef.current;
    if (!chart || !candle || !volume) return;

    candle.applyOptions({
      upColor: candleStyle === "hollow" ? c.cardBg : c.up,
      downColor: c.down,
      borderUpColor: c.up,
      borderDownColor: c.down,
      wickUpColor: c.up,
      wickDownColor: c.down,
    });

    candle.setData(rows.map((item) => ({
      time: item.date,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
    })));

    // 同花顺副图切换: VOL / AMO / MACD / KDJ / RSI
    if (subIndicator === "VOL" || subIndicator === "AMO") {
      const isAmo = subIndicator === "AMO";
      chart.priceScale("right", VOLUME_PANE_INDEX).applyOptions({
        scaleMargins: { top: 0.18, bottom: 0 },
      });
      volume.applyOptions({
        priceFormat: {
          type: "custom",
          minMove: 1,
          formatter: (value: number) => (isAmo ? formatAmount(value) : formatVolume(value)),
        },
      });
      volume.setData(rows.map((item, index) => {
        const prevClose = index > 0 ? rows[index - 1].close : null;
        const isUp = item.close > item.open
          ? true
          : item.close < item.open
            ? false
            : prevClose != null
              ? item.close >= prevClose
              : true;
        const val = item.amount ?? item.volume;
        return {
          time: item.date,
          value: val,
          color: isUp ? hexToRgba(c.up, 0.5) : hexToRgba(c.down, 0.5),
        };
      }));
      for (const cfg of MAVOL_CONFIGS) {
        const volLine = mavolSeriesMapRef.current.get(cfg.key);
        if (volLine) {
          const volPoints = calculateMAVOL(rows, cfg.period, "amount");
          volLine.setData(volPoints.map((pt) => ({ time: pt.time as BusinessDay, value: pt.value })));
        }
      }
      macdSeriesRef.current.bar?.setData([]);
      macdSeriesRef.current.dif?.setData([]);
      macdSeriesRef.current.dea?.setData([]);
      kdjSeriesRef.current.k?.setData([]);
      kdjSeriesRef.current.d?.setData([]);
      kdjSeriesRef.current.j?.setData([]);
      rsiSeriesRef.current.rsi6?.setData([]);
      rsiSeriesRef.current.rsi12?.setData([]);
      rsiSeriesRef.current.rsi24?.setData([]);
    } else {
      volume.setData([]);
      for (const cfg of MAVOL_CONFIGS) {
        mavolSeriesMapRef.current.get(cfg.key)?.setData([]);
      }
      chart.priceScale("right", VOLUME_PANE_INDEX).applyOptions({
        scaleMargins: { top: 0.1, bottom: 0.1 },
      });

      if (subIndicator === "MACD") {
        const { macd } = calculations;
        macdSeriesRef.current.bar?.setData(macd.macd.map((pt) => ({
          time: pt.time as BusinessDay,
          value: pt.value,
          color: pt.value >= 0 ? hexToRgba(c.up, 0.75) : hexToRgba(c.down, 0.75),
        })));
        macdSeriesRef.current.dif?.setData(macd.dif.map((pt) => ({ time: pt.time as BusinessDay, value: pt.value })));
        macdSeriesRef.current.dea?.setData(macd.dea.map((pt) => ({ time: pt.time as BusinessDay, value: pt.value })));
        kdjSeriesRef.current.k?.setData([]);
        kdjSeriesRef.current.d?.setData([]);
        kdjSeriesRef.current.j?.setData([]);
        rsiSeriesRef.current.rsi6?.setData([]);
        rsiSeriesRef.current.rsi12?.setData([]);
        rsiSeriesRef.current.rsi24?.setData([]);
      } else if (subIndicator === "KDJ") {
        const { kdj } = calculations;
        macdSeriesRef.current.bar?.setData([]);
        macdSeriesRef.current.dif?.setData([]);
        macdSeriesRef.current.dea?.setData([]);
        kdjSeriesRef.current.k?.setData(kdj.k.map((pt) => ({ time: pt.time as BusinessDay, value: pt.value })));
        kdjSeriesRef.current.d?.setData(kdj.d.map((pt) => ({ time: pt.time as BusinessDay, value: pt.value })));
        kdjSeriesRef.current.j?.setData(kdj.j.map((pt) => ({ time: pt.time as BusinessDay, value: pt.value })));
        rsiSeriesRef.current.rsi6?.setData([]);
        rsiSeriesRef.current.rsi12?.setData([]);
        rsiSeriesRef.current.rsi24?.setData([]);
      } else if (subIndicator === "RSI") {
        const { rsi } = calculations;
        macdSeriesRef.current.bar?.setData([]);
        macdSeriesRef.current.dif?.setData([]);
        macdSeriesRef.current.dea?.setData([]);
        kdjSeriesRef.current.k?.setData([]);
        kdjSeriesRef.current.d?.setData([]);
        kdjSeriesRef.current.j?.setData([]);
        rsiSeriesRef.current.rsi6?.setData(rsi.rsi6.map((pt) => ({ time: pt.time as BusinessDay, value: pt.value })));
        rsiSeriesRef.current.rsi12?.setData(rsi.rsi12.map((pt) => ({ time: pt.time as BusinessDay, value: pt.value })));
        rsiSeriesRef.current.rsi24?.setData(rsi.rsi24.map((pt) => ({ time: pt.time as BusinessDay, value: pt.value })));
      }
    }

    // Set MA Lines Data
    for (const cfg of MA_CONFIGS) {
      const maLine = maSeriesMapRef.current.get(cfg.key);
      if (maLine) {
        if (mainOverlay === "MA") {
          const maPoints = calculateMA(rows, cfg.period);
          maLine.setData(maPoints.map((pt) => ({ time: pt.time as BusinessDay, value: pt.value })));
        } else {
          maLine.setData([]);
        }
      }
    }

    // Set BOLL Data
    const { boll } = calculations;
    if (bollSeriesRef.current.mid && bollSeriesRef.current.upper && bollSeriesRef.current.lower) {
      if (mainOverlay === "BOLL") {
        bollSeriesRef.current.mid.setData(boll.mid.map((pt) => ({ time: pt.time as BusinessDay, value: pt.value })));
        bollSeriesRef.current.upper.setData(boll.upper.map((pt) => ({ time: pt.time as BusinessDay, value: pt.value })));
        bollSeriesRef.current.lower.setData(boll.lower.map((pt) => ({ time: pt.time as BusinessDay, value: pt.value })));
      } else {
        bollSeriesRef.current.mid.setData([]);
        bollSeriesRef.current.upper.setData([]);
        bollSeriesRef.current.lower.setData([]);
      }
    }

    const validDates = new Set(data.map((item) => item.date));
    const tradeMarkerList = buildKlineTradeMarkers(
      tradeMarkers,
      { buy: c.up, sell: c.down },
      validDates,
    );
    const chanlunMarkerList = chanlun
      ? buildChanlunMarkers(chanlun, { up: c.up, down: c.down }, validDates)
      : [];
    baseMarkersRef.current = [...tradeMarkerList, ...chanlunMarkerList];
    updateHighLowMarkers(chart.timeScale().getVisibleLogicalRange?.() ?? null);

    // 历史扩充后按新增条数平移视窗，避免图表跳回首日。
    // 锚点只在同一 viewKey 且数据确实变长时生效；切换标的或数据变短都要丢弃，
    // 否则会用上一只票的行数平移当前视窗。
    const anchor = anchoredLogicalRangeRef.current;
    if (anchor && (anchor.viewKey !== viewKey || rows.length <= anchor.length)) {
      anchoredLogicalRangeRef.current = null;
    }
    const pendingAnchor = anchoredLogicalRangeRef.current;
    if (pendingAnchor && rows.length > pendingAnchor.length) {
      anchoredLogicalRangeRef.current = null;
      const added = rows.length - pendingAnchor.length;
      chart.timeScale().setVisibleLogicalRange({
        from: pendingAnchor.from + added,
        to: pendingAnchor.to + added,
      });
    } else if (rows.length > 0 && shouldFitChartContent(fittedViewKeyRef.current, viewKey)) {
      if (rows.length > 80) {
        chart.timeScale().setVisibleLogicalRange({ from: rows.length - 80, to: rows.length + 2 });
      } else {
        chart.timeScale().fitContent();
      }
      fittedViewKeyRef.current = viewKey;
      setIsZoomed(false);
    }
  }, [c.down, c.up, c.cardBg, candleStyle, subIndicator, data, height, rows, tradeMarkers, viewKey, chanlun, mainOverlay, calculations, showHighLowMarkers, updateHighLowMarkers]);

  // 缠论图层：笔折线 + 中枢上下沿虚线
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    for (const series of chanlunSeriesRef.current) {
      chart.removeSeries(series);
    }
    chanlunSeriesRef.current = [];
    if (!chanlun || chanlun.bis.length === 0) return;

    const baseOptions = {
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      pointMarkersVisible: false,
    };

    const biPoints: { time: BusinessDay; value: number }[] = [];
    const firstTime = toBusinessDay(chanlun.bis[0].start.mid.date);
    if (firstTime) {
      biPoints.push({ time: firstTime, value: chanlun.bis[0].start.val });
    }
    for (const bi of chanlun.bis) {
      const time = toBusinessDay(bi.end.mid.date);
      if (time) biPoints.push({ time, value: bi.end.val });
    }
    if (biPoints.length >= 2) {
      const biSeries = chart.addSeries(LineSeries, {
        color: c.accent, lineWidth: 2, ...baseOptions,
      });
      biSeries.setData(biPoints);
      chanlunSeriesRef.current.push(biSeries);
    }

    for (const zs of chanlun.zss) {
      const startTime = toBusinessDay(zs.startDate);
      const endTime = toBusinessDay(zs.endDate);
      if (!startTime || !endTime) continue;
      for (const value of [zs.zg, zs.zd]) {
        const series = chart.addSeries(LineSeries, {
          color: c.info, lineWidth: 1, lineStyle: LineStyle.Dashed, ...baseOptions,
        });
        series.setData([
          { time: startTime, value },
          { time: endTime, value },
        ]);
        chanlunSeriesRef.current.push(series);
      }
    }
  }, [chanlun, c.accent, c.info, height]);

  // 筹码峰主图水平参考线 (PriceLine)
  useEffect(() => {
    const candle = candleSeriesRef.current;
    if (!candle) return;
    if (chipPriceLineRef.current) {
      try {
        candle.removePriceLine(chipPriceLineRef.current);
      } catch {
        // ignore
      }
      chipPriceLineRef.current = null;
    }
    if (showChipPeak && chipDistribution?.peak_price != null && Number.isFinite(chipDistribution.peak_price)) {
      chipPriceLineRef.current = candle.createPriceLine({
        price: chipDistribution.peak_price,
        color: "#faad14",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: "筹码峰",
      });
    }
    return () => {
      if (chipPriceLineRef.current && candleSeriesRef.current) {
        try {
          candleSeriesRef.current.removePriceLine(chipPriceLineRef.current);
        } catch {
          // ignore
        }
        chipPriceLineRef.current = null;
      }
    };
  }, [showChipPeak, chipDistribution, height]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const paneConfig = getChartPaneThemeConfig(c);
    chart.applyOptions({
      layout: {
        background: { type: ColorType.Solid, color: c.cardBg },
        textColor: c.textSecondary,
        panes: paneConfig.panes,
      },
      grid: paneConfig.grid,
      timeScale: { borderColor: c.border },
      rightPriceScale: { borderColor: c.border },
      leftPriceScale: { borderColor: c.border },
      crosshair: {
        vertLine: { color: c.textMuted, labelBackgroundColor: c.border },
        horzLine: { color: c.textMuted, labelBackgroundColor: c.border },
      },
    });

    candleSeriesRef.current?.applyOptions({
      upColor: candleStyle === "hollow" ? c.cardBg : c.up,
      downColor: c.down,
      borderUpColor: c.up,
      borderDownColor: c.down,
      wickUpColor: c.up,
      wickDownColor: c.down,
    });
    volumeSeriesRef.current?.setData(rows.map((item, index) => {
      const prevClose = index > 0 ? rows[index - 1].close : null;
      const isUp = item.close > item.open
        ? true
        : item.close < item.open
          ? false
          : prevClose != null
            ? item.close >= prevClose
            : true;
      const val = item.amount ?? item.volume;
      return {
        time: item.date,
        value: val,
        color: isUp ? hexToRgba(c.up, 0.5) : hexToRgba(c.down, 0.5),
      };
    }));
    chart.priceScale("right", 0).applyOptions({ borderColor: c.border });
    chart.priceScale("right", VOLUME_PANE_INDEX).applyOptions({ borderColor: c.border });
  }, [c.border, c.cardBg, c.down, c.primary, c.accent, c.isLight, c.textMuted, c.textSecondary, c.up, candleStyle, height, rows]);

  useEffect(() => {
    const chart = chartRef.current;
    const el = chartElRef.current;
    if (!chart || !el) return;
    const timer = setTimeout(() => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        chart.applyOptions({ width: Math.floor(rect.width), height: Math.floor(rect.height) });
        applyVolumePaneLayout(chart, paneRatio);
        updateLayoutMetrics();
      }
    }, 40);
    return () => clearTimeout(timer);
  }, [isLandscape, isRotated, paneRatio]);

  return (
    <div
      ref={wrapperRef}
      tabIndex={0}
      role="region"
      aria-label="K线图交互区"
      title="左键拖拽平移画布，按住 Shift 拖拽框选放大，双击重置全景"
      onKeyDown={handleKeyDown}
      className={`kline-chart ${isLandscape ? "kline-chart--landscape" : ""}`}
      style={
        isLandscape
          ? isRotated
            ? {
                position: "fixed",
                top: 0,
                left: 0,
                width: "100vh",
                height: "100vw",
                transform: "rotate(90deg) translateY(-100%)",
                transformOrigin: "top left",
                zIndex: 2000,
                display: "flex",
                flexDirection: "column",
                backgroundColor: c.cardBg,
                outline: "none",
                overflow: "hidden",
                boxShadow: "0 0 20px rgba(0,0,0,0.5)",
              }
            : {
                position: "fixed",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                width: "100vw",
                height: "100vh",
                zIndex: 2000,
                display: "flex",
                flexDirection: "column",
                backgroundColor: c.cardBg,
                outline: "none",
                overflow: "hidden",
              }
          : {
              position: "relative",
              width: "100%",
              height,
              minHeight: height,
              display: "flex",
              flexDirection: "column",
              backgroundColor: c.cardBg,
              outline: "none",
            }
      }
    >
      {/* Allow wrapped quotes to grow without overlapping the toolbar or plot. */}
      <div ref={hudRef} className="kline-chart__hud" style={{
        minHeight: 32,
        padding: "4px 10px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap",
        rowGap: 4,
        columnGap: 8,
        flexShrink: 0,
        fontSize: "11px",
        color: c.textSecondary,
        backgroundColor: c.nestedBg,
        borderBottom: `1px solid ${c.border}`,
        fontFamily: "var(--c-font-mono)",
        userSelect: "none",
      }}>
        {activeCandle ? (
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "4px 10px",
            flexWrap: "wrap",
            flex: "1 1 auto",
            minWidth: 0,
            lineHeight: 1.4,
          }}>
            <span style={{
              color: c.textPrimary,
              fontWeight: 700,
              minWidth: 80,
              flexShrink: 0,
              paddingRight: 6,
              borderRight: `1px solid ${c.border}`,
              marginRight: 2,
            }}>
              {activeCandle.dateStr}
            </span>
            <span style={{ whiteSpace: "nowrap" }}>开: <strong style={{ color: activeCandle.close >= activeCandle.open ? c.up : c.down }}>{activeCandle.open.toFixed(2)}</strong></span>
            <span style={{ whiteSpace: "nowrap" }}>高: <strong style={{ color: c.up }}>{activeCandle.high.toFixed(2)}</strong></span>
            <span style={{ whiteSpace: "nowrap" }}>低: <strong style={{ color: c.down }}>{activeCandle.low.toFixed(2)}</strong></span>
            <span style={{ whiteSpace: "nowrap" }}>收: <strong style={{ color: activeCandle.close >= activeCandle.open ? c.up : c.down }}>{activeCandle.close.toFixed(2)}</strong></span>
            {activeCandle.changePct != null && (
              <span style={{ whiteSpace: "nowrap", color: activeCandle.changePct >= 0 ? c.up : c.down }}>
                ({activeCandle.changePct >= 0 ? `+${activeCandle.changePct.toFixed(2)}%` : `${activeCandle.changePct.toFixed(2)}%`})
              </span>
            )}
            {activeCandle.volume != null && (
              <span
                style={{ whiteSpace: "nowrap" }}
                title={`成交量: ${activeCandle.volume.toLocaleString("zh-CN")} 股`}
              >
                量: <strong style={{ color: c.textPrimary }}>{formatVolume(activeCandle.volume)}</strong>
              </span>
            )}
            {activeCandle.amount != null && (
              <span
                style={{ whiteSpace: "nowrap" }}
                title={`成交额: ${activeCandle.amount.toLocaleString("zh-CN", { maximumFractionDigits: 2 })} 元`}
              >
                额: <strong style={{ color: c.textPrimary }}>{formatAmount(activeCandle.amount)}</strong>
              </span>
            )}
            {activeCandle.turnoverPct != null && (
              <span style={{ whiteSpace: "nowrap" }}>换: <strong style={{ color: c.textPrimary }}>{activeCandle.turnoverPct.toFixed(2)}%</strong></span>
            )}
            {activeCandle.amplitude != null && (
              <span style={{ whiteSpace: "nowrap" }}>振: <strong style={{ color: c.textPrimary }}>{activeCandle.amplitude.toFixed(2)}%</strong></span>
            )}
            {mainOverlay === "MA" ? (
              <>
                <span style={{ whiteSpace: "nowrap", color: "#f0b90b" }}>MA5: {activeCandle.ma5 != null ? activeCandle.ma5.toFixed(2) : "-"}</span>
                <span style={{ whiteSpace: "nowrap", color: "#1890ff" }}>MA10: {activeCandle.ma10 != null ? activeCandle.ma10.toFixed(2) : "-"}</span>
                <span style={{ whiteSpace: "nowrap", color: "#9254de" }}>MA20: {activeCandle.ma20 != null ? activeCandle.ma20.toFixed(2) : "-"}</span>
                <span style={{ whiteSpace: "nowrap", color: "#13c2c2" }}>MA30: {activeCandle.ma30 != null ? activeCandle.ma30.toFixed(2) : "-"}</span>
                <span style={{ whiteSpace: "nowrap", color: "#ff7a45" }}>MA60: {activeCandle.ma60 != null ? activeCandle.ma60.toFixed(2) : "-"}</span>
              </>
            ) : mainOverlay === "BOLL" ? (
              <>
                <span style={{ whiteSpace: "nowrap", color: "#f0b90b" }}>MID: {activeCandle.bollMid != null ? activeCandle.bollMid.toFixed(2) : "-"}</span>
                <span style={{ whiteSpace: "nowrap", color: "#ff7a45" }}>UP: {activeCandle.bollUp != null ? activeCandle.bollUp.toFixed(2) : "-"}</span>
                <span style={{ whiteSpace: "nowrap", color: "#9254de" }}>DN: {activeCandle.bollDn != null ? activeCandle.bollDn.toFixed(2) : "-"}</span>
              </>
            ) : null}
            {showChipPeak && chipDistribution?.peak_price != null && (
              <>
                <span style={{ whiteSpace: "nowrap", color: "#faad14" }}>
                  筹码峰: {chipDistribution.peak_price.toFixed(2)}
                </span>
                {chipDistribution.profit_ratio != null && (
                  <span style={{ whiteSpace: "nowrap", color: c.textMuted }}>
                    获利盘: <strong style={{ color: chipDistribution.profit_ratio >= 0.5 ? c.up : c.down }}>{(chipDistribution.profit_ratio * 100).toFixed(1)}%</strong>
                  </span>
                )}
              </>
            )}
          </div>
        ) : (
          <span>等待K线数据...</span>
        )}

        {/* Range & Overlay controls */}
        <div className="kline-chart__hud-controls" style={{ display: "flex", alignItems: "center", gap: 4, flex: "0 0 auto", marginLeft: "auto", flexWrap: "wrap" }}>
          <button
            type="button"
            className="kline-chart__hud-btn"
            onClick={() => handleRangeSelect("1M")}
            title="查看近1月 (约22根K线)"
            style={{
              padding: "1px 6px",
              fontSize: "11px",
              borderRadius: 4,
              border: `1px solid ${c.border}`,
              background: "transparent",
              color: c.textSecondary,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            1月
          </button>
          <button
            type="button"
            className="kline-chart__hud-btn"
            onClick={() => handleRangeSelect("3M")}
            title="查看近3月 (约66根K线)"
            style={{
              padding: "1px 6px",
              fontSize: "11px",
              borderRadius: 4,
              border: `1px solid ${c.border}`,
              background: "transparent",
              color: c.textSecondary,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            3月
          </button>
          <button
            type="button"
            className="kline-chart__hud-btn"
            onClick={() => handleRangeSelect("1Y")}
            title="查看近1年 (约250根K线)"
            style={{
              padding: "1px 6px",
              fontSize: "11px",
              borderRadius: 4,
              border: `1px solid ${c.border}`,
              background: "transparent",
              color: c.textSecondary,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            1年
          </button>
          <button
            type="button"
            className="kline-chart__hud-btn"
            onClick={() => handleRangeSelect("ALL")}
            title="查看全部K线"
            style={{
              padding: "1px 6px",
              fontSize: "11px",
              borderRadius: 4,
              border: `1px solid ${c.border}`,
              background: "transparent",
              color: c.textSecondary,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            全部
          </button>

          {/* 主图指标切换 */}
          <button
            type="button"
            className="kline-chart__hud-btn"
            onClick={() => setMainOverlay(mainOverlay === "MA" ? "BOLL" : mainOverlay === "BOLL" ? "NONE" : "MA")}
            title="切换主图技术指标 (MA/BOLL/无)"
            style={{
              padding: "1px 7px",
              fontSize: "11px",
              borderRadius: 4,
              border: `1px solid ${c.border}`,
              background: hexToRgba(c.primary, 0.08),
              color: c.primary,
              cursor: "pointer",
              fontWeight: 600,
              whiteSpace: "nowrap",
            }}
          >
            {mainOverlay === "MA" ? "主:MA" : mainOverlay === "BOLL" ? "主:BOLL" : "主:无"}
          </button>

          {/* 同花顺经典 红空绿实 / 实心蜡烛 切换 */}
          <button
            type="button"
            className="kline-chart__hud-btn"
            onClick={() => setCandleStyle(candleStyle === "solid" ? "hollow" : "solid")}
            title={candleStyle === "solid" ? "切换为同花顺红空绿实（阳线镂空）" : "切换为常规实心K线"}
            style={{
              padding: "1px 7px",
              fontSize: "11px",
              borderRadius: 4,
              border: `1px solid ${candleStyle === "hollow" ? c.primary : c.border}`,
              background: candleStyle === "hollow" ? hexToRgba(c.primary, 0.12) : "transparent",
              color: candleStyle === "hollow" ? c.primary : c.textSecondary,
              cursor: "pointer",
              fontWeight: candleStyle === "hollow" ? 600 : 400,
              whiteSpace: "nowrap",
            }}
          >
            {candleStyle === "hollow" ? "红空绿实" : "实心K线"}
          </button>

          {/* 筹码峰与CYQ筹码分布开关 */}
          {chipDistribution && (
            <button
              type="button"
              className="kline-chart__hud-btn"
              onClick={() => setShowChipPeak(!showChipPeak)}
              title={showChipPeak ? "隐藏筹码峰与CYQ筹码分布" : "显示筹码峰与CYQ筹码分布"}
              style={{
                padding: "1px 7px",
                fontSize: "11px",
                borderRadius: 4,
                border: `1px solid ${showChipPeak ? "#faad14" : c.border}`,
                background: showChipPeak ? hexToRgba("#faad14", 0.15) : "transparent",
                color: showChipPeak ? "#faad14" : c.textSecondary,
                cursor: "pointer",
                fontWeight: showChipPeak ? 600 : 400,
                whiteSpace: "nowrap",
              }}
            >
              筹码峰
            </button>
          )}

          {/* 放大横屏模式切换 */}
          <button
            type="button"
            className="kline-chart__hud-btn"
            onClick={toggleLandscape}
            title={isLandscape ? "退出横屏放大模式 (Esc)" : "放大横屏看盘 (沉浸式全屏横屏)"}
            style={{
              padding: "1px 7px",
              fontSize: "11px",
              borderRadius: 4,
              border: `1px solid ${isLandscape ? c.primary : c.border}`,
              background: isLandscape ? hexToRgba(c.primary, 0.15) : hexToRgba(c.primary, 0.05),
              color: isLandscape ? c.primary : c.textPrimary,
              cursor: "pointer",
              fontWeight: 600,
              whiteSpace: "nowrap",
              display: "inline-flex",
              alignItems: "center",
              gap: 3,
            }}
          >
            <span style={{ fontSize: "12px", lineHeight: 1 }}>{isLandscape ? "✕" : "⛶"}</span>
            {isLandscape ? "退出横屏" : "放大横屏"}
          </button>

          {isLandscape && (
            <button
              type="button"
              className="kline-chart__hud-btn"
              onClick={() => setIsRotated(!isRotated)}
              title="在竖屏与横屏方向之间旋转 90° (适配手机竖屏横拿看盘)"
              style={{
                padding: "1px 7px",
                fontSize: "11px",
                borderRadius: 4,
                border: `1px solid ${c.border}`,
                background: isRotated ? hexToRgba(c.primary, 0.15) : "transparent",
                color: isRotated ? c.primary : c.textSecondary,
                cursor: "pointer",
                fontWeight: 500,
                whiteSpace: "nowrap",
              }}
            >
              {isRotated ? "还原旋转" : "90°旋转"}
            </button>
          )}
        </div>

        {isLandscape && landscapeToolbar ? (
          <div
            className="kline-chart__landscape-toolbar"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              flex: "1 1 100%",
              flexWrap: "wrap",
              rowGap: 4,
            }}
          >
            {landscapeToolbar}
          </div>
        ) : null}
      </div>

      <div className="kline-chart__plot" style={{ position: "relative", flex: 1, width: "100%", minHeight: 0, backgroundColor: c.cardBg }}>
        <div ref={chartElRef} style={{ width: "100%", height: "100%", backgroundColor: c.cardBg }} />
        <div ref={brushRef} className="kline-chart__brush" style={{
          position: "absolute", top: 0, bottom: 0, display: "none", pointerEvents: "none",
          background: hexToRgba(c.primary, 0.12), border: `1px solid ${hexToRgba(c.primary, 0.35)}`,
        }} />

        {/* 股价与副图窗格中间区分栏 (带背景色、带指标说明、左右不穿透坐标轴) */}
        <div
          className="kline-chart__separator-bar"
          style={{
            position: "absolute",
            top: pane0Height - 11,
            left: 0,
            right: rightScaleWidth + 1,
            height: 22,
            backgroundColor: c.nestedBg,
            borderTop: `1px solid ${c.border}`,
            borderBottom: `1px solid ${c.border}`,
            boxShadow: c.isLight ? "0 1px 2px rgba(44, 34, 20, 0.04)" : "0 1px 3px rgba(0, 0, 0, 0.25)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 8px",
            zIndex: 3,
            cursor: "row-resize",
            userSelect: "none",
          }}
          onMouseDown={handleSeparatorMouseDown}
          title="上下拖拽可调整K线图与副图高度比例"
        >
          <div className="kline-chart__subindicator-info" style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "nowrap", overflow: "hidden", minWidth: 0 }}>
            {/* 同花顺风格副图指标切换器 */}
            <div className="kline-chart__subindicator-tabs" style={{ display: "flex", alignItems: "center", gap: 2, flexShrink: 0 }} onMouseDown={(e) => e.stopPropagation()}>
              {(["VOL", "AMO", "MACD", "KDJ", "RSI"] as const).map((tab) => {
                const isActive = subIndicator === tab;
                return (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setSubIndicator(tab)}
                    className="kline-chart__subindicator-tab-btn"
                    style={{
                      padding: "0 5px",
                      height: 16,
                      fontSize: "10px",
                      fontWeight: isActive ? 700 : 500,
                      borderRadius: 2,
                      border: isActive ? `1px solid ${c.primary}` : "1px solid transparent",
                      background: isActive ? hexToRgba(c.primary, 0.12) : "transparent",
                      color: isActive ? c.primary : c.textSecondary,
                      cursor: "pointer",
                      lineHeight: "14px",
                    }}
                  >
                    {tab}
                  </button>
                );
              })}
            </div>

            {activeCandle && (
              <div
                className="kline-chart__subindicator-stats"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  flexWrap: "nowrap",
                  overflowX: "auto",
                  scrollbarWidth: "none",
                }}
              >
                {subIndicator === "VOL" && (
                  <>
                    <span
                      className="kline-chart__vol-stat"
                      title={activeCandle.volume != null ? `成交量: ${activeCandle.volume.toLocaleString("zh-CN")} 股` : "成交量"}
                      style={{ fontSize: "11px", color: c.textMuted, whiteSpace: "nowrap" }}
                    >
                      VOL: <strong style={{ color: c.textPrimary, fontFamily: APP_FONT_FAMILY }}>{formatVolume(activeCandle.volume ?? activeCandle.amount)}</strong>
                    </span>
                    {renderVolumeRatioBadge(activeCandle.volume, activeCandle.vol5, { up: c.up, down: c.down, muted: c.textMuted, secondary: c.textSecondary })}
                    {activeCandle.amount != null && (
                      <span
                        className="kline-chart__vol-stat"
                        title={`成交额: ${activeCandle.amount.toLocaleString("zh-CN", { maximumFractionDigits: 2 })} 元`}
                        style={{ fontSize: "11px", color: c.textMuted, whiteSpace: "nowrap" }}
                      >
                        额: <strong style={{ color: c.textPrimary, fontFamily: APP_FONT_FAMILY }}>{formatAmount(activeCandle.amount)}</strong>
                      </span>
                    )}
                    {activeCandle.turnoverPct != null && (
                      <span
                        className="kline-chart__vol-stat"
                        title={`换手率: ${activeCandle.turnoverPct.toFixed(2)}%`}
                        style={{ fontSize: "11px", color: c.textMuted, whiteSpace: "nowrap" }}
                      >
                        换手: <strong style={{ color: c.textPrimary, fontFamily: APP_FONT_FAMILY }}>{activeCandle.turnoverPct.toFixed(2)}%</strong>
                      </span>
                    )}
                    {activeCandle.vol5 != null && (
                      <span
                        className="kline-chart__vol-stat"
                        title={`5日均量: ${formatVolume(activeCandle.vol5)}`}
                        style={{ fontSize: "11px", color: "#f0b90b", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 3 }}
                      >
                        <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", backgroundColor: "#f0b90b" }} />
                        MA5: <strong style={{ fontFamily: APP_FONT_FAMILY }}>{formatVolume(activeCandle.vol5)}</strong>
                      </span>
                    )}
                    {activeCandle.vol10 != null && (
                      <span
                        className="kline-chart__vol-stat"
                        title={`10日均量: ${formatVolume(activeCandle.vol10)}`}
                        style={{ fontSize: "11px", color: "#00d4d4", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 3 }}
                      >
                        <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", backgroundColor: "#00d4d4" }} />
                        MA10: <strong style={{ fontFamily: APP_FONT_FAMILY }}>{formatVolume(activeCandle.vol10)}</strong>
                      </span>
                    )}
                  </>
                )}
                {subIndicator === "AMO" && (
                  <>
                    <span
                      className="kline-chart__vol-stat"
                      title={activeCandle.amount != null ? `成交额: ${activeCandle.amount.toLocaleString("zh-CN", { maximumFractionDigits: 2 })} 元` : "成交额"}
                      style={{ fontSize: "11px", color: c.textMuted, whiteSpace: "nowrap" }}
                    >
                      AMO: <strong style={{ color: c.textPrimary, fontFamily: APP_FONT_FAMILY }}>{formatAmount(activeCandle.amount ?? activeCandle.volume)}</strong>
                    </span>
                    {renderVolumeRatioBadge(activeCandle.amount, activeCandle.amo5, { up: c.up, down: c.down, muted: c.textMuted, secondary: c.textSecondary })}
                    {activeCandle.volume != null && (
                      <span
                        className="kline-chart__vol-stat"
                        title={`成交量: ${activeCandle.volume.toLocaleString("zh-CN")} 股`}
                        style={{ fontSize: "11px", color: c.textMuted, whiteSpace: "nowrap" }}
                      >
                        量: <strong style={{ color: c.textPrimary, fontFamily: APP_FONT_FAMILY }}>{formatVolume(activeCandle.volume)}</strong>
                      </span>
                    )}
                    {activeCandle.turnoverPct != null && (
                      <span
                        className="kline-chart__vol-stat"
                        title={`换手率: ${activeCandle.turnoverPct.toFixed(2)}%`}
                        style={{ fontSize: "11px", color: c.textMuted, whiteSpace: "nowrap" }}
                      >
                        换手: <strong style={{ color: c.textPrimary, fontFamily: APP_FONT_FAMILY }}>{activeCandle.turnoverPct.toFixed(2)}%</strong>
                      </span>
                    )}
                    {activeCandle.amo5 != null && (
                      <span
                        className="kline-chart__vol-stat"
                        title={`5日均额: ${formatAmount(activeCandle.amo5)}`}
                        style={{ fontSize: "11px", color: "#f0b90b", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 3 }}
                      >
                        <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", backgroundColor: "#f0b90b" }} />
                        MA5: <strong style={{ fontFamily: APP_FONT_FAMILY }}>{formatAmount(activeCandle.amo5)}</strong>
                      </span>
                    )}
                    {activeCandle.amo10 != null && (
                      <span
                        className="kline-chart__vol-stat"
                        title={`10日均额: ${formatAmount(activeCandle.amo10)}`}
                        style={{ fontSize: "11px", color: "#00d4d4", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 3 }}
                      >
                        <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", backgroundColor: "#00d4d4" }} />
                        MA10: <strong style={{ fontFamily: APP_FONT_FAMILY }}>{formatAmount(activeCandle.amo10)}</strong>
                      </span>
                    )}
                  </>
                )}
                {subIndicator === "MACD" && (
                  <>
                    <span className="kline-chart__vol-stat" style={{ fontSize: "11px", color: "#f0b90b", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 3 }}>
                      <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", backgroundColor: "#f0b90b" }} />
                      DIF: <strong style={{ fontFamily: APP_FONT_FAMILY }}>{activeCandle.dif != null ? activeCandle.dif.toFixed(2) : "-"}</strong>
                    </span>
                    <span className="kline-chart__vol-stat" style={{ fontSize: "11px", color: "#e879f9", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 3 }}>
                      <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", backgroundColor: "#e879f9" }} />
                      DEA: <strong style={{ fontFamily: APP_FONT_FAMILY }}>{activeCandle.dea != null ? activeCandle.dea.toFixed(2) : "-"}</strong>
                    </span>
                    <span className="kline-chart__vol-stat" style={{ fontSize: "11px", color: (activeCandle.macd ?? 0) >= 0 ? c.up : c.down, whiteSpace: "nowrap" }}>
                      MACD: <strong style={{ fontFamily: APP_FONT_FAMILY }}>{activeCandle.macd != null ? activeCandle.macd.toFixed(2) : "-"}</strong>
                    </span>
                  </>
                )}
                {subIndicator === "KDJ" && (
                  <>
                    <span className="kline-chart__vol-stat" style={{ fontSize: "11px", color: "#f0b90b", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 3 }}>
                      <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", backgroundColor: "#f0b90b" }} />
                      K: <strong style={{ fontFamily: APP_FONT_FAMILY }}>{activeCandle.k != null ? activeCandle.k.toFixed(2) : "-"}</strong>
                    </span>
                    <span className="kline-chart__vol-stat" style={{ fontSize: "11px", color: "#38bdf8", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 3 }}>
                      <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", backgroundColor: "#38bdf8" }} />
                      D: <strong style={{ fontFamily: APP_FONT_FAMILY }}>{activeCandle.d != null ? activeCandle.d.toFixed(2) : "-"}</strong>
                    </span>
                    <span className="kline-chart__vol-stat" style={{ fontSize: "11px", color: "#d946ef", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 3 }}>
                      <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", backgroundColor: "#d946ef" }} />
                      J: <strong style={{ fontFamily: APP_FONT_FAMILY }}>{activeCandle.j != null ? activeCandle.j.toFixed(2) : "-"}</strong>
                    </span>
                  </>
                )}
                {subIndicator === "RSI" && (
                  <>
                    <span className="kline-chart__vol-stat" style={{ fontSize: "11px", color: "#f0b90b", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 3 }}>
                      <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", backgroundColor: "#f0b90b" }} />
                      RSI6: <strong style={{ fontFamily: APP_FONT_FAMILY }}>{activeCandle.rsi6 != null ? activeCandle.rsi6.toFixed(2) : "-"}</strong>
                    </span>
                    <span className="kline-chart__vol-stat" style={{ fontSize: "11px", color: "#38bdf8", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 3 }}>
                      <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", backgroundColor: "#38bdf8" }} />
                      RSI12: <strong style={{ fontFamily: APP_FONT_FAMILY }}>{activeCandle.rsi12 != null ? activeCandle.rsi12.toFixed(2) : "-"}</strong>
                    </span>
                    <span className="kline-chart__vol-stat" style={{ fontSize: "11px", color: "#c084fc", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 3 }}>
                      <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", backgroundColor: "#c084fc" }} />
                      RSI24: <strong style={{ fontFamily: APP_FONT_FAMILY }}>{activeCandle.rsi24 != null ? activeCandle.rsi24.toFixed(2) : "-"}</strong>
                    </span>
                  </>
                )}
              </div>
            )}
          </div>

          <div className="kline-chart__separator-drag" style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
            <div style={{
              width: 22,
              height: 3,
              borderRadius: 2,
              backgroundColor: c.border,
              opacity: 0.8,
            }} />
            <span className="kline-chart__separator-unit" style={{ fontSize: "10px", color: c.textMuted, opacity: 0.75 }}>
              {subIndicator === "VOL" ? "单位: 股/元" : subIndicator === "AMO" ? "单位: 元" : subIndicator === "MACD" ? "参数: 12,26,9" : subIndicator === "KDJ" ? "参数: 9,3,3" : "参数: 6,12,24"}
            </span>
          </div>
        </div>

        {/* 同花顺风格 侧边 CYQ 筹码分布悬浮微图 */}
        {showChipPeak && chipDistribution && sortedHistogramSlice.length > 0 && (
          <div
            className="pdf-hide"
            style={{
              position: "absolute",
              right: 58,
              top: 6,
              width: 108,
              maxHeight: Math.min(pane0Height - 16, 200),
              backgroundColor: hexToRgba(c.cardBg, 0.88),
              border: `1px solid ${hexToRgba(c.border, 0.8)}`,
              borderRadius: 4,
              padding: "4px 6px",
              boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
              zIndex: 3,
              pointerEvents: "none",
              display: "flex",
              flexDirection: "column",
              backdropFilter: "blur(2px)",
              overflow: "hidden",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 3 }}>
              <span style={{ fontSize: "9px", fontWeight: 700, color: c.textSecondary, letterSpacing: "0.02em" }}>
                CYQ 筹码
              </span>
              <span style={{ fontSize: "9px", fontWeight: 700, color: "#faad14" }}>
                峰:{chipDistribution.peak_price.toFixed(2)}
              </span>
            </div>

            {/* 柱状分布图 */}
            <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 1, overflow: "hidden" }}>
              {sortedHistogramSlice.map((item, idx) => {
                const currentPrice = activeCandle?.close ?? chipDistribution.peak_price;
                const isProfit = item.price <= currentPrice;
                const isPeak = Math.abs(item.price - chipDistribution.peak_price) < 0.05;
                const barColor = isPeak ? "#faad14" : isProfit ? hexToRgba(c.up, 0.75) : hexToRgba(c.down, 0.65);
                const widthPct = Math.min(100, Math.max(4, Math.round((item.ratio / maxChipRatio) * 100)));

                return (
                  <div key={idx} style={{ display: "flex", alignItems: "center", height: 4, gap: 3 }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${widthPct}%`,
                        backgroundColor: barColor,
                        borderRadius: 1,
                      }}
                    />
                  </div>
                );
              })}
            </div>

            {/* 统计指标 */}
            <div style={{ marginTop: 3, paddingTop: 2, borderTop: `1px dashed ${hexToRgba(c.border, 0.6)}`, display: "flex", flexDirection: "column", gap: 1 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "9px" }}>
                <span style={{ color: c.textMuted }}>获利比例</span>
                <span style={{ color: (chipDistribution.profit_ratio ?? 0) >= 0.5 ? c.up : c.down, fontWeight: 600 }}>
                  {chipDistribution.profit_ratio != null ? `${(chipDistribution.profit_ratio * 100).toFixed(1)}%` : "-"}
                </span>
              </div>
              {chipDistribution.concentration_90 != null && (
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "9px" }}>
                  <span style={{ color: c.textMuted }}>90%集中度</span>
                  <span style={{ color: c.textSecondary, fontWeight: 500 }}>
                    {(chipDistribution.concentration_90 * 100).toFixed(1)}%
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {isZoomed && (
          <div className="pdf-hide" style={{ position: "absolute", right: 12, top: 10, zIndex: 5 }}>
            <button type="button" onClick={() => { chartRef.current?.timeScale().fitContent(); setIsZoomed(false); }}
              style={{
                padding: "6px 12px", fontSize: "var(--c-font-sm)", fontWeight: "var(--c-weight-semibold)", color: c.primary,
                background: hexToRgba(c.pageBg, 0.98), border: `1px solid ${c.border}`,
                borderRadius: 999, cursor: "pointer", boxShadow: `0 4px 12px ${hexToRgba(c.primary, 0.15)}`,
              }}>
              返回全视图
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
