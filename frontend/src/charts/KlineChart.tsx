import { useEffect, useMemo, useRef, useState } from "react";
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
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
  type BusinessDay,
  type MouseEventParams,
  type CandlestickData,
} from "lightweight-charts";
import type { KlineItem } from "../types/stock";
import type { ChanlunResult, MmdType } from "../utils/chanlun";
import { useColors } from "../styles/ui";
import { APP_FONT_FAMILY, APP_FONT_SIZE } from "../theme/typography";
import { createDebouncedResizeHandler, shouldFitChartContent } from "./chartLifecycle";
import { toBusinessDay, hexToRgba } from "./utils";
import { buildKlineTradeMarkers, type KlineTradeMarker } from "./klineMarkers";
import { calculateMA, calculateMAVOL, calculateBOLL, MA_CONFIGS, MAVOL_CONFIGS } from "./movingAverages";

type Props = {
  data: KlineItem[];
  height?: number;
  viewKey?: string;
  tradeMarkers?: KlineTradeMarker[];
  /** 缠论分析结果：叠加笔、中枢区间与买卖点标记 */
  chanlun?: ChanlunResult | null;
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
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma30: number | null;
  ma60: number | null;
  vol5: number | null;
  vol10: number | null;
  bollMid: number | null;
  bollUp: number | null;
  bollDn: number | null;
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

function formatAmount(val: number | null | undefined): string {
  if (val == null || isNaN(val)) return "-";
  if (Math.abs(val) >= 1e8) return `${(val / 1e8).toFixed(2)}亿`;
  if (Math.abs(val) >= 1e4) return `${(val / 1e4).toFixed(2)}万`;
  return val.toFixed(0);
}

export default function KlineChart({ data, height = 500, viewKey = "default", tradeMarkers = [], chanlun = null }: Props) {
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
  const tradeMarkersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const chanlunSeriesRef = useRef<ISeriesApi<"Line">[]>([]);
  const fittedViewKeyRef = useRef<string | null>(null);
  const [isZoomed, setIsZoomed] = useState(false);
  const [hoverInfo, setHoverInfo] = useState<HoverCandleInfo | null>(null);
  const [mainOverlay, setMainOverlay] = useState<"MA" | "BOLL">("MA");

  const rows = useMemo<ChartItem[]>(
    () => data
      .map((item) => {
        const date = toBusinessDay(item.date);
        return date ? { ...item, date, rawDate: item.date } : null;
      })
      .filter((item): item is ChartItem => item !== null),
    [data]
  );

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
      const volPoints = calculateMAVOL(rows, cfg.period);
      const dateMap = new Map<string, number>();
      for (const pt of volPoints) {
        const d = pt.time as BusinessDay;
        const key = `${d.year}-${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`;
        dateMap.set(key, pt.value);
      }
      mavolMaps.set(cfg.key, dateMap);
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

    return { maMaps, mavolMaps, boll, bollMidMap, bollUpMap, bollDnMap };
  }, [rows]);

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
      amount: last.amount ?? last.volume ?? null,
      ma5: calculations.maMaps.get("ma5")?.get(dateKey) ?? null,
      ma10: calculations.maMaps.get("ma10")?.get(dateKey) ?? null,
      ma20: calculations.maMaps.get("ma20")?.get(dateKey) ?? null,
      ma30: calculations.maMaps.get("ma30")?.get(dateKey) ?? null,
      ma60: calculations.maMaps.get("ma60")?.get(dateKey) ?? null,
      vol5: calculations.mavolMaps.get("vol5")?.get(dateKey) ?? null,
      vol10: calculations.mavolMaps.get("vol10")?.get(dateKey) ?? null,
      bollMid: calculations.bollMidMap.get(dateKey) ?? null,
      bollUp: calculations.bollUpMap.get(dateKey) ?? null,
      bollDn: calculations.bollDnMap.get(dateKey) ?? null,
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
        amount: target.amount ?? target.volume ?? null,
        ma5: calculations.maMaps.get("ma5")?.get(dateKey) ?? null,
        ma10: calculations.maMaps.get("ma10")?.get(dateKey) ?? null,
        ma20: calculations.maMaps.get("ma20")?.get(dateKey) ?? null,
        ma30: calculations.maMaps.get("ma30")?.get(dateKey) ?? null,
        ma60: calculations.maMaps.get("ma60")?.get(dateKey) ?? null,
        vol5: calculations.mavolMaps.get("vol5")?.get(dateKey) ?? null,
        vol10: calculations.mavolMaps.get("vol10")?.get(dateKey) ?? null,
        bollMid: calculations.bollMidMap.get(dateKey) ?? null,
        bollUp: calculations.bollUpMap.get(dateKey) ?? null,
        bollDn: calculations.bollDnMap.get(dateKey) ?? null,
      });
    } else if (e.key === "Escape") {
      selectedIndexRef.current = null;
      setHoverInfo(null);
    }
  };

  useEffect(() => {
    if (!wrapperRef.current || !chartElRef.current || !brushRef.current) return;
    chartRef.current?.remove();
    const colors = colorsRef.current;

    const chart = createChart(chartElRef.current, {
      width: chartElRef.current.clientWidth,
      height: height - 32,
      layout: {
        background: { type: ColorType.Solid, color: colors.cardBg },
        textColor: colors.textSecondary,
        fontFamily: APP_FONT_FAMILY,
        fontSize: APP_FONT_SIZE.sm,
        attributionLogo: false,
      },
      grid: { vertLines: { color: colors.border }, horzLines: { color: colors.border } },
      timeScale: { timeVisible: false, borderColor: colors.border },
      rightPriceScale: { visible: true, borderColor: colors.border },
      leftPriceScale: { visible: true, borderColor: colors.border },
      crosshair: {
        vertLine: { color: colors.textMuted, labelBackgroundColor: colors.border },
        horzLine: { color: colors.textMuted, labelBackgroundColor: colors.border },
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: false, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
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
    chart.priceScale("right").applyOptions({
      visible: true, borderColor: colors.border,
      scaleMargins: { top: 0.05, bottom: 0.22 },
    });

    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "custom", minMove: 1,
        formatter: (value: number) => Math.abs(value) >= 1e8
          ? `${(value / 1e8).toFixed(2)}亿` : `${(value / 1e4).toFixed(2)}万`,
      },
      priceScaleId: "left",
    });
    volumeSeriesRef.current = volume;
    chart.priceScale("left").applyOptions({
      visible: true, borderColor: colors.border,
      scaleMargins: { top: 0.82, bottom: 0 },
    });

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
        priceScaleId: "left",
      });
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

    const wrapper = wrapperRef.current;
    const brush = brushRef.current;
    const resizeObserver = new ResizeObserver(
      createDebouncedResizeHandler((entry) => {
        chart.applyOptions({ width: Math.floor(entry.contentRect.width), height: height - 32 });
      })
    );
    resizeObserver.observe(chartElRef.current);
    let startX: number | null = null;

    const resetBrush = () => { brush.style.display = "none"; brush.style.left = "0px"; brush.style.width = "0px"; };

    const handleMouseDown = (event: MouseEvent) => {
      if (event.button !== 0) return;
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
        const changePct = cData.open > 0 ? ((cData.close - cData.open) / cData.open) * 100 : null;
        setHoverInfo({
          dateStr: dateKey,
          open: cData.open,
          high: cData.high,
          low: cData.low,
          close: cData.close,
          changePct,
          amount: vData?.value ?? null,
          ma5: calculations.maMaps.get("ma5")?.get(dateKey) ?? null,
          ma10: calculations.maMaps.get("ma10")?.get(dateKey) ?? null,
          ma20: calculations.maMaps.get("ma20")?.get(dateKey) ?? null,
          ma30: calculations.maMaps.get("ma30")?.get(dateKey) ?? null,
          ma60: calculations.maMaps.get("ma60")?.get(dateKey) ?? null,
          vol5: calculations.mavolMaps.get("vol5")?.get(dateKey) ?? null,
          vol10: calculations.mavolMaps.get("vol10")?.get(dateKey) ?? null,
          bollMid: calculations.bollMidMap.get(dateKey) ?? null,
          bollUp: calculations.bollUpMap.get(dateKey) ?? null,
          bollDn: calculations.bollDnMap.get(dateKey) ?? null,
        });
      }
    };

    chart.subscribeCrosshairMove(handleCrosshairMove);

    wrapper.addEventListener("mousedown", handleMouseDown);
    wrapper.addEventListener("mousemove", handleMouseMove);
    wrapper.addEventListener("mouseup", handleMouseUp);
    wrapper.addEventListener("mouseleave", handleMouseLeave);
    wrapper.addEventListener("dblclick", handleDoubleClick);

    return () => {
      resizeObserver.disconnect();
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
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
      tradeMarkersRef.current = null;
      chanlunSeriesRef.current = [];
    };
  }, [height, calculations]);

  useEffect(() => {
    const chart = chartRef.current;
    const candle = candleSeriesRef.current;
    const volume = volumeSeriesRef.current;
    if (!chart || !candle || !volume) return;

    candle.setData(rows.map((item) => ({
      time: item.date,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
    })));
    volume.setData(rows.map((item) => ({
      time: item.date,
      value: item.amount ?? item.volume,
      color: item.close >= item.open ? hexToRgba(c.up, 0.5) : hexToRgba(c.down, 0.5),
    })));

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

    // Set MAVOL Data
    for (const cfg of MAVOL_CONFIGS) {
      const volLine = mavolSeriesMapRef.current.get(cfg.key);
      if (volLine) {
        const volPoints = calculateMAVOL(rows, cfg.period);
        volLine.setData(volPoints.map((pt) => ({ time: pt.time as BusinessDay, value: pt.value })));
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
    const timeKey = (time: Time) => {
      const day = time as BusinessDay;
      return `${day.year ?? 0}-${String(day.month ?? 0).padStart(2, "0")}-${String(day.day ?? 0).padStart(2, "0")}`;
    };
    tradeMarkersRef.current?.setMarkers(
      [...tradeMarkerList, ...chanlunMarkerList].sort((a, b) => (timeKey(a.time) < timeKey(b.time) ? -1 : 1)),
    );

    if (rows.length > 0 && shouldFitChartContent(fittedViewKeyRef.current, viewKey)) {
      if (rows.length > 80) {
        chart.timeScale().setVisibleLogicalRange({ from: rows.length - 80, to: rows.length + 2 });
      } else {
        chart.timeScale().fitContent();
      }
      fittedViewKeyRef.current = viewKey;
      setIsZoomed(false);
    }
  }, [c.down, c.up, data, height, rows, tradeMarkers, viewKey, chanlun, mainOverlay, calculations]);

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

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    chart.applyOptions({
      layout: { background: { type: ColorType.Solid, color: c.cardBg }, textColor: c.textSecondary },
      grid: { vertLines: { color: c.border }, horzLines: { color: c.border } },
      timeScale: { borderColor: c.border },
      rightPriceScale: { borderColor: c.border },
      leftPriceScale: { borderColor: c.border },
      crosshair: {
        vertLine: { color: c.textMuted, labelBackgroundColor: c.border },
        horzLine: { color: c.textMuted, labelBackgroundColor: c.border },
      },
    });

    candleSeriesRef.current?.applyOptions({
      upColor: c.up, downColor: c.down,
      borderUpColor: c.up, borderDownColor: c.down,
      wickUpColor: c.up, wickDownColor: c.down,
    });
    volumeSeriesRef.current?.setData(rows.map((item) => ({
      time: item.date,
      value: item.amount ?? item.volume,
      color: item.close >= item.open ? hexToRgba(c.up, 0.5) : hexToRgba(c.down, 0.5),
    })));
    chart.priceScale("right").applyOptions({ borderColor: c.border });
    chart.priceScale("left").applyOptions({ borderColor: c.border });
  }, [c.cardBg, c.border, c.down, c.textMuted, c.textSecondary, c.up, height, rows]);

  return (
    <div
      ref={wrapperRef}
      tabIndex={0}
      role="region"
      aria-label="K线图交互区"
      onKeyDown={handleKeyDown}
      className="kline-chart"
      style={{
        position: "relative",
        width: "100%",
        minHeight: height,
        display: "flex",
        flexDirection: "column",
        backgroundColor: c.cardBg,
        outline: "none",
      }}
    >
      {/* Allow wrapped quotes to grow without overlapping the toolbar or plot. */}
      <div className="kline-chart__hud" style={{
        minHeight: 32,
        flexShrink: 0,
        padding: "4px 8px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        fontSize: "11px",
        color: c.textSecondary,
        backgroundColor: c.nestedBg,
        borderBottom: `1px solid ${c.border}`,
        fontFamily: "var(--c-font-mono)",
        userSelect: "none",
        gap: 8,
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
            <span>日期: <strong style={{ color: c.textPrimary }}>{activeCandle.dateStr}</strong></span>
            <span>开: <strong style={{ color: activeCandle.close >= activeCandle.open ? c.up : c.down }}>{activeCandle.open.toFixed(2)}</strong></span>
            <span>高: <strong style={{ color: c.up }}>{activeCandle.high.toFixed(2)}</strong></span>
            <span>低: <strong style={{ color: c.down }}>{activeCandle.low.toFixed(2)}</strong></span>
            <span>收: <strong style={{ color: activeCandle.close >= activeCandle.open ? c.up : c.down }}>{activeCandle.close.toFixed(2)}</strong></span>
            {activeCandle.changePct != null && (
              <span style={{ color: activeCandle.changePct >= 0 ? c.up : c.down }}>
                ({activeCandle.changePct >= 0 ? `+${activeCandle.changePct.toFixed(2)}%` : `${activeCandle.changePct.toFixed(2)}%`})
              </span>
            )}
            {activeCandle.amount != null && (
              <span>额: <strong style={{ color: c.textPrimary }}>{formatAmount(activeCandle.amount)}</strong></span>
            )}
            {mainOverlay === "MA" ? (
              <>
                <span style={{ color: "#f0b90b" }}>MA5: {activeCandle.ma5 != null ? activeCandle.ma5.toFixed(2) : "-"}</span>
                <span style={{ color: "#1890ff" }}>MA10: {activeCandle.ma10 != null ? activeCandle.ma10.toFixed(2) : "-"}</span>
                <span style={{ color: "#9254de" }}>MA20: {activeCandle.ma20 != null ? activeCandle.ma20.toFixed(2) : "-"}</span>
                <span style={{ color: "#13c2c2" }}>MA30: {activeCandle.ma30 != null ? activeCandle.ma30.toFixed(2) : "-"}</span>
                <span style={{ color: "#ff7a45" }}>MA60: {activeCandle.ma60 != null ? activeCandle.ma60.toFixed(2) : "-"}</span>
              </>
            ) : (
              <>
                <span style={{ color: "#f0b90b" }}>MID: {activeCandle.bollMid != null ? activeCandle.bollMid.toFixed(2) : "-"}</span>
                <span style={{ color: "#ff7a45" }}>UP: {activeCandle.bollUp != null ? activeCandle.bollUp.toFixed(2) : "-"}</span>
                <span style={{ color: "#9254de" }}>DN: {activeCandle.bollDn != null ? activeCandle.bollDn.toFixed(2) : "-"}</span>
              </>
            )}
            <span style={{ color: "#f0b90b", opacity: 0.9 }}>V5: {formatAmount(activeCandle.vol5)}</span>
            <span style={{ color: "#1890ff", opacity: 0.9 }}>V10: {formatAmount(activeCandle.vol10)}</span>
          </div>
        ) : (
          <span>等待K线数据...</span>
        )}

        {/* Range & Overlay controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 3, flex: "0 0 auto", marginLeft: 4 }}>
          <button
            type="button"
            onClick={() => handleRangeSelect("1M")}
            title="查看近1月 (约22根K线)"
            style={{
              padding: "1px 5px",
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
            onClick={() => handleRangeSelect("3M")}
            title="查看近3月 (约66根K线)"
            style={{
              padding: "1px 5px",
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
            onClick={() => handleRangeSelect("1Y")}
            title="查看近1年 (约250根K线)"
            style={{
              padding: "1px 5px",
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
            onClick={() => handleRangeSelect("ALL")}
            title="查看全部K线"
            style={{
              padding: "1px 5px",
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
          <button
            type="button"
            onClick={() => setMainOverlay(mainOverlay === "MA" ? "BOLL" : "MA")}
            style={{
              padding: "1px 6px",
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
            {mainOverlay === "MA" ? "切换BOLL" : "切换MA"}
          </button>
        </div>
      </div>

      <div className="kline-chart__plot" style={{ position: "relative", flex: "0 0 auto", width: "100%", height: height - 32, backgroundColor: c.cardBg }}>
        <div ref={chartElRef} style={{ width: "100%", height: "100%", backgroundColor: c.cardBg }} />
        <div ref={brushRef} style={{
          position: "absolute", top: 0, bottom: 0, display: "none", pointerEvents: "none",
          background: hexToRgba(c.primary, 0.12), border: `1px solid ${hexToRgba(c.primary, 0.35)}`,
        }} />
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
