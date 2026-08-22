import type { QuantBacktestResult } from "../../../api/queries";

interface ChartPalette {
  border: string;
  down: string;
  primary: string;
  textMuted: string;
  textSecondary: string;
}

function formatValue(value: unknown, digits: number, suffix = ""): string {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${numeric.toFixed(digits)}${suffix}` : "-";
}

function formatDateLabel(value: string, isNarrow: boolean): string {
  return isNarrow && value.length >= 10 ? value.slice(5) : value;
}

export function buildEquityChartOption(
  equityCurve: QuantBacktestResult["equity_curve"],
  colors: ChartPalette,
  isNarrow: boolean,
) {
  return {
    animation: equityCurve.length <= 120,
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line" },
      valueFormatter: (value: unknown) => formatValue(value, 4),
    },
    legend: {
      data: ["策略净值", "基准净值"],
      top: isNarrow ? 6 : 4,
      left: "center",
      itemGap: isNarrow ? 12 : 20,
      itemWidth: isNarrow ? 18 : 25,
      textStyle: { color: colors.textSecondary },
    },
    grid: {
      left: isNarrow ? 12 : 16,
      right: isNarrow ? 12 : 20,
      top: isNarrow ? 62 : 58,
      bottom: isNarrow ? 12 : 16,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: equityCurve.map((point) => point.date),
      axisLabel: {
        color: colors.textMuted,
        hideOverlap: true,
        margin: 12,
        formatter: (value: string) => formatDateLabel(value, isNarrow),
      },
      axisLine: { lineStyle: { color: colors.border } },
      axisTick: { alignWithLabel: true },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: {
        color: colors.textMuted,
        margin: 10,
        formatter: (value: number) => formatValue(value, 2),
      },
      splitLine: { lineStyle: { color: colors.border } },
    },
    series: [
      {
        name: "策略净值",
        type: "line",
        showSymbol: false,
        sampling: "lttb",
        data: equityCurve.map((point) => point.equity),
        lineStyle: { color: colors.primary, width: 2 },
        emphasis: { focus: "series" },
      },
      {
        name: "基准净值",
        type: "line",
        showSymbol: false,
        sampling: "lttb",
        data: equityCurve.map((point) => point.benchmark),
        lineStyle: { color: colors.textMuted, type: "dashed" },
        emphasis: { focus: "series" },
      },
    ],
  };
}

export function buildDrawdownChartOption(
  equityCurve: QuantBacktestResult["equity_curve"],
  colors: ChartPalette,
  isNarrow: boolean,
) {
  return {
    animation: equityCurve.length <= 120,
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line" },
      valueFormatter: (value: unknown) => formatValue(value, 2, "%"),
    },
    grid: {
      left: isNarrow ? 12 : 16,
      right: isNarrow ? 12 : 20,
      top: 20,
      bottom: isNarrow ? 12 : 16,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: equityCurve.map((point) => point.date),
      axisLabel: {
        color: colors.textMuted,
        hideOverlap: true,
        margin: 12,
        formatter: (value: string) => formatDateLabel(value, isNarrow),
      },
      axisLine: { lineStyle: { color: colors.border } },
      axisTick: { alignWithLabel: true },
    },
    yAxis: {
      type: "value",
      max: 0,
      axisLabel: {
        formatter: (value: number) => formatValue(value, 1, "%"),
        color: colors.textMuted,
        margin: 10,
      },
      splitLine: { lineStyle: { color: colors.border } },
    },
    series: [{
      name: "回撤",
      type: "line",
      showSymbol: false,
      sampling: "lttb",
      areaStyle: { color: `${colors.down}30` },
      lineStyle: { color: colors.down },
      emphasis: { focus: "series" },
      data: equityCurve.map((point) => point.drawdown * 100),
    }],
  };
}
