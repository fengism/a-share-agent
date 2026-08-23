import { useEffect, useMemo, useRef } from "react";
import { AreaSeries, ColorType, HistogramSeries, LineStyle, createChart, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
import type { IntradayItem } from "../types/stock";
import { useColors } from "../styles/ui";
import { buildIntradayVisibleRange } from "./intradayTimeRange";
import { hexToRgba } from "./utils";

type Props = {
  data: IntradayItem[];
  prevClose?: number | null;
  height?: number;
  viewKey?: string;
};

function toTimestamp(time: string): UTCTimestamp | null {
  const text = String(time || "").trim();
  if (!text) return null;
  const match = text.match(/^(?:(\d{4})-(\d{2})-(\d{2})\s+)?(\d{2}):(\d{2})(?::(\d{2}))?/);
  if (!match) return null;
  const [, year = "2024", month = "01", day = "01", hour, minute, second = "00"] = match;
  return Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second)) / 1000 as UTCTimestamp;
}

export default function IntradayChart({ data, prevClose, height = 320, viewKey }: Props) {
  const c = useColors();
  const colorsRef = useRef(c);
  colorsRef.current = c;
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const priceSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const avgSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const priceLineRef = useRef<ReturnType<ISeriesApi<"Area">["createPriceLine"]> | null>(null);
  // Tracks what was last pushed into the series so a poll that only appends
  // recent rows can use series.update() instead of a full setData, which would
  // also discard any visible range the chart recreates from scratch.
  const appliedRef = useRef<{ viewKey: string; firstTime: UTCTimestamp | null; length: number } | null>(null);
  const rows = useMemo(
    () => data
      .map((item) => {
        const time = toTimestamp(item.time);
        return time ? { ...item, time } : null;
      })
      .filter((item): item is IntradayItem & { time: UTCTimestamp } => item !== null),
    [data]
  );

  useEffect(() => {
    if (!containerRef.current) return;

    chartRef.current?.remove();

    const container = containerRef.current;
    const colors = colorsRef.current;
    const chart = createChart(container, {
      width: container.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: colors.cardBg },
        textColor: colors.textSecondary,
        fontSize: 12,
        attributionLogo: false,
      },
      grid: { vertLines: { color: colors.border }, horzLines: { color: colors.border } },
      timeScale: { timeVisible: true, secondsVisible: false, borderColor: colors.border },
      rightPriceScale: { visible: true, borderColor: colors.border },
      leftPriceScale: { visible: true, borderColor: colors.border },
      crosshair: {
        vertLine: { color: colors.textMuted, labelBackgroundColor: colors.border },
        horzLine: { color: colors.textMuted, labelBackgroundColor: colors.border },
      },
      handleScroll: false,
      handleScale: { mouseWheel: false, pinch: false, axisPressedMouseMove: { time: false, price: true } },
    });
    chartRef.current = chart;

    const priceSeries = chart.addSeries(AreaSeries, {
      lineColor: colors.primary,
      topColor: hexToRgba(colors.primary, 0.18),
      bottomColor: hexToRgba(colors.primary, 0.02),
      lineWidth: 2,
      priceLineVisible: false,
    });
    priceSeriesRef.current = priceSeries;

    const avgSeries = chart.addSeries(AreaSeries, {
      lineColor: colors.accent,
      topColor: hexToRgba(colors.accent, 0),
      bottomColor: hexToRgba(colors.accent, 0),
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
    });
    avgSeriesRef.current = avgSeries;

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceScaleId: "left",
      priceLineVisible: false,
      priceFormat: {
        type: "custom",
        minMove: 1,
        formatter: (value: number) => Math.abs(value) >= 1e8
          ? `${(value / 1e8).toFixed(2)}亿`
          : `${(value / 1e4).toFixed(2)}万`,
      },
    });
    volumeSeriesRef.current = volumeSeries;

    chart.priceScale("left").applyOptions({
      visible: true,
      borderColor: colors.border,
      scaleMargins: { top: 0.72, bottom: 0 },
    });

    const resizeObserver = new ResizeObserver(([entry]) => {
      const width = Math.floor(entry.contentRect.width);
      if (width <= 0) return;
      chart.applyOptions({ width, height });
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      priceSeriesRef.current = null;
      avgSeriesRef.current = null;
      volumeSeriesRef.current = null;
      priceLineRef.current = null;
      appliedRef.current = null;
    };
  }, [height]);

  useEffect(() => {
    const chart = chartRef.current;
    const priceSeries = priceSeriesRef.current;
    const avgSeries = avgSeriesRef.current;
    const volumeSeries = volumeSeriesRef.current;
    if (!chart || !priceSeries || !avgSeries || !volumeSeries) return;

    const effectiveViewKey = viewKey ?? "";
    const firstTime = rows.length > 0 ? rows[0].time : null;
    const applied = appliedRef.current;
    // Append-only refresh (typical 30s poll during trading hours): rewrite only
    // the trailing rows so the user's zoom/pan state survives.
    const canAppend = applied !== null
      && applied.viewKey === effectiveViewKey
      && applied.firstTime !== null
      && applied.firstTime === firstTime
      && rows.length >= applied.length
      && rows.length - applied.length <= 120;

    const volumePoint = (item: IntradayItem & { time: UTCTimestamp }) => ({
      time: item.time,
      value: item.volume ?? 0,
      color: prevClose != null && item.price < prevClose
        ? hexToRgba(c.down, 0.24)
        : hexToRgba(c.up, 0.24),
    });

    if (canAppend && applied) {
      for (let i = Math.max(0, applied.length - 1); i < rows.length; i++) {
        priceSeries.update({ time: rows[i].time, value: rows[i].price });
        volumeSeries.update(volumePoint(rows[i]));
      }
    } else {
      priceSeries.setData(rows.map((item) => ({ time: item.time, value: item.price })));
      volumeSeries.setData(rows.map(volumePoint));
      if (rows.length > 0) {
        const visibleRange = buildIntradayVisibleRange(rows[0].time);
        if (visibleRange) chart.timeScale().setVisibleRange(visibleRange);
      }
    }
    // The average line is sparse (nulls filtered out) and cheap to rebuild.
    avgSeries.setData(rows
      .filter((item) => item.avg_price != null)
      .map((item) => ({ time: item.time, value: item.avg_price as number })));

    appliedRef.current = { viewKey: effectiveViewKey, firstTime, length: rows.length };

    if (priceLineRef.current) {
      priceSeries.removePriceLine(priceLineRef.current);
      priceLineRef.current = null;
    }
    if (prevClose != null) {
      priceLineRef.current = priceSeries.createPriceLine({
        price: prevClose,
        color: c.textMuted,
        lineStyle: LineStyle.Dashed,
        lineWidth: 1,
        axisLabelVisible: true,
        title: "昨收",
      });
    }
  }, [c.down, c.up, c.textMuted, height, prevClose, rows, viewKey]);

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
    priceSeriesRef.current?.applyOptions({
      lineColor: c.primary,
      topColor: hexToRgba(c.primary, 0.18),
      bottomColor: hexToRgba(c.primary, 0.02),
    });
    avgSeriesRef.current?.applyOptions({
      lineColor: c.accent,
      topColor: hexToRgba(c.accent, 0),
      bottomColor: hexToRgba(c.accent, 0),
    });
  }, [c.accent, c.border, c.cardBg, c.primary, c.textMuted, c.textSecondary, height]);

  return <div ref={containerRef} style={{ width: "100%", height, minHeight: height }} />;
}
