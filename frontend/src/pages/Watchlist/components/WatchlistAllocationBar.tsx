import React, { useMemo } from "react";
import { Tooltip } from "antd";
import type { WatchlistItem } from "../../../types/watchlist";

interface WatchlistAllocationBarProps {
  items: WatchlistItem[];
  activeConcept: string;
  onSelectConcept: (conceptName: string) => void;
}

const BAR_COLORS = [
  "#3b82f6", // 蓝色
  "#8b5cf6", // 紫色
  "#10b981", // 绿色
  "#f59e0b", // 琥珀/橙色
  "#ec4899", // 粉色
  "#06b6d4", // 青色
];

export const WatchlistAllocationBar: React.FC<WatchlistAllocationBarProps> = ({
  items,
  activeConcept,
  onSelectConcept,
}) => {
  const allocation = useMemo(() => {
    if (!items.length) return [];

    const conceptCounts = new Map<string, number>();
    let totalStockConceptLinks = 0;

    for (const item of items) {
      const concepts = (item.concepts || []).filter((c) => c.name?.trim());
      if (concepts.length > 0) {
        for (const c of concepts) {
          const name = c.name.trim();
          conceptCounts.set(name, (conceptCounts.get(name) || 0) + 1);
          totalStockConceptLinks += 1;
        }
      } else {
        conceptCounts.set("未分类", (conceptCounts.get("未分类") || 0) + 1);
        totalStockConceptLinks += 1;
      }
    }

    if (totalStockConceptLinks === 0) return [];

    const sorted = Array.from(conceptCounts.entries())
      .map(([name, count]) => ({
        name,
        count,
        percentage: (count / totalStockConceptLinks) * 100,
      }))
      .sort((a, b) => b.count - a.count);

    // 取前 5 个，其余合并为“其他”
    const top = sorted.slice(0, 5);
    const rest = sorted.slice(5);
    if (rest.length > 0) {
      const restCount = rest.reduce((sum, r) => sum + r.count, 0);
      top.push({
        name: "其他",
        count: restCount,
        percentage: (restCount / totalStockConceptLinks) * 100,
      });
    }

    return top;
  }, [items]);

  if (!allocation.length) return null;

  return (
    <div
      className="watchlist-allocation-bar"
      style={{
        margin: "12px 0 16px",
        padding: "var(--c-pad-inset, 7px 12px)",
        background: "var(--c-card-bg)",
        border: "1px solid var(--c-border)",
        borderRadius: 8,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 8,
          fontSize: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontWeight: 600, color: "var(--c-text-primary)" }}>
            组合概念暴露分布
          </span>
          <span style={{ color: "var(--c-text-muted)" }}>
            (点击标签快速按板块过滤)
          </span>
        </div>
        {activeConcept !== "all" && (
          <button
            type="button"
            onClick={() => onSelectConcept("all")}
            style={{
              background: "none",
              border: "none",
              color: "var(--c-primary)",
              cursor: "pointer",
              fontSize: 12,
              padding: 0,
            }}
          >
            清除概念过滤
          </button>
        )}
      </div>

      {/* 分段条 */}
      <div
        style={{
          display: "flex",
          width: "100%",
          height: 8,
          borderRadius: 4,
          overflow: "hidden",
          gap: 2,
        }}
      >
        {allocation.map((item, idx) => {
          const color = BAR_COLORS[idx % BAR_COLORS.length];
          const isSelected = activeConcept === item.name;
          return (
            <Tooltip
              key={item.name}
              title={`${item.name}: ${item.count} 次标的关联 (${item.percentage.toFixed(1)}%)`}
            >
              <div
                role="button"
                tabIndex={0}
                onClick={() => onSelectConcept(item.name === "其他" ? "all" : item.name)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    onSelectConcept(item.name === "其他" ? "all" : item.name);
                  }
                }}
                style={{
                  width: `${item.percentage}%`,
                  height: "100%",
                  background: color,
                  opacity: activeConcept === "all" || isSelected ? 1 : 0.35,
                  cursor: "pointer",
                  transition: "opacity 0.2s, transform 0.2s",
                }}
              />
            </Tooltip>
          );
        })}
      </div>

      {/* 图例列表 */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "8px 14px",
          marginTop: 8,
          fontSize: 12,
        }}
      >
        {allocation.map((item, idx) => {
          const color = BAR_COLORS[idx % BAR_COLORS.length];
          const isSelected = activeConcept === item.name;
          return (
            <button
              key={item.name}
              type="button"
              onClick={() => onSelectConcept(isSelected ? "all" : item.name)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                padding: "2px 6px",
                borderRadius: 4,
                border: isSelected ? `1px solid ${color}` : "1px solid transparent",
                background: isSelected ? "color-mix(in srgb, var(--c-primary) 12%, transparent)" : "transparent",
                color: isSelected ? "var(--c-primary)" : "var(--c-text-secondary)",
                cursor: "pointer",
                fontSize: 12,
                transition: "all 0.15s ease",
              }}
            >
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: color,
                  display: "inline-block",
                }}
              />
              <span>主线 · {item.name}</span>
              <span style={{ color: "var(--c-text-muted)", fontFamily: "var(--c-font-mono)", fontSize: 11 }}>
                {item.percentage.toFixed(0)}%
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
