import { useEffect, useMemo, useRef, useState } from "react";
import { AreaSeries, ColorType, HistogramSeries, LineStyle, createChart, type IChartApi, type ISeriesApi, type UTCTimestamp, type MouseEventParams, type Time } from "lightweight-charts";
import type { IntradayItem } from "../types/stock";
import { useColors } from "../styles/ui";
import { APP_FONT_SIZE } from "../theme/typography";
import { buildIntradayVisibleRange } from "./intradayTimeRange";
import { hexToRgba } from "./utils";

type Props = {
  data: IntradayItem[];
  prevClose?: number | null;
  height?: number;
  viewKey?: string;
};

interface DisplayPoint {
  timeStr: string;
  price: number;
  avgPrice: number | null;
  volume: number | null;
}

function toTimestamp(time: string): UTCTimestamp | null {
  const text = String(time || "").trim();
  if (!text) return null;
  const match = text.match(/^(?:(\d{4})-(\d{2})-(\d{2})\s+)?(\d{2}):(\d{2})(?::(\d{2}))?/);
  if (!match) return null;
  const [, year = "2024", month = "01", day = "01", hour, minute, second = "00"] = match;
  return Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second)) / 1000 as UTCTimestamp;
}

function formatVolume(val: number | null | undefined): string {
  if (val == null || isNaN(val)) return "-";
  if (Math.abs(val) >= 1e8) return `${(val / 1e8).toFixed(2)}亿`;
  if (Math.abs(val) >= 1e4) return `${(val / 1e4).toFixed(2)}万`;
  return val.toFixed(0);
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
  const appliedRef = useRef<{ viewKey: string; firstTime: UTCTimestamp | null; length: number } | null>(null);
  const [hoverPoint, setHoverPoint] = useState<DisplayPoint | null>(null);

  const rows = useMemo(
    () => data
      .map((item) => {
        const time = toTimestamp(item.time);
        return time ? { ...item, time, rawTime: item.time } : null;
      })
      .filter((item): item is IntradayItem & { time: UTCTimestamp; rawTime: string } => item !== null),
    [data]
  );

  const latestPoint = useMemo<DisplayPoint | null>(() => {
    if (rows.length === 0) return null;
    const last = rows[rows.length - 1];
    return {
      timeStr: String(last.rawTime || "").slice(-5),
      price: last.price,
      avgPrice: last.avg_price ?? null,
      volume: last.volume ?? null,
    };
  }, [rows]);

  const activePoint = hoverPoint ?? latestPoint;

  useEffect(() => {
    if (!containerRef.current) return;

    chartRef.current?.remove();

    const container = containerRef.current;
    const colors = colorsRef.current;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: height - 32,
      layout: {
        background: { type: ColorType.Solid, color: colors.cardBg },
        textColor: colors.textSecondary,
        fontSize: APP_FONT_SIZE.sm,
        attributionLogo: false,
      },
      grid: { vertLines: { color: colors.border }, horzLines: { color: colors.border } },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: colors.border,
        fixLeftEdge: true,
        fixRightEdge: true,
      },
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
      topColor: hexToRgba(colors.primary, 0.22),
      bottomColor: hexToRgba(colors.primary, 0.01),
      lineWidth: 2,
      priceLineVisible: false,
    });
    priceSeriesRef.current = priceSeries;

    const avgSeries = chart.addSeries(AreaSeries, {
      lineColor: colors.accent,
      topColor: hexToRgba(colors.accent, 0),
      bottomColor: hexToRgba(colors.accent, 0),
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
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
      chart.applyOptions({ width, height: height - 32 });
    });
    resizeObserver.observe(container);

    const handleCrosshairMove = (param: MouseEventParams<Time>) => {
      if (!param.time || !param.seriesData) {
        setHoverPoint(null);
        return;
      }
      const pData = param.seriesData.get(priceSeries) as { value?: number } | undefined;
      const aData = param.seriesData.get(avgSeries) as { value?: number } | undefined;
      const vData = param.seriesData.get(volumeSeries) as { value?: number } | undefined;
      if (pData?.value != null && typeof param.time === "number") {
        const timeSec = param.time;
        const d = new Date(timeSec * 1000);
        const hours = String(d.getUTCHours()).padStart(2, "0");
        const minutes = String(d.getUTCMinutes()).padStart(2, "0");
        setHoverPoint({
          timeStr: `${hours}:${minutes}`,
          price: pData.value,
          avgPrice: aData?.value ?? null,
          volume: vData?.value ?? null,
        });
      }
    };

    chart.subscribeCrosshairMove(handleCrosshairMove);

    return () => {
      resizeObserver.disconnect();
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
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

    const canAppend = applied !== null
      && applied.viewKey === effectiveViewKey
      && applied.firstTime !== null
      && applied.firstTime === firstTime
      && rows.length >= applied.length
      && rows.length - applied.length <= 120;

    const volumePoint = (item: IntradayItem & { time: UTCTimestamp }, index: number) => {
      const isUp = index === 0
        ? (prevClose != null ? item.price >= prevClose : true)
        : item.price >= rows[index - 1].price;
      return {
        time: item.time,
        value: item.volume ?? 0,
        color: isUp ? hexToRgba(c.up, 0.38) : hexToRgba(c.down, 0.38),
      };
    };

    if (canAppend && applied) {
      for (let i = Math.max(0, applied.length - 1); i < rows.length; i++) {
        priceSeries.update({ time: rows[i].time, value: rows[i].price });
        volumeSeries.update(volumePoint(rows[i], i));
      }
    } else {
      priceSeries.setData(rows.map((item) => ({ time: item.time, value: item.price })));
      volumeSeries.setData(rows.map(volumePoint));
      if (rows.length > 0) {
        const visibleRange = buildIntradayVisibleRange(rows[0].time);
        if (visibleRange) chart.timeScale().setVisibleRange(visibleRange);
      }
    }

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
        title: `昨收 ${prevClose.toFixed(2)}`,
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
      topColor: hexToRgba(c.primary, 0.22),
      bottomColor: hexToRgba(c.primary, 0.01),
    });
    avgSeriesRef.current?.applyOptions({
      lineColor: c.accent,
      topColor: hexToRgba(c.accent, 0),
      bottomColor: hexToRgba(c.accent, 0),
    });
  }, [c.accent, c.border, c.cardBg, c.primary, c.textMuted, c.textSecondary, height]);

  const diffAmount = activePoint && prevClose != null ? activePoint.price - prevClose : null;
  const diffPct = activePoint && prevClose != null && prevClose > 0 ? ((activePoint.price - prevClose) / prevClose) * 100 : null;
  const priceColor = diffAmount == null || diffAmount === 0 ? c.textPrimary : diffAmount > 0 ? c.up : c.down;

  return (
    <div style={{ width: "100%", height, display: "flex", flexDirection: "column" }}>
      {/* Real-time Interactive HUD status bar */}
      <div style={{
        minHeight: 28,
        padding: "4px 8px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        fontSize: "11px",
        color: c.textSecondary,
        borderBottom: `1px solid ${c.border}`,
        fontFamily: "var(--c-font-mono)",
        userSelect: "none",
        gap: 8,
      }}>
        {activePoint ? (
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "4px 10px",
            flexWrap: "wrap",
            flex: "1 1 auto",
            minWidth: 0,
            lineHeight: 1.4,
          }}>
            <span>时间: <strong style={{ color: c.textPrimary }}>{activePoint.timeStr}</strong></span>
            <span>价格: <strong style={{ color: priceColor }}>{activePoint.price.toFixed(2)}</strong></span>
            {diffAmount != null && (
              <span style={{ color: priceColor }}>
                {diffAmount >= 0 ? `+${diffAmount.toFixed(2)}` : diffAmount.toFixed(2)} ({diffPct != null ? (diffPct >= 0 ? `+${diffPct.toFixed(2)}%` : `${diffPct.toFixed(2)}%`) : ""})
              </span>
            )}
            {activePoint.avgPrice != null && (
              <span>均价: <strong style={{ color: c.accent }}>{activePoint.avgPrice.toFixed(2)}</strong></span>
            )}
            {activePoint.volume != null && (
              <span>分量: <strong style={{ color: c.textPrimary }}>{formatVolume(activePoint.volume)}</strong></span>
            )}
          </div>
        ) : (
          <span>等待分时数据...</span>
        )}
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "11px", flex: "0 0 auto" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: c.primary }} />
            分时线
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
            <span style={{ width: 6, height: 2, background: c.accent }} />
            均价线
          </span>
          {prevClose != null && (
            <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
              <span style={{ width: 6, height: 1, borderTop: `1px dashed ${c.textMuted}` }} />
              昨收 {prevClose.toFixed(2)}
            </span>
          )}
        </div>
      </div>
      <div ref={containerRef} style={{ flex: 1, width: "100%", minHeight: height - 32 }} />
    </div>
  );
}
