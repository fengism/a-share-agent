import React, { useMemo } from "react";
import { Button, Space, Tag, Tooltip } from "antd";
import { BulbOutlined, FilterOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import type { ScreenerItem } from "../../types/stock";
import ChangeValue from "../../components/ChangeValue";
import * as uiStyles from "../../styles/ui";

const DEFAULT_COLORS = {
  primary: "#1677ff",
  textPrimary: "rgba(0, 0, 0, 0.88)",
  textMuted: "rgba(0, 0, 0, 0.45)",
  up: "#f5222d",
  down: "#52c41a",
};

interface ScreenerPoolInsightsBarProps {
  items: ScreenerItem[];
  total: number;
  onSelectIndustry?: (industry: string) => void;
  selectedIndustry?: string | null;
}

const PALETTE = [
  "#1677ff",
  "#52c41a",
  "#722ed1",
  "#fa8c16",
  "#13c2c2",
  "#eb2f96",
  "#faad14",
  "#2f54eb",
];

function calculateMedian(values: (number | null | undefined)[]): number | null {
  const nums = values.filter((v): v is number => typeof v === "number" && !isNaN(v)).sort((a, b) => a - b);
  if (nums.length === 0) return null;
  const mid = Math.floor(nums.length / 2);
  return nums.length % 2 !== 0 ? nums[mid] : (nums[mid - 1] + nums[mid]) / 2;
}

export const ScreenerPoolInsightsBar: React.FC<ScreenerPoolInsightsBarProps> = ({
  items,
  total,
  onSelectIndustry,
  selectedIndustry,
}) => {
  const c = typeof uiStyles.useColors === "function" ? uiStyles.useColors() : DEFAULT_COLORS;
  const navigate = useNavigate();

  const insights = useMemo(() => {
    if (!items || items.length === 0) return null;

    // 1. 行业分布
    const industryCounts: Record<string, number> = {};
    let withIndustryCount = 0;

    items.forEach((item) => {
      const ind = item.first_industry?.name || item.second_industry?.name || item.exchange_industry || "其他行业";
      industryCounts[ind] = (industryCounts[ind] || 0) + 1;
      withIndustryCount += 1;
    });

    const topIndustries = Object.entries(industryCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([name, count], index) => ({
        name,
        count,
        percent: Math.round((count / (withIndustryCount || 1)) * 100),
        color: PALETTE[index % PALETTE.length],
      }));

    // 2. 中位核心估值 & 盘面指标
    const medianPe = calculateMedian(items.map((i) => i.pe_ttm));
    const medianPb = calculateMedian(items.map((i) => i.pb));
    const medianCap = calculateMedian(items.map((i) => i.market_cap));
    const medianChange = calculateMedian(items.map((i) => i.change_pct));

    // 3. 多空分布
    let upCount = 0;
    let downCount = 0;
    let flatCount = 0;

    items.forEach((item) => {
      const chg = item.change_pct ?? 0;
      if (chg > 0) upCount += 1;
      else if (chg < 0) downCount += 1;
      else flatCount += 1;
    });

    return {
      topIndustries,
      medianPe,
      medianPb,
      medianCap,
      medianChange,
      upCount,
      downCount,
      flatCount,
    };
  }, [items]);

  if (!insights || items.length === 0) return null;

  const handleAiDiagnosePool = () => {
    const topStocks = items.slice(0, 8).map((s) => `${s.name}(${s.code})`).join("、");
    const prompt = `请作为资深投研顾问，对当前量化选股候选池中前 8 只标的（${topStocks}）进行综合诊断。重点剖析：1. 所属行业与当前主线匹配度；2. 估值分位与安全边际；3. 潜在上涨催化剂与风险点。`;
    navigate(`/chat?prompt=${encodeURIComponent(prompt)}`);
  };

  return (
    <div
      style={{
        background: "var(--c-fill-quaternary, rgba(0, 0, 0, 0.02))",
        border: "1px solid var(--c-border, #f0f0f0)",
        borderRadius: 8,
        padding: "var(--c-pad-inset, 7px 12px)",
        marginBottom: 12,
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      {/* 顶部指标统计栏与 AI 快捷入口 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <Space size={16} wrap style={{ fontSize: 13, color: c.textMuted }}>
          <span>
            样本透视 (前 {items.length} 只 / 总 {total} 只)
          </span>
          <span>
            中位涨跌:{" "}
            <strong style={{ fontWeight: 600 }}>
              <ChangeValue value={insights.medianChange} />
            </strong>
          </span>
          <span>
            中位 PE:{" "}
            <strong style={{ color: c.textPrimary, fontFamily: "var(--c-font-mono)" }}>
              {insights.medianPe != null ? insights.medianPe.toFixed(1) : "-"}
            </strong>
          </span>
          <span>
            中位 PB:{" "}
            <strong style={{ color: c.textPrimary, fontFamily: "var(--c-font-mono)" }}>
              {insights.medianPb != null ? insights.medianPb.toFixed(2) : "-"}
            </strong>
          </span>
          <span>
            中位市值:{" "}
            <strong style={{ color: c.textPrimary, fontFamily: "var(--c-font-mono)" }}>
              {insights.medianCap != null
                ? insights.medianCap >= 10000
                  ? `${(insights.medianCap / 10000).toFixed(1)}万亿`
                  : `${insights.medianCap.toFixed(1)}亿`
                : "-"}
            </strong>
          </span>
          <span>
            多空比:{" "}
            <span style={{ color: c.up, fontWeight: 600 }}>{insights.upCount}涨</span>
            {" / "}
            <span style={{ color: c.down, fontWeight: 600 }}>{insights.downCount}跌</span>
            {insights.flatCount > 0 ? ` (${insights.flatCount}平)` : ""}
          </span>
        </Space>

        <Button
          size="small"
          type="primary"
          ghost
          icon={<BulbOutlined />}
          onClick={handleAiDiagnosePool}
        >
          AI 诊断候选池
        </Button>
      </div>

      {/* 行业分布占比条与快捷过滤 */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {/* 多彩占比比例条 */}
        <div
          style={{
            display: "flex",
            height: 6,
            borderRadius: 3,
            overflow: "hidden",
            background: "var(--c-border, #e8e8e8)",
            width: "100%",
          }}
        >
          {insights.topIndustries.map((ind) => (
            <Tooltip key={ind.name} title={`${ind.name}: ${ind.count} 只 (${ind.percent}%)`}>
              <div
                style={{
                  width: `${ind.percent}%`,
                  backgroundColor: ind.color,
                  minWidth: ind.percent > 0 ? 4 : 0,
                  transition: "width 0.3s ease",
                  cursor: onSelectIndustry ? "pointer" : "default",
                }}
                onClick={() => onSelectIndustry?.(ind.name)}
              />
            </Tooltip>
          ))}
        </div>

        {/* 行业标签流 */}
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
          <span style={{ fontSize: 12, color: c.textMuted, display: "flex", alignItems: "center", gap: 3 }}>
            <FilterOutlined style={{ fontSize: 11 }} />
            主要行业分布:
          </span>
          {insights.topIndustries.map((ind) => {
            const isSelected = selectedIndustry === ind.name;
            return (
              <Tag
                key={ind.name}
                color={isSelected ? "processing" : undefined}
                style={{
                  cursor: onSelectIndustry ? "pointer" : "default",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  fontSize: 12,
                  padding: "0 6px",
                  lineHeight: "20px",
                  borderRadius: 4,
                  borderColor: isSelected ? ind.color : undefined,
                  fontWeight: isSelected ? 600 : 400,
                }}
                onClick={() => onSelectIndustry?.(ind.name)}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    backgroundColor: ind.color,
                    display: "inline-block",
                  }}
                />
                <span>{ind.name}</span>
                <span style={{ color: c.textMuted, fontSize: 11 }}>{ind.percent}%</span>
              </Tag>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default ScreenerPoolInsightsBar;
