import React, { useMemo } from "react";
import { BulbOutlined } from "@ant-design/icons";
import { useColors, useTokens } from "../../../styles/ui";

interface NextPromptSuggestionsProps {
  content: string;
  stockCodes: string[];
  onSelectPrompt: (prompt: string) => void;
}

export function generateSuggestedPrompts(content: string, stockCodes: string[]): string[] {
  const suggestions: string[] = [];

  // 1. 如果回答中包含具体股票
  if (stockCodes.length === 1) {
    const code = stockCodes[0];
    suggestions.push(`分析 ${code} 的近期主力资金动向与龙虎榜席位`);
    suggestions.push(`对比 ${code} 与行业同类龙头的估值水平和毛利率`);
    suggestions.push(`从技术形态（日线/周线/均线）诊断 ${code} 当前处于什么周期？`);
  } else if (stockCodes.length > 1) {
    const [c1, c2] = stockCodes;
    suggestions.push(`对比分析 ${c1} 与 ${c2} 的基本面优势与风险`);
    suggestions.push(`这些标的各自的估值百分位是多少？哪只更具安全边际？`);
  }

  // 2. 如果包含“选股”、“筛选”或指标
  if (content.includes("选股") || content.includes("PE") || content.includes("股息率")) {
    if (suggestions.length < 3) {
      suggestions.push("按股息率从高到低对上述股票重新排序并标明近期分红预案");
    }
    if (suggestions.length < 3) {
      suggestions.push("上述标的近期是否有大股东减持或解禁风险？");
    }
  }

  // 3. 如果包含“主线”、“大盘”、“连板”或“题材”
  if (content.includes("主线") || content.includes("连板") || content.includes("涨停") || content.includes("题材")) {
    if (suggestions.length < 3) {
      suggestions.push("分析领涨题材的持续性，后排跟风股有补涨机会吗？");
    }
    if (suggestions.length < 3) {
      suggestions.push("今日炸板率是多少？短线情绪处于加速还是分歧阶段？");
    }
  }

  // 默认补充建议
  if (suggestions.length < 3) {
    suggestions.push("详细分析核心标的的催化剂与潜在下行风险");
  }
  if (suggestions.length < 3) {
    suggestions.push("结合最新券商研报，机构核心观点与盈利预测如何？");
  }

  return suggestions.slice(0, 3);
}

export const NextPromptSuggestions = React.memo(function NextPromptSuggestions({
  content,
  stockCodes,
  onSelectPrompt,
}: NextPromptSuggestionsProps) {
  const c = useColors();
  const t = useTokens();

  const suggestions = useMemo(() => {
    return generateSuggestedPrompts(content, stockCodes);
  }, [content, stockCodes]);

  if (suggestions.length === 0) return null;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
        marginTop: 10,
        padding: "var(--c-pad-inset, 7px 12px)",
        background: `color-mix(in srgb, ${c.hoverBg} 70%, transparent)`,
        borderRadius: t.radius.md,
        border: `1px dashed ${c.border}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: t.font.xs, color: c.textMuted }}>
        <BulbOutlined style={{ color: c.primary }} />
        <span>猜你想问（点击快速追问）：</span>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {suggestions.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onSelectPrompt(prompt)}
            style={{
              textAlign: "left",
              fontSize: t.font.xs,
              color: c.textSecondary,
              background: c.nestedBg,
              border: `1px solid ${c.border}`,
              borderRadius: t.radius.pill,
              padding: "3px 10px",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = c.primary;
              e.currentTarget.style.color = c.primary;
              e.currentTarget.style.transform = "translateY(-1px)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = c.border;
              e.currentTarget.style.color = c.textSecondary;
              e.currentTarget.style.transform = "none";
            }}
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
});
