import React, { useMemo } from "react";
import { Empty } from "antd";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import type { LeekHistoryPoint } from "../../api/queryHooks/sentiment";

interface Props {
  industryName: string;
  history: LeekHistoryPoint[];
}

export const LeekDualAxisChart: React.FC<Props> = ({ industryName, history }) => {
  // 历史数据按日期正序排列
  const sortedHistory = useMemo(() => {
    return [...history].sort((a, b) => a.date.localeCompare(b.date));
  }, [history]);

  // 计算累计收益率序列
  const { dates, scores, cumReturns, stats } = useMemo(() => {
    const datesArr: string[] = [];
    const scoresArr: number[] = [];
    const cumReturnsArr: number[] = [];

    let cumMultiplier = 1.0;
    let highRiskCount = 0;
    let lowRiskCount = 0;

    for (const pt of sortedHistory) {
      datesArr.push(pt.date.slice(5)); // '10-22' 紧凑显示
      scoresArr.push(Number(pt.score.toFixed(1)));

      const dailyPct = pt.industry_change_pct ?? 0;
      cumMultiplier *= 1 + dailyPct / 100;
      cumReturnsArr.push(Number(((cumMultiplier - 1) * 100).toFixed(2)));

      if (pt.score >= 75) highRiskCount++;
      if (pt.score <= 35) lowRiskCount++;
    }

    return {
      dates: datesArr,
      scores: scoresArr,
      cumReturns: cumReturnsArr,
      stats: {
        totalDays: sortedHistory.length,
        highRiskCount,
        lowRiskCount,
        latestScore: scoresArr[scoresArr.length - 1] ?? 0,
        latestCumReturn: cumReturnsArr[cumReturnsArr.length - 1] ?? 0,
      },
    };
  }, [sortedHistory]);

  const chartOption = useMemo(() => {
    return {
      title: {
        text: `${industryName} · 韭菜指数与累计走势双轴复盘`,
        subtext: "左轴柱状: 韭菜指数 (0-100) | 右轴折线: 行业区间累计涨跌幅 (%)",
        left: 0,
        top: 0,
        textStyle: { fontSize: 13, fontWeight: 600, color: "var(--c-text-primary, #1e293b)" },
        subtextStyle: { fontSize: 11, color: "var(--c-text-muted, #94a3b8)" },
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross", crossStyle: { color: "#94a3b8" } },
        formatter: (params: Array<{ seriesName: string; value: number; dataIndex: number }>) => {
          if (!params || params.length === 0) return "";
          const idx = params[0].dataIndex;
          const pt = sortedHistory[idx];
          if (!pt) return "";
          return `
            <div style="font-size:12px;line-height:1.6;min-width:180px;">
              <div style="font-weight:700;margin-bottom:4px;border-bottom:1px solid rgba(148,163,184,0.3);padding-bottom:2px;">
                ${pt.date} · ${industryName}
              </div>
              <div>韭菜指数: <strong>${pt.score.toFixed(1)}</strong></div>
              <div>当日涨跌: <strong>${(pt.industry_change_pct ?? 0) >= 0 ? "+" : ""}${(pt.industry_change_pct ?? 0).toFixed(2)}%</strong></div>
              <div>区间累计涨幅: <strong>${(cumReturns[idx] ?? 0) >= 0 ? "+" : ""}${(cumReturns[idx] ?? 0).toFixed(2)}%</strong></div>
              <div style="font-size:11px;color:#94a3b8;margin-top:4px;">
                资金流: ${pt.sub_scores.flow.toFixed(0)} | 股吧: ${pt.sub_scores.guba.toFixed(0)} | 拥挤: ${pt.sub_scores.crowd.toFixed(0)} | 套牢: ${pt.sub_scores.trap.toFixed(0)}
              </div>
            </div>
          `;
        },
      },
      legend: {
        data: ["韭菜指数", "行业累计收益"],
        right: 10,
        top: 0,
        textStyle: { fontSize: 11, color: "var(--c-text-secondary, #64748b)" },
      },
      grid: {
        top: 55,
        left: 40,
        right: 48,
        bottom: 30,
      },
      xAxis: {
        type: "category",
        data: dates,
        axisLine: { lineStyle: { color: "#cbd5e1" } },
        axisLabel: { fontSize: 10, color: "#64748b" },
      },
      yAxis: [
        {
          type: "value",
          name: "韭菜指数",
          min: 0,
          max: 100,
          interval: 25,
          axisLine: { show: false },
          splitLine: { lineStyle: { type: "dashed", color: "var(--c-border, #e2e8f0)" } },
          axisLabel: { fontSize: 10, color: "#64748b" },
        },
        {
          type: "value",
          name: "累计涨幅(%)",
          axisLine: { show: false },
          splitLine: { show: false },
          axisLabel: {
            fontSize: 10,
            color: "#64748b",
            formatter: (v: number) => `${v >= 0 ? "+" : ""}${v}%`,
          },
        },
      ],
      series: [
        {
          name: "韭菜指数",
          type: "bar",
          yAxisIndex: 0,
          data: scores,
          barMaxWidth: 16,
          itemStyle: {
            color: (p: { value: number }) => {
              if (p.value >= 75) return "#dc2626";
              if (p.value >= 60) return "#f59e0b";
              if (p.value >= 35) return "#3b82f6";
              return "#059669";
            },
            borderRadius: [3, 3, 0, 0],
          },
          markLine: {
            silent: true,
            symbol: "none",
            data: [
              {
                yAxis: 75,
                lineStyle: { type: "dashed", color: "#dc2626", width: 1.2 },
                label: { formatter: "75分 见顶预警", position: "insideEndTop", fontSize: 10, color: "#dc2626" },
              },
              {
                yAxis: 35,
                lineStyle: { type: "dashed", color: "#059669", width: 1.2 },
                label: { formatter: "35分 黄金坑出清", position: "insideEndBottom", fontSize: 10, color: "#059669" },
              },
            ],
          },
        },
        {
          name: "行业累计收益",
          type: "line",
          yAxisIndex: 1,
          data: cumReturns,
          smooth: true,
          symbolSize: 4,
          lineStyle: { color: "#6366f1", width: 2.2 },
          itemStyle: { color: "#6366f1" },
        },
      ],
    };
  }, [industryName, dates, scores, cumReturns, sortedHistory]);

  if (!sortedHistory || sortedHistory.length === 0) {
    return (
      <div className="leek-dual-axis-empty">
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史归档时序数据" />
      </div>
    );
  }

  return (
    <div className="leek-dual-axis-container">
      <ReactECharts
        echarts={echarts}
        option={chartOption}
        className="leek-dual-axis-echarts"
        notMerge
      />
      <div className="leek-dual-axis-stats">
        <div className="leek-dual-axis-stat-item">
          <span className="leek-dual-axis-stat-label">近 {stats.totalDays} 日冲顶(&gt;75分)频次</span>
          <strong className={stats.highRiskCount > 0 ? "leek-dual-axis-stat-risk" : ""}>
            {stats.highRiskCount} 次
          </strong>
        </div>
        <div className="leek-dual-axis-stat-item">
          <span className="leek-dual-axis-stat-label">筹码出清(&lt;35分)天数</span>
          <strong className={stats.lowRiskCount > 0 ? "leek-dual-axis-stat-safe" : ""}>
            {stats.lowRiskCount} 天
          </strong>
        </div>
        <div className="leek-dual-axis-stat-item">
          <span className="leek-dual-axis-stat-label">区间累计涨跌</span>
          <strong className={stats.latestCumReturn >= 0 ? "leek-diff-val--inflow" : "leek-diff-val--outflow"}>
            {stats.latestCumReturn >= 0 ? "+" : ""}{stats.latestCumReturn.toFixed(2)}%
          </strong>
        </div>
      </div>
    </div>
  );
};
