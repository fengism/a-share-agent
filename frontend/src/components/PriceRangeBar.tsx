import React from "react";
import { Tooltip } from "antd";

interface PriceRangeBarProps {
  low: number | null;
  high: number | null;
  current: number | null;
}

export const PriceRangeBar: React.FC<PriceRangeBarProps> = ({ low, high, current }) => {
  if (low == null || high == null || current == null || high <= low) {
    return <span style={{ color: "var(--c-text-muted)", fontSize: 12 }}>-</span>;
  }

  const range = high - low;
  const currentRatio = Math.min(100, Math.max(0, ((current - low) / range) * 100));

  return (
    <Tooltip
      title={
        <div style={{ fontSize: 12, lineHeight: 1.6 }}>
          <div>最高：{high.toFixed(2)}</div>
          <div>最低：{low.toFixed(2)}</div>
          <div>当前：{current.toFixed(2)}（区间分位 {currentRatio.toFixed(0)}%）</div>
        </div>
      }
    >
      <div
        className="watchlist-price-range"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 2,
          minWidth: 72,
          cursor: "pointer",
        }}
      >
        <div
          style={{
            position: "relative",
            width: "100%",
            height: 4,
            background: "color-mix(in srgb, var(--c-border) 80%, transparent)",
            borderRadius: 2,
            overflow: "visible",
          }}
        >
          <div
            style={{
              position: "absolute",
              left: `${currentRatio}%`,
              top: -2,
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: currentRatio >= 50 ? "var(--c-up)" : "var(--c-down)",
              transform: "translateX(-50%)",
              boxShadow: "0 0 4px rgba(0,0,0,0.25)",
            }}
          />
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: 10,
            fontFamily: "var(--c-font-mono)",
            color: "var(--c-text-muted)",
            lineHeight: 1,
          }}
        >
          <span>{low.toFixed(1)}</span>
          <span>{high.toFixed(1)}</span>
        </div>
      </div>
    </Tooltip>
  );
};
