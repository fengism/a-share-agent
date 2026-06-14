import { useEffect, useMemo, useRef, useState } from "react";
import { createChart, CandlestickSeries, HistogramSeries, ColorType, type IChartApi, type BusinessDay } from "lightweight-charts";
import type { KlineItem } from "../types/stock";
import { useColors } from "../styles/ui";

type Props = { data: KlineItem[]; height?: number };
type ChartItem = Omit<KlineItem, "date"> & { date: BusinessDay };

function toBusinessDay(value: string): BusinessDay | null {
  const text = String(value || "").trim();
  if (!text) return null;
  const normalized = /^\d{8}$/.test(text)
    ? `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`
    : /^\d{4}[/-]\d{2}[/-]\d{2}/.test(text)
      ? text.slice(0, 10).replace(/\//g, "-")
      : null;
  if (!normalized) return null;
  const [year, month, day] = normalized.split("-").map(Number);
  return year && month && day ? { year, month, day } : null;
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

export default function KlineChart({ data, height = 500 }: Props) {
  const c = useColors();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const chartElRef = useRef<HTMLDivElement>(null);
  const brushRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [isZoomed, setIsZoomed] = useState(false);
  const rows = useMemo<ChartItem[]>(
    () => data
      .map((item) => {
        const date = toBusinessDay(item.date);
        return date ? { ...item, date } : null;
      })
      .filter((item): item is ChartItem => item !== null),
    [data]
  );

  useEffect(() => {
    if (!wrapperRef.current || !chartElRef.current || !brushRef.current || rows.length === 0) return;
    chartRef.current?.remove();

    const chart = createChart(chartElRef.current, {
      width: chartElRef.current.clientWidth,
      height,
      layout: { background: { type: ColorType.Solid, color: c.cardBg }, textColor: c.textSecondary, fontSize: 12, attributionLogo: false },
      grid: { vertLines: { color: c.border }, horzLines: { color: c.border } },
      timeScale: { timeVisible: false, borderColor: c.border },
      rightPriceScale: { visible: true, borderColor: c.border },
      crosshair: {
        vertLine: { color: c.textMuted, labelBackgroundColor: c.border },
        horzLine: { color: c.textMuted, labelBackgroundColor: c.border },
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: false, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
    });
    chartRef.current = chart;

    const candle = chart.addSeries(CandlestickSeries, {
      upColor: c.up, downColor: c.down,
      borderUpColor: c.up, borderDownColor: c.down,
      wickUpColor: c.up, wickDownColor: c.down,
      priceScaleId: "right",
    });
    chart.priceScale("right").applyOptions({
      visible: true, borderColor: c.border,
      scaleMargins: { top: 0.05, bottom: 0.22 },
    });

    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "custom", minMove: 1,
        formatter: (value: number) => Math.abs(value) >= 1e8
          ? `${(value / 1e8).toFixed(2)}亿` : `${(value / 1e4).toFixed(2)}万`,
      },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      visible: false, scaleMargins: { top: 0.82, bottom: 0 },
    });

    candle.setData(rows.map((item) => ({ time: item.date, open: item.open, high: item.high, low: item.low, close: item.close })));
    volume.setData(rows.map((item) => ({
      time: item.date,
      value: item.amount ?? item.volume,
      color: item.close >= item.open ? hexToRgba(c.up, 0.5) : hexToRgba(c.down, 0.5),
    })));
    chart.timeScale().fitContent();

    const wrapper = wrapperRef.current;
    const brush = brushRef.current;
    const resizeObserver = new ResizeObserver(([entry]) => {
      chart.applyOptions({ width: Math.floor(entry.contentRect.width) });
    });
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

    const handleMouseLeave = () => { startX = null; resetBrush(); wrapper.style.cursor = "default"; };
    const handleDoubleClick = () => { chart.timeScale().fitContent(); setIsZoomed(false); };

    wrapper.addEventListener("mousedown", handleMouseDown);
    wrapper.addEventListener("mousemove", handleMouseMove);
    wrapper.addEventListener("mouseup", handleMouseUp);
    wrapper.addEventListener("mouseleave", handleMouseLeave);
    wrapper.addEventListener("dblclick", handleDoubleClick);

    return () => {
      resizeObserver.disconnect();
      wrapper.removeEventListener("mousedown", handleMouseDown);
      wrapper.removeEventListener("mousemove", handleMouseMove);
      wrapper.removeEventListener("mouseup", handleMouseUp);
      wrapper.removeEventListener("mouseleave", handleMouseLeave);
      wrapper.removeEventListener("dblclick", handleDoubleClick);
      chart.remove();
      chartRef.current = null;
    };
  }, [height, rows, c.pageBg]);

  return (
    <div ref={wrapperRef} style={{ position: "relative", width: "100%" }}>
      <div ref={chartElRef} />
      <div ref={brushRef} style={{
        position: "absolute", top: 0, bottom: 0, display: "none", pointerEvents: "none",
        background: hexToRgba(c.primary, 0.12), border: `1px solid ${hexToRgba(c.primary, 0.35)}`,
      }} />
      <div style={{ position: "absolute", right: 12, top: 12, display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
        <div style={{
          padding: "6px 10px", fontSize: 12, color: c.textSecondary,
          background: hexToRgba(c.pageBg, 0.96), border: `1px solid ${c.border}`,
          borderRadius: 8, boxShadow: "0 1px 4px rgba(0,0,0,0.2)", pointerEvents: "none",
        }}>
          左键拖拽框选缩放，双击重置
        </div>
        {isZoomed && (
          <button type="button" onClick={() => { chartRef.current?.timeScale().fitContent(); setIsZoomed(false); }}
            style={{
              padding: "8px 12px", fontSize: 12, fontWeight: 600, color: c.primary,
              background: hexToRgba(c.pageBg, 0.98), border: `1px solid ${c.border}`,
              borderRadius: 999, cursor: "pointer", boxShadow: `0 4px 12px ${hexToRgba(c.primary, 0.15)}`,
            }}>
            返回全视图
          </button>
        )}
      </div>
    </div>
  );
}
