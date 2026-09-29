import { useEffect, useRef, useState } from "react";
import { Segmented, Skeleton } from "antd";
import { createChart, LineSeries, HistogramSeries, ColorType, type IChartApi, type ISeriesApi, type BusinessDay } from "lightweight-charts";
import { useIndicators } from "../api/queries";
import type { TechnicalIndicators } from "../types/stock";
import { useColors } from "../styles/ui";
import { APP_FONT_SIZE } from "../theme/typography";
import type { ThemeColors } from "../theme/themes";
import { createDebouncedResizeHandler, shouldFitChartContent } from "./chartLifecycle";
import { toBusinessDay, hexToRgba } from "./utils";

export type IndicatorType = "macd" | "rsi" | "kdj";
type Props = {
  code: string;
  types?: readonly IndicatorType[];
  height?: number;
  activeType?: IndicatorType;
  onTypeChange?: (type: IndicatorType) => void;
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
}: Props) {
  const c = useColors();
  const colorsRef = useRef(c);
  colorsRef.current = c;
  const [internalIndicatorType, setInternalIndicatorType] = useState<IndicatorType>(
    controlledActiveType ?? types[0] ?? "macd",
  );
  const availableTypes = types.length > 0 ? types : DEFAULT_INDICATOR_TYPES;
  const activeIndicatorType = controlledActiveType ?? (
    availableTypes.includes(internalIndicatorType) ? internalIndicatorType : availableTypes[0]
  );
  const { data: indicators, isLoading } = useIndicators(code);
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
      handleScroll: { mouseWheel: true, pressedMouseMove: false, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
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

    return () => {
      resizeObserver.disconnect();
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

    const viewKey = `${code}:${activeIndicatorType}`;
    if (shouldFitChartContent(fittedViewKeyRef.current, viewKey)) {
      chart.timeScale().fitContent();
      fittedViewKeyRef.current = viewKey;
    }
  }, [activeIndicatorType, c, code, indicators]);

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

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
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
        <div style={{ display: "flex", gap: 12, alignItems: "center", fontSize: "var(--c-font-xs)", color: c.textSecondary }}>
          {activeIndicatorType === "macd" && (
            <>
              <span style={{ color: c.primary, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 2, background: c.primary, display: "inline-block" }} /> DIF
              </span>
              <span style={{ color: c.accent, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 2, background: c.accent, display: "inline-block" }} /> DEA
              </span>
              <span style={{ color: c.up, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 6, height: 6, background: c.up, display: "inline-block" }} /> MACD柱
              </span>
            </>
          )}
          {activeIndicatorType === "rsi" && (
            <>
              <span style={{ color: c.accent, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 2, background: c.accent, display: "inline-block" }} /> RSI(14)
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
                <span style={{ width: 8, height: 2, background: c.primary, display: "inline-block" }} /> K
              </span>
              <span style={{ color: c.accent, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 2, background: c.accent, display: "inline-block" }} /> D
              </span>
              <span style={{ color: c.warning, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 8, height: 2, background: c.warning, display: "inline-block" }} /> J
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
