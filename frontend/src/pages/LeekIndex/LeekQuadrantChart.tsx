import React, { useMemo } from "react";
import { Empty } from "antd";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import type { IndustryLeekItem } from "../../api/queryHooks/sentiment";
import "./leek-quadrant.css";

interface Props {
  industries: IndustryLeekItem[];
  onSelectIndustry: (ind: IndustryLeekItem) => void;
}

export const LeekQuadrantChart: React.FC<Props> = ({ industries, onSelectIndustry }) => {
  const chartOption = useMemo(() => {
    // 准备散点数据：[涨跌幅, 资金背离剪刀差(亿), 韭菜指数, 行业名称, 主力净流入, 散户净买入]
    const data = industries.map((ind) => {
      const diffYuan = ind.retail_net - ind.main_net;
      const diff100m = round2(diffYuan / 1e8);
      return [
        ind.change_pct,
        diff100m,
        ind.leek_score,
        ind.industry_name,
        round2(ind.main_net / 1e8),
        round2(ind.retail_net / 1e8),
      ];
    });

    return {
      title: {
        text: "行业博弈四象限矩阵 (涨跌幅 vs 资金剪刀差)",
        subtext: "气泡颜色反映韭菜指数（绿出清 / 蓝均衡 / 橙过热 / 红极度接盘） | 点击气泡可查看行业详情",
        left: 10,
        top: 6,
        textStyle: { fontSize: 13, fontWeight: 600, color: "var(--c-text-primary, #1e293b)" },
        subtextStyle: { fontSize: 11, color: "var(--c-text-muted, #94a3b8)" },
      },
      tooltip: {
        trigger: "item",
        formatter: (params: { value: [number, number, number, string, number, number] }) => {
          const [pct, diff, score, name, main, retail] = params.value;
          return `
            <div style="font-size:12px;line-height:1.6;">
              <strong>${name}</strong> · 韭菜指数: <strong>${score}</strong><br/>
              涨跌幅: <strong>${pct >= 0 ? "+" : ""}${pct}%</strong><br/>
              资金剪刀差: <strong>${diff >= 0 ? "+" : ""}${diff} 亿元</strong><br/>
              主力净流入: ${main} 亿元<br/>
              散户净买入: ${retail} 亿元
            </div>
          `;
        },
      },
      grid: {
        top: 65,
        right: 35,
        bottom: 40,
        left: 55,
      },
      xAxis: {
        name: "涨跌幅 (%)",
        nameLocation: "middle",
        nameGap: 24,
        type: "value",
        splitLine: { lineStyle: { type: "dashed", color: "var(--c-border, #e2e8f0)" } },
        axisLine: { lineStyle: { color: "#94a3b8" } },
      },
      yAxis: {
        name: "剪刀差 (散户买 - 主力买 / 亿元)",
        nameLocation: "middle",
        nameGap: 38,
        type: "value",
        splitLine: { lineStyle: { type: "dashed", color: "var(--c-border, #e2e8f0)" } },
        axisLine: { lineStyle: { color: "#94a3b8" } },
      },
      visualMap: {
        show: false,
        dimension: 2,
        min: 20,
        max: 85,
        inRange: {
          color: ["#10b981", "#3b82f6", "#f59e0b", "#ef4444"],
        },
      },
      series: [
        {
          type: "scatter",
          symbolSize: (val: [number, number, number, string, number, number]) => {
            const score = val[2];
            return Math.max(16, Math.min(36, score * 0.38));
          },
          data,
          label: {
            show: true,
            formatter: (param: { value: [number, number, number, string, number, number] }) => param.value[3],
            position: "top",
            fontSize: 10,
            color: "var(--c-text-secondary, #64748b)",
          },
          markLine: {
            silent: true,
            lineStyle: { type: "solid", color: "rgba(148, 163, 184, 0.5)" },
            data: [{ xAxis: 0 }, { yAxis: 0 }],
          },
        },
      ],
    };
  }, [industries]);

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
        style={{ height: 290, width: "100%" }}
        notMerge
        onEvents={{
          click: (params: { componentType?: string; value?: [number, number, number, string, number, number] }) => {
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
