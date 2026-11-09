import React, { useMemo } from "react";
import { Empty } from "antd";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import type { IndustryLeekItem } from "../../api/queryHooks/sentiment";
import "./leek-quadrant.css";

interface Props {
  industries: IndustryLeekItem[];
  selectedIndustryName?: string;
  onSelectIndustry: (ind: IndustryLeekItem) => void;
}

export const LeekQuadrantChart: React.FC<Props> = ({
  industries,
  selectedIndustryName,
  onSelectIndustry,
}) => {
  const chartOption = useMemo(() => {
    // 散点数据格式：[涨跌幅, 资金背离剪刀差(亿), 韭菜指数, 行业名称, 主力净流入, 散户净买入]
    let minPct = -3;
    let maxPct = 3;
    let minDiff = -10;
    let maxDiff = 10;

    const data = industries.map((ind) => {
      const diffYuan = ind.retail_net - ind.main_net;
      const diff100m = round2(diffYuan / 1e8);
      if (ind.change_pct < minPct) minPct = ind.change_pct;
      if (ind.change_pct > maxPct) maxPct = ind.change_pct;
      if (diff100m < minDiff) minDiff = diff100m;
      if (diff100m > maxDiff) maxDiff = diff100m;

      return [
        ind.change_pct,
        diff100m,
        ind.leek_score,
        ind.industry_name,
        round2(ind.main_net / 1e8),
        round2(ind.retail_net / 1e8),
      ];
    });

    const xBound = Math.max(Math.abs(minPct), Math.abs(maxPct)) * 1.25;
    const yBound = Math.max(Math.abs(minDiff), Math.abs(maxDiff)) * 1.25;

    return {
      title: {
        text: "行业博弈四象限矩阵 (涨跌幅 vs 资金剪刀差)",
        subtext:
          "右上: 高危诱多 | 左上: 飞刀接盘 | 左下: 恐慌黄金坑 | 右下: 主力主升浪 · 气泡大小与颜色反映韭菜指数",
        left: 10,
        top: 6,
        textStyle: { fontSize: 13, fontWeight: 600, color: "var(--c-text-primary, #1e293b)" },
        subtextStyle: { fontSize: 11, color: "var(--c-text-muted, #94a3b8)" },
      },
      tooltip: {
        trigger: "item",
        axisPointer: {
          type: "cross",
          lineStyle: { type: "dashed", color: "rgba(148, 163, 184, 0.6)" },
        },
        formatter: (params: { value: [number, number, number, string, number, number] }) => {
          const [pct, diff, score, name, main, retail] = params.value;
          return `
            <div style="font-size:12px;line-height:1.6;min-width:180px;">
              <div style="font-weight:700;font-size:13px;border-bottom:1px solid rgba(148,163,184,0.3);padding-bottom:4px;margin-bottom:4px;">
                ${name} · 韭菜指数: <strong style="color:${score >= 75 ? "#dc2626" : score >= 60 ? "#f59e0b" : score >= 35 ? "#3b82f6" : "#059669"}">${score.toFixed(1)}</strong>
              </div>
              <div>当日涨跌幅: <strong>${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%</strong></div>
              <div>资金剪刀差: <strong>${diff >= 0 ? "+" : ""}${diff.toFixed(1)} 亿元</strong></div>
              <div style="color:#64748b;">主力净额: ${main >= 0 ? "+" : ""}${main.toFixed(1)} 亿 / 散户: ${retail >= 0 ? "+" : ""}${retail.toFixed(1)} 亿</div>
              <div style="margin-top:4px;font-size:11px;color:#94a3b8;">点击气泡查看该行业深度复盘双轴曲线</div>
            </div>
          `;
        },
      },
      grid: {
        top: 62,
        right: 40,
        bottom: 45,
        left: 65,
      },
      xAxis: {
        name: "当日涨跌幅 (%)",
        nameLocation: "middle",
        nameGap: 26,
        type: "value",
        min: -Math.ceil(xBound),
        max: Math.ceil(xBound),
        splitLine: { lineStyle: { type: "dashed", color: "var(--c-border, #e2e8f0)" } },
        axisLine: { lineStyle: { color: "#94a3b8" } },
        axisPointer: {
          label: {
            formatter: (p: { value: number }) => `${Number(p.value).toFixed(2)}%`,
          },
        },
      },
      yAxis: {
        name: "资金剪刀差 (散户净额 - 主力净额 / 亿元)",
        nameLocation: "middle",
        nameGap: 46,
        type: "value",
        min: -Math.ceil(yBound),
        max: Math.ceil(yBound),
        splitLine: { lineStyle: { type: "dashed", color: "var(--c-border, #e2e8f0)" } },
        axisLine: { lineStyle: { color: "#94a3b8" } },
        axisPointer: {
          label: {
            formatter: (p: { value: number }) => `${Number(p.value).toFixed(1)} 亿`,
          },
        },
      },
      visualMap: {
        show: false,
        dimension: 2,
        min: 20,
        max: 85,
        inRange: {
          color: ["#059669", "#3b82f6", "#f59e0b", "#dc2626"],
        },
      },
      series: [
        {
          type: "scatter",
          symbolSize: (val: [number, number, number, string, number, number]) => {
            const score = val[2];
            const isSelected = selectedIndustryName === val[3];
            const base = Math.max(16, Math.min(36, score * 0.38));
            return isSelected ? base * 1.35 : base;
          },
          data,
          label: {
            show: true,
            formatter: (param: { value: [number, number, number, string, number, number] }) =>
              param.value[3],
            position: "top",
            fontSize: 10,
            color: "var(--c-text-secondary, #64748b)",
          },
          markLine: {
            silent: true,
            lineStyle: { type: "solid", color: "rgba(148, 163, 184, 0.45)", width: 1.2 },
            data: [{ xAxis: 0 }, { yAxis: 0 }],
          },
          markArea: {
            silent: true,
            itemStyle: { opacity: 0.045 },
            data: [
              // 右上象限：🔥 高危诱多区
              [
                {
                  name: "🔥 高危诱多区\n(主力大单出货 · 散户追高接盘)",
                  coord: [0, 0],
                  itemStyle: { color: "#ef4444" },
                  label: {
                    position: "insideTopRight",
                    color: "rgba(220, 38, 38, 0.75)",
                    fontSize: 11,
                    fontWeight: "bold",
                    lineHeight: 16,
                  },
                },
                { coord: [xBound * 1.5, yBound * 1.5] },
              ],
              // 左上象限：⚠️ 飞刀接盘区
              [
                {
                  name: "⚠️ 飞刀接盘区\n(板块破位杀跌 · 散户逆势抄底)",
                  coord: [-xBound * 1.5, 0],
                  itemStyle: { color: "#f59e0b" },
                  label: {
                    position: "insideTopLeft",
                    color: "rgba(217, 119, 6, 0.75)",
                    fontSize: 11,
                    fontWeight: "bold",
                    lineHeight: 16,
                  },
                },
                { coord: [0, yBound * 1.5] },
              ],
              // 左下象限：💎 恐慌黄金坑
              [
                {
                  name: "💎 恐慌黄金坑\n(超跌恐慌割肉 · 筹码彻底出清)",
                  coord: [-xBound * 1.5, -yBound * 1.5],
                  itemStyle: { color: "#059669" },
                  label: {
                    position: "insideBottomLeft",
                    color: "rgba(5, 150, 105, 0.75)",
                    fontSize: 11,
                    fontWeight: "bold",
                    lineHeight: 16,
                  },
                },
                { coord: [0, 0] },
              ],
              // 右下象限：🚀 健康主升浪
              [
                {
                  name: "🚀 健康主升浪\n(主力机构独食锁仓 · 散户犹豫轻仓)",
                  coord: [0, -yBound * 1.5],
                  itemStyle: { color: "#3b82f6" },
                  label: {
                    position: "insideBottomRight",
                    color: "rgba(37, 99, 235, 0.75)",
                    fontSize: 11,
                    fontWeight: "bold",
                    lineHeight: 16,
                  },
                },
                { coord: [xBound * 1.5, 0] },
              ],
            ],
          },
        },
      ],
    };
  }, [industries, selectedIndustryName]);

  if (industries.length === 0) {
    return (
      <div className="leek-quadrant-chart-card leek-quadrant-empty">
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前筛选条件下暂无行业散点数据" />
      </div>
    );
  }

  return (
    <div className="leek-quadrant-chart-card">
      <ReactECharts
        echarts={echarts}
        option={chartOption}
        className="leek-quadrant-echarts"
        notMerge
        onEvents={{
          click: (params: {
            componentType?: string;
            value?: [number, number, number, string, number, number];
          }) => {
            if (params.componentType === "series" && params.value) {
              const name = params.value[3];
              const ind = industries.find((i) => i.industry_name === name);
              if (ind) onSelectIndustry(ind);
            }
          },
        }}
      />
    </div>
  );
};

function round2(num: number): number {
  return Math.round(num * 100) / 100;
}
