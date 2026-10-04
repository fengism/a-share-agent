import { useEffect, useMemo, useRef, useState } from "react";
import { Segmented, Skeleton } from "antd";
import { createChart, LineSeries, HistogramSeries, ColorType, type IChartApi, type ISeriesApi, type BusinessDay, type MouseEventParams, type Time } from "lightweight-charts";
import { useIndicators } from "../api/queries";
import type { TechnicalIndicators } from "../types/stock";
import { useColors } from "../styles/ui";
import { APP_FONT_SIZE } from "../theme/typography";
import type { ThemeColors } from "../theme/themes";
import { createDebouncedResizeHandler, shouldFitChartContent } from "./chartLifecycle";
import { toBusinessDay, hexToRgba } from "./utils";
import { MAX_KLINE_HISTORY_YEARS } from "../utils/date";

export type IndicatorType = "macd" | "rsi" | "kdj";
type Props = {
  code: string;
  types?: readonly IndicatorType[];
  height?: number;
  activeType?: IndicatorType;
  onTypeChange?: (type: IndicatorType) => void;
  period?: string;
  onPeriodChange?: (period: string) => void;
  startDate?: string;
  historyYears?: number;
  onReachLeftEdge?: () => void;
  historyLimitReached?: boolean;
};
const DEFAULT_INDICATOR_TYPES: readonly IndicatorType[] = ["macd", "rsi", "kdj"];
type IndicatorSeries = ISeriesApi<"Line"> | ISeriesApi<"Histogram">;


function macdChart(
  chart: IChartApi,
  seriesData: TechnicalIndicators["series"],
  dates: BusinessDay[],
  c: ThemeColors,
): IndicatorSeries[] {
  const dif = chart.addSeries(LineSeries, {
    color: c.primary, lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
    priceFormat: { type: "custom", minMove: 0.01, formatter: (v: number) => v.toFixed(2) },
  });
  const dea = chart.addSeries(LineSeries, {
    color: c.accent, lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
    priceFormat: { type: "custom", minMove: 0.01, formatter: (v: number) => v.toFixed(2) },
  });
  const hist = chart.addSeries(HistogramSeries, {
    priceFormat: { type: "custom", minMove: 0.01, formatter: (v: number) => v.toFixed(2) },
    priceLineVisible: false, lastValueVisible: false,
  });

  const difData: { time: BusinessDay; value: number }[] = [];
  const deaData: { time: BusinessDay; value: number }[] = [];
  const histData: { time: BusinessDay; value: number; color: string }[] = [];

  for (let i = 0; i < dates.length; i++) {
    const h = seriesData.macd_hist?.[i];
    const d = seriesData.dif?.[i];
    const e = seriesData.dea?.[i];
    if (h != null) histData.push({ time: dates[i], value: h, color: h >= 0 ? c.up : c.down });
    if (d != null) difData.push({ time: dates[i], value: d });
    if (e != null) deaData.push({ time: dates[i], value: e });
  }

  dif.setData(difData);
  dea.setData(deaData);
  hist.setData(histData);

  chart.priceScale("right").applyOptions({
    scaleMargins: { top: 0.12, bottom: 0.12 },
  });
  return [dif, dea, hist];
}

function rsiChart(
  chart: IChartApi,
  series: TechnicalIndicators["series"],
  dates: BusinessDay[],
  c: ThemeColors,
): IndicatorSeries[] {
  const rsiLine = chart.addSeries(LineSeries, {
    color: c.accent, lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
    priceFormat: { type: "custom", minMove: 0.1, formatter: (v: number) => v.toFixed(1) },
  });

  const data: { time: BusinessDay; value: number }[] = [];
  for (let i = 0; i < dates.length; i++) {
    const v = series.rsi?.[i];
    if (v != null) data.push({ time: dates[i], value: v });
  }
  rsiLine.setData(data);

  const ref70 = chart.addSeries(LineSeries, {
    color: hexToRgba(c.up, 0.35), lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false,
  });
  const ref50 = chart.addSeries(LineSeries, {
    color: hexToRgba(c.textMuted, 0.2), lineWidth: 1, lineStyle: 3, priceLineVisible: false, lastValueVisible: false,
  });
  const ref30 = chart.addSeries(LineSeries, {
    color: hexToRgba(c.down, 0.35), lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false,
  });

  if (data.length >= 2) {
    ref70.setData([
      { time: data[0].time, value: 70 },
      { time: data[data.length - 1].time, value: 70 },
    ]);
    ref50.setData([
      { time: data[0].time, value: 50 },
      { time: data[data.length - 1].time, value: 50 },
    ]);
    ref30.setData([
      { time: data[0].time, value: 30 },
      { time: data[data.length - 1].time, value: 30 },
    ]);
  }

  chart.priceScale("right").applyOptions({
    scaleMargins: { top: 0.12, bottom: 0.12 },
  });
  return [rsiLine, ref70, ref50, ref30];
}

function kdjChart(
  chart: IChartApi,
  series: TechnicalIndicators["series"],
  dates: BusinessDay[],
  c: ThemeColors,
): IndicatorSeries[] {
  const kLine = chart.addSeries(LineSeries, {
    color: c.primary, lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
    priceFormat: { type: "custom", minMove: 0.01, formatter: (v: number) => v.toFixed(2) },
  });
  const dLine = chart.addSeries(LineSeries, {
    color: c.accent, lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
    priceFormat: { type: "custom", minMove: 0.01, formatter: (v: number) => v.toFixed(2) },
  });
  const jLine = chart.addSeries(LineSeries, {
    color: c.warning, lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
    priceFormat: { type: "custom", minMove: 0.01, formatter: (v: number) => v.toFixed(2) },
  });

  const kData: { time: BusinessDay; value: number }[] = [];
  const dData: { time: BusinessDay; value: number }[] = [];
  const jData: { time: BusinessDay; value: number }[] = [];

  for (let i = 0; i < dates.length; i++) {
    const kv = series.k?.[i];
    const dv = series.d?.[i];
    const jv = series.j?.[i];
    if (kv != null) kData.push({ time: dates[i], value: kv });
    if (dv != null) dData.push({ time: dates[i], value: dv });
    if (jv != null) jData.push({ time: dates[i], value: jv });
  }

  kLine.setData(kData);
  dLine.setData(dData);
  jLine.setData(jData);

  chart.priceScale("right").applyOptions({
    scaleMargins: { top: 0.12, bottom: 0.12 },
  });
  return [kLine, dLine, jLine];
}

export default function IndicatorSubCharts({
  code,
  types = DEFAULT_INDICATOR_TYPES,
  height = 180,
  activeType: controlledActiveType,
  onTypeChange,
  period: controlledPeriod,
  onPeriodChange,
  startDate,
  historyYears = 1,
  onReachLeftEdge,
  historyLimitReached = false,
}: Props) {
  const c = useColors();
  const colorsRef = useRef(c);
  colorsRef.current = c;
  const [internalPeriod, setInternalPeriod] = useState("daily");
  const activePeriod = controlledPeriod ?? internalPeriod;
  const [internalIndicatorType, setInternalIndicatorType] = useState<IndicatorType>(
    controlledActiveType ?? types[0] ?? "macd",
  );
  const availableTypes = types.length > 0 ? types : DEFAULT_INDICATOR_TYPES;
  const activeIndicatorType = controlledActiveType ?? (
    availableTypes.includes(internalIndicatorType) ? internalIndicatorType : availableTypes[0]
  );
  const { data: indicators, isLoading } = useIndicators(code, activePeriod, { startDate });
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const onReachLeftEdgeRef = useRef(onReachLeftEdge);
  onReachLeftEdgeRef.current = onReachLeftEdge;
  const historyLimitRef = useRef(historyLimitReached);
  historyLimitRef.current = historyLimitReached;
  const leftEdgePendingRef = useRef(false);
  const anchoredLogicalRangeRef = useRef<{ from: number; to: number; length: number; viewKey: string } | null>(null);

  const dates = useMemo(() => {
    return indicators?.series?.dates ?? [];
  }, [indicators]);

  const dateToIndexMap = useMemo(() => {
    const map = new Map<string, number>();
    for (let i = 0; i < dates.length; i++) {
      map.set(dates[i], i);
    }
    return map;
  }, [dates]);
  const dateToIndexMapRef = useRef(dateToIndexMap);
  dateToIndexMapRef.current = dateToIndexMap;

  const activeIdx = hoverIndex ?? (dates.length > 0 ? dates.length - 1 : null);
  const activeDate = activeIdx != null ? dates[activeIdx] : null;
  const difVal = activeIdx != null ? indicators?.series?.dif?.[activeIdx] ?? null : null;
  const deaVal = activeIdx != null ? indicators?.series?.dea?.[activeIdx] ?? null : null;
  const macdHistVal = activeIdx != null ? indicators?.series?.macd_hist?.[activeIdx] ?? null : null;
  const rsiVal = activeIdx != null ? indicators?.series?.rsi?.[activeIdx] ?? null : null;
  const kVal = activeIdx != null ? indicators?.series?.k?.[activeIdx] ?? null : null;
  const dVal = activeIdx != null ? indicators?.series?.d?.[activeIdx] ?? null : null;
  const jVal = activeIdx != null ? indicators?.series?.j?.[activeIdx] ?? null : null;

  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<IChartApi | null>(null);
  const seriesRefs = useRef<IndicatorSeries[]>([]);
  const fittedViewKeyRef = useRef<string | null>(null);
  const initialHeightRef = useRef(height);

  useEffect(() => {
    if (!chartRef.current) return;
    const colors = colorsRef.current;

    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: initialHeightRef.current,
      layout: { background: { type: ColorType.Solid, color: colors.cardBg }, textColor: colors.textSecondary, fontSize: APP_FONT_SIZE.xs, attributionLogo: false },
      grid: { vertLines: { color: colors.border }, horzLines: { color: colors.border } },
      timeScale: { timeVisible: false, borderColor: colors.border },
      rightPriceScale: { visible: true, borderColor: colors.border },
      crosshair: {
        vertLine: { color: colors.textMuted, labelBackgroundColor: colors.border },
        horzLine: { color: colors.textMuted, labelBackgroundColor: colors.border },
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
      kineticScroll: { touch: true, mouse: false },
      trackingMode: { exitMode: 0 },
    });
    chartInstanceRef.current = chart;
    fittedViewKeyRef.current = null;

    const resizeObserver = new ResizeObserver(
      createDebouncedResizeHandler((entry) => {
        const width = Math.floor(entry.contentRect.width);
        if (width > 0) chart.applyOptions({ width });
      })
    );
    resizeObserver.observe(chartRef.current);

    const handleCrosshairMove = (param: MouseEventParams<Time>) => {
      if (!param.time || typeof param.time !== "object" || !("year" in param.time)) {
        setHoverIndex(null);
        return;
      }
      const day = param.time as BusinessDay;
      const dateKey = `${day.year}-${String(day.month).padStart(2, "0")}-${String(day.day).padStart(2, "0")}`;
      const idx = dateToIndexMapRef.current.get(dateKey);
      setHoverIndex(idx ?? null);
    };

    chart.subscribeCrosshairMove(handleCrosshairMove);

    const handleVisibleRangeChange = (range: { from: number; to: number } | null) => {
      if (!range || historyLimitRef.current) {
        leftEdgePendingRef.current = false;
        return;
      }
      if (range.from > 8) {
        leftEdgePendingRef.current = false;
        return;
      }
      if (leftEdgePendingRef.current) return;
      leftEdgePendingRef.current = true;
      const currentLength = dateToIndexMapRef.current.size;
      anchoredLogicalRangeRef.current = {
        from: range.from,
        to: range.to,
        length: currentLength,
        viewKey: fittedViewKeyRef.current ?? "",
      };
      onReachLeftEdgeRef.current?.();
    };

    chart.timeScale()?.subscribeVisibleLogicalRangeChange?.(handleVisibleRangeChange);

    return () => {
      resizeObserver.disconnect();
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      chart.timeScale()?.unsubscribeVisibleLogicalRangeChange?.(handleVisibleRangeChange);
      chart.remove();
      chartInstanceRef.current = null;
      seriesRefs.current = [];
    };
  }, []);

  useEffect(() => {
    chartInstanceRef.current?.applyOptions({ height });
  }, [height]);

  useEffect(() => {
    const chart = chartInstanceRef.current;
    if (!chart || !indicators?.series) return;

    for (const series of seriesRefs.current) chart.removeSeries(series);
    seriesRefs.current = [];

    const dates = indicators.series.dates
      ?.map((date) => toBusinessDay(date))
      .filter((date): date is BusinessDay => date !== null) ?? [];
    if (dates.length === 0) return;

    switch (activeIndicatorType) {
      case "macd":
        seriesRefs.current = macdChart(chart, indicators.series, dates, c);
        break;
      case "rsi":
        seriesRefs.current = rsiChart(chart, indicators.series, dates, c);
        break;
      case "kdj":
        seriesRefs.current = kdjChart(chart, indicators.series, dates, c);
        break;
    }

    const viewKey = `${code}:${activeIndicatorType}:${activePeriod}`;
    const anchor = anchoredLogicalRangeRef.current;
    if (anchor && (anchor.viewKey !== viewKey || dates.length <= anchor.length)) {
      anchoredLogicalRangeRef.current = null;
    }
    const pendingAnchor = anchoredLogicalRangeRef.current;
    if (pendingAnchor && dates.length > pendingAnchor.length) {
      anchoredLogicalRangeRef.current = null;
      const added = dates.length - pendingAnchor.length;
      chart.timeScale().setVisibleLogicalRange({
        from: pendingAnchor.from + added,
        to: pendingAnchor.to + added,
      });
    } else if (dates.length > 0 && shouldFitChartContent(fittedViewKeyRef.current, viewKey)) {
      if (dates.length > 80) {
        chart.timeScale().setVisibleLogicalRange({ from: dates.length - 80, to: dates.length + 2 });
      } else {
        chart.timeScale().fitContent();
      }
      fittedViewKeyRef.current = viewKey;
    }
  }, [activeIndicatorType, activePeriod, c, code, indicators]);

  useEffect(() => {
    const chart = chartInstanceRef.current;
    if (!chart) return;
    chart.applyOptions({
      layout: { background: { type: ColorType.Solid, color: c.cardBg }, textColor: c.textSecondary },
      grid: { vertLines: { color: c.border }, horzLines: { color: c.border } },
      timeScale: { borderColor: c.border },
      rightPriceScale: { borderColor: c.border },
      crosshair: {
        vertLine: { color: c.textMuted, labelBackgroundColor: c.border },
        horzLine: { color: c.textMuted, labelBackgroundColor: c.border },
      },
    });
  }, [c.border, c.cardBg, c.textMuted, c.textSecondary]);

  const handleIndicatorChange = (val: IndicatorType) => {
    setInternalIndicatorType(val);
    onTypeChange?.(val);
  };

  const handlePeriodChange = (val: string) => {
    setInternalPeriod(val);
    onPeriodChange?.(val);
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {availableTypes.length > 1 ? (
            <Segmented
              value={activeIndicatorType}
              onChange={(val) => handleIndicatorChange(val as IndicatorType)}
              options={[
                { label: "MACD(12,26,9)", value: "macd" as const },
                { label: "RSI(14)", value: "rsi" as const },
                { label: "KDJ(9,3,3)", value: "kdj" as const },
              ].filter((option) => availableTypes.includes(option.value))}
              size="small"
            />
          ) : (
            <strong className="indicator-subchart__label">
              {activeIndicatorType === "macd" ? "MACD(12,26,9)" : activeIndicatorType === "rsi" ? "RSI(14)" : "KDJ(9,3,3)"}
            </strong>
          )}
          <Segmented
            aria-label="指标周期"
            value={activePeriod}
            onChange={(val) => handlePeriodChange(String(val))}
            options={[
              { label: "日K", value: "daily" },
              { label: "周K", value: "weekly" },
              { label: "月K", value: "monthly" },
              { label: "年K", value: "annual" },
            ]}
            size="small"
          />
          <span className="stock-chart-hint" data-testid="indicator-history-range">
            {historyLimitReached
              ? `已加载近 ${MAX_KLINE_HISTORY_YEARS} 年（上限）`
              : `近 ${historyYears} 年 · 向左滑动加载更早数据（最多 ${MAX_KLINE_HISTORY_YEARS} 年）`}
          </span>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", fontSize: "var(--c-font-xs)", color: c.textSecondary, flexWrap: "wrap" }}>
          {activeDate && (
            <span style={{ color: c.textMuted, fontFamily: "var(--c-font-mono)", fontSize: "11px" }}>{activeDate}</span>
          )}
          {activeIndicatorType === "macd" && (
            <>
              <span style={{ color: c.primary, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 2, background: c.primary, display: "inline-block" }} />
                <span>DIF</span>
                {difVal != null && <strong style={{ fontFamily: "var(--c-font-mono)" }}>{difVal.toFixed(2)}</strong>}
              </span>
              <span style={{ color: c.accent, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 2, background: c.accent, display: "inline-block" }} />
                <span>DEA</span>
                {deaVal != null && <strong style={{ fontFamily: "var(--c-font-mono)" }}>{deaVal.toFixed(2)}</strong>}
              </span>
              <span style={{ color: macdHistVal != null && macdHistVal >= 0 ? c.up : c.down, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 6, height: 6, background: macdHistVal != null && macdHistVal >= 0 ? c.up : c.down, display: "inline-block" }} />
                <span>MACD柱</span>
                {macdHistVal != null && (
                  <strong style={{ fontFamily: "var(--c-font-mono)" }}>
                    {macdHistVal >= 0 ? `+${macdHistVal.toFixed(2)}` : macdHistVal.toFixed(2)}
                  </strong>
                )}
              </span>
            </>
          )}
          {activeIndicatorType === "rsi" && (
            <>
              <span style={{ color: c.accent, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 2, background: c.accent, display: "inline-block" }} />
                <span>RSI(14)</span>
                {rsiVal != null && <strong style={{ fontFamily: "var(--c-font-mono)" }}>{rsiVal.toFixed(1)}</strong>}
              </span>
              <span style={{ color: c.up, opacity: 0.8, display: "inline-flex", alignItems: "center", gap: 4 }}>
                ┄ 70超买
              </span>
              <span style={{ color: c.down, opacity: 0.8, display: "inline-flex", alignItems: "center", gap: 4 }}>
                ┄ 30超卖
              </span>
            </>
          )}
          {activeIndicatorType === "kdj" && (
            <>
              <span style={{ color: c.primary, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 2, background: c.primary, display: "inline-block" }} />
                <span>K</span>
                {kVal != null && <strong style={{ fontFamily: "var(--c-font-mono)" }}>{kVal.toFixed(2)}</strong>}
              </span>
              <span style={{ color: c.accent, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 2, background: c.accent, display: "inline-block" }} />
                <span>D</span>
                {dVal != null && <strong style={{ fontFamily: "var(--c-font-mono)" }}>{dVal.toFixed(2)}</strong>}
              </span>
              <span style={{ color: c.warning, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 2, background: c.warning, display: "inline-block" }} />
                <span>J</span>
                {jVal != null && <strong style={{ fontFamily: "var(--c-font-mono)" }}>{jVal.toFixed(2)}</strong>}
              </span>
            </>
          )}
        </div>
      </div>
      <div style={{ position: "relative", height }}>
        <div ref={chartRef} style={{ height }} />
        {isLoading && (
          <Skeleton.Node
            active
            style={{ position: "absolute", inset: 0, width: "100%", height }}
          />
        )}
      </div>
    </div>
  );
}
