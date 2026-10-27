import { useEffect, useMemo, useRef, useState } from "react";
import { AreaSeries, ColorType, HistogramSeries, LineStyle, createChart, type AutoscaleInfoProvider, type IChartApi, type ISeriesApi, type UTCTimestamp, type MouseEventParams, type Time } from "lightweight-charts";
import type { IntradayItem } from "../types/stock";
import { useColors } from "../styles/ui";
import { APP_FONT_FAMILY, APP_FONT_SIZE } from "../theme/typography";
import { createDebouncedResizeHandler } from "./chartLifecycle";
import { buildIntradayVisibleRange } from "./intradayTimeRange";
import { VOLUME_PANE_INDEX, PRICE_PANE_RATIO, applyVolumePaneLayout, getChartPaneThemeConfig } from "./chartPaneLayout";
import { hexToRgba } from "./utils";

type Props = {
  data: IntradayItem[];
  prevClose?: number | null;
  height?: number;
  viewKey?: string;
  showAvgLine?: boolean;
  showPrevCloseLine?: boolean;
  market?: "cn" | "hk";
};

interface DisplayPoint {
  timeStr: string;
  price: number;
  avgPrice: number | null;
  volume: number | null;
  amount: number | null;
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

function formatAmount(val: number | null | undefined): string {
  if (val == null || isNaN(val)) return "-";
  if (Math.abs(val) >= 1e8) return `${(val / 1e8).toFixed(2)}亿`;
  if (Math.abs(val) >= 1e4) return `${(val / 1e4).toFixed(2)}万`;
  return val.toFixed(0);
}

function formatIntradayTime(rawTime: string | null | undefined): string {
  if (!rawTime) return "";
  const str = String(rawTime).trim();
  const dateMatch = str.match(/^(\d{4}[-/]\d{1,2}[-/]\d{1,2})/);
  const timeMatch = str.match(/(\d{2}:\d{2})/);
  if (dateMatch && timeMatch) {
    return `${dateMatch[1]} ${timeMatch[1]}`;
  }
  if (timeMatch) {
    return timeMatch[1];
  }
  return str.slice(-5);
}

export default function IntradayChart({
  data,
  prevClose,
  height = 380,
  viewKey,
  showAvgLine = true,
  showPrevCloseLine = true,
  market,
}: Props) {
  const c = useColors();
  const colorsRef = useRef(c);
  colorsRef.current = c;
  const prevCloseRef = useRef(prevClose);
  prevCloseRef.current = prevClose;
  const hudRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const priceSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const avgSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const priceLineRef = useRef<ReturnType<ISeriesApi<"Area">["createPriceLine"]> | null>(null);
  const appliedRef = useRef<{ viewKey: string; firstTime: UTCTimestamp | null; length: number } | null>(null);
  const [hoverPoint, setHoverPoint] = useState<DisplayPoint | null>(null);
  const [paneRatio, setPaneRatio] = useState<number>(PRICE_PANE_RATIO);
  const [pane0Height, setPane0Height] = useState<number>(() => Math.floor((height - 32) * PRICE_PANE_RATIO));
  const [rightScaleWidth, setRightScaleWidth] = useState<number>(58);

  const rows = useMemo(
    () => data
      .map((item) => {
        const time = toTimestamp(item.time);
        return time ? { ...item, time, rawTime: item.time } : null;
      })
      .filter((item): item is IntradayItem & { time: UTCTimestamp; rawTime: string } => item !== null),
    [data]
  );

  const resolvedMarket = useMemo<"cn" | "hk">(() => {
    if (market) return market;
    if (viewKey) {
      const cleanKey = viewKey.toLowerCase().replace(/^(?:stock|index):/, "");
      if (cleanKey.startsWith("hk") || /^\d{5}$/.test(cleanKey) || cleanKey === "hsi" || cleanKey === "hstech" || cleanKey === "hscei") {
        return "hk";
      }
    }
    if (rows.length > 0) {
      const lastRow = rows[rows.length - 1];
      const d = new Date(lastRow.time * 1000);
      const hours = d.getUTCHours();
      const mins = d.getUTCMinutes();
      if (hours > 15 || (hours === 15 && mins > 0)) {
        return "hk";
      }
    }
    return "cn";
  }, [market, viewKey, rows]);

  const timeToRowMap = useMemo(() => {
    const map = new Map<number, (typeof rows)[number]>();
    for (const r of rows) {
      map.set(r.time, r);
    }
    return map;
  }, [rows]);
  const timeToRowMapRef = useRef(timeToRowMap);
  timeToRowMapRef.current = timeToRowMap;

  const latestPoint = useMemo<DisplayPoint | null>(() => {
    if (rows.length === 0) return null;
    const last = rows[rows.length - 1];
    return {
      timeStr: formatIntradayTime(last.rawTime),
      price: last.price,
      avgPrice: last.avg_price ?? null,
      volume: last.volume ?? null,
      amount: last.amount ?? null,
    };
  }, [rows]);

  const sessionStats = useMemo(() => {
    if (rows.length === 0) return null;
    let high = -Infinity;
    let low = Infinity;
    for (const r of rows) {
      if (r.price > high) high = r.price;
      if (r.price < low) low = r.price;
    }
    return { high, low };
  }, [rows]);

  const maxPct = useMemo(() => {
    if (!prevClose || prevClose <= 0 || !sessionStats) return 0.5;
    const maxDelta = Math.max(
      Math.abs(sessionStats.high - prevClose),
      Math.abs(sessionStats.low - prevClose)
    );
    const minDelta = prevClose * 0.002;
    const effectiveDelta = Math.max(maxDelta, minDelta);
    return (effectiveDelta / prevClose) * 100;
  }, [prevClose, sessionStats]);

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

  const selectedIndexRef = useRef<number | null>(null);

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
      setHoverPoint({
        timeStr: formatIntradayTime(target.rawTime),
        price: target.price,
        avgPrice: target.avg_price ?? null,
        volume: target.volume ?? null,
        amount: target.amount ?? null,
      });
    } else if (e.key === "Escape") {
      selectedIndexRef.current = null;
      setHoverPoint(null);
    }
  };

  const activePoint = hoverPoint ?? latestPoint;

  useEffect(() => {
    if (!containerRef.current) return;

    chartRef.current?.remove();

    const container = containerRef.current;
    const colors = colorsRef.current;
    const initialHudHeight = hudRef.current?.clientHeight || 32;
    const chart = createChart(container, {
      width: container.clientWidth,
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
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: colors.border,
        fixLeftEdge: true,
        fixRightEdge: true,
      },
      // 价格与成交量各自独立窗格、各自独立量纲，两条轴都放右侧（同花顺/通达信布局）。
      // 左侧轴必须整体关闭，详见 chartPaneLayout.ts 里 lightweight-charts 5.2.1 的多窗格缺陷。
      rightPriceScale: { visible: true, borderColor: colors.border },
      leftPriceScale: { visible: false, borderColor: colors.border },
      crosshair: {
        vertLine: { color: colors.textMuted, labelBackgroundColor: colors.border },
        horzLine: { color: colors.textMuted, labelBackgroundColor: colors.border },
      },
      handleScroll: false,
      handleScale: { mouseWheel: false, pinch: false, axisPressedMouseMove: { time: false, price: true } },
      trackingMode: { exitMode: 0 },
    });
    chartRef.current = chart;

    const priceSeries = chart.addSeries(AreaSeries, {
      lineColor: colors.primary,
      topColor: hexToRgba(colors.primary, 0.22),
      bottomColor: hexToRgba(colors.primary, 0.01),
      lineWidth: 2,
      priceLineVisible: false,
      priceScaleId: "right",
      autoscaleInfoProvider: ((original) => {
        const res = original();
        const base = prevCloseRef.current;
        // priceRange 也可能为 null（序列无有效数据），必须一并判空，
        // 否则解构 .maxValue 会在运行时抛错、整张分时图不渲染。
        if (!res?.priceRange || base == null || !Number.isFinite(base) || base <= 0) {
          return res;
        }
        const maxDelta = Math.max(
          Math.abs(res.priceRange.maxValue - base),
          Math.abs(res.priceRange.minValue - base)
        );
        const minDelta = base * 0.002;
        const effectiveDelta = Math.max(maxDelta, minDelta);
        return {
          priceRange: {
            minValue: base - effectiveDelta,
            maxValue: base + effectiveDelta,
          },
        };
      }) satisfies AutoscaleInfoProvider,
    });
    priceSeriesRef.current = priceSeries;

    const avgSeries = chart.addSeries(AreaSeries, {
      lineColor: colors.accent,
      topColor: hexToRgba(colors.accent, 0),
      bottomColor: hexToRgba(colors.accent, 0),
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      priceLineVisible: false,
      priceScaleId: "right",
      autoscaleInfoProvider: () => null,
    });
    avgSeriesRef.current = avgSeries;

    chart.priceScale("right", 0).applyOptions({
      borderColor: colors.border,
      scaleMargins: { top: 0.08, bottom: 0.08 },
    });

    // 成交量放到独立的下窗格：分时价与分时量量纲差几个数量级，
    // 共享一个绘图区时量柱会被压在底部一条窄缝里
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceScaleId: "right",
      priceLineVisible: false,
      priceFormat: {
        type: "custom",
        minMove: 1,
        formatter: (value: number) => Math.abs(value) >= 1e8
          ? `${(value / 1e8).toFixed(2)}亿`
          : `${(value / 1e4).toFixed(2)}万`,
      },
    }, VOLUME_PANE_INDEX);
    volumeSeriesRef.current = volumeSeries;

    chart.priceScale("right", VOLUME_PANE_INDEX).applyOptions({
      borderColor: colors.border,
      scaleMargins: { top: 0.18, bottom: 0 },
    });
    applyVolumePaneLayout(chart, paneRatio);
    updateLayoutMetrics();

    const resizeObserver = new ResizeObserver(
      createDebouncedResizeHandler((entry) => {
        const width = Math.floor(entry.contentRect.width);
        if (width <= 0) return;
        const hudHeight = hudRef.current?.clientHeight ?? 32;
        chart.applyOptions({ width, height: Math.max(100, height - hudHeight) });
        updateLayoutMetrics();
      })
    );
    resizeObserver.observe(container);

    const handleCrosshairMove = (param: MouseEventParams<Time>) => {
      if (!param.time || !param.seriesData) {
        if (selectedIndexRef.current === null) {
          setHoverPoint(null);
        }
        return;
      }
      selectedIndexRef.current = null;
      const pData = param.seriesData.get(priceSeries) as { value?: number } | undefined;
      const aData = param.seriesData.get(avgSeries) as { value?: number } | undefined;
      const vData = param.seriesData.get(volumeSeries) as { value?: number } | undefined;
      if (pData?.value != null && typeof param.time === "number") {
        const timeSec = param.time;
        const row = timeToRowMapRef.current.get(timeSec as UTCTimestamp);
        let timeStr: string;
        if (row?.rawTime) {
          timeStr = formatIntradayTime(row.rawTime);
        } else {
          const d = new Date(timeSec * 1000);
          const hours = String(d.getUTCHours()).padStart(2, "0");
          const minutes = String(d.getUTCMinutes()).padStart(2, "0");
          timeStr = `${hours}:${minutes}`;
        }
        setHoverPoint({
          timeStr,
          price: pData.value,
          avgPrice: aData?.value ?? row?.avg_price ?? null,
          volume: vData?.value ?? row?.volume ?? null,
          amount: row?.amount ?? null,
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
  }, [height, paneRatio]);

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
      const prevPrice = index === 0 ? prevClose : rows[index - 1].price;
      const isUp = prevPrice != null
        ? (item.price > prevPrice || (item.price === prevPrice && (prevClose != null ? item.price >= prevClose : true)))
        : true;
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
        const visibleRange = buildIntradayVisibleRange(rows[0].time, resolvedMarket);
        if (visibleRange) chart.timeScale().setVisibleRange(visibleRange);
      }
    }

    if (showAvgLine) {
      avgSeries.setData(rows
        .filter((item) => item.avg_price != null)
        .map((item) => ({ time: item.time, value: item.avg_price as number })));
    } else {
      avgSeries.setData([]);
    }

    appliedRef.current = { viewKey: effectiveViewKey, firstTime, length: rows.length };

    if (priceLineRef.current) {
      priceSeries.removePriceLine(priceLineRef.current);
      priceLineRef.current = null;
    }
    if (prevClose != null && showPrevCloseLine) {
      priceLineRef.current = priceSeries.createPriceLine({
        price: prevClose,
        color: c.textMuted,
        lineStyle: LineStyle.Dashed,
        lineWidth: 1,
        axisLabelVisible: true,
        title: `昨收 ${prevClose.toFixed(2)} (0.0%)`,
      });
    }
  }, [c.down, c.up, c.textMuted, height, prevClose, resolvedMarket, rows, showAvgLine, showPrevCloseLine, viewKey]);

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
    chart.priceScale("right", 0).applyOptions({ borderColor: c.border });
    chart.priceScale("right", VOLUME_PANE_INDEX).applyOptions({ borderColor: c.border });
  }, [c, height]);

  const diffAmount = activePoint && prevClose != null ? activePoint.price - prevClose : null;
  const diffPct = activePoint && prevClose != null && prevClose > 0 ? ((activePoint.price - prevClose) / prevClose) * 100 : null;
  const priceColor = diffAmount == null || diffAmount === 0 ? c.textPrimary : diffAmount > 0 ? c.up : c.down;

  return (
    <div
      tabIndex={0}
      role="region"
      aria-label="分时图交互区"
      onKeyDown={handleKeyDown}
      style={{
        position: "relative",
        width: "100%",
        height,
        display: "flex",
        flexDirection: "column",
        backgroundColor: c.cardBg,
        outline: "none",
      }}
    >
      {/* Real-time Interactive HUD status bar */}
      <div
        ref={hudRef}
        className="intraday-chart__hud"
        style={{
          minHeight: 32,
          flexWrap: "wrap",
          rowGap: 4,
          columnGap: 8,
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
        }}
      >
        {activePoint ? (
          <div className="intraday-chart__hud-stats" style={{
            display: "flex",
            alignItems: "center",
            gap: "4px 8px",
            flexWrap: "wrap",
            flex: "1 1 auto",
            minWidth: 0,
            lineHeight: 1.4,
          }}>
            <span style={{
              color: c.textPrimary,
              fontWeight: 700,
              minWidth: activePoint.timeStr.length > 5 ? 110 : 40,
              flexShrink: 0,
              paddingRight: 6,
              borderRight: `1px solid ${c.border}`,
              marginRight: 2,
              whiteSpace: "nowrap",
            }}>{activePoint.timeStr}</span>
            <span style={{ whiteSpace: "nowrap" }}>价格: <strong style={{ color: priceColor }}>{activePoint.price.toFixed(2)}</strong></span>
            {diffAmount != null && (
              <span style={{ color: priceColor, whiteSpace: "nowrap" }}>
                {diffAmount >= 0 ? `+${diffAmount.toFixed(2)}` : diffAmount.toFixed(2)} ({diffPct != null ? (diffPct >= 0 ? `+${diffPct.toFixed(2)}%` : `${diffPct.toFixed(2)}%`) : ""})
              </span>
            )}
            {activePoint.avgPrice != null && showAvgLine && (
              <span style={{ whiteSpace: "nowrap" }}>均价: <strong style={{ color: c.accent }}>{activePoint.avgPrice.toFixed(2)}</strong></span>
            )}
            {activePoint.amount != null && (
              <span style={{ whiteSpace: "nowrap" }}>分额: <strong style={{ color: c.textPrimary }}>{formatAmount(activePoint.amount)}</strong></span>
            )}
            {sessionStats && (
              <>
                <span style={{ whiteSpace: "nowrap" }}>高: <strong style={{ color: c.up }}>{sessionStats.high.toFixed(2)}</strong></span>
                <span style={{ whiteSpace: "nowrap" }}>低: <strong style={{ color: c.down }}>{sessionStats.low.toFixed(2)}</strong></span>
              </>
            )}
          </div>
        ) : (
          <span>等待分时数据...</span>
        )}
        <div className="intraday-chart__hud-legend" style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "11px", flex: "0 0 auto" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: c.primary }} />
            分时线
          </span>
          {showAvgLine && (
            <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
              <span style={{ width: 6, height: 2, background: c.accent }} />
              均价线
            </span>
          )}
          {prevClose != null && showPrevCloseLine && (
            <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
              <span style={{ width: 6, height: 1, borderTop: `1px dashed ${c.textMuted}` }} />
              昨收 {prevClose.toFixed(2)}
            </span>
          )}
          <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
            <span style={{ width: 6, height: 6, borderRadius: 1, background: c.up, opacity: 0.8 }} />
            成交量
          </span>
        </div>
      </div>

      {/* 绘图区包装容器 (承载左侧涨跌幅标尺、中间量价分界栏与轻量图表) */}
      <div style={{ position: "relative", flex: 1, width: "100%", minHeight: 0 }}>
        {/* 左侧涨跌幅刻度栏 (Symmetric Percentage Scale aligned with prevClose zero-line) */}
        {prevClose != null && prevClose > 0 && pane0Height > 0 && (
          <div
            style={{
              position: "absolute",
              left: 6,
              top: 0,
              width: 50,
              height: pane0Height,
              pointerEvents: "none",
              zIndex: 3,
              userSelect: "none",
            }}
          >
            {/* Top (+maxPct%) */}
            <span style={{
              position: "absolute",
              top: "8%",
              transform: "translateY(-50%)",
              fontSize: "10px",
              lineHeight: 1,
              fontWeight: 600,
              color: c.up,
              fontFamily: "var(--c-font-mono)",
              padding: "1px 3px",
              borderRadius: 2,
              backgroundColor: c.isLight ? "rgba(250, 246, 238, 0.85)" : "rgba(18, 23, 34, 0.85)",
            }}>
              +{maxPct.toFixed(2)}%
            </span>
            {/* Mid-top (+maxPct/2%) */}
            <span style={{
              position: "absolute",
              top: "29%",
              transform: "translateY(-50%)",
              fontSize: "10px",
              lineHeight: 1,
              color: hexToRgba(c.up, 0.85),
              fontFamily: "var(--c-font-mono)",
              padding: "1px 3px",
              borderRadius: 2,
              backgroundColor: c.isLight ? "rgba(250, 246, 238, 0.75)" : "rgba(18, 23, 34, 0.75)",
            }}>
              +{(maxPct / 2).toFixed(2)}%
            </span>
            {/* Center (0.00% 昨收线) */}
            <span style={{
              position: "absolute",
              top: "50%",
              transform: "translateY(-50%)",
              fontSize: "10px",
              lineHeight: 1,
              fontWeight: 600,
              color: c.textMuted,
              fontFamily: "var(--c-font-mono)",
              padding: "1px 3px",
              borderRadius: 2,
              backgroundColor: c.isLight ? "rgba(250, 246, 238, 0.85)" : "rgba(18, 23, 34, 0.85)",
            }}>
              0.00%
            </span>
            {/* Mid-bottom (-maxPct/2%) */}
            <span style={{
              position: "absolute",
              top: "71%",
              transform: "translateY(-50%)",
              fontSize: "10px",
              lineHeight: 1,
              color: hexToRgba(c.down, 0.85),
              fontFamily: "var(--c-font-mono)",
              padding: "1px 3px",
              borderRadius: 2,
              backgroundColor: c.isLight ? "rgba(250, 246, 238, 0.75)" : "rgba(18, 23, 34, 0.75)",
            }}>
              -{(maxPct / 2).toFixed(2)}%
            </span>
            {/* Bottom (-maxPct%) */}
            <span style={{
              position: "absolute",
              top: "92%",
              transform: "translateY(-50%)",
              fontSize: "10px",
              lineHeight: 1,
              fontWeight: 600,
              color: c.down,
              fontFamily: "var(--c-font-mono)",
              padding: "1px 3px",
              borderRadius: 2,
              backgroundColor: c.isLight ? "rgba(250, 246, 238, 0.85)" : "rgba(18, 23, 34, 0.85)",
            }}>
              -{maxPct.toFixed(2)}%
            </span>

            {/* Hovered point dynamic crosshair badge on left */}
            {diffPct != null && hoverPoint != null && maxPct > 0 && (
              <div
                style={{
                  position: "absolute",
                  left: -2,
                  top: `${Math.max(4, Math.min(pane0Height - 14, pane0Height * (0.08 + Math.max(0, Math.min(1, (maxPct - diffPct) / (2 * maxPct))) * 0.84) - 8))}px`,
                  backgroundColor: diffPct >= 0 ? c.up : c.down,
                  color: "#ffffff",
                  fontSize: "10px",
                  fontWeight: 700,
                  fontFamily: "var(--c-font-mono)",
                  padding: "1px 4px",
                  borderRadius: "2px",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.35)",
                  whiteSpace: "nowrap",
                  transition: "top 0.04s ease-out",
                  zIndex: 4,
                }}
              >
                {diffPct > 0 ? "+" : ""}{diffPct.toFixed(2)}%
              </div>
            )}
          </div>
        )}

        {/* 股价与成交量窗格中间区分栏 (带背景色、带说明、左右不穿透坐标轴) */}
        <div
          className="intraday-chart__separator-bar"
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
          title="上下拖拽可调整分时图与成交量高度比例"
        >
          <div className="intraday-chart__volume-info" style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0, overflow: "hidden", flexWrap: "nowrap" }}>
            <span className="intraday-chart__volume-title" style={{
              fontSize: "11px",
              fontWeight: 700,
              color: c.textSecondary,
              letterSpacing: "0.02em",
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}>
              成交量 VOL
            </span>
            <span className="intraday-chart__volume-stat" style={{ fontSize: "11px", color: c.textMuted, whiteSpace: "nowrap" }}>
              量: <strong style={{ color: c.textPrimary, fontFamily: APP_FONT_FAMILY }}>{formatVolume(activePoint?.volume)}</strong>
            </span>
            {activePoint?.amount != null && (
              <span className="intraday-chart__volume-stat" style={{ fontSize: "11px", color: c.textMuted, whiteSpace: "nowrap" }}>
                额: <strong style={{ color: c.textPrimary, fontFamily: APP_FONT_FAMILY }}>{formatAmount(activePoint.amount)}</strong>
              </span>
            )}
          </div>

          <div className="intraday-chart__separator-drag" style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
            <div style={{
              width: 22,
              height: 3,
              borderRadius: 2,
              backgroundColor: c.border,
              opacity: 0.8,
            }} />
            <span className="intraday-chart__separator-unit" style={{ fontSize: "10px", color: c.textMuted, opacity: 0.75 }}>
              单位: 股/元
            </span>
          </div>
        </div>

        {/* Chart canvas container */}
        <div ref={containerRef} style={{ width: "100%", height: "100%", backgroundColor: c.cardBg }} />
      </div>
    </div>
  );
}
