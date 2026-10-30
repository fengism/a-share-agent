import {
  BellOutlined,
  ExperimentOutlined,
  FilterOutlined,
  LineChartOutlined,
  StarOutlined,
} from "@ant-design/icons";
import { Button, Space, Typography } from "antd";
import { useColors, useTokens } from "../../../styles/ui";
import { buildStockAnalysisUrl } from "../../../utils/stockLinks";
import type {
  ChatResultActionHandler,
  ChatResultContext,
} from "../chatResultActions";

const { Text } = Typography;

interface ChatResultActionsProps {
  context: ChatResultContext;
  onAction: ChatResultActionHandler;
}

export function ChatResultActions({ context, onAction }: ChatResultActionsProps) {
  const t = useTokens();
  const c = useColors();
  const hasStocks = context.stockCodes.length > 0;
  if (!hasStocks && !context.screenerState) return null;

  return (
    <div
      className="chat-result-actions"
      style={{
        marginTop: 10,
        padding: "var(--c-pad-inset, 7px 12px)",
        background: `color-mix(in srgb, ${c.nestedBg} 85%, transparent)`,
        border: `1px solid ${c.border}`,
        borderRadius: t.radius.md,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {hasStocks && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <span style={{ fontSize: 11, color: c.textMuted }}>识别标的：</span>
            {context.stockCodes.slice(0, 6).map((code) => (
              <a
                key={code}
                href={buildStockAnalysisUrl(code)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  padding: "1px 6px",
                  borderRadius: 4,
                  fontSize: 11,
                  fontFamily: "monospace",
                  background: c.hoverBg,
                  border: `1px solid ${c.border}`,
                  color: c.textSecondary,
                  textDecoration: "none",
                  cursor: "pointer",
                }}
                title={`查看 ${code} 深度研报`}
              >
                <LineChartOutlined style={{ marginRight: 3, color: c.primary }} />
                {code}
              </a>
            ))}
            {context.stockCodes.length > 6 && (
              <span style={{ fontSize: 11, color: c.textMuted }}>
                等共 {context.stockCodes.length} 只标的
              </span>
            )}
          </div>
        )}

        <Space size={6} wrap align="center">
          <Text type="secondary" style={{ fontSize: t.font.xs }}>投研动作：</Text>
          {hasStocks ? (
            <Button
              size="small"
              icon={<StarOutlined />}
              onClick={() => onAction("watchlist", context)}
            >
              加入自选 ({context.stockCodes.length})
            </Button>
          ) : null}
          {hasStocks ? (
            <Button size="small" icon={<BellOutlined />} onClick={() => onAction("alert", context)}>
              设置提醒
            </Button>
          ) : null}
          {context.screenerState ? (
            <Button size="small" icon={<FilterOutlined />} onClick={() => onAction("screener", context)}>
              保存筛选方案
            </Button>
          ) : null}
          {hasStocks ? (
            <Button size="small" icon={<ExperimentOutlined />} onClick={() => onAction("quant", context)}>
              转为量化策略
            </Button>
          ) : null}
        </Space>
      </div>
    </div>
  );
}
