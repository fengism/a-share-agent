import { useMemo, useState } from "react";
import { Card, Segmented, Tag, Typography } from "antd";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../../charts/echarts-setup";
import { useColors } from "../../../styles/ui";
import { APP_FONT_FAMILY } from "../../../theme/typography";
import { formatNumberWithSeparators } from "../../../utils/format";
import type { NationalTeamDailyFlow, NationalTeamMilestone } from "../../../types/stock";
import { escapeHtml } from "../utils/html";
import LazyChart from "./LazyChart";

const { Text } = Typography;

function formatSignedFlow(value: number | null | undefined, unit = "亿元") {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${value > 0 ? "+" : ""}${formatNumberWithSeparators(value, 2)}${unit ? " " + unit : ""}`;
}

export type MacroChartMode = "net_flow" | "turnover" | "stacked";

interface MacroFlowChartProps {
  dailyFlows?: NationalTeamDailyFlow[];
  milestones?: NationalTeamMilestone[];
  defaultMode?: MacroChartMode;
}

export default function MacroFlowChart({
  dailyFlows,
  milestones,
  defaultMode = "net_flow",
}: MacroFlowChartProps) {
  const colors = useColors();
  const [mode, setMode] = useState<MacroChartMode>(defaultMode);

  const flows = useMemo(() => dailyFlows ?? [], [dailyFlows]);
  const relevantMilestones = useMemo(() => {
    if (!milestones || !flows.length) return [];
    const dateSet = new Set(flows.map((f) => f.date));
    return milestones.filter((m) => dateSet.has(m.date));
  }, [milestones, flows]);

  if (!flows.length) return null;

  const dates = flows.map((f) => f.date);
  const benchmarkValues = flows.map((f) => f.benchmark_close ?? null);
  const hasBenchmark = benchmarkValues.some((v) => v != null);

  const categories = [
    { key: "core_broad", name: "核心大盘", color: "#1677ff" },
    { key: "a500", name: "新质A500", color: "#faad14" },
    { key: "growth", name: "中小成长", color: "#13c2c2" },
    { key: "dividend", name: "红利防御", color: "#722ed1" },
  ];

  const commonDataZoom = [
    { type: "inside", start: Math.max(0, 100 - (30 / Math.max(1, dates.length)) * 100), end: 100 },
    {
      type: "slider",
      start: Math.max(0, 100 - (30 / Math.max(1, dates.length)) * 100),
      end: 100,
      height: 18,
      bottom: 2,
      borderColor: "transparent",
      backgroundColor: "rgba(128, 128, 128, 0.08)",
      fillerColor: "rgba(22, 119, 255, 0.15)",
      textStyle: { color: colors.textSecondary, fontSize: 10 },
      handleStyle: { color: colors.primary, borderColor: colors.primary },
    },
  ];

  // 1. 资金净流入与累计净流入走势 (双轴)
  const netFlowOption = {
    animationDuration: 300,
    textStyle: { fontFamily: APP_FONT_FAMILY },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross", crossStyle: { color: colors.border } },
      backgroundColor: colors.elevatedBg,
      borderColor: colors.border,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: colors.textPrimary, fontSize: 12, fontFamily: APP_FONT_FAMILY },
      extraCssText: "box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22); border-radius: 8px; backdrop-filter: blur(8px);",
      formatter: (params: Array<{ seriesName: string; value: number | null; marker: string }>) => {
        if (!params.length) return "";
        const dataIdx = (params[0] as unknown as { dataIndex: number }).dataIndex;
        const pt = flows[dataIdx];
        const dateStr = pt?.date || "";
        const totalFlow = pt?.total_flow_100m;
        const cumulativeFlow = pt?.cumulative_flow_100m;
        const benchClose = pt?.benchmark_close;
        const milestoneHit = relevantMilestones.find((m) => m.date === dateStr);

        let html = `<div style="font-weight:600;margin-bottom:6px;font-size:12px;color:${colors.textPrimary}">${escapeHtml(dateStr)}</div>`;

        if (totalFlow != null) {
          const flowColor = totalFlow >= 0 ? colors.up : colors.down;
          html += `<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:4px;font-size:12px">
            <span>当日估算净申购</span>
            <b style="font-family:var(--c-font-mono);color:${flowColor}">${formatSignedFlow(totalFlow, "亿元")}</b>
          </div>`;
        }

        if (cumulativeFlow != null) {
          const cumColor = cumulativeFlow >= 0 ? colors.up : colors.down;
          html += `<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:4px;font-size:12px">
            <span>区间累计净申购</span>
            <b style="font-family:var(--c-font-mono);color:${cumColor}">${formatSignedFlow(cumulativeFlow, "亿元")}</b>
          </div>`;
        }

        if (benchClose != null) {
          html += `<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:4px;font-size:12px;color:${colors.textSecondary}">
            <span>基准指数 (沪深300)</span>
            <span style="font-family:var(--c-font-mono)">${formatNumberWithSeparators(benchClose, 1)} 点</span>
          </div>`;
        }

        if (milestoneHit) {
          html += `<div style="margin-top:6px;padding:4px 6px;border-radius:4px;background:rgba(250,173,20,0.12);border:1px solid #faad14;font-size:11px">
            <div style="color:#d48806;font-weight:600">★ 关键救市节点：${escapeHtml(milestoneHit.title)}</div>
            <div style="color:${colors.textSecondary};margin-top:2px;line-height:1.3">${escapeHtml(milestoneHit.description)}</div>
          </div>`;
        }

        return html;
      },
    },
    legend: {
      show: true,
      top: 0,
      right: 12,
      textStyle: { color: colors.textSecondary, fontSize: 11 },
      itemWidth: 12,
      itemHeight: 10,
    },
    grid: { left: 52, right: hasBenchmark ? 52 : 24, top: 28, bottom: 32 },
    xAxis: {
      type: "category",
      data: dates,
      axisLabel: { color: colors.textSecondary, hideOverlap: true, fontSize: 10 },
      axisLine: { lineStyle: { color: colors.border } },
    },
    yAxis: [
      {
        type: "value",
        name: "净申购（亿元）",
        nameTextStyle: { color: colors.textSecondary, fontSize: 10, padding: [0, 0, 2, 0] },
        axisLabel: {
          color: colors.textSecondary,
          fontSize: 10,
          formatter: (val: number) => formatNumberWithSeparators(val, 0),
        },
        splitLine: { lineStyle: { color: colors.border, type: "dashed", opacity: 0.35 } },
      },
      {
        type: "value",
        name: "基准指数（点）",
        scale: true,
        show: hasBenchmark,
        nameTextStyle: { color: colors.textSecondary, fontSize: 10, padding: [0, 0, 2, 0] },
        axisLabel: {
          color: colors.textSecondary,
          fontSize: 10,
          formatter: (val: number) => String(Math.round(val)),
        },
        splitLine: { show: false },
      },
    ],
    dataZoom: commonDataZoom,
    series: [
      {
        name: "日度净申购",
        type: "bar",
        data: flows.map((f) => {
          const val = f.total_flow_100m ?? 0;
          return {
            value: val,
            itemStyle: {
              color: val >= 0 ? colors.up : colors.down,
              borderRadius: val >= 0 ? [2, 2, 0, 0] : [0, 0, 2, 2],
            },
          };
        }),
        markLine: relevantMilestones.length > 0 ? {
          symbol: ["none", "none"],
          label: {
            show: true,
            position: "insideEndTop",
            formatter: (p: { name: string }) => `★ ${p.name}`,
            fontSize: 10,
            color: "#faad14",
          },
          lineStyle: { color: "#faad14", type: "dashed", width: 1.5 },
          data: relevantMilestones.map((m) => ({ xAxis: m.date, name: m.title })),
        } : undefined,
      },
      {
        name: "累计净流入",
        type: "line",
        smooth: true,
        symbol: "none",
        lineStyle: { width: 2.2, color: colors.primary },
        itemStyle: { color: colors.primary },
        data: flows.map((f) => f.cumulative_flow_100m ?? null),
      },
      ...(hasBenchmark ? [{
        name: "基准指数",
        type: "line",
        yAxisIndex: 1,
        smooth: true,
        symbol: "none",
        lineStyle: { width: 1.5, color: "#faad14", type: "dashed" },
        itemStyle: { color: "#faad14" },
        data: benchmarkValues,
      }] : []),
    ],
  };

  // 2. 成交额趋势与指数双轴图
  const turnoverOption = {
    animationDuration: 300,
    textStyle: { fontFamily: APP_FONT_FAMILY },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross", crossStyle: { color: colors.border } },
      backgroundColor: colors.elevatedBg,
      borderColor: colors.border,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: colors.textPrimary, fontSize: 12, fontFamily: APP_FONT_FAMILY },
      extraCssText: "box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22); border-radius: 8px;",
      formatter: (params: Array<{ seriesName: string; value: number | null }>) => {
        if (!params.length) return "";
        const dataIdx = (params[0] as unknown as { dataIndex: number }).dataIndex;
        const pt = flows[dataIdx];
        const dateStr = pt?.date || "";
        const amt = pt?.total_amount_100m;
        const benchClose = pt?.benchmark_close;

        let html = `<div style="font-weight:600;margin-bottom:6px;font-size:12px;color:${colors.textPrimary}">${escapeHtml(dateStr)}</div>`;
        if (amt != null) {
          html += `<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:4px;font-size:12px">
            <span>样本 ETF 总成交额</span>
            <b style="font-family:var(--c-font-mono);color:${colors.primary}">${formatNumberWithSeparators(amt, 1)} 亿元</b>
          </div>`;
        }
        if (benchClose != null) {
          html += `<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:4px;font-size:12px;color:${colors.textSecondary}">
            <span>基准指数 (沪深300)</span>
            <span style="font-family:var(--c-font-mono)">${formatNumberWithSeparators(benchClose, 1)} 点</span>
          </div>`;
        }
        return html;
      },
    },
    legend: {
      show: true,
      top: 0,
      right: 12,
      textStyle: { color: colors.textSecondary, fontSize: 11 },
      itemWidth: 12,
      itemHeight: 10,
    },
    grid: { left: 52, right: hasBenchmark ? 52 : 24, top: 28, bottom: 32 },
    xAxis: {
      type: "category",
      data: dates,
      axisLabel: { color: colors.textSecondary, hideOverlap: true, fontSize: 10 },
      axisLine: { lineStyle: { color: colors.border } },
    },
    yAxis: [
      {
        type: "value",
        name: "成交额（亿元）",
        nameTextStyle: { color: colors.textSecondary, fontSize: 10, padding: [0, 0, 2, 0] },
        axisLabel: {
          color: colors.textSecondary,
          fontSize: 10,
          formatter: (val: number) => formatNumberWithSeparators(val, 0),
        },
        splitLine: { lineStyle: { color: colors.border, type: "dashed", opacity: 0.35 } },
      },
      {
        type: "value",
        name: "基准指数（点）",
        scale: true,
        show: hasBenchmark,
        nameTextStyle: { color: colors.textSecondary, fontSize: 10, padding: [0, 0, 2, 0] },
        axisLabel: {
          color: colors.textSecondary,
          fontSize: 10,
          formatter: (val: number) => String(Math.round(val)),
        },
        splitLine: { show: false },
      },
    ],
    dataZoom: commonDataZoom,
    series: [
      {
        name: "样本ETF成交额",
        type: "bar",
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "#1677ff" },
            { offset: 1, color: "rgba(22, 119, 255, 0.35)" },
          ]),
          borderRadius: [2, 2, 0, 0],
        },
        data: flows.map((f) => f.total_amount_100m ?? 0),
      },
      ...(hasBenchmark ? [{
        name: "基准指数",
        type: "line",
        yAxisIndex: 1,
        smooth: true,
        symbol: "none",
        lineStyle: { width: 1.8, color: "#faad14" },
        itemStyle: { color: "#faad14" },
        data: benchmarkValues,
      }] : []),
    ],
  };

  // 3. 原战术板块堆叠柱状图
  const stackedOption = {
    animationDuration: 300,
    textStyle: { fontFamily: APP_FONT_FAMILY },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: colors.elevatedBg,
      borderColor: colors.border,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: colors.textPrimary, fontSize: 12, fontFamily: APP_FONT_FAMILY },
      extraCssText: "box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22); border-radius: 8px;",
      formatter: (params: Array<{ seriesName: string; value: number; marker: string }>) => {
        if (!params.length) return "";
        const dataIdx = (params[0] as unknown as { dataIndex: number }).dataIndex;
        const pt = flows[dataIdx];
        const dateStr = pt?.date || "";
        const totalFlow = pt?.total_flow_100m;
        const totalShares = pt?.total_shares_change_100m;
        const totalColor = totalFlow != null && totalFlow >= 0 ? colors.up : colors.down;
        const milestoneHit = relevantMilestones.find((m) => m.date === dateStr);

        let rows = "";
        for (const p of params) {
          if (p.value !== 0 && p.value != null) {
            const pColor = p.value >= 0 ? colors.up : colors.down;
            rows += `<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;margin-top:3px;font-size:11px">
              <span style="display:flex;align-items:center;gap:5px">${p.marker}${escapeHtml(p.seriesName)}</span>
              <b style="font-family:var(--c-font-mono);color:${pColor}">${formatSignedFlow(p.value, "亿元")}</b>
            </div>`;
          }
        }

        const milestoneHtml = milestoneHit
          ? `<div style="margin-top:6px;padding:4px 6px;border-radius:4px;background:rgba(250,173,20,0.12);border:1px solid #faad14;font-size:11px">
              <div style="color:#d48806;font-weight:600">★ 关键救市节点：${escapeHtml(milestoneHit.title)}</div>
              <div style="color:${colors.textSecondary};margin-top:2px;line-height:1.3">${escapeHtml(milestoneHit.description)}</div>
            </div>`
          : "";

        return `<div style="font-weight:600;margin-bottom:4px;font-size:12px;color:${colors.textPrimary}">${escapeHtml(dateStr)}</div>
          <div style="display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:6px;padding-bottom:4px;border-bottom:1px solid ${colors.border};font-size:12px">
            <span>当日宽基净申购合计</span>
            <b style="font-family:var(--c-font-mono);color:${totalColor}">${formatSignedFlow(totalFlow, "亿元")}</b>
          </div>
          ${rows}
          ${totalShares != null ? `<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;margin-top:4px;padding-top:4px;border-top:1px dashed ${colors.border};font-size:11px;color:${colors.textSecondary}">
            <span>当日份额变动合计</span>
            <span style="font-family:var(--c-font-mono)">${formatSignedFlow(totalShares, "亿份")}</span>
          </div>` : ""}
          ${milestoneHtml}`;
      },
    },
    legend: {
      show: true,
      top: 0,
      right: 12,
      textStyle: { color: colors.textSecondary, fontSize: 11 },
      itemWidth: 10,
      itemHeight: 10,
    },
    grid: { left: 48, right: 24, top: 28, bottom: 32 },
    xAxis: {
      type: "category",
      data: dates,
      axisLabel: { color: colors.textSecondary, hideOverlap: true, fontSize: 10 },
      axisLine: { lineStyle: { color: colors.border } },
    },
    yAxis: {
      type: "value",
      name: "估算净申购（亿元）",
      nameTextStyle: { color: colors.textSecondary, fontSize: 10, padding: [0, 0, 2, 0] },
      axisLabel: {
        color: colors.textSecondary,
        fontSize: 10,
        formatter: (val: number) => formatNumberWithSeparators(val, 1),
      },
      splitLine: { lineStyle: { color: colors.border, type: "dashed", opacity: 0.35 } },
    },
    dataZoom: commonDataZoom,
    series: categories.map((cat, idx) => ({
      name: cat.name,
      type: "bar",
      stack: "net_flow",
      itemStyle: { color: cat.color, borderRadius: [2, 2, 0, 0] },
      data: flows.map((f) => f.flows_by_category?.[cat.key] ?? 0),
      markLine: (idx === 0 && relevantMilestones.length > 0) ? {
        symbol: ["none", "none"],
        label: {
          show: true,
          position: "insideEndTop",
          formatter: (p: { name: string }) => `★ ${p.name}`,
          fontSize: 10,
          color: "#faad14",
        },
        lineStyle: {
          color: "#faad14",
          type: "dashed",
          width: 1.5,
        },
        data: relevantMilestones.map((m) => ({
          xAxis: m.date,
          name: m.title,
        })),
      } : undefined,
    })),
  };

  const currentOption = mode === "turnover" ? turnoverOption : mode === "stacked" ? stackedOption : netFlowOption;

  return (
    <Card
      className="national-team-stacked-flow-card"
      size="small"
      data-testid="national-team-daily-flow-chart"
      title={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>全市场宽基每日净申赎走势</span>
            <Tag color={mode === "turnover" ? "blue" : mode === "stacked" ? "purple" : "blue"} style={{ fontSize: 10, lineHeight: "18px", padding: "0 6px" }}>
              {mode === "turnover" ? "二级市场成交口径" : "申赎估算口径（Δ份额×价格）"}
            </Tag>
            <Text type="secondary" style={{ fontSize: 11 }}>
              {mode === "turnover" ? "样本 ETF 每日总成交额与基准指数对比" : mode === "stacked" ? "各战术板块资金净申购/净赎回估算（亿元）" : "日度净流入、累计流入与指数点位走势"}
            </Text>
          </div>
          <Segmented
            size="small"
            value={mode}
            options={[
              { label: "净流入与累计走势", value: "net_flow" },
              { label: "成交额趋势", value: "turnover" },
              { label: "板块细分堆叠", value: "stacked" },
            ]}
            onChange={(val) => setMode(val as MacroChartMode)}
            className="national-team-segmented"
          />
        </div>
      }
    >
      <div data-testid="national-team-daily-flow-chart-container">
        <LazyChart height={240}>
          <ReactECharts
            echarts={echarts}
            option={currentOption}
            data-testid="national-team-daily-flow-echarts"
            style={{ width: "100%", height: 240 }}
            notMerge
          />
        </LazyChart>
      </div>
    </Card>
  );
}
