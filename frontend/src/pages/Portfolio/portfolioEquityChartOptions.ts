import type { ThemeColors } from "../../theme/themes";
import { APP_FONT_FAMILY, APP_FONT_SIZE } from "../../theme/typography";
import type { PortfolioEquityCurveResponse } from "../../types/portfolio";
import { formatMoney } from "./portfolioFormatters";

function formatDate(value: string, narrow: boolean) {
  return narrow && value.length >= 10 ? value.slice(5) : value;
}

export function buildPortfolioEquityOption(
  curve: PortfolioEquityCurveResponse,
  colors: ThemeColors,
  narrow: boolean,
) {
  const totalMode = curve.mode === "total_assets";
  const points = curve.points ?? [];
  return {
    animation: points.length <= 120,
    textStyle: { fontFamily: APP_FONT_FAMILY, fontSize: APP_FONT_SIZE.sm },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line" },
      valueFormatter: (value: unknown) => formatMoney(Number(value)),
    },
    legend: {
      data: totalMode ? ["总资产", "证券市值", "现金余额"] : ["证券市值"],
      top: 4,
      left: "center",
      textStyle: { color: colors.textSecondary, fontSize: APP_FONT_SIZE.sm },
    },
    grid: { left: 16, right: 20, top: 52, bottom: 18, containLabel: true },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: points.map((point) => point.date),
      axisLabel: {
        color: colors.textMuted,
        fontSize: APP_FONT_SIZE.xs,
        hideOverlap: true,
        formatter: (value: string) => formatDate(value, narrow),
      },
      axisLine: { lineStyle: { color: colors.border } },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: {
        color: colors.textMuted,
        fontSize: APP_FONT_SIZE.xs,
        formatter: (value: number) => `¥${(value / 10_000).toFixed(0)}万`,
      },
      splitLine: { lineStyle: { color: colors.border } },
    },
    dataZoom: points.length > 180 ? [{ type: "inside" }, { type: "slider", height: 16 }] : [],
    series: [
      ...(totalMode ? [{
        name: "总资产",
        type: "line",
        showSymbol: false,
        sampling: "lttb",
        data: points.map((point) => point.total_assets),
        lineStyle: { color: colors.primary, width: 2.5 },
        areaStyle: { color: `${colors.primary}18` },
      }] : []),
      {
        name: "证券市值",
        type: "line",
        showSymbol: false,
        sampling: "lttb",
        data: points.map((point) => point.securities_value),
        lineStyle: { color: colors.up, width: 1.8 },
      },
      ...(totalMode ? [{
        name: "现金余额",
        type: "line",
        showSymbol: false,
        sampling: "lttb",
        data: points.map((point) => point.cash_balance),
        lineStyle: { color: colors.textMuted, type: "dashed" },
      }] : []),
    ],
  };
}
