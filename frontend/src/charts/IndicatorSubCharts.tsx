import { useEffect, useRef, useState } from "react";
import { Segmented, Spin } from "antd";
import { createChart, LineSeries, HistogramSeries, ColorType, type IChartApi, type BusinessDay } from "lightweight-charts";
import { useIndicators } from "../api/queries";
import type { TechnicalIndicators } from "../types/stock";
import { useColors } from "../styles/ui";
import type { ThemeColors } from "../theme/themes";
import { toBusinessDay, hexToRgba } from "./utils";

type Props = { code: string };
type IndicatorType = "macd" | "rsi" | "kdj";


function macdChart(
  chart: IChartApi,
  seriesData: TechnicalIndicators["series"],
  dates: BusinessDay[],
  c: ThemeColors,
) {
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
}

function rsiChart(
  chart: IChartApi,
  series: TechnicalIndicators["series"],
  dates: BusinessDay[],
  c: ThemeColors,
) {
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

  // Reference lines at 70 and 30 using price line series
  const ref70 = chart.addSeries(LineSeries, {
    color: hexToRgba(c.up, 0.3), lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false,
  });
  const ref30 = chart.addSeries(LineSeries, {
    color: hexToRgba(c.down, 0.3), lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false,
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
  c: ThemeColors,
) {
  const kLine = chart.addSeries(LineSeries, {
    color: c.primary, lineWidth: 1, priceLineVisible: false, lastValueVisible: true,
    priceFormat: { type: "custom", minMove: 0.01, formatter: (v: number) => v.toFixed(2) },
  });
  const dLine = chart.addSeries(LineSeries, {
    color: c.accent, lineWidth: 1, priceLineVisible: false, lastValueVisible: true,
    priceFormat: { type: "custom", minMove: 0.01, formatter: (v: number) => v.toFixed(2) },
  });
  const jLine = chart.addSeries(LineSeries, {
    color: c.textSecondary, lineWidth: 1, priceLineVisible: false, lastValueVisible: true,
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
        macdChart(chart, indicators.series, dates, c);
        break;
      case "rsi":
        rsiChart(chart, indicators.series, dates, c);
        break;
      case "kdj":
        kdjChart(chart, indicators.series, dates, c);
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
  }, [indicatorType, indicators, c]);

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
