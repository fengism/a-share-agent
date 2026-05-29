import { useEffect, useMemo, useRef } from "react";
import { AreaSeries, ColorType, HistogramSeries, LineStyle, createChart, type IChartApi, type UTCTimestamp } from "lightweight-charts";
import type { IntradayItem } from "../types/stock";

type Props = {
  data: IntradayItem[];
  prevClose?: number | null;
  height?: number;
};

function toTimestamp(time: string): UTCTimestamp | null {
  const text = String(time || "").trim();
  if (!text) return null;
  const match = text.match(/^(?:(\d{4})-(\d{2})-(\d{2})\s+)?(\d{2}):(\d{2})(?::(\d{2}))?/);
  if (!match) return null;
  const [, year = "2024", month = "01", day = "01", hour, minute, second = "00"] = match;
  return Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second)) / 1000 as UTCTimestamp;
}

export default function IntradayChart({ data, prevClose, height = 320 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
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
    if (!containerRef.current || rows.length === 0) return;

    chartRef.current?.remove();

    const container = containerRef.current;
    const chart = createChart(container, {
      width: container.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#111827" },
        textColor: "#9ca3af",
        fontSize: 12,
        attributionLogo: false,
      },
      grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
      timeScale: { timeVisible: true, secondsVisible: false, borderColor: "#1e293b" },
      rightPriceScale: { visible: true, borderColor: "#1e293b" },
      leftPriceScale: { visible: true, borderColor: "#1e293b" },
      crosshair: {
        vertLine: { color: "#4b5563", labelBackgroundColor: "#1e293b" },
        horzLine: { color: "#4b5563", labelBackgroundColor: "#1e293b" },
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
    });
    chartRef.current = chart;

    const priceSeries = chart.addSeries(AreaSeries, {
      lineColor: "#3b82f6",
      topColor: "rgba(59,130,246,0.18)",
      bottomColor: "rgba(59,130,246,0.02)",
      lineWidth: 2,
      priceLineVisible: false,
    });

    const avgSeries = chart.addSeries(AreaSeries, {
      lineColor: "#6366f1",
      topColor: "rgba(99,102,241,0)",
      bottomColor: "rgba(99,102,241,0)",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
    });

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

    chart.priceScale("left").applyOptions({
      visible: true,
      borderColor: "#1e293b",
      scaleMargins: { top: 0.72, bottom: 0 },
    });

    priceSeries.setData(rows.map((item) => ({ time: item.time, value: item.price })));
    avgSeries.setData(rows.filter((item) => item.avg_price != null).map((item) => ({ time: item.time, value: item.avg_price as number })));
    volumeSeries.setData(rows.map((item) => ({
      time: item.time,
      value: item.volume ?? 0,
      color: prevClose != null && item.price < prevClose ? "rgba(34,197,94,0.24)" : "rgba(239,68,68,0.24)",
    })));

    if (prevClose != null) {
      priceSeries.createPriceLine({
        price: prevClose,
        color: "#6b7280",
        lineStyle: LineStyle.Dashed,
        lineWidth: 1,
        axisLabelVisible: true,
        title: "昨收",
      });
    }

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(([entry]) => {
      const width = Math.floor(entry.contentRect.width);
      if (width <= 0) return;
      chart.applyOptions({ width, height });
      chart.timeScale().fitContent();
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [height, prevClose, rows]);

  return <div ref={containerRef} style={{ width: "100%", height, minHeight: height }} />;
}
