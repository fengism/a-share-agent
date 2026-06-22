import { useEffect, useRef, useState } from "react";
import { Segmented, Spin } from "antd";
import { createChart, LineSeries, HistogramSeries, ColorType, type IChartApi, type BusinessDay } from "lightweight-charts";
import { useIndicators } from "../api/queries";
import type { TechnicalIndicators } from "../types/stock";
import { useColors } from "../styles/ui";

type Props = { code: string };
type IndicatorType = "macd" | "rsi" | "kdj";

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


function macdChart(
  chart: IChartApi,
  seriesData: TechnicalIndicators["series"],
  dates: BusinessDay[],

) {
  const dif = chart.addSeries(LineSeries, {
    color: "#4a9eff", lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
    priceFormat: { type: "custom", minMove: 0.01, formatter: (v: number) => v.toFixed(2) },
  });
  const dea = chart.addSeries(LineSeries, {
    color: "#f5a623", lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
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
    if (h != null) histData.push({ time: dates[i], value: h, color: h >= 0 ? "#e74c3c" : "#2ecc71" });
    if (d != null) difData.push({ time: dates[i], value: d });
    if (e != null) deaData.push({ time: dates[i], value: e });
  }

  dif.setData(difData);
  dea.setData(deaData);
  hist.setData(histData);

  chart.priceScale("right").applyOptions({
    scaleMargins: { top: 0.12, bottom: 0.12 },
  });
}

function rsiChart(
  chart: IChartApi,
  series: TechnicalIndicators["series"],
  dates: BusinessDay[],

) {
  const rsiLine = chart.addSeries(LineSeries, {
    color: "#ab47bc", lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
    priceFormat: { type: "custom", minMove: 0.1, formatter: (v: number) => v.toFixed(1) },
  });

  const data: { time: BusinessDay; value: number }[] = [];
  for (let i = 0; i < dates.length; i++) {
    const v = series.rsi?.[i];
    if (v != null) data.push({ time: dates[i], value: v });
  }
  rsiLine.setData(data);

  // Reference lines at 70 and 30 using price line series
  const ref70 = chart.addSeries(LineSeries, {
    color: hexToRgba("#e74c3c", 0.3), lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false,
  });
  const ref30 = chart.addSeries(LineSeries, {
    color: hexToRgba("#2ecc71", 0.3), lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false,
  });

  if (data.length >= 2) {
    ref70.setData([
      { time: data[0].time, value: 70 },
      { time: data[data.length - 1].time, value: 70 },
    ]);
    ref30.setData([
      { time: data[0].time, value: 30 },
      { time: data[data.length - 1].time, value: 30 },
    ]);
  }

  chart.priceScale("right").applyOptions({
    scaleMargins: { top: 0.12, bottom: 0.12 },
  });
}

function kdjChart(
  chart: IChartApi,
  series: TechnicalIndicators["series"],
  dates: BusinessDay[],

) {
  const kLine = chart.addSeries(LineSeries, {
    color: "#4a9eff", lineWidth: 1, priceLineVisible: false, lastValueVisible: true,
    priceFormat: { type: "custom", minMove: 0.01, formatter: (v: number) => v.toFixed(2) },
  });
  const dLine = chart.addSeries(LineSeries, {
    color: "#f5a623", lineWidth: 1, priceLineVisible: false, lastValueVisible: true,
    priceFormat: { type: "custom", minMove: 0.01, formatter: (v: number) => v.toFixed(2) },
  });
  const jLine = chart.addSeries(LineSeries, {
    color: "#ab47bc", lineWidth: 1, priceLineVisible: false, lastValueVisible: true,
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
}

export default function IndicatorSubCharts({ code }: Props) {
  const c = useColors();
  const [indicatorType, setIndicatorType] = useState<IndicatorType>("macd");
  const { data: indicators, isLoading } = useIndicators(code);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartRef.current || !indicators?.series) return;

    chartInstanceRef.current?.remove();
    const dates = indicators.series.dates?.map((d) => toBusinessDay(d)).filter((d): d is BusinessDay => d !== null) || [];
    if (dates.length === 0) return;

    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 180,
      layout: { background: { type: ColorType.Solid, color: c.cardBg }, textColor: c.textSecondary, fontSize: 11, attributionLogo: false },
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
    chartInstanceRef.current = chart;


    switch (indicatorType) {
      case "macd":
        macdChart(chart, indicators.series, dates);
        break;
      case "rsi":
        rsiChart(chart, indicators.series, dates);
        break;
      case "kdj":
        kdjChart(chart, indicators.series, dates);
        break;
    }

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(([entry]) => {
      chart.applyOptions({ width: Math.floor(entry.contentRect.width) });
    });
    resizeObserver.observe(chartRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartInstanceRef.current = null;
    };
  }, [indicatorType, indicators, c.cardBg, c.border, c.down, c.textMuted, c.textSecondary, c.up, c.primary]);

  return (
    <div>
      <Segmented
        value={indicatorType}
        onChange={(val) => setIndicatorType(val as IndicatorType)}
        options={[
          { label: "MACD", value: "macd" },
          { label: "RSI", value: "rsi" },
          { label: "KDJ", value: "kdj" },
        ]}
        style={{ marginBottom: 8 }}
        size="small"
      />
      {isLoading ? (
        <div style={{ textAlign: "center", padding: 20 }}><Spin /></div>
      ) : (
        <div ref={chartRef} />
      )}
    </div>
  );
}
